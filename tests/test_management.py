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
        for route in ('/login', '/miniapp', '/api/miniapp/accounts', '/file/create', '/integrations/discord', '/integrations/facebook'):
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

    def test_multiple_pages_route_batched_messages_using_their_own_tokens(self):
        values = self.configure('facebook', {'token': 'page-one-token'})
        self.configure('facebook', {'page_id': '9877', 'token': 'page-two-token', 'owner_ids': '456'})
        payload = {'entry': [
            {'id': '9876', 'messaging': [{'sender': {'id': '123'}, 'message': {'mid': 'same-mid', 'text': '.menu'}}]},
            {'id': '9877', 'messaging': [{'sender': {'id': '456'}, 'message': {'mid': 'same-mid', 'text': '.menu'}}]}
        ]}
        raw = json.dumps(payload).encode()
        sig = 'sha256=' + hmac.new(values['app_secret'].encode(), raw, hashlib.sha256).hexdigest()
        sent, done, lock = [], threading.Event(), threading.Lock()
        reply = MagicMock(status_code=200)
        reply.__enter__.return_value = reply

        def send(url, **kwargs):
            with lock:
                sent.append((url, kwargs['headers']['Authorization'], kwargs['json']['recipient']['id']))
                if len(sent) == 2:
                    done.set()
            return reply

        with patch.object(official.requests, 'post', side_effect=send):
            result = self.client.post('/integrations/facebook', data=raw, content_type='application/json', headers={'X-Hub-Signature-256': sig})
            self.assertEqual(result.status_code, 200)
            self.assertTrue(done.wait(3))
            self.assertEqual(self.client.post('/integrations/facebook', data=raw, content_type='application/json', headers={'X-Hub-Signature-256': sig}).status_code, 200)
        self.assertEqual(len(sent), 2)
        self.assertIn(('https://graph.facebook.com/v23.0/9876/messages', 'Bearer page-one-token', '123'), sent)
        self.assertIn(('https://graph.facebook.com/v23.0/9877/messages', 'Bearer page-two-token', '456'), sent)

    def test_facebook_verify_signature_owner_and_duplicate_stop(self):
        values = self.configure('facebook')
        challenge = self.client.get('/integrations/facebook', query_string={'hub.mode': 'subscribe', 'hub.verify_token': 'verification', 'hub.challenge': '1234'})
        self.assertEqual(challenge.text, '1234')
        self.assertEqual(self.client.post('/integrations/facebook', json={}).status_code, 403)
        event = {'entry': [{'id': '9876', 'messaging': [{'sender': {'id': '123'}, 'message': {'mid': 'message-one', 'text': 'stopall'}}]}]}
        raw = json.dumps(event).encode()
        sig = 'sha256=' + hmac.new(values['app_secret'].encode(), raw, hashlib.sha256).hexdigest()
        delivered = threading.Event()
        reply = MagicMock(status_code=200)
        reply.__enter__.return_value = reply

        def send(*args, **kwargs):
            delivered.set()
            return reply

        with patch.object(app, 'stop_tasks_for_thread', return_value=1) as stop, patch.object(official.requests, 'post', side_effect=send):
            for _ in range(2):
                result = self.client.post('/integrations/facebook', data=raw, content_type='application/json', headers={'X-Hub-Signature-256': sig})
                self.assertEqual(result.status_code, 200)
            self.assertTrue(delivered.wait(2))
            stop.assert_called_once_with(None)
            event['entry'][0]['messaging'][0]['sender']['id'] = '999'
            event['entry'][0]['messaging'][0]['message']['mid'] = 'not-an-owner'
            denied_raw = json.dumps(event).encode()
            denied_sig = 'sha256=' + hmac.new(values['app_secret'].encode(), denied_raw, hashlib.sha256).hexdigest()
            self.client.post('/integrations/facebook', data=denied_raw, content_type='application/json', headers={'X-Hub-Signature-256': denied_sig})
            stop.assert_called_once_with(None)

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
        self.configure('facebook')
        response = self.client.post('/api/miniapp/integrations/disconnect', json={'provider': 'discord'})
        self.assertTrue(response.json['ok'])
        providers = self.client.get('/api/miniapp/integrations').json['integrations']
        status = {item['provider']: item['configured'] for item in providers}
        self.assertEqual(status, {'discord': False, 'facebook': True})


if __name__ == '__main__':
    unittest.main()
