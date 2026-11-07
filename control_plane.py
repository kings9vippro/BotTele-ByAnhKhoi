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
    'menu': 'Bảng điều khiển', 'help': 'Hướng dẫn', 'functions': 'Các chức năng Zalo', 'accounts': 'Tài khoản Zalo và Discord',
    'discord_login': 'Liên kết Discord OAuth2', 'discord_accounts': 'Tài khoản Discord',
    'discord_status': 'Trạng thái OAuth', 'discord_logout': 'Ngắt liên kết: ID',
    'tasks': 'Task theo cookie: /tasks [acc_id]', 'admin_tasks': 'Root: toàn bộ tác vụ',
    'dsbox': 'Nhóm Zalo riêng: /dsbox [acc_id] [trang]',
    'watch_status': 'Canh Zalo theo cookie: /watch_status [acc_id]',
    'task_status': 'Chi tiết: ID',
    'task_pause': 'Tạm dừng tác vụ chờ: ID', 'task_resume': 'Tiếp tục: ID',
    'task_stop': 'Dừng: ID', 'task_retry': 'Thử lại tác vụ thất bại: ID',
    'channels': 'Kênh webhook được cấp quyền', 'send': 'Gửi: channel_id | nội dung',
    'send_multi': 'Gửi: id1,id2 | nội dung (tối đa 5 kênh)',
    'delay': 'Độ trễ nhân tạo: 0 giây; API rate limit vẫn áp dụng',
    'performance': 'Hiệu suất tác vụ', 'logs': 'Nhật ký tác vụ',
    'settings': 'Cấu hình trong Mini App', 'system': 'Trạng thái máy chủ',
    'miniapp_check': 'Kiểm tra URL Mini App', 'miniapp': 'Mở Mini App', 'zalo': 'Menu Zalo', 'start': 'Khởi động',
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
        root_view = is_root(user)
        tasks = queue.list_all_for_root() if root_view else queue.list(user)
        counts = {}
        for t in tasks:
            counts[t['status']] = counts.get(t['status'],0)+1
        c = db()
        try:
            if root_view:
                oldest = c.execute('SELECT MIN(seq) FROM notification_events').fetchone()[0]
                reset = bool(cursor and oldest and cursor < oldest - 1)
                events = [dict(r) for r in c.execute(
                    'SELECT owner,task,status,at,seq FROM notification_events WHERE seq>? ORDER BY seq LIMIT 200',
                    (0 if reset else cursor,))]
            else:
                oldest = c.execute('SELECT MIN(seq) FROM notification_events WHERE owner=?', (str(user),)).fetchone()[0]
                reset = bool(cursor and oldest and cursor < oldest - 1)
                events = [dict(r) for r in c.execute(
                    'SELECT owner,task,status,at,seq FROM notification_events WHERE owner=? AND seq>? ORDER BY seq LIMIT 200',
                    (str(user), 0 if reset else cursor))]
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

    def is_root(principal):
        return bool(os.environ.get('TELEGRAM_ADMIN_ID')) and str(principal) == str(os.environ['TELEGRAM_ADMIN_ID'])

    def controlled_owner(principal, task_id):
        """Only authenticated root can operate tasks belonging to other users."""
        if is_root(principal):
            return queue.owner_of_task(task_id) or str(principal)
        return str(principal)

    def unified_tasks(principal, account_id=None):
        from task_registry import aggregate_tasks
        principal = str(principal)
        legacy = []
        is_admin = is_root(principal)
        if is_admin:
            import app as runtime
            # Legacy task records are process-local and may be interrupted by restart.
            legacy = runtime.task_snapshots(runtime.ACTIVE_TASKS, runtime.TASKS_RAM_STORE,
                [], runtime.TASKS_RAM_LOCK, account_id=account_id)
        rows = queue.list_all_for_root() if is_admin else queue.list(principal)
        if is_admin and not rows:
            rows = queue.list(principal)  # Backward-compatible empty registry fallback.
        items = aggregate_tasks(rows, legacy, owner=principal,
                                include_legacy=is_admin, include_all_notifications=is_admin)
        if account_id is not None:
            # No task is silently reattributed to a cookie missing from its metadata.
            from account_views import task_belongs_to_account
            items = [t for t in items if task_belongs_to_account(t, account_id)]
        return items

    app.extensions['unified_tasks'] = unified_tasks
    app.extensions['root_task_control_owner'] = controlled_owner

    @app.get('/api/miniapp/task_registry')
    def api_task_registry():
        principal = str(owner())
        account_id = str(request.args.get('account_id') or '').strip()
        if account_id:
            from get_ck_im_zalo import get_user_visible_accounts
            allowed = {str(a['id']) for a in get_user_visible_accounts(
                principal, enabled_only=False, platform='zalo', strict=True)}
            if not account_id.isdigit() or account_id not in allowed or principal != str(os.environ.get('TELEGRAM_ADMIN_ID') or ''):
                return jsonify(ok=False, error='Tài khoản Zalo không được cấp quyền.'), 403
        return jsonify(ok=True, owner=principal, account_id=account_id or None,
                       tasks=unified_tasks(principal, account_id=account_id if account_id else None))

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
            actor = str(owner())
            task_id = str(data.get('id',''))
            return jsonify(ok=True,status=queue.control(
                controlled_owner(actor, task_id),task_id,str(data.get('action',''))))
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
    # /menu uses the existing interactive Telegram media/card navigation.
    if name not in COMMANDS or name in ('start','zalo','miniapp','menu'):
        return False
    import app as runtime
    import html
    ext = runtime.app.extensions
    queue = ext['notification_queue']
    answer = ''
    try:
        if name == 'functions':
            from get_ck_im_zalo import FUNCTION_ITEMS_32
            supported = [item for item in FUNCTION_ITEMS_32 if item.get('id') and item.get('label')]
            rows = []
            for index in range(0,min(len(supported),24),2):
                rows.append([{'text': str(item['label'])[:46],
                              'callback_data': 'pickfn:'+str(item['id'])}
                             for item in supported[index:index+2]])
            lines = ['<b>GLAZE · CHỨC NĂNG ZALO</b>',
                     '<blockquote>Chọn chức năng bên dưới để mở hướng dẫn và thao tác tương ứng.']
            lines.extend(html.escape(str(item['label'])) for item in supported[:24])
            lines.append('</blockquote>')
            bot.send_text(chat,'\n'.join(lines), reply_markup={'inline_keyboard':rows})
            return True
        if name in ('menu','help'):
            answer = '\n'.join('/'+key+' — '+value for key,value in COMMANDS.items())+'\n/files — Kho tệp\n/sticker — Tạo nhãn dán\n/stopall — Dừng tác vụ Zalo'
        elif name == 'dsbox':
            from account_views import groups_for_account, paginate, request_group_refresh
            from get_ck_im_zalo import get_user_visible_accounts
            visible = get_user_visible_accounts(user, enabled_only=True, platform='zalo', strict=True)
            allowed = {str(a['id']): a for a in visible}
            parts = args.strip().split()
            if not parts:
                answer = ('Các tài khoản Zalo được phép xem:\n' +
                    '\n'.join(f"#{a['id']} · {a['name']}" for a in visible) +
                    '\nDùng /dsbox <acc_id> [trang].') if visible else 'Chưa có tài khoản Zalo.'
            elif len(parts)>2 or not all(part.isdigit() for part in parts):
                answer = 'Cú pháp: /dsbox <acc_id> [trang]'
            elif parts[0] not in allowed:
                answer = 'Tài khoản này không thuộc quyền quản lý của bạn.'
            else:
                account = allowed[parts[0]]
                try:
                    result = paginate(groups_for_account(account, runtime.Zalo._GROUPS_CACHE,
                        runtime.KNOWN_GROUPS_BY_ACC),int(parts[1]) if len(parts)>1 else 1,size=12)
                except ValueError:
                    answer = 'Trang không hợp lệ. Dùng /dsbox '+parts[0]+' 1'
                else:
                    a_id = str(account['id'])
                    page = result['page']
                    report = [f"BOX RIÊNG ACC #{a_id} · {account['name']}",
                              f"Trang {page}/{result['total_pages']} · {result['total']} nhóm"]
                    report.extend(f"{(page-1)*12+i}. {b['name']} · {b['id']}" for i,b in enumerate(result['rows'],1))
                    cache = runtime.Zalo._GROUPS_CACHE
                    cache_record = cache.get(str(account.get('uid') or '')) or cache.get(str(account.get('imei') or ''))
                    cache_timestamp = cache_record.get('ts', 0) if isinstance(cache_record,dict) else 0
                    stale = not result['total'] or not cache_record or bool(cache_timestamp and time.time()-float(cache_timestamp)>180)
                    if stale:
                        def _load_account():
                            client = runtime.Zalo.get_pooled_client(account['imei'], account['cookies'],
                                user_agent=account.get('user_agent') or '',
                                zpw_enk_hint=account.get('zpw_enk') or '',
                                uid_hint=account.get('uid') or '')
                            client.get_groups(use_cache=False)
                        def _notify_loaded(ok):
                            if ok:
                                bot.send_text(chat,'Đã đồng bộ nhóm acc #'+a_id+'. Xem /dsbox '+a_id+' 1')
                        queued = request_group_refresh(a_id, _load_account, _notify_loaded)
                        if queued:
                            report.append('Dữ liệu cache, đang cập nhật nền riêng của cookie này…')
                        elif not result['total']:
                            report.append('Chưa có dữ liệu. Thử lại sau khi phiên Zalo hoạt động.')
                    keyboard = []
                    nav = []
                    if result['has_previous']:
                        nav.append({'text':'‹ Trang trước','callback_data':f'v8:dsbox:{a_id}:{page-1}'})
                    if result['has_next']:
                        nav.append({'text':'Trang tiếp ›','callback_data':f'v8:dsbox:{a_id}:{page+1}'})
                    if nav:
                        keyboard.append(nav)
                    bot.send_text(chat,html.escape('\n'.join(report)),
                        reply_markup={'inline_keyboard':keyboard})
                    return True
        elif name == 'watch_status':
            if not os.environ.get('TELEGRAM_ADMIN_ID') or str(user) != str(os.environ.get('TELEGRAM_ADMIN_ID')):
                answer = 'Chỉ quản trị viên được xem thông tin canh box.'
            else:
                requested_account = args.strip()
                watched = runtime.CanhTreoWatchdogEngine.get_watched_boxes()
                if requested_account and not requested_account.isdigit():
                    answer = 'Cú pháp: /watch_status [acc_id]'
                elif not requested_account:
                    grouped = {}
                    for watch in watched:
                        key = str(watch.get('acc_id') or 'không xác định')
                        grouped[key] = grouped.get(key, 0) + 1
                    answer = ('CANH BOX ZALO THEO COOKIE\n' + ('\n'.join(
                        f'Acc #{k}: {count} box · /watch_status {k}' for k,count in sorted(grouped.items()))
                        or 'Chưa có box được canh trong tiến trình hiện tại.'))
                else:
                    subset = [w for w in watched if str(w.get('acc_id') or '') == requested_account]
                    items = ['CANH BOX ACC #' + requested_account]
                    for watch in subset[:10]:
                        label = str(watch.get('box_name') or watch.get('box_id'))[:65]
                        if watch.get('status') == 'awaiting_message':
                            status = 'Chờ tin nhắn đầu tiên'
                        else:
                            status = (f"{watch.get('silence_seconds') or 0:.0f}s/"
                                      f"{watch.get('timeout_sec') or 90:.0f}s") + (' · ĐÃ IM LẶNG' if watch.get('status') == 'silent' else '')
                        sync = 'API Zalo chưa đồng bộ' if watch.get('last_sync_at') is None else (
                            'API Zalo lỗi, dữ liệu cũ' if watch.get('last_sync_ok') is False else
                            'Đồng bộ '+str(int(watch.get('last_sync_age_seconds') or 0))+'s trước')
                        items.append(f"{label} · {status}\n  Tin cuối: {watch.get('last_message_at_label') or 'Chưa có'} · {sync}")
                    if len(subset)>10:
                        items.append(f'Còn {len(subset)-10} box: mở Mini App để xem.')
                    if not subset:
                        items.append('Chưa canh box nào ở cookie này hoặc watch đã mất sau restart.')
                    answer = '\n'.join(items)
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
            task_id = args.strip()
            if not task_id:
                answer = 'Cú pháp: /' + name + ' <task_id>'
            elif task_id.startswith('legacy:'):
                if not os.environ.get('TELEGRAM_ADMIN_ID') or str(user) != str(os.environ.get('TELEGRAM_ADMIN_ID')):
                    answer = 'Không đủ quyền quản lý tác vụ tiến trình.'
                elif name != 'task_stop':
                    answer = 'Tác vụ tiến trình chỉ hỗ trợ dừng; không hỗ trợ tạm dừng, tiếp tục hay thử lại.'
                else:
                    state = runtime.cancel_one(task_id[len('legacy:'):], runtime.ACTIVE_TASKS,
                        runtime.TASKS_RAM_STORE, runtime.TASKS_RAM_LOCK)
                    answer = 'Không tìm thấy tác vụ.' if state is None else 'Trạng thái hiện tại: ' + state
            else:
                answer = queue.control(ext['root_task_control_owner'](str(user),task_id), task_id, name[5:])
        elif name in ('tasks', 'task_status', 'admin_tasks'):
            if name == 'admin_tasks':
                if str(user) != str(os.environ.get('TELEGRAM_ADMIN_ID') or '') or not os.environ.get('TELEGRAM_ADMIN_ID'):
                    bot.send_text(chat, 'Chỉ root admin được xem toàn bộ tác vụ.')
                    return True
                name = 'tasks'
                args = '' 
            if name == 'task_status' and not args.strip():
                bot.send_text(chat, 'Cú pháp: /task_status <task_id>')
                return True
            requested_account = args.strip() if name == 'tasks' else ''
            if requested_account:
                from get_ck_im_zalo import get_user_visible_accounts
                allowed = {str(a['id']) for a in get_user_visible_accounts(
                    user, enabled_only=False, platform='zalo', strict=True)}
                if not requested_account.isdigit() or requested_account not in allowed or str(user) != str(os.environ.get('TELEGRAM_ADMIN_ID') or ''):
                    bot.send_text(chat,'Tài khoản Zalo không được cấp quyền. Cú pháp: /tasks <acc_id>')
                    return True
            rows = ext['unified_tasks'](str(user), account_id=requested_account) if requested_account else ext['unified_tasks'](str(user))
            if name == 'task_status':
                rows = [row for row in rows if row['id'] == args.strip() or row['source_id'] == args.strip()]
            answer = '\n'.join(
                f"{row['id']} · " + ("ACC #"+",".join(row['account_ids']) if row.get('account_ids') else row['platform'].upper()) +
                f" · {row['status']}" +
                (' · tạm thời theo tiến trình' if row['persistence'] == 'process_local' else '')
                for row in rows[:15]
            ) or ('Không tìm thấy tác vụ.' if name == 'task_status' else 'Chưa có tác vụ')
            if name == 'tasks' and not requested_account:
                answer = 'TÁC VỤ HIỆN CÓ\nLọc riêng: /tasks <acc_id>\n' + answer
            if name == 'tasks' and requested_account:
                answer = 'TÁC VỤ ACC #' + requested_account + '\n' + answer
            if not rows and name == 'tasks':
                answer += '\nLưu ý: task Zalo trong RAM có thể mất sau khi hosting khởi động lại.' 
            keyboard = []
            for row in rows[:5]:
                if row['execution_source'] == 'durable_notifications' and row['actions']:
                    keyboard.append([{'text': action + ' ' + row['source_id'][:6],
                        'callback_data': 'v4:' + action + ':' + row['source_id']}
                        for action in row['actions']])
            header = ('QUẢN TRỊ TÁC VỤ' if str(user) == str(os.environ.get('TELEGRAM_ADMIN_ID') or '') else 'TÁC VỤ CỦA BẠN')
            bot.send_text(chat, '<b>GLAZE · '+header+'</b>\n<blockquote>'+html.escape(answer)+'</blockquote>',
                          reply_markup={'inline_keyboard': keyboard})
            return True
        elif name == 'channels':
            answer = '\n'.join(f"{r['id']} · {r['name']}" for r in ext['managed_channels'](user)) or 'Thêm webhook trong Mini App → Discord'
        elif name in ('send','send_multi'):
            ids, separator, content = args.partition('|')
            targets = [v.strip() for v in ids.split(',')]
            maximum = 1 if name == 'send' else 5
            if not separator or not content.strip() or not 1 <= len(targets) <= maximum or any(not v for v in targets):
                answer = ('CÚ PHÁP: /send <channel_id> | <nội dung>' if name == 'send'
                          else 'CÚ PHÁP: /send_multi <id1>,<id2> | <nội dung> (tối đa 5 kênh)')
                answer += '\nXem /channels để biết các webhook được cấp quyền.'
            else:
                allowed = {r['id'] for r in ext['managed_channels'](user)}
                if any(v not in allowed for v in targets):
                    answer = 'Kênh chưa được cấp quyền. Mở /channels hoặc Mini App → Discord.'
                else:
                    answer = '\n'.join(queue.submit_many(user,targets,content.strip()))
        elif name == 'delay': answer = 'artificial_delay_seconds = 0; Retry-After của API vẫn được tôn trọng.'
        elif name == 'miniapp_check':
            from miniapp_url import public_miniapp_url
            url = public_miniapp_url()
            if url:
                answer = ('MINI APP GLAZE\nURL cấu hình: ' + url +
                          '\nNếu trang chưa tải, kiểm tra DNS, HTTPS, hosting và BotFather.')
            else:
                answer = ('MINI APP CHƯA CẤU HÌNH\n'
                          'Đặt MINIAPP_PUBLIC_URL bằng URL HTTPS công khai của hosting.\n'
                          'Sau đó kiểm tra /healthz và mở lại /miniapp.')
        elif name == 'settings': answer = 'Mở /miniapp → Cài đặt để cấu hình kết nối.'
        elif name == 'performance':
            from command_metrics import snapshot as command_snapshot
            stats = command_snapshot()
            data = ext['control_snapshot'](user)
            counts = data['counts'] or {}
            answer = ('HIỆU SUẤT BOT TELEGRAM\n'
                + 'Worker thông báo: ' + str(data['workers']) + '\n'
                + 'Tác vụ: ' + (', '.join(f'{k}={v}' for k,v in sorted(counts.items())) or 'Chưa có') + '\n'
                + 'Độ trễ Discord API: ' + (
                    f"{1000*data['api_latency_seconds']:.0f} ms" if data['api_latency_seconds'] is not None
                    else 'Chưa có mẫu gửi thành công') + '\n'
                + 'Lệnh Telegram đã đo: ' + str(stats['sample_count']) + '\n'                + 'Lệnh Zalo đã đo: ' + str(stats['zalo']['count']) + '\n'
                + 'Thời gian xử lý p50: ' + (str(stats['p50_handler_ms'])+' ms' if stats['p50_handler_ms'] is not None else 'Chưa đo') + '\n'
                + 'Thời gian xử lý p95: ' + (str(stats['p95_handler_ms'])+' ms' if stats['p95_handler_ms'] is not None else 'Cần ít nhất 20 mẫu') + '\n'                + 'Zalo handler p50: ' + (str(stats['zalo']['p50_ms'])+' ms' if stats['zalo']['p50_ms'] is not None else 'Chưa đo') + '\n'
                + 'Không bao gồm thời gian mạng Zalo hoặc giao hàng Telegram.')
        elif name == 'logs':
            data = ext['control_snapshot'](user)
            items = data['events'][-10:]
            answer = ('\n'.join(
                f"{str(item.get('status') or 'event')} · ID {str(item.get('task') or '')[:16]}"
                for item in items) or 'Chưa có nhật ký tác vụ thông báo.')
        elif name == 'system':
            data = ext['control_snapshot'](user)
            answer = ('MÁY CHỦ BOT\n' + 'Worker thông báo: '+str(data['workers'])
                + '\\nTask thuộc tiến trình: '+str(len(ext['unified_tasks'](str(user))))
                + '\\nĐồng bộ: '+time.strftime('%H:%M:%S',time.localtime(data['snapshot_at'])))
        else:
            answer = 'Hãy xem /help để biết lệnh và cú pháp hỗ trợ.'
    except (ValueError,KeyError):
        answer = 'Cấu hình hoặc tham số chưa hợp lệ. Xem /help và kiểm tra OAuth trong Mini App.'
    section = {
        'help':'HƯỚNG DẪN LỆNH', 'performance':'HIỆU SUẤT',
        'logs':'NHẬT KÝ', 'system':'MÁY CHỦ', 'channels':'KÊNH',
        'send_multi':'GỬI NHIỀU KÊNH', 'send':'GỬI THÔNG BÁO',
        'miniapp_check':'MINI APP',
    }.get(name, name.replace('_',' ').upper())
    bot.send_text(chat,'<b>GLAZE · '+html.escape(section)+'</b>\n<blockquote>'
                  +html.escape(str(answer))+'</blockquote>')
    return True