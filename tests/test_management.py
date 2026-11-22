"""Storage, controls and official callbacks. Author: Dev Anh Khôi. Version: 1.3.0."""
import hashlib
import hmac
import importlib
import json
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import test_data_consistency as fixtures
import app
import official_integrations as official
from scripts.verify_startup import check_runtime, check_entry


class ManagementTests(unittest.TestCase):
    def setUp(self):
        fixtures.DataConsistencyTests.setUp(self)

    def test_entry_points_share_runtime_and_complete_management_routes(self):
        self.assertIs(app, importlib.import_module('glaze_app'))
        self.assertTrue(callable(app.ensure_telegram_bot_started))
        routes = {rule.rule for rule in app.app.url_map.iter_rules()}
        for route in ('/login', '/miniapp', '/api/miniapp/accounts', '/file/create', '/integrations/discord', '/api/miniapp/control'):
            self.assertIn(route, routes)

    def test_errors_do_not_return_empty_dashboard_or_success(self):
        failures = (
            ("/miniapp", app, "render_template_string"),
            ("/api/miniapp/telemetry", app.RenderRAMAutoCleaner, "get_current_rss_mb"),
        )
        for path, target, method in failures:
            with self.subTest(path=path), patch.object(target, method, side_effect=RuntimeError('private-exception-value')):
                result = self.client.get(path)
                self.assertEqual(result.status_code, 500)
                self.assertNotIn('private-exception-value', result.text)
                self.assertNotIn('metric-accounts', result.text)
                if result.is_json:
                    self.assertFalse(result.json['ok'])
                    self.assertNotIn('total_accs', result.json)

    def test_unknown_api_route_keeps_404(self):
        self.assertEqual(self.client.get('/api/miniapp/does-not-exist').status_code, 404)

    def test_zalo_session_export_round_trips_through_import_parser(self):
        from get_ck_im_zalo import parse_imei_and_cookie_from_text
        conn = app.db()
        account_id = conn.execute(
            "INSERT INTO accounts(name,platform,imei,cookies) VALUES(?,?,?,?)",
            ('Fixture', 'zalo', '1234567890abcdef', json.dumps({'zpsid': 'fixture-session-cookie-value', 'unused': 'EXPIRED'})),
        ).lastrowid
        conn.commit()
        result = self.client.post('/api/miniapp/export_zalo_session', json={'account_id': account_id})
        self.assertEqual(result.status_code, 200)
        imei, cookies, _ = parse_imei_and_cookie_from_text(result.json['text'])
        self.assertEqual(imei, '1234567890abcdef')
        self.assertEqual(cookies['zpsid'], 'fixture-session-cookie-value')
        self.assertNotIn('unused', cookies)

    def test_finished_legacy_task_can_be_deleted(self):
        conn = app.db()
        conn.execute("INSERT INTO tasks(id,status) VALUES('finished-fixture','stopped')")
        conn.execute("INSERT INTO tasks(id,status) VALUES('running-fixture','running')")
        conn.commit()
        active = self.client.post('/api/miniapp/delete_finished_task', json={'task_ref': 'legacy:running-fixture'})
        self.assertEqual(active.status_code, 409)
        response = self.client.post('/api/miniapp/delete_finished_task', json={'task_ref': 'legacy:finished-fixture'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['deleted'])
        self.assertIsNone(conn.execute("SELECT id FROM tasks WHERE id='finished-fixture'").fetchone())

    def test_disabled_selected_account_never_falls_back_to_another_account(self):
        saved = {'fixture-task': {'id': 'fixture-task', 'status': 'running', 'meta': {'account_ids': [2]}}}
        active = {'fixture-task': {'stop': threading.Event()}}
        with patch.object(app, 'TASKS_RAM_STORE', saved), patch.object(app, 'ACTIVE_TASKS', active), \
                patch.object(app, 'get_all_accounts_from_ram', return_value=[{'id': 1, 'platform': 'zalo'}]), \
                patch.object(app, 'single_acc_multi_box_dispatcher') as dispatch:
            app.task_supervisor('fixture-task', [], [], {}, False, threading.Event(), account_ids=[2])
        dispatch.assert_not_called()
        self.assertEqual(saved['fixture-task']['status'], 'stopped')
        self.assertIn('Tài khoản đã chọn', saved['fixture-task']['error'])

    def test_missing_multi_account_anchor_does_not_start_unrelated_accounts(self):
        saved = {'fixture-task': {'id': 'fixture-task', 'status': 'running'}}
        with patch.object(app, 'TASKS_RAM_STORE', saved), patch.object(app, 'ACTIVE_TASKS', {}), \
                patch.object(app, 'get_all_accounts_from_ram', return_value=[{'id': 1, 'platform': 'zalo'}]), \
                patch.object(app, 'get_account_from_ram', return_value=None), \
                patch.object(app, 'single_acc_multi_box_dispatcher') as dispatch:
            app.task_supervisor('fixture-task', [], [], {}, True, threading.Event(), specific_acc_id=2)
        dispatch.assert_not_called()
        self.assertEqual(saved['fixture-task']['status'], 'stopped')

    def test_zalo_worker_auth_failure_is_visible_as_failed_task(self):
        saved = {'fixture-task': {'id': 'fixture-task', 'status': 'running'}}
        account = {'id': 2, 'platform': 'zalo', 'name': 'Fixture', 'imei': 'device', 'cookies': '{}'}
        with patch.object(app, 'TASKS_RAM_STORE', saved), patch.object(app, 'ACTIVE_TASKS', {}), \
                patch.object(app, 'get_all_accounts_from_ram', return_value=[account]), \
                patch.object(app.Zalo, 'get_pooled_client', side_effect=ValueError('private-cookie-secret')), \
                patch.object(app.HEALTH_MGR, 'report_error'), \
                patch.object(app.WaveFairnessEngine, 'register_accounts_for_wave'):
            app.task_supervisor('fixture-task', [{'id': 'box', 'type': 'group'}], ['hi'], {},
                                False, threading.Event(), account_ids=[2])
        self.assertEqual(saved['fixture-task']['status'], 'failed')
        self.assertIn('Cookie và IMEI', saved['fixture-task']['error'])
        self.assertNotIn('private-cookie-secret', saved['fixture-task']['error'])

    def test_discord_token_link_is_verified_encrypted_and_removable(self):
        profile = Mock(status_code=200)
        profile.json.return_value = {'id': '123456789', 'username': 'Fixture', 'bot': True}
        with patch('credential_links.requests.get', return_value=profile) as get:
            result = self.client.post('/api/miniapp/credential_links', json={
                'platform': 'discord', 'kind': 'bot', 'credential': 'fixture-discord-token',
            })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['link']['uid'], '123456789')
        self.assertIsInstance(result.json['link']['id'], int)
        self.assertNotIn('encrypted', result.json['link'])
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'Bot fixture-discord-token')
        row = app.db().execute('SELECT encrypted FROM credential_links').fetchone()
        self.assertNotIn('fixture-discord-token', row['encrypted'])
        listing = self.client.get('/api/miniapp/credential_links').json['links']
        self.assertEqual(len(listing), 1)
        self.assertNotIn('encrypted', listing[0])
        removed = self.client.delete('/api/miniapp/credential_links', json={'id': listing[0]['id']})
        self.assertTrue(removed.json['deleted'])

    def test_facebook_cookie_link_rejects_login_redirect_and_hides_cookie(self):
        cookie = 'c_user=123456789; xs=fixture-session-value'
        rejected = Mock(status_code=200, url='https://mbasic.facebook.com/login.php', text='<title>Login</title>')
        with patch('credential_links.requests.get', return_value=rejected):
            result = self.client.post('/api/miniapp/credential_links', json={'platform': 'facebook', 'credential': cookie})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client.get('/api/miniapp/credential_links').json['links'], [])
        accepted = Mock(status_code=200, url='https://mbasic.facebook.com/profile.php', text='<title>Fixture Profile</title>')
        with patch('credential_links.requests.get', return_value=accepted):
            result = self.client.post('/api/miniapp/credential_links', json={'platform': 'facebook', 'credential': cookie})
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('fixture-session-value', result.text)
        self.assertEqual(result.json['link']['name'], 'Fixture Profile')
        row = app.db().execute('SELECT encrypted FROM credential_links').fetchone()
        self.assertNotIn('fixture-session-value', row['encrypted'])

    def test_facebook_cookie_formats_and_redirect_does_not_leak_cookie(self):
        from credential_links import CredentialRejected, normalize_facebook_cookie, verify_facebook
        uid, normalized = normalize_facebook_cookie(json.dumps([
            {'name': 'c_user', 'value': '123456789'}, {'name': 'xs', 'value': 'fixture-session'},
        ]))
        self.assertEqual(uid, '123456789')
        self.assertIn('xs=fixture-session', normalized)
        redirect = Mock(status_code=302, headers={'Location': 'https://outside.example/collect'},
                        url='https://mbasic.facebook.com/profile.php')
        with patch('credential_links.requests.get', return_value=redirect) as get:
            with self.assertRaises(CredentialRejected):
                verify_facebook(normalized)
        self.assertEqual(get.call_count, 1)
        self.assertFalse(get.call_args.kwargs['allow_redirects'])

    def test_discord_bot_link_recheck_marks_provider_failure_without_losing_secret(self):
        profile = Mock(status_code=200)
        profile.json.return_value = {'id': '123456789', 'username': 'Fixture', 'bot': True}
        with patch('credential_links.requests.get', return_value=profile) as get:
            result = self.client.post('/api/miniapp/credential_links', json={
                'platform': 'discord', 'kind': 'bot', 'credential': 'fixture-bot-token',
            })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'Bot fixture-bot-token')
        link = self.client.get('/api/miniapp/credential_links').json['links'][0]
        self.assertEqual(link['kind'], 'bot')
        unavailable = Mock(status_code=429)
        with patch('credential_links.requests.get', return_value=unavailable):
            checked = self.client.post('/api/miniapp/credential_links/check', json={'id': link['id']})
        self.assertEqual(checked.json['result']['status'], 'unknown')
        rejected = Mock(status_code=401)
        with patch('credential_links.requests.get', return_value=rejected):
            checked = self.client.post('/api/miniapp/credential_links/check', json={'id': link['id']})
        self.assertEqual(checked.json['result']['status'], 'invalid')
        self.assertNotIn('fixture-bot-token', checked.text)
        stored = app.db().execute('SELECT encrypted,status FROM credential_links').fetchone()
        self.assertEqual(stored['status'], 'invalid')
        self.assertNotIn('fixture-bot-token', stored['encrypted'])

    def test_linked_discord_account_sends_and_reports_permission_failure(self):
        profile = Mock(status_code=200)
        profile.json.return_value = {'id': '123456789', 'username': 'Fixture', 'bot': True}
        with patch('credential_links.requests.get', return_value=profile):
            self.client.post('/api/miniapp/credential_links', json={
                'platform': 'discord', 'kind': 'bot', 'credential': 'fixture-bot-token',
            }).json['link']
        link_id = self.client.get('/api/miniapp/credential_links').json['links'][0]['id']
        message = Mock(status_code=200)
        message.json.return_value = {'id': '987654321098765432'}
        with patch('credential_links.requests.post', return_value=message) as send:
            result = self.client.post('/api/miniapp/credential_links/send_discord', json={
                'id': link_id, 'channel_id': '123456789012345678', 'content': 'Xin chào',
            })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['message_id'], '987654321098765432')
        self.assertEqual(send.call_args.kwargs['headers']['Authorization'], 'Bot fixture-bot-token')
        self.assertEqual(send.call_args.kwargs['json']['allowed_mentions'], {'parse': []})
        self.assertNotIn('fixture-bot-token', result.text)
        denied = Mock(status_code=403)
        with patch('credential_links.requests.post', return_value=denied):
            result = self.client.post('/api/miniapp/credential_links/send_discord', json={
                'id': link_id, 'channel_id': '123456789012345678', 'content': 'Xin chào',
            })
        self.assertEqual(result.status_code, 400)
        self.assertIn('không có quyền', result.json['error'])
        expired = Mock(status_code=401)
        with patch('credential_links.requests.post', return_value=expired):
            result = self.client.post('/api/miniapp/credential_links/send_discord', json={
                'id': link_id, 'channel_id': '123456789012345678', 'content': 'Xin chào',
            })
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.client.get('/api/miniapp/credential_links').json['links'][0]['status'], 'invalid')

    def test_existing_credential_vault_gains_health_columns_without_losing_links(self):
        import sqlite3
        from credential_links import ensure_schema, list_links
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        connection.execute('''CREATE TABLE credential_links (
            id INTEGER PRIMARY KEY, owner TEXT NOT NULL, platform TEXT NOT NULL,
            uid TEXT NOT NULL, name TEXT NOT NULL, encrypted TEXT NOT NULL,
            updated REAL NOT NULL, UNIQUE(owner,platform,uid))''')
        connection.execute("INSERT INTO credential_links VALUES(1,'root','discord','123','Old account','ciphertext',1)")
        ensure_schema(connection)
        row = list_links(connection, 'root')[0]
        self.assertEqual(row['name'], 'Old account')
        self.assertEqual(row['status'], 'unknown')
        self.assertNotIn('encrypted', row)

    def test_build_check_rejects_valid_python_with_missing_runtime_tail(self):
        with self.assertRaisesRegex(ValueError, 'ensure_telegram_bot_started'):
            check_runtime('app = object()\ndef init_db():\n    pass\n# cut at a comment, so syntax alone passes\n')

    def test_build_check_rejects_replaced_legacy_entry_point(self):
        with self.assertRaisesRegex(ValueError, 'phải nạp runtime'):
            check_entry('app = object()\n# a legacy partial upload\n')

    def test_real_telegram_save_and_miniapp_read_same_account_and_storage(self):
        import get_ck_im_zalo as telegram
        with patch.object(telegram.ZaloPCSessionKeeper, 'register_and_keep_alive'), patch.object(app.ZaloCookieVaultEngine, 'save_zalo_vault_record'), patch.object(app, 'add_authorized_user'), patch.object(app, 'refresh_owner_uids'), patch.object(app, 'sync_all_zalo_listeners'), patch.object(telegram.threading, 'Thread'):
            account_id = telegram.sync_zalo_account_to_web_db('90000123', 'Imported', 'device-fixture', {'zpsid': 'fixture-session'}, zpw_enk='fixture-key', owner_tg_id=telegram.ROOT_ADMIN_ID)
            self.assertIsNotNone(account_id)
            app.db().execute('UPDATE accounts SET chat_cmd_enabled=0 WHERE id=?', (account_id,))
            app.db().commit()
            again = telegram.sync_zalo_account_to_web_db('90000123', 'Imported', 'device-fixture', {'zpsid': 'fixture-session-2'}, zpw_enk='fixture-key', owner_tg_id=telegram.ROOT_ADMIN_ID)
        self.assertEqual(again, account_id)
        receipt = telegram.saved_account_receipt(account_id)
        listing = self.client.get('/api/miniapp/accounts').json
        telemetry = self.client.get('/api/miniapp/telemetry').json
        self.assertEqual([row['id'] for row in listing['accounts']], [account_id])
        self.assertEqual(telemetry['total_accs'], 1)
        self.assertFalse(listing['accounts'][0]['chat_cmd_enabled'])
        self.assertFalse(receipt['commands_enabled'])
        self.assertEqual(receipt['storage_id'], listing['storage_id'])
        self.assertEqual(receipt['storage_id'], telemetry['storage_id'])

    def test_zalo_owner_cannot_be_taken_by_matching_uid(self):
        import get_ck_im_zalo as telegram
        self.assertTrue(telegram.can_user_access_account(telegram.ROOT_ADMIN_ID, ''))
        self.assertFalse(telegram.can_user_access_account('other-user', ''))
        with patch.object(telegram.ZaloPCSessionKeeper, 'register_and_keep_alive'), patch.object(app.ZaloCookieVaultEngine, 'save_zalo_vault_record'), patch.object(app.Zalo, 'get_pooled_client', return_value=SimpleNamespace(uid='owner-test-uid', secret_key='fixture-key')), patch.object(app, 'add_authorized_user'), patch.object(app, 'refresh_owner_uids'), patch.object(app, 'sync_all_zalo_listeners'), patch.object(telegram.threading, 'Thread'):
            saved=telegram.sync_zalo_account_to_web_db('owner-test-uid','Owner','owner-imei',{'zpsid':'valid-fixture'},zpw_enk='fixture-key',owner_tg_id='alice')
            self.assertIsNotNone(saved)
            stolen=telegram.sync_zalo_account_to_web_db('owner-test-uid','Intruder','owner-imei',{'zpsid':'different-fixture'},zpw_enk='fixture-key',owner_tg_id='bob')
        self.assertIsNone(stolen)
        record=app.db().execute('SELECT owner_tg_id,name,cookies FROM accounts WHERE id=?',(saved,)).fetchone()
        self.assertEqual(record['owner_tg_id'],'alice')
        self.assertEqual(record['name'],'Owner')
        self.assertNotIn('different-fixture',record['cookies'])

    def test_signed_delegate_sees_only_scoped_miniapp_services(self):
        import os
        import hmac
        uid='123456789'
        conn=app.db()
        conn.execute('CREATE TABLE IF NOT EXISTS tg_authorized_users(uid TEXT PRIMARY KEY,name TEXT,role TEXT,added_at INTEGER)')
        conn.execute("INSERT OR REPLACE INTO tg_authorized_users VALUES(?, 'Fixture', 'VIP', 1)",(uid,))
        conn.commit()
        from durable_tasks import TaskQueue
        TaskQueue(lambda: app.db(), lambda *_args: None).close()
        conn.execute('CREATE TABLE IF NOT EXISTS webhook_channels(id TEXT PRIMARY KEY,owner TEXT NOT NULL,name TEXT NOT NULL,secret TEXT NOT NULL,created REAL NOT NULL)')
        conn.commit()
        values={'auth_date':str(int(time.time())),'user':json.dumps({'id':int(uid)},separators=(',',':'))}
        key=hmac.new(b'WebAppData',os.environ['TELEGRAM_BOT_TOKEN'].encode(),hashlib.sha256).digest()
        check='\n'.join(f'{k}={values[k]}' for k in sorted(values))
        values['hash']=hmac.new(key,check.encode(),hashlib.sha256).hexdigest()
        from urllib.parse import urlencode
        client=app.app.test_client()
        headers={'X-Telegram-Init-Data':urlencode(values)}
        self.assertEqual(client.get('/api/miniapp/session',headers=headers).json['owner'],uid)
        self.assertEqual(client.get('/api/miniapp/control',headers=headers).status_code,200)
        self.assertEqual(client.get('/api/miniapp/oauth/connections',headers=headers).status_code,200)
        self.assertEqual(client.get('/api/miniapp/credential_links',headers=headers).status_code,403)
        self.assertEqual(client.get('/api/miniapp/accounts',headers=headers).status_code,403)
        self.assertEqual(client.post('/api/miniapp/oauth/configure',headers=headers,json={}).status_code,403)

    def test_miniapp_launch_uses_selected_account_and_named_boxes(self):
        accounts=[{'id':1,'name':'First','platform':'zalo','uid':'uid-first','enabled':1},
                  {'id':2,'name':'Second','platform':'zalo','uid':'uid-second','enabled':1}]
        groups={'uid-first':{'data':[{'id':'box-one','name':'Box One'}]},
                'uid-second':{'data':[{'id':'box-two','name':'Box Two'}]}}
        with patch.object(app,'get_all_accounts_from_ram',return_value=accounts), \
             patch.dict(app.Zalo._GROUPS_CACHE,groups,clear=True), \
             patch.dict(app.KNOWN_GROUPS_BY_ACC,{},clear=True), \
             patch.object(app,'start_task_programmatic',return_value='task-fixture') as launch:
            listing=self.client.get('/api/miniapp/boxes?account_id=2')
            self.assertEqual([(box['id'],box['name']) for box in listing.json['boxes']],[('box-two','Box Two')])
            bad=self.client.post('/api/miniapp/launch',json={'account_id':2,'box_ids':['box-one'],'mode':'treo_ngon','custom_text':'Hello'})
            self.assertEqual(bad.status_code,409)
            self.assertFalse(launch.called)
            good=self.client.post('/api/miniapp/launch',json={'account_id':2,'box_ids':['box-two'],'mode':'treo_ngon','custom_text':'Hello','delay':0})
            self.assertTrue(good.json['ok'])
            self.assertEqual(launch.call_args.kwargs['account_ids'],[2])
            self.assertEqual(launch.call_args.kwargs['targets'][0]['name'],'Box Two')
            self.assertEqual(launch.call_args.kwargs['delay'],0)

    def test_miniapp_launch_rejects_bad_delay_before_starting_task(self):
        with patch.object(app,'start_task_programmatic') as launch:
            response=self.client.post('/api/miniapp/launch',json={'delay':'NaN'})
        self.assertEqual(response.status_code,400)
        launch.assert_not_called()

    def test_parallel_zalo_reconciliation_does_not_overlap(self):
        active=0
        maximum=0
        guard=threading.Lock()
        def reconcile():
            nonlocal active,maximum
            with guard:
                active+=1
                maximum=max(maximum,active)
            time.sleep(0.02)
            with guard:
                active-=1
        with patch.object(app,'_sync_all_zalo_listeners_locked',side_effect=reconcile):
            workers=[threading.Thread(target=app.sync_all_zalo_listeners) for _ in range(5)]
            for worker in workers:worker.start()
            for worker in workers:worker.join(2)
        self.assertEqual(maximum,1)
        self.assertTrue(all(not worker.is_alive() for worker in workers))

    def test_global_stop_no_longer_needs_retired_discord_engine(self):
        event=threading.Event()
        active={'fixture':{'stop':event,'targets':['group-fixture']}}
        saved={'fixture':{'status':'running','meta':{'targets':['group-fixture']}}}
        with patch.object(app,'ACTIVE_TASKS',active),patch.object(app,'TASKS_RAM_STORE',saved):
            self.assertGreaterEqual(app.stop_tasks_for_thread(None),1)
        self.assertTrue(event.is_set())

    def test_stop_retains_inflight_task_until_worker_finishes(self):
        stopped, release = threading.Event(), threading.Event()
        worker = threading.Thread(target=lambda: release.wait(3))
        worker.start()
        self.addCleanup(lambda: (release.set(), worker.join(3)))
        active = {'job': {'stop': stopped, 'thread': worker, 'targets': ['channel']}}
        saved = {'job': {'type': 'test', 'status': 'running', 'started_at': time.time(), 'meta': {'target_names': ['Full channel name'], 'targets': ['channel']}}}
        with patch.object(app, 'ACTIVE_TASKS', active), patch.object(app, 'TASKS_RAM_STORE', saved):
            result = self.client.post('/api/miniapp/stop_task', json={'task_id': 'job'})
            self.assertEqual(result.status_code, 202)
            self.assertTrue(stopped.is_set())
            self.assertIn('job', active)
            current = self.client.get('/api/miniapp/telemetry').json
            self.assertEqual(current['stopping_tasks'], 1)
            self.assertEqual(current['tasks'][0]['target_label'], 'Full channel name')
            release.set()
            worker.join(2)
            self.assertEqual(self.client.get('/api/miniapp/telemetry').json['tasks'][0]['status'], 'stopped')
            app._flush_ram_tasks_to_db()
            self.assertEqual(app.db().execute("SELECT status FROM tasks WHERE id='job'").fetchone()[0], 'stopped')
        self.assertEqual(self.client.post('/api/miniapp/stop_task', json={'task_id': 'missing'}).status_code, 404)

    def test_unified_task_registry_exposes_and_routes_both_task_engines(self):
        """A Mini App snapshot is the same read model used by bot commands."""
        stop = threading.Event()
        active = {'legacy-fixture': {'stop': stop, 'targets': ['zalo-room'], 'source': 'fixture'}}
        saved = {'legacy-fixture': {
            'id': 'legacy-fixture', 'type': 'treo_ngon', 'status': 'running',
            'started_at': time.time(), 'meta': {'target_names': ['Zalo room']},
        }}
        queue = app.app.extensions['notification_queue']
        queue.ensure_schema()
        durable_id = queue.submit(str(app.TELEGRAM_ADMIN_ID), 'discord-channel', 'fixture notification')
        with patch.object(app, 'ACTIVE_TASKS', active), patch.object(app, 'TASKS_RAM_STORE', saved):
            snapshot = self.client.get('/api/miniapp/control').json
            refs = {row['task_ref'] for row in snapshot['tasks']}
            self.assertIn('legacy:legacy-fixture', refs)
            self.assertIn('durable:' + durable_id, refs)

            legacy_stop = self.client.post('/api/miniapp/task_control', json={
                'task_ref': 'legacy:legacy-fixture', 'action': 'stop',
            })
            self.assertEqual(legacy_stop.status_code, 200)
            self.assertTrue(stop.is_set())
            durable_stop = self.client.post('/api/miniapp/task_control', json={
                'task_ref': 'durable:' + durable_id, 'action': 'stop',
            })
            self.assertEqual(durable_stop.status_code, 200)
            self.assertEqual(durable_stop.json['status'], 'CANCELLED')

    def test_failed_task_flush_keeps_pending_changes(self):
        saved = {'job': {'type': 'test', 'status': 'stopped', 'dirty': True, 'meta': {}}}
        with patch.object(app, 'TASKS_RAM_STORE', saved), patch.object(app.db(), 'commit', side_effect=app.sqlite3.OperationalError('busy')):
            app._flush_ram_tasks_to_db()
        self.assertTrue(saved['job']['dirty'])
        self.assertFalse(saved['job'].get('persisted', False))

    def test_disabled_account_cannot_handle_queued_menu(self):
        with patch.object(app, 'get_account_from_ram', return_value={'id': 7, 'enabled': 1, 'chat_cmd_enabled': 0}):
            self.assertFalse(app.parse_and_execute_inchat_command(None, {'id': 7}, 'group', True, 'owner', '.menu'))

    def test_menu_dispatches_on_first_message_without_external_network(self):
        account = {'id': 7, 'uid': '90000123', 'enabled': 1, 'chat_cmd_enabled': 1}
        client = Mock(uid='90000123', send2me_id='90000123')
        executor = Mock()
        executor.submit.side_effect = lambda function, *args: function(*args)
        with patch.object(app, 'get_account_from_ram', return_value=account), patch.object(app, 'get_all_accounts_from_ram', return_value=[account]), patch.object(app, '_INTERACTIVE_REPLY_EXECUTOR', executor), patch.object(app, 'GLOBAL_CMD_DEDUPE_CACHE', {}), patch.object(app, 'log_system_command'):
            accepted = app.parse_and_execute_inchat_command(client, account, 'group', True, '0', '.menu', msg_id='first-menu')
        self.assertTrue(accepted)
        client.send_adv.assert_called_once()
        self.assertIn('.menu', client.send_adv.call_args.args[0])

    def test_stopall_cancels_shared_task_and_does_not_stop_unrelated_account(self):
        first, other = threading.Event(), threading.Event()
        active = {'shared': {'stop': first, 'targets': ['channel']}, 'other': {'stop': other, 'targets': ['other-channel']}}
        saved = {'shared': {'status': 'running', 'meta': {'account_ids': [1, 2]}}, 'other': {'status': 'running', 'meta': {'account_ids': [3]}}}
        conn = app.db()
        conn.executemany("INSERT INTO tasks(id,status) VALUES(?,'running')", [('shared',), ('other',)])
        conn.commit()

        class InlineThread:
            def __init__(self, target, **kwargs):
                self.target = target
            def start(self):
                self.target()

        with patch.object(app, 'ACTIVE_TASKS', active), patch.object(app, 'TASKS_RAM_STORE', saved), patch.object(app.threading, 'Thread', InlineThread):
            app.stop_tasks_for_thread(None, acc_id=1)
        self.assertTrue(first.is_set())
        self.assertFalse(other.is_set())
        self.assertEqual(conn.execute("SELECT status FROM tasks WHERE id='other'").fetchone()[0], 'running')

    def test_unusual_message_command_field_does_not_drop_menu(self):
        listener = app.ZaloRealtimeListener(7)
        client = Mock(uid='90000123', send2me_id='90000123')
        message = {'msgId': 'unique-menu', 'content': '.menu', 'cmd': 'message', 'grid': 'group-1', 'uidFrom': '0', '_is_group_hint': True}
        with patch.object(app, 'get_account_from_ram', return_value={'id': 7, 'enabled': 1, 'chat_cmd_enabled': 1}), patch.object(app, 'parse_and_execute_inchat_command', return_value=True) as dispatch, patch.object(app.CanhTreoWatchdogEngine, 'record_incoming_message'):
            listener._process_msg_item(client, {'id': 7, 'uid': '90000123'}, message)
        dispatch.assert_called_once()
        self.assertEqual(dispatch.call_args.kwargs['raw_msg'], '.menu')

    def test_deleted_or_disabled_account_cannot_run_queued_emergency_command(self):
        listener = app.ZaloRealtimeListener(7)
        message = {'msgId': 'stop-menu', 'content': '.stopall', 'grid': 'group-1', 'uidFrom': '0'}
        for account in (None, {'id': 7, 'enabled': 1, 'chat_cmd_enabled': 0}):
            with patch.object(app, 'get_account_from_ram', return_value=account), patch.object(app, 'stop_tasks_for_thread') as stop:
                listener._process_msg_item(Mock(uid='90000123'), {'id': 7}, message)
                stop.assert_not_called()

    def configure(self, provider, extra=None):
        self.signing = Ed25519PrivateKey.generate()
        key = self.signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        values = {'provider': provider, 'token': 'private-token', 'owner_ids': '123', 'public_key': key,
                  'page_id': '9876', 'app_secret': 'private-app-secret', 'verify_token': 'verification', 'graph_version': 'v23.0'}
        values.update(extra or {})
        response = MagicMock(status_code=200)
        response.__enter__.return_value = response
        response.json.return_value = {'id': str(values.get('page_id') or '9876'), 'name': 'Managed', 'bot': True, 'category': 'Business'}
        with patch.object(official.requests, 'get', return_value=response):
            result = self.client.post('/api/miniapp/integrations/configure', json=values)
        self.assertEqual(result.status_code, 200, result.json)
        return values

    def discord_post(self, data, signature_valid=True):
        raw = json.dumps(data).encode()
        stamp = str(int(time.time()))
        sig = self.signing.sign(stamp.encode() + raw).hex() if signature_valid else '00' * 64
        return self.client.post('/integrations/discord', data=raw, content_type='application/json', headers={'X-Signature-Timestamp': stamp, 'X-Signature-Ed25519': sig})

    def test_discord_ping_signature_permissions_and_replay(self):
        self.configure('discord')
        self.assertEqual(self.discord_post({'type': 1}).json, {'type': 1})
        self.assertEqual(self.discord_post({'type': 1}, False).status_code, 401)
        with patch.object(app, 'stop_tasks_for_thread', return_value=2) as stop:
            denied = self.discord_post({'type': 2, 'id': '400', 'user': {'id': '456'}, 'data': {'name': 'stopall'}})
            stop.assert_not_called()
            self.assertIn('chưa được cấp quyền', denied.json['data']['content'])
            message = {'type': 2, 'id': '401', 'user': {'id': '123'}, 'data': {'name': 'stopall'}}
            self.assertEqual(self.discord_post(message).status_code, 200)
            self.discord_post(message)
            stop.assert_called_once_with(None)
        listing = self.client.get('/api/miniapp/integrations')
        self.assertNotIn('private-token', listing.text)
        record = app.db().execute("SELECT credentials FROM official_integrations WHERE provider='discord:9876'").fetchone()[0]
        self.assertNotIn('private-token', record)

    def test_discord_command_registration_preserves_unrelated_commands(self):
        self.configure('discord')
        reply = MagicMock(status_code=201)
        reply.__enter__.return_value = reply
        with patch.object(official.requests, 'post', return_value=reply) as post, patch.object(official.requests, 'put') as bulk:
            self.assertTrue(self.client.post('/api/miniapp/integrations/discord/commands').json['ok'])
        self.assertEqual(post.call_count, 4)
        bulk.assert_not_called()

    def test_multiple_discord_bots_have_independent_signatures_and_deletion(self):
        self.configure('discord')
        first_key = self.signing
        self.configure('discord', {'page_id': '9877'})
        second_key = self.signing
        listing = self.client.get('/api/miniapp/integrations').json['integrations']
        self.assertEqual(len([item for item in listing if item['provider'] == 'discord' and item['configured']]), 2)
        self.signing = first_key
        self.assertEqual(self.discord_post({'type': 1, 'application_id': '9876'}).status_code, 200)
        self.signing = second_key
        self.assertEqual(self.discord_post({'type': 1, 'application_id': '9876'}).status_code, 401)
        self.assertEqual(self.discord_post({'type': 1, 'application_id': '9877'}).json, {'type': 1})
        ambiguous = self.client.post('/api/miniapp/integrations/disconnect', json={'provider': 'discord'})
        self.assertEqual(ambiguous.status_code, 400)
        self.assertTrue(self.client.post('/api/miniapp/integrations/disconnect', json={'provider': 'discord', 'id': '9876'}).json['ok'])
        self.assertEqual(self.discord_post({'type': 1, 'application_id': '9877'}).status_code, 200)



    def test_oauth_configuration_is_retired_without_storing_secret(self):
        result = self.client.post('/api/miniapp/oauth/configure', json={'provider': 'discord', 'client_id': '1234', 'client_secret': 'private-new-secret', 'public_base_url': 'https://bot.example'})
        self.assertEqual(result.status_code, 410)
        self.assertNotIn('private-new-secret', result.text)
        self.assertIsNone(app.db().execute("SELECT encrypted FROM oauth_configuration WHERE provider='discord'").fetchone())
        self.assertEqual(self.client.post('/api/miniapp/oauth/start', json={'provider': 'discord'}).status_code, 410)

    def test_new_configuration_endpoints_require_authentication(self):
        client = app.app.test_client()
        for path in ('oauth/configure', 'integrations/configure', 'integrations/disconnect', 'integrations/discord/commands'):
            self.assertEqual(client.post('/api/miniapp/' + path, json={}).status_code, 401)

    def test_oauth_configuration_rejects_non_https_base(self):
        response = self.client.post('/api/miniapp/oauth/configure', json={'provider': 'discord', 'client_id': '1234', 'client_secret': 'fixture-secret', 'public_base_url': 'http://bot.example'})
        self.assertEqual(response.status_code, 410)
        self.assertEqual(app.db().execute('SELECT count(*) FROM oauth_configuration').fetchone()[0], 0)

    def test_disconnect_removes_only_the_selected_integration(self):
        self.configure('discord')
        response = self.client.post('/api/miniapp/integrations/disconnect', json={'provider': 'discord'})
        self.assertTrue(response.json['ok'])
        providers = self.client.get('/api/miniapp/integrations').json['integrations']
        status = {item['provider']: item['configured'] for item in providers}
        self.assertEqual(status, {'discord': False})


if __name__ == '__main__':
    unittest.main()
