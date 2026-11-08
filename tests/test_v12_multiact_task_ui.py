"""V12 synthetic regression tests for many Zalo cookies and per-account task controls.

No real Zalo cookies, credentials, Telegram messages, or network provider calls.
"""
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault('DISABLE_TELEGRAM_BOT', '1')
os.environ.setdefault('DISABLE_BACKGROUND_WORKERS', '1')
os.environ.setdefault('SECRET_KEY', 'v12-test')
import app
import get_ck_im_zalo as botmod
from control_plane import telegram_command


def account(aid, imei, uid=""):
    return {'id': aid, 'imei': imei, 'uid': uid, 'chat_cmd_enabled': 1,
            'name': 'Zalo Profile '+str(aid), 'platform':'zalo',
            'enabled':1, 'owner_tg_id':'321'}


class PlanTests(unittest.TestCase):
    def test_two_distinct_sessions_survive_duplicate_uid_hint(self):
        ordered, skipped = app._plan_zalo_listener_rows([
            account(1, 'device-A', 'stale-hint'),
            account(2, 'device-B', 'stale-hint'),
        ])
        self.assertEqual(ordered, [1, 2])
        self.assertEqual(skipped, {})

    def test_duplicate_imei_is_explicit_and_not_started_twice(self):
        ordered, skipped = app._plan_zalo_listener_rows([
            account(1, 'same-device','1'),
            account(2, 'same-device','2'),
            account(3, 'different-device','3'),
        ])
        self.assertEqual(ordered, [1, 3])
        self.assertEqual(skipped, {2:1})

    def test_disabled_account_not_started(self):
        rows = [account(1,'first'),account(2,'second')]
        rows[0]['chat_cmd_enabled']=0
        self.assertEqual(app._plan_zalo_listener_rows(rows),([2],{}))

    def test_failure_in_first_account_does_not_skip_second(self):
        rows=[account(1,'A'),account(2,'B')]
        class FakeConn:
            def execute(self,*args): return self
            def fetchall(self):return rows
            def close(self):pass
        live={}
        failures={}
        good=Mock()
        good.thread.is_alive.return_value=True
        good.poller_thread.is_alive.return_value=True
        good.stop_ev.is_set.return_value=False
        def make(aid):
            if aid==1: raise RuntimeError("synthetic")
            return good
        with patch.object(app,'db',return_value=FakeConn()),patch.object(
            app,'refresh_accounts_ram_cache'),patch.object(app,'refresh_owner_uids'),patch.object(
            app,'ZaloRealtimeListener',side_effect=make),patch.object(
            app,'ACTIVE_LISTENERS',live),patch.object(app,'_ZALO_LISTENER_FAILURES',failures):
            app._sync_all_zalo_listeners_locked()
        self.assertIn(2,live)
        self.assertEqual(good.start.call_count,1)
        self.assertEqual(failures[1]['code'],'listener_start_failed')

    def test_status_does_not_leak_cookie(self):
        with patch.object(app,'ACTIVE_LISTENERS',{}),patch.object(
            app,'_ZALO_LISTENER_FAILURES',{7:{'code':'duplicate_imei','conflicting_acc_id':2}}):
            self.assertEqual(app.zalo_listener_status(7),{
                'code':'duplicate_imei','conflicting_acc_id':2})


class AccountImportSessions(unittest.TestCase):
    def setUp(self):
        from test_data_consistency import DataConsistencyTests
        DataConsistencyTests.setUp(self)

    def test_same_owner_different_imei_keeps_two_account_records(self):
        import get_ck_im_zalo as telegram
        from types import SimpleNamespace
        with patch.object(telegram.ZaloPCSessionKeeper,'register_and_keep_alive'), patch.object(
            app.ZaloCookieVaultEngine,'save_zalo_vault_record'),patch.object(
            app,'add_authorized_user'),patch.object(app,'refresh_owner_uids'),patch.object(
            app,'sync_all_zalo_listeners'),patch.object(
            telegram.threading,'Thread'),patch.object(
            app.Zalo,'get_pooled_client',return_value=SimpleNamespace(uid='90000123',secret_key='fixture')):
            first=telegram.sync_zalo_account_to_web_db(
                '90000123','First','imei-first',{'zpsid':'fake-a'},
                zpw_enk='fixture',owner_tg_id='321')
            second=telegram.sync_zalo_account_to_web_db(
                '90000123','Second','imei-second',{'zpsid':'fake-b'},
                zpw_enk='fixture',owner_tg_id='321')
            overwritten=telegram.sync_zalo_account_to_web_db(
                '90000123','Intruder','imei-third',{'zpsid':'fake-c'},
                zpw_enk='fixture',owner_tg_id='other-user')
        self.assertNotEqual(first,second)
        self.assertIsNone(overwritten)
        rows=app.db().execute(
            "SELECT id,name,imei,owner_tg_id FROM accounts WHERE platform='zalo' ORDER BY id").fetchall()
        self.assertEqual(len(rows),2)
        self.assertEqual([r['imei'] for r in rows],['imei-first','imei-second'])
        self.assertEqual({r['owner_tg_id'] for r in rows},{'321'})

