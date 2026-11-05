"""Persistent bounded notification queue. Dev Anh Khôi, v2.0.

Only explicit, finite webhook notifications enter this queue. A send with an
unknown network outcome is never retried automatically.
"""
import json
import math
import sqlite3
import threading
import time
import uuid


class RetryAfter(Exception):
    def __init__(self, seconds, global_limit=False):
        if not math.isfinite(float(seconds)):
            seconds = 60
        self.seconds = max(1, min(float(seconds), 86400))
        self.global_limit = global_limit


class UncertainDelivery(Exception):
    pass


class TaskQueue:
    def __init__(self, db, sender, workers=5, limit=200, worker_cleanup=None):
        self.db, self.sender = db, sender
        self.workers, self.limit = max(1, min(workers, 8)), limit
        self.wake = threading.Condition()
        self.shutdown_event = threading.Event()
        self.threads = []
        self.last_owner = ''
        self.delay = 0.0
        self.worker_cleanup = worker_cleanup
        c = db()
        c.executescript('''
        CREATE TABLE IF NOT EXISTS notification_tasks (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, channel TEXT NOT NULL,
          payload TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL,
          started REAL, updated REAL NOT NULL, completed REAL, attempts INTEGER DEFAULT 0,
          due REAL DEFAULT 0, error TEXT DEFAULT '', latency REAL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS notification_ready ON notification_tasks(status,due,created);
        CREATE TABLE IF NOT EXISTS notification_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, task TEXT NOT NULL,
          status TEXT NOT NULL, at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS notification_limits(name TEXT PRIMARY KEY, until REAL NOT NULL);
        ''')
        # Only safe before worker startup; enforce one application worker.
        c.execute("UPDATE notification_tasks SET status='UNKNOWN', error='Restart during request; reconcile before retry', updated=? WHERE status IN ('RUNNING','CANCELLING')", (time.time(),))
        c.commit()
        c.close()

    def _event(self, c, row, status):
        c.execute('INSERT INTO notification_events(owner,task,status,at) VALUES(?,?,?,?)', (row['owner'], row['id'], status, time.time()))
        c.execute('DELETE FROM notification_events WHERE seq < (SELECT COALESCE(MAX(seq),0)-2000 FROM notification_events)')

    def submit(self, owner, channel, content):
        return self.submit_many(owner, [channel], content)[0]

    def submit_many(self, owner, channels, content):
        if not channels or len(channels)>5 or len(set(channels))!=len(channels):
            raise ValueError('Chọn 1–5 kênh khác nhau')
        if not content or len(content) > 2000:
            raise ValueError('Nội dung phải có 1–2000 ký tự')
        c = self.db()
        try:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT COUNT(*) FROM notification_tasks WHERE status IN ('QUEUED','RUNNING','RETRYING','PAUSED','CANCELLING')").fetchone()[0] + len(channels) > self.limit:
                raise ValueError('Hàng chờ đầy, hãy đợi tác vụ hoàn thành')
            if c.execute("SELECT COUNT(*) FROM notification_tasks WHERE owner=? AND status IN ('QUEUED','RETRYING','PAUSED')", (str(owner),)).fetchone()[0] + len(channels) > 50:
                raise ValueError('Đạt giới hạn 50 tác vụ chờ cho người dùng')
            ids=[]
            for channel in channels:
                now, task_id = time.time(), uuid.uuid4().hex
                c.execute('INSERT INTO notification_tasks(id,owner,channel,payload,status,created,updated) VALUES(?,?,?,?,?,?,?)', (task_id, str(owner), str(channel), json.dumps({'content': content}), 'QUEUED', now, now))
                self._event(c, {'owner': str(owner), 'id': task_id}, 'QUEUED')
                ids.append(task_id)
            c.execute("DELETE FROM notification_tasks WHERE id IN (SELECT id FROM notification_tasks WHERE status IN ('COMPLETED','CANCELLED') ORDER BY created DESC LIMIT -1 OFFSET 2000)")
            c.commit()
        finally:
            c.rollback()
            c.close()
        with self.wake:
            self.wake.notify_all()
        return ids

    def list(self, owner):
        c = self.db()
        try:
            return [dict(r) for r in c.execute("SELECT id,owner,channel,status,created,started,updated,completed,attempts,error,latency FROM notification_tasks WHERE owner=? ORDER BY (status IN ('QUEUED','RUNNING','RETRYING','PAUSED','CANCELLING')) DESC, created DESC LIMIT 200", (str(owner),))]
        finally:
            c.rollback()
            c.close()

    def stop_all(self, owner):
        c = self.db()
        try:
            c.execute('BEGIN IMMEDIATE')
            rows = c.execute("SELECT id,owner,status FROM notification_tasks WHERE owner=? AND status IN ('QUEUED','RUNNING','PAUSED','RETRYING')", (str(owner),)).fetchall()
            for row in rows:
                status = 'CANCELLING' if row['status'] == 'RUNNING' else 'CANCELLED'
                now = time.time()
                c.execute('UPDATE notification_tasks SET status=?,updated=?,completed=? WHERE id=?', (status,now,now if status=='CANCELLED' else None,row['id']))
                self._event(c,row,status)
            c.commit()
            return len(rows)
        finally:
            c.rollback()
            c.close()

    def control(self, owner, task_id, action):
        transitions = {'pause': {'QUEUED': 'PAUSED', 'RETRYING': 'PAUSED'},
                       'resume': {'PAUSED': 'QUEUED'},
                       'stop': {s: ('CANCELLING' if s == 'RUNNING' else 'CANCELLED') for s in ('QUEUED','RETRYING','RUNNING','PAUSED')},
                       'retry': {'FAILED': 'QUEUED'}}
        c = self.db()
        try:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM notification_tasks WHERE id=? AND owner=?', (task_id, str(owner))).fetchone()
            if not row:
                raise ValueError('Không tìm thấy tác vụ thuộc tài khoản này')
            status = transitions.get(action, {}).get(row['status'])
            if not status:
                raise ValueError('Thao tác không hỗ trợ ở trạng thái này; yêu cầu mạng đang gửi không thể tạm dừng')
            if action == 'retry':
                total = c.execute("SELECT COUNT(*) FROM notification_tasks WHERE status IN ('QUEUED','RUNNING','RETRYING','PAUSED','CANCELLING')").fetchone()[0]
                waiting = c.execute("SELECT COUNT(*) FROM notification_tasks WHERE owner=? AND status IN ('QUEUED','RETRYING','PAUSED')", (str(owner),)).fetchone()[0]
                if total >= self.limit or waiting >= 50:
                    raise ValueError('Hàng chờ đầy; chưa thể thử lại tác vụ')
            now = time.time()
            c.execute('UPDATE notification_tasks SET status=?, updated=?, completed=?, error=\'\' WHERE id=?', (status, now, now if status=='CANCELLED' else None, task_id))
            self._event(c, row, status)
            c.commit()
        finally:
            c.rollback()
            c.close()
        with self.wake:
            self.wake.notify_all()
        return status

    def claim(self):
        c = self.db()
        try:
            c.execute('BEGIN IMMEDIATE')
            limit = c.execute("SELECT until FROM notification_limits WHERE name='discord-global'").fetchone()
            if limit and limit[0] > time.time():
                return None
            row = c.execute('''SELECT t.* FROM notification_tasks t
              WHERE t.status IN ('QUEUED','RETRYING') AND t.due<=?
              AND NOT EXISTS (SELECT 1 FROM notification_limits l WHERE l.name='channel:' || t.channel AND l.until>?)
              AND NOT EXISTS (SELECT 1 FROM notification_tasks r WHERE r.channel=t.channel AND r.status='RETRYING' AND r.due>?)
              AND NOT EXISTS (SELECT 1 FROM notification_tasks r WHERE r.channel=t.channel AND r.status IN ('RUNNING','CANCELLING'))
              AND (SELECT COUNT(*) FROM notification_tasks r WHERE r.owner=t.owner AND r.status IN ('RUNNING','CANCELLING')) < 5
              ORDER BY (t.owner=?), t.updated, t.created LIMIT 1''', (time.time(), time.time(), time.time(), self.last_owner)).fetchone()
            if not row:
                return None
            self.last_owner = row['owner']
            c.execute("UPDATE notification_tasks SET status='RUNNING', started=COALESCE(started,?), updated=?, attempts=attempts+1 WHERE id=?", (time.time(), time.time(), row['id']))
            self._event(c, row, 'RUNNING')
            c.commit()
            return dict(row)
        finally:
            c.rollback()
            c.close()

    def run_one(self):
        row = self.claim()
        if not row:
            return False
        started, status, error, due = time.monotonic(), 'COMPLETED', '', 0
        global_until = 0
        channel_until = 0
        try:
            self.sender(row['owner'], row['channel'], json.loads(row['payload']))
        except RetryAfter as ex:
            channel_until = time.time() + ex.seconds
            status, due = ('RETRYING', time.time() + ex.seconds) if row['attempts'] < 7 else ('FAILED', 0)
            error = 'API rate limit'
            if ex.global_limit:
                global_until = time.time() + ex.seconds
        except UncertainDelivery:
            status, error = 'UNKNOWN', 'Kết quả gửi chưa xác định; kiểm tra kênh trước khi tạo tác vụ mới'
        except Exception:
            status, error = 'FAILED', 'API từ chối hoặc cấu hình kênh không còn hợp lệ'
        # Retain the result in this worker until SQLite accepts the final state.
        # Retrying the database write must never repeat the external send.
        while not self.shutdown_event.is_set():
            c = None
            try:
                c = self.db()
                c.execute('BEGIN IMMEDIATE')
                if global_until:
                    c.execute("INSERT INTO notification_limits VALUES('discord-global',?) ON CONFLICT(name) DO UPDATE SET until=MAX(until,excluded.until)", (global_until,))
                if channel_until:
                    c.execute('INSERT INTO notification_limits VALUES(?,?) ON CONFLICT(name) DO UPDATE SET until=MAX(until,excluded.until)', ('channel:'+row['channel'],channel_until))
                current = c.execute('SELECT status FROM notification_tasks WHERE id=?', (row['id'],)).fetchone()[0]
                final_status = 'CANCELLED' if current == 'CANCELLING' and status == 'RETRYING' else status
                # An accepted request remains COMPLETED even if stop raced it.
                c.execute('UPDATE notification_tasks SET status=?,error=?,due=?,updated=?,completed=?,latency=? WHERE id=?', (final_status,error,due,time.time(),time.time() if final_status != 'RETRYING' else None,time.monotonic()-started,row['id']))
                self._event(c, row, final_status)
                c.commit()
                break
            except sqlite3.Error:
                self.shutdown_event.wait(1)
            finally:
                if c is not None:
                    c.rollback()
                    c.close()
        return True

    def start(self):
        if self.threads:
            return
        def loop():
            try:
                while not self.shutdown_event.is_set():
                    try:
                        work = self.run_one()
                    except sqlite3.Error:
                        work = False
                    if not work:
                        with self.wake:
                            self.wake.wait(timeout=1)
            finally:
                if self.worker_cleanup:
                    self.worker_cleanup()
        for i in range(self.workers):
            t = threading.Thread(target=loop, name=f'Notification-{i}', daemon=True)
            self.threads.append(t)
            t.start()

    def close(self):
        self.shutdown_event.set()
        with self.wake:
            self.wake.notify_all()
        for thread in self.threads:
            thread.join(timeout=1)
