"""V8: per-cookie task and box isolation, Telegram pagination, and command lanes.

All fixtures are synthetic. No Zalo or Telegram API calls are performed.
"""
import os
import threading
import unittest
from unittest.mock import Mock,patch

os.environ.setdefault('DISABLE_TELEGRAM_BOT','1')
os.environ.setdefault('DISABLE_BACKGROUND_WORKERS','1')
os.environ.setdefault('SECRET_KEY','v8-test')
import app
import get_ck_im_zalo as bot_module
from account_views import groups_for_account, paginate, task_belongs_to_account
from control_plane import telegram_command
from task_control import task_snapshots
from task_registry import aggregate_tasks


def account(i,uid):
    return {'id':i,'uid':uid,'imei':'fixture-imei-'+str(i),
            'name':'Cookie '+str(i),'platform':'zalo','enabled':1,
            'cookies':{'fixture':'not-a-real-cookie'},
            'user_agent':'fixture','zpw_enk':''}


class V8Isolation(unittest.TestCase):
    def test_two_cookies_share_group_id_without_mixing_names(self):
        a,b=account(7,'uid7'),account(8,'uid8')
        cache={'uid7':{'data':[{'id':'100','name':'Box A'}]},
               'uid8':{'data':[{'id':'100','name':'Box B'}]}}
        known={'uid7':{'100','201'},'uid8':{'100','301'}}
        rows_a=groups_for_account(a,cache,known)
        rows_b=groups_for_account(b,cache,known)
        self.assertEqual(set(r['id'] for r in rows_a),{'100','201'})
        self.assertEqual(set(r['id'] for r in rows_b),{'100','301'})
        self.assertEqual([r['name'] for r in rows_a if r['id']=='100'],['Box A'])
        self.assertEqual([r['name'] for r in rows_b if r['id']=='100'],['Box B'])

    def test_twelve_per_page_in_telegram_with_last_page(self):
        rows=[{'id':str(x),'name':'Box '+str(x)} for x in range(29)]
        self.assertEqual(paginate(rows,1)['total_pages'],3)
        self.assertEqual(len(paginate(rows,2)['rows']),12)
        self.assertEqual(len(paginate(rows,3)['rows']),5)
        with self.assertRaises(ValueError):paginate(rows,4)

    def test_telegram_page_buttons_use_only_selected_cookie(self):
        acc=account(7,'uid7')
        fake_groups=[{'id':str(i),'name':'My group '+str(i)} for i in range(28)]
        bot=Mock()
        with patch.object(bot_module,'get_user_visible_accounts',return_value=[acc]),patch.dict(
            app.Zalo._GROUPS_CACHE, {'uid7':{'data':fake_groups}},clear=True
        ),patch.dict(app.KNOWN_GROUPS_BY_ACC,{'uid7':set()},clear=True):
            self.assertTrue(telegram_command(bot,'321','chat','dsbox','7 2'))
        text=bot.send_text.call_args.args[1]
        self.assertIn('Trang 2/3',text)
        self.assertIn('Cookie 7',text)
        keyboard=bot.send_text.call_args.kwargs['reply_markup']['inline_keyboard']
        ids=[button['callback_data'] for row in keyboard for button in row]
        self.assertEqual(set(ids),{'v8:dsbox:7:1','v8:dsbox:7:3'})

    def test_telegram_forbids_unowned_cookie(self):
        bot=Mock()
        with patch.object(bot_module,'get_user_visible_accounts',return_value=[account(7,'uid7')]):
            telegram_command(bot,'321','chat','dsbox','8 1')
        self.assertIn('không thuộc quyền',bot.send_text.call_args.args[1])
        self.assertNotIn('cookie',bot.send_text.call_args.args[1].lower())

    def test_task_snapshots_preserve_owning_cookie(self):
        saved={
            't7':{'meta':{'account_ids':[7],'targets':['A']},'started_at':10,'status':'running'},
            't8':{'meta':{'account_ids':[8],'targets':['B']},'started_at':11,'status':'running'}
        }
        active={
            't7':{'stop':threading.Event(),'acc_id':7,'started_at':10},
            't8':{'stop':threading.Event(),'acc_id':8,'started_at':11},
        }
        rows=task_snapshots(active,saved,[account(7,'uid7'),account(8,'uid8')],threading.RLock())
        self.assertEqual({r['id']:r['account_ids'] for r in rows},{'t7':['7'],'t8':['8']})
        self.assertTrue(task_belongs_to_account(rows[0],rows[0]['account_ids'][0]))
        self.assertFalse(task_belongs_to_account(rows[0],'999'))

    def test_account_pagination_happens_before_snapshot_limit(self):
        # A noisy cookie must not hide recent tasks belonging to another cookie.
        saved={}
        for i in range(140):
            saved['a'+str(i)]={'meta':{'account_ids':[7]},'started_at':1000+i,'status':'stopped'}
        for i in range(120):
            saved['b'+str(i)]={'meta':{'account_ids':[8]},'started_at':100+i,'status':'stopped'}
        rows=task_snapshots({},saved,[],threading.RLock(),account_id='8')
        self.assertEqual(len(rows),100)
        self.assertTrue(all(row['account_ids']==['8'] for row in rows))

    def test_shared_execution_does_not_offer_single_cookie_stop(self):
        legacy={'id':'shared','mode':'zalo','status':'running',
                'account_ids':['7','8'],'can_stop':True}
        tasks=aggregate_tasks([], [legacy],owner='321',include_legacy=True)
        self.assertTrue(tasks[0]['shared_execution'])
        self.assertEqual(tasks[0]['actions'],[])

    def test_registry_api_rejects_unknown_cookie(self):
        client=app.app.test_client()
        with client.session_transaction() as session:session['logged_in']=True
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            bot_module,'get_user_visible_accounts',return_value=[account(7,'uid7')]
        ):
            response=client.get('/api/miniapp/task_registry?account_id=8')
        self.assertEqual(response.status_code,403)

    def test_registry_api_only_returns_selected_cookie(self):
        client=app.app.test_client()
        with client.session_transaction() as session:session['logged_in']=True
        fixtures=[{'id':'t7','mode':'Zalo','status':'running','account_ids':['7'],'can_stop':True},
                  {'id':'t8','mode':'Zalo','status':'running','account_ids':['8'],'can_stop':True}]
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            bot_module,'get_user_visible_accounts',return_value=[account(7,'uid7'),account(8,'uid8')]
        ),patch.object(app,'task_snapshots',return_value=fixtures):
            response=client.get('/api/miniapp/task_registry?account_id=7')
        self.assertEqual(response.status_code,200)
        self.assertEqual([t['id'] for t in response.json['tasks']],['legacy:t7'])

    def test_tasks_command_isolates_cookie(self):
        records=[{'id':'legacy:t7','source_id':'t7','platform':'zalo','account_ids':['7'],
                  'status':'RUNNING','persistence':'process_local','actions':[], 'execution_source':'legacy_process'},
                 {'id':'legacy:t8','source_id':'t8','platform':'zalo','account_ids':['8'],
                  'status':'RUNNING','persistence':'process_local','actions':[], 'execution_source':'legacy_process'}]
        bot=Mock()
        with patch.dict(os.environ,{'TELEGRAM_ADMIN_ID':'321'}),patch.object(
            bot_module,'get_user_visible_accounts',return_value=[account(7,'uid7')]
        ),patch.dict(app.app.extensions,{'unified_tasks':Mock(side_effect=lambda user,account_id=None:
                    [r for r in records if account_id in r['account_ids']] if account_id else records)}):
            self.assertTrue(telegram_command(bot,'321','chat','tasks','7'))
        result=bot.send_text.call_args.args[1]
        self.assertIn('legacy:t7',result)
        self.assertNotIn('legacy:t8',result)

    def test_interactive_inputs_do_not_run_in_poll_pool(self):
        self.assertIs(app._zalo_input_executor('.menu'),app._INTERACTIVE_INPUT_EXECUTOR)
        self.assertIs(app._zalo_input_executor('.dsbox 2'),app._INTERACTIVE_INPUT_EXECUTOR)
        self.assertIsNot(app._zalo_input_executor('.menu'),app._SHARED_ZALO_POLLER_POOL)

    def test_full_poll_queue_returns_false_at_capacity(self):
        with patch.object(app,'_ZALO_POLL_SLOTS',threading.BoundedSemaphore(0)):
            self.assertFalse(app._submit_zalo_background_poll(lambda:None))

if __name__=='__main__':unittest.main()