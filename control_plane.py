"""Official Discord webhook management shared by Telegram and Mini App. v2.0."""
import atexit
import base64
import hashlib
import json
import os
import re
import threading
import time

import requests
from cryptography.fernet import Fernet
from flask import Response, jsonify, request, stream_with_context
from durable_tasks import TaskQueue, RetryAfter, UncertainDelivery

COMMANDS = {
    'menu': 'Toàn bộ lệnh', 'help': 'Hướng dẫn', 'accounts': 'Tài khoản Zalo và Discord',
    'discord_login': 'Liên kết Discord OAuth2', 'discord_accounts': 'Tài khoản Discord',
    'discord_status': 'Trạng thái OAuth', 'discord_logout': 'Ngắt liên kết: ID',
    'tasks': 'Danh sách tác vụ thông báo', 'task_status': 'Chi tiết: ID',
    'task_pause': 'Tạm dừng tác vụ chờ: ID', 'task_resume': 'Tiếp tục: ID',
    'task_stop': 'Dừng: ID', 'task_retry': 'Thử lại tác vụ thất bại: ID',
    'channels': 'Kênh webhook được cấp quyền', 'send': 'Gửi: channel_id | nội dung',
    'send_multi': 'Gửi: id1,id2 | nội dung (tối đa 5 kênh)',
    'delay': 'Độ trễ nhân tạo: 0 giây; API rate limit vẫn áp dụng',
    'performance': 'Hiệu suất tác vụ', 'logs': 'Nhật ký tác vụ',
    'settings': 'Cấu hình trong Mini App', 'system': 'Trạng thái máy chủ',
    'miniapp': 'Mở Mini App', 'zalo': 'Menu Zalo', 'start': 'Khởi động',
}


