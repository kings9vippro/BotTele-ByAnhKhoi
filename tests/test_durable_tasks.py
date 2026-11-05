import os
import sqlite3
import tempfile
import threading
import time
import unittest
from durable_tasks import TaskQueue, RetryAfter, UncertainDelivery


class DurableTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name,'queue.db')
        self.sent = []
        self.queue = TaskQueue(self.db, lambda *args:self.sent.append(args))
        self.addCleanup(self.queue.close)

    def db(self):
        c=sqlite3.connect(self.path,timeout=10)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL')
        return c

    def test_pause_resume_cancel_and_owner_isolation(self):
        task=self.queue.submit('a','c','hello')
        with self.assertRaises(ValueError): self.queue.control('b',task,'stop')
        self.assertEqual(self.queue.control('a',task,'pause'),'PAUSED')
        self.assertFalse(self.queue.run_one())
        self.queue.control('a',task,'resume')
        self.queue.control('a',task,'stop')
        self.assertFalse(self.queue.run_one())
        self.assertEqual(self.sent,[])

    def test_five_independent_channels_really_execute_concurrently(self):
        barrier=threading.Barrier(5,timeout=3)
        done=threading.Event()
        count=[]
        def send(*args):
            barrier.wait()
            count.append(args)
            if len(count)==5: done.set()
        self.queue.sender=send
        for i in range(5): self.queue.submit('owner',str(i),'notice')
        self.queue.start()
        self.assertTrue(done.wait(5),'Five workers must reach the barrier concurrently')
        self.queue.close()
        self.assertEqual(len(count),5)
        self.assertEqual({t['status'] for t in self.queue.list('owner')},{'COMPLETED'})

    def test_rate_limited_channel_does_not_block_other_channel_or_leak_through(self):
        def send(owner,channel,payload):
            if channel=='slow': raise RetryAfter(30)
            self.sent.append(channel)
        self.queue.sender=send
        self.queue.submit('a','slow','one')
        self.queue.submit('a','slow','two')
        self.queue.submit('a','fast','three')
        self.queue.run_one();self.queue.run_one()
        self.assertEqual(self.sent,['fast'])
        self.assertFalse(self.queue.run_one())

    def test_failure_isolation_and_explicit_retry(self):
        def send(owner,channel,payload):
            if channel=='bad': raise ValueError('secret-provider-response')
            self.sent.append(channel)
        self.queue.sender=send
        bad=self.queue.submit('a','bad','one');self.queue.submit('a','good','two')
        self.queue.run_one();self.queue.run_one()
        self.assertEqual(self.sent,['good'])
        self.assertNotIn('secret-provider-response',str(self.queue.list('a')))
        self.queue.sender=lambda *args:None
        self.queue.control('a',bad,'retry');self.queue.run_one()
        self.assertEqual({t['status'] for t in self.queue.list('a')},{'COMPLETED'})

    def test_restart_does_not_duplicate_uncertain_or_completed_delivery(self):
        first=self.queue.submit('a','c','one');self.queue.run_one()
        second=self.queue.submit('a','c','two');self.queue.claim()
        restored=TaskQueue(self.db,self.queue.sender)
        self.assertFalse(restored.run_one())
        states={t['id']:t['status'] for t in restored.list('a')}
        self.assertEqual(states,{first:'COMPLETED',second:'UNKNOWN'})
        with self.assertRaises(ValueError):restored.control('a',second,'retry')

    def test_backpressure_and_duplicate_channel_claim(self):
        self.queue.limit=2
        self.queue.submit('a','c','one');self.queue.submit('a','c','two')
        with self.assertRaises(ValueError):self.queue.submit('a','d','three')
        self.assertIsNotNone(self.queue.claim())
        self.assertIsNone(self.queue.claim())

    def test_claims_round_robin_between_owners(self):
        for owner, channel in (('alice','a1'), ('alice','a2'), ('bob','b1'), ('bob','b2')):
            self.queue.submit(owner, channel, 'notice')
        claimed=[self.queue.claim()['owner'] for _ in range(4)]
        self.assertEqual(claimed, ['alice','bob','alice','bob'])

    def test_ambiguous_send_is_not_automatically_retried(self):
        def send(*args):raise UncertainDelivery()
        self.queue.sender=send
        self.queue.submit('a','c','one');self.queue.run_one()
        self.assertEqual(self.queue.list('a')[0]['status'],'UNKNOWN')
        self.assertFalse(self.queue.run_one())

    def test_global_limit_survives_cancelling_rate_limited_task(self):
        def send(*args): raise RetryAfter(30, global_limit=True)
        self.queue.sender=send
        task=self.queue.submit('a','first','one');self.queue.run_one()
        self.queue.control('a',task,'stop')
        self.queue.submit('b','second','two')
        self.assertFalse(self.queue.run_one())

    def test_last_retry_still_preserves_channel_limit(self):
        def send(*args): raise RetryAfter(30)
        self.queue.sender=send
        task=self.queue.submit('a','limited','one')
        c=self.db();c.execute('UPDATE notification_tasks SET attempts=7 WHERE id=?',(task,));c.commit();c.close()
        self.queue.run_one()
        self.assertEqual(self.queue.list('a')[0]['status'],'FAILED')
        self.queue.submit('a','limited','two')
        self.assertFalse(self.queue.run_one())

    def test_retry_cannot_bypass_backpressure(self):
        def send(*args): raise ValueError('rejected')
        self.queue.sender=send
        task=self.queue.submit('a','c','one');self.queue.run_one()
        self.queue.limit=1
        self.queue.submit('a','d','two')
        with self.assertRaises(ValueError):self.queue.control('a',task,'retry')

    def test_stop_all_is_owner_scoped_and_persistent(self):
        self.queue.submit_many('a',['1','2'],'hello');self.queue.submit('b','3','keep')
        self.assertEqual(self.queue.stop_all('a'),2)
        restored=TaskQueue(self.db,self.queue.sender)
        self.assertEqual({t['status'] for t in restored.list('a')},{'CANCELLED'})
        self.assertEqual(restored.list('b')[0]['status'],'QUEUED')

    def test_final_database_write_retries_without_resending(self):
        calls=[]
        original_db=self.queue.db
        class FailOnce:
            def __init__(self,connection):self.connection=connection
            def execute(self,sql,*args):
                if sql=='BEGIN IMMEDIATE' and calls and calls[-1]=='sent' and 'failed' not in calls:
                    calls.append('failed');raise sqlite3.OperationalError('temporary lock')
                return self.connection.execute(sql,*args)
            def __getattr__(self,name):return getattr(self.connection,name)
        self.queue.db=lambda:FailOnce(original_db())
        self.queue.sender=lambda *args:calls.append('sent')
        self.queue.submit('a','one','hello')
        self.queue.run_one()
        self.assertEqual(calls.count('sent'),1)
        self.assertEqual(self.queue.list('a')[0]['status'],'COMPLETED')

    def test_stop_race_converts_definitive_failure_to_cancelled(self):
        task = None

        def send(*args):
            # Simulate a stop request arriving while the provider is in flight.
            self.queue.control('a', task, 'stop')
            raise ValueError('provider rejected')

        self.queue.sender = send
        task = self.queue.submit('a', 'c', 'one')
        self.queue.run_one()
        row = self.queue.list('a')[0]
        self.assertEqual(row['status'], 'CANCELLED')
        self.assertEqual(row['completed'] is not None, True)

    def test_shutdown_still_persists_completed_send(self):
        def send(*args):
            # A graceful shutdown may be requested by the sender's owner after
            # the provider has accepted the request.
            self.queue.shutdown_event.set()

        self.queue.sender = send
        self.queue.submit('a', 'c', 'one')
        self.assertTrue(self.queue.run_one())
        self.assertEqual(self.queue.list('a')[0]['status'], 'COMPLETED')