class TelegramTaskAccountTests(unittest.TestCase):
    def setUp(self):
        self.bot=Mock()
        self.records=[
            {'id':f'legacy:t{i}', 'source_id':f't{i}', 'account_ids':['2'],
             'status':'RUNNING', 'persistence':'process_local', 'platform':'zalo',
             'actions':[], 'execution_source':'legacy_process'}
            for i in range(25)]
        self.ext={'unified_tasks': lambda _user, account_id=None:
                  [t for t in self.records if account_id in t['account_ids']]
                  if account_id else list(self.records)}
        self.accounts=[account(2,'devB')]
    def test_root_can_select_account_by_number(self):
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            botmod,'get_user_visible_accounts',return_value=self.accounts),patch.object(
            app,'zalo_listener_status',return_value={'code':'running'}),patch.dict(
            app.app.extensions,self.ext):
            self.assertTrue(telegram_command(self.bot,'321','321','task_accounts',''))
        response=self.bot.send_text.call_args.args[1]
        self.assertIn('Zalo Profile 2',response)
        self.assertIn('25 task',response)
        buttons=self.bot.send_text.call_args.kwargs['reply_markup']['inline_keyboard']
        callbacks=[b['callback_data'] for row in buttons for b in row]
        self.assertIn('v12:tasks:2:1',callbacks)

    def test_tasks_pagination_preserves_account_scope(self):
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            botmod,'get_user_visible_accounts',return_value=self.accounts),patch.dict(
            app.app.extensions,self.ext):
            telegram_command(self.bot,'321','321','tasks','2 2')
        msg=self.bot.send_text.call_args.args[1]
        self.assertIn('Trang 2/3',msg)
        self.assertIn('legacy:t15',msg)
        self.assertNotIn('legacy:t1 ·',msg)
        callbacks=[b['callback_data'] for row in self.bot.send_text.call_args.kwargs[
            'reply_markup']['inline_keyboard'] for b in row]
        self.assertIn('v12:tasks:2:3',callbacks)

    def test_internal_account_alias_filters_same_task_owner(self):
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            botmod,'get_user_visible_accounts',return_value=self.accounts),patch.dict(
            app.app.extensions,self.ext):
            telegram_command(self.bot,'321','321','tasks','ACC-2 2')
        self.assertIn('Trang 2/3',self.bot.send_text.call_args.args[1])
        self.assertIn('Zalo Profile 2',self.bot.send_text.call_args.args[1])

    def test_root_all_tasks_page_two(self):
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.dict(
            app.app.extensions,self.ext):
            telegram_command(self.bot,'321','321','tasks','all 2')
        self.assertIn('Trang 2/3',self.bot.send_text.call_args.args[1])

    def test_unauthorized_account_not_visible(self):
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            botmod,'get_user_visible_accounts',return_value=self.accounts),patch.dict(
            app.app.extensions,self.ext):
            telegram_command(self.bot,'321','321','tasks','8')
        self.assertIn('không thuộc quyền',self.bot.send_text.call_args.args[1])

    def test_secondary_account_with_no_tasks_still_listed(self):
        accs=[account(1,'A'),account(2,'B')]
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            botmod,'get_user_visible_accounts',return_value=accs),patch.object(
            app,'zalo_listener_status',return_value={'code':'not_started'}),patch.dict(
            app.app.extensions,self.ext):
            telegram_command(self.bot,'321','321','task_accounts','1')
        body=self.bot.send_text.call_args.args[1]
        self.assertIn('Zalo Profile 1',body)
        self.assertIn('0 task',body)


class ProtectedQRReceipt(unittest.TestCase):
    def test_receipt_document_api_protects_content(self):
        from get_ck_im_zalo import DirectTelegramBotRunner
        bot=object.__new__(DirectTelegramBotRunner)
        bot.api_call=Mock(return_value={'ok':True})
        bot.send_doc_bytes('123',b'ACC-1 (NO COOKIE)','receipt.txt',
                           protect_content=True)
        args=bot.api_call.call_args
        self.assertEqual(args.args[0],'sendDocument')
        self.assertTrue(args.kwargs['data']['protect_content'])
        self.assertNotIn(b'cookie-secret',str(args.kwargs['files']).encode())

class MobileAndQRContracts(unittest.TestCase):
    def test_equal_svg_navigation_icons(self):
        root=Path(__file__).resolve().parents[1]
        js=(root/'static/control.js').read_text()
        self.assertIn("document.createElementNS(ns,'svg')",js)
        self.assertIn("setAttribute('width','24')",js)
        css=(root/'static/v11.css').read_text()
        self.assertIn('grid-template-columns:repeat(5,minmax(0,1fr))',css)

    def test_qr_imei_and_account_ref_without_auto_cookie_forward(self):
        bot=(Path(__file__).resolve().parents[1]/'get_ck_im_zalo.py').read_text()
        self.assertIn('IMEI đầy đủ:',bot)
        self.assertIn('ACC-{acc_id}',bot)
        self.assertIn('_is_private_owner_chat',bot)


if __name__ == '__main__':
    unittest.main()