def register(app, db, owner):
    def cipher():
        if not os.environ.get('SECRET_KEY'):
            raise ValueError('Cần SECRET_KEY cố định trong Environment')
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('webhooks:' + str(app.secret_key)).encode()).digest()))

    c = db()
    c.execute('CREATE TABLE IF NOT EXISTS webhook_channels(id TEXT PRIMARY KEY,owner TEXT NOT NULL,name TEXT NOT NULL,secret TEXT NOT NULL,created REAL NOT NULL)')
    c.commit()
    c.close()
    local = threading.local()
    def cleanup_worker():
        if hasattr(local, 'http'):
            local.http.close()
        connection = db()
        connection.rollback()
        # Legacy runtime pools connections per thread; close its underlying handle
        # when this owned worker exits instead of keeping it alive indefinitely.
        getattr(connection, '_conn', connection).close()

    def channels(user):
        c = db()
        try:
            return [dict(r) for r in c.execute('SELECT id,name,created FROM webhook_channels WHERE owner=?', (str(user),))]
        finally:
            c.close()

    def send(user, channel, payload):
        c = db()
        try:
            row = c.execute('SELECT secret FROM webhook_channels WHERE owner=? AND id=?', (user,channel)).fetchone()
        finally:
            c.close()
        if not row:
            raise ValueError('Kênh đã bị xóa')
        url = cipher().decrypt(row[0].encode()).decode()
        if not hasattr(local, 'http'):
            local.http = requests.Session()
        try:
            with local.http.post(url + '?wait=true', json={**payload,'allowed_mentions': {'parse': []}}, timeout=(4,12), allow_redirects=False) as response:
                if response.status_code == 429:
                    try:
                        limit_data = response.json()
                        seconds = float(limit_data.get('retry_after', response.headers.get('Retry-After', 5)))
                    except (ValueError, TypeError, AttributeError):
                        seconds = 5
                        limit_data = {}
                    raise RetryAfter(seconds, bool(limit_data.get('global')))
                if response.status_code >= 500:
                    raise UncertainDelivery()
                if response.status_code not in (200,204):
                    raise ValueError('API rejected')
        except requests.RequestException:
            raise UncertainDelivery() from None

    queue = TaskQueue(db, send, worker_cleanup=cleanup_worker)
    app.extensions['notification_queue'] = queue
    app.extensions['managed_channels'] = channels
    def oauth_notice(user, name):
        import app as runtime
        import html
        bot = getattr(runtime, '_TELEGRAM_BOT_RUNNER', None)
        if bot is not None:
            bot.interactive_executor.submit(bot.send_text, user, 'Đã liên kết Discord: ' + html.escape(name) + '. Xem /discord_accounts.')
    app.extensions['oauth_notice'] = oauth_notice
    atexit.register(queue.close)
    if os.environ.get('DISABLE_BACKGROUND_WORKERS') != '1':
        queue.start()

    def snapshot(user, cursor=0):
        tasks = queue.list(user)
        counts = {}
        for t in tasks:
            counts[t['status']] = counts.get(t['status'],0)+1
        c = db()
        try:
            oldest = c.execute('SELECT MIN(seq) FROM notification_events WHERE owner=?', (str(user),)).fetchone()[0]
            reset = bool(cursor and oldest and cursor < oldest - 1)
            events = [dict(r) for r in c.execute('SELECT * FROM notification_events WHERE owner=? AND seq>? ORDER BY seq LIMIT 200', (str(user), 0 if reset else cursor))]
        finally:
            c.close()
        durations = [t['latency'] for t in tasks if t['attempts'] > 0 and t['latency'] > 0]
        completed = [t for t in tasks if t['status'] == 'COMPLETED']
        return {'ok': True,'tasks':tasks,'counts':counts,'events':events,'reset':reset,'cursor':events[-1]['seq'] if events else cursor,
                'channels':channels(user),'workers':sum(t.is_alive() for t in queue.threads),
                'artificial_delay_seconds':0,'api_latency_seconds':sum(durations)/len(durations) if durations else None,
                'snapshot_at':time.time(),'metrics_window':'200 tác vụ gần nhất',
                'queue_wait_seconds':sum(t['started']-t['created'] for t in tasks if t['started'])/max(1,sum(bool(t['started']) for t in tasks)) if any(t['started'] for t in tasks) else None,
                'completion_seconds':sum(t['completed']-t['created'] for t in completed)/len(completed) if completed else None,
                'completed_last_minute':sum(t['completed'] >= time.time()-60 for t in completed),
                'retry_count':sum(max(0,t['attempts']-1) for t in tasks),
                'commands':[{'name':k,'description':v,'usage':'/'+k,'permission':'authorized_owner','handler':'telegram_command','availability':'supported'} for k,v in COMMANDS.items()]}

    app.extensions['control_snapshot'] = snapshot

    @app.get('/api/miniapp/control')
    def control_snapshot():
        return jsonify(snapshot(owner(), max(0, request.args.get('cursor',0,type=int) or 0)))

    @app.post('/api/miniapp/channels')
    def configure_channel():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify(ok=False,error='Cần một đối tượng JSON'),400
        url = str(data.get('url','')).strip()
        match = re.fullmatch(r'https://discord\.com/api/webhooks/(\d+)/([A-Za-z0-9_-]+)',url)
        if not match:
            return jsonify(ok=False,error='Cần URL webhook chính thức discord.com/api/webhooks/…'),400
        try:
            encrypted = cipher().encrypt(url.encode()).decode()
            with requests.get(url, timeout=(4,10), allow_redirects=False) as response:
                profile = response.json() if response.status_code == 200 else {}
            if str(profile.get('id')) != match[1] or profile.get('type') != 1:
                raise ValueError('Webhook không hợp lệ')
            c = db()
            try:
                c.execute('BEGIN IMMEDIATE')
                previous = c.execute('SELECT owner FROM webhook_channels WHERE id=?',(match[1],)).fetchone()
                if previous and previous[0] != str(owner()):
                    raise ValueError('Kênh đã thuộc người quản lý khác')
                c.execute('INSERT OR REPLACE INTO webhook_channels VALUES(?,?,?,?,?)',(match[1],str(owner()),str(profile.get('name') or 'Discord')[:100],encrypted,time.time()))
                c.commit()
            finally:
                c.rollback()
                c.close()
            return jsonify(ok=True)
        except (requests.RequestException,ValueError):
            return jsonify(ok=False,error='Không xác minh được webhook hoặc chưa có SECRET_KEY cố định'),422

    @app.post('/api/miniapp/notifications')
    def submit():
        data = request.get_json(silent=True) or {}
        if not isinstance(data,dict) or not isinstance(data.get('content'),str):
            return jsonify(ok=False,error='Nội dung cần là văn bản'),400
        selected = data.get('channels')
        allowed = {c['id'] for c in channels(owner())}
        if not isinstance(selected,list) or not 1 <= len(selected) <= 5 or any(not isinstance(c,str) for c in selected) or len(set(selected)) != len(selected) or any(c not in allowed for c in selected):
            return jsonify(ok=False,error='Chọn từ 1 đến 5 kênh được cấp quyền'),400
        try:
            ids = queue.submit_many(owner(),selected,str(data.get('content','')))
            return jsonify(ok=True,ids=ids),202
        except ValueError as ex:
            return jsonify(ok=False,error=str(ex)),400

    @app.post('/api/miniapp/notification_control')
    def control():
        data = request.get_json(silent=True) or {}
        if not isinstance(data,dict):
            return jsonify(ok=False,error='Cần một đối tượng JSON'),400
        try:
            return jsonify(ok=True,status=queue.control(owner(),str(data.get('id','')),str(data.get('action',''))))
        except ValueError as ex:
            return jsonify(ok=False,error=str(ex)),409

    @app.post('/api/miniapp/notifications/stop_all')
    def stop_all():
        return jsonify(ok=True,count=queue.stop_all(owner()))

    @app.post('/api/miniapp/channels/delete')
    def delete_channel():
        data = request.get_json(silent=True) or {}
        if not isinstance(data,dict):
            return jsonify(ok=False,error='Cần một đối tượng JSON'),400
        c = db()
        try:
            c.execute('BEGIN IMMEDIATE')
            channel = str(data.get('id',''))
            busy = c.execute("SELECT 1 FROM notification_tasks WHERE owner=? AND channel=? AND status IN ('QUEUED','RUNNING','PAUSED','RETRYING','CANCELLING')",(str(owner()),channel)).fetchone()
            if busy:
                return jsonify(ok=False,error='Dừng hoặc hoàn thành các tác vụ của kênh trước khi xóa'),409
            c.execute('DELETE FROM webhook_channels WHERE id=? AND owner=?',(channel,str(owner())))
            c.commit()
        finally:
            c.rollback()
            c.close()
        return jsonify(ok=True)

    # Gunicorn runs 16 request threads; reserve half for commands and mutations.
    streams = threading.BoundedSemaphore(8)
    @app.get('/api/miniapp/events')
    def events():
        if not streams.acquire(blocking=False):
            return jsonify(ok=False,error='Đang có nhiều kết nối; thử lại sau'),503
        user = str(owner())
        cursor = max(0,request.args.get('cursor',0,type=int) or 0)
        request_id = request.headers.get('X-Request-ID', '')
        if not re.fullmatch(r'[A-Za-z0-9._:-]{1,160}', request_id):
            request_id = ''
        @stream_with_context
        def generate():
            nonlocal cursor
            previous = None
            try:
                for _ in range(15):
                    try:
                        data = snapshot(user,cursor)
                        cursor = data['cursor']
                        signature = json.dumps({k:v for k,v in data.items() if k not in ('snapshot_at','events')},sort_keys=True)
                        if signature != previous or data['events']:
                            # Include the cursor as a resumable SSE id; clients still
                            # send it explicitly because Telegram WebViews do not
                            # consistently preserve Last-Event-ID across reconnects.
                            yield f"id: {cursor}\nevent: snapshot\ndata: {json.dumps(data)}\n\n"
                            previous = signature
                        else:
                            yield ': heartbeat\n\n'
                    except Exception:
                        # A transient database/provider failure must close this
                        # bounded stream cleanly. The browser's capped backoff then
                        # retries and performs a fresh cursor reconciliation.
                        yield ': retry\n\n'
                        break
                    if queue.shutdown_event.wait(2):
                        break
            finally:
                streams.release()
        headers={'Cache-Control':'no-store','X-Accel-Buffering':'no','Connection':'keep-alive'}
        if request_id:
            headers['X-Request-ID'] = request_id
        return Response(generate(), mimetype='text/event-stream', headers=headers)


def telegram_command(bot, user, chat, name, args):
    """Caller must authorize Telegram user before invoking this shared service."""
    if name not in COMMANDS or name in ('start','zalo','miniapp'):
        return False
    import app as runtime
    import html
    ext = runtime.app.extensions
    queue = ext['notification_queue']
    answer = ''
    try:
        if name in ('menu','help'):
            answer = '\n'.join('/'+key+' — '+value for key,value in COMMANDS.items())+'\n/files — Kho tệp\n/sticker — Tạo nhãn dán\n/stopall — Dừng tác vụ Zalo'
        elif name == 'discord_login':
            url = ext['discord_oauth_start'](str(user))['url']
            bot.send_text(chat,'Liên kết tài khoản tại Discord chính thức.',reply_markup={'inline_keyboard':[[{'text':'Đăng nhập Discord','url':url}]]})
            return True
        elif name in ('discord_accounts','discord_status','accounts'):
            from miniapp_oauth import _public_connections
            rows = _public_connections(runtime.db,str(user))
            answer = '\n'.join(f"#{r['id']} {r['display_name']} · {r['status']}" for r in rows) or 'Chưa liên kết Discord'
            if name == 'accounts':
                answer += '\nZalo: mở /zalo để quản lý tài khoản của bạn.'
        elif name == 'discord_logout':
            answer = ext['discord_oauth_disconnect'](str(user), int(args))
        elif name.startswith('task_') and name != 'task_status':
            answer = queue.control(user,args.strip(),name[5:])
        elif name in ('tasks','task_status'):
            rows = queue.list(user)
            if name == 'task_status': rows = [r for r in rows if r['id'] == args.strip()]
            answer = '\n'.join(f"{r['id']} · {r['channel']} · {r['status']}" for r in rows[:15]) or 'Chưa có tác vụ'
            keyboard=[]
            for r in rows[:5]:
                actions={'QUEUED':['pause','stop'],'RETRYING':['pause','stop'],'PAUSED':['resume','stop'],'RUNNING':['stop'],'FAILED':['retry']}.get(r['status'],[])
                if actions:keyboard.append([{'text':a+' '+r['id'][:6], 'callback_data':'v4:'+a+':'+r['id']} for a in actions])
            bot.send_text(chat,html.escape(answer),reply_markup={'inline_keyboard':keyboard})
            return True
        elif name == 'channels':
            answer = '\n'.join(f"{r['id']} · {r['name']}" for r in ext['managed_channels'](user)) or 'Thêm webhook trong Mini App → Discord'
        elif name in ('send','send_multi'):
            ids, separator, content = args.partition('|')
            targets = [s.strip() for s in ids.split(',')]
            allowed = {r['id'] for r in ext['managed_channels'](user)}
            if not separator or not 1 <= len(targets) <= (1 if name == 'send' else 5) or any(c not in allowed for c in targets):
                raise ValueError('Cú pháp: /send channel_id | nội dung; chỉ kênh được cấp quyền')
            answer = '\n'.join(queue.submit_many(user,targets,content.strip()))
        elif name == 'delay': answer = 'artificial_delay_seconds = 0; Retry-After của API vẫn được tôn trọng.'
        elif name == 'settings': answer = 'Mở /miniapp → Cài đặt để cấu hình kết nối.'
        else:
            data = ext['control_snapshot'](user)
            answer = json.dumps(data['events'][-10:] if name == 'logs' else {'workers':data['workers'],'tasks':data['counts'],'api_latency_seconds':data['api_latency_seconds']},ensure_ascii=False)
    except (ValueError,KeyError):
        answer = 'Cấu hình hoặc tham số chưa hợp lệ. Xem /help và kiểm tra OAuth trong Mini App.'
    bot.send_text(chat,html.escape(answer))
    return True
