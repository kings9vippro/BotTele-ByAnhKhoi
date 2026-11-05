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
        with patch.object(app.RenderRAMAutoCleaner, 'get_current_rss_mb', side_effect=RuntimeError('private-exception-value')):
            for path in ('/miniapp', '/api/miniapp/telemetry'):
                result = self.client.get(path)
                self.assertEqual(result.status_code, 500)
                self.assertNotIn('private-exception-value', result.text)
                self.assertNotIn('metric-accounts', result.text)
                if result.is_json:
                    self.assertFalse(result.json['ok'])
                    self.assertNotIn('total_accs', result.json)

    def test_unknown_api_route_keeps_404(self):
        self.assertEqual(self.client.get('/api/miniapp/does-not-exist').status_code, 404)

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
        self.assertEqual(client.get('/api/miniapp/accounts',headers=headers).status_code,401)
        self.assertEqual(client.post('/api/miniapp/oauth/configure',headers=headers,json={}).status_code,401)

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



    def test_oauth_configuration_form_is_encrypted_and_secret_free(self):
        result = self.client.post('/api/miniapp/oauth/configure', json={'provider': 'discord', 'client_id': '1234', 'client_secret': 'private-new-secret', 'public_base_url': 'https://bot.example'})
        self.assertEqual(result.status_code, 200)
        providers = self.client.get('/api/miniapp/oauth/providers')
        discord = next(item for item in providers.json['providers'] if item['id'] == 'discord')
        self.assertTrue(discord['configured'])
        self.assertNotIn('private-new-secret', providers.text)
        encrypted = app.db().execute("SELECT encrypted FROM oauth_configuration WHERE provider='discord'").fetchone()[0]
        self.assertNotIn('private-new-secret', encrypted)

    def test_new_configuration_endpoints_require_authentication(self):
        client = app.app.test_client()
        for path in ('oauth/configure', 'integrations/configure', 'integrations/disconnect', 'integrations/discord/commands'):
            self.assertEqual(client.post('/api/miniapp/' + path, json={}).status_code, 401)

    def test_oauth_configuration_rejects_non_https_base(self):
        response = self.client.post('/api/miniapp/oauth/configure', json={'provider': 'discord', 'client_id': '1234', 'client_secret': 'fixture-secret', 'public_base_url': 'http://bot.example'})
        self.assertEqual(response.status_code, 400)
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
