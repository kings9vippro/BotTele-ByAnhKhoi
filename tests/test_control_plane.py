import json
import tempfile
import sqlite3
import os
import unittest
from unittest.mock import patch,MagicMock
from flask import Flask
import control_plane


class ControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=os.path.join(self.temp.name,'test.db')
        self.app=Flask(__name__);self.app.secret_key='test-secret'
        self.owner='alice'
        self.env=patch.dict(os.environ,{'SECRET_KEY':'test-secret','DISABLE_BACKGROUND_WORKERS':'1'})
        self.env.start();self.addCleanup(self.env.stop)
        control_plane.register(self.app,self.db,lambda:self.owner)
        self.queue=self.app.extensions['notification_queue'];self.addCleanup(self.queue.close)
        self.client=self.app.test_client()

    def db(self):
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;return c

    def add_channel(self):
        response=MagicMock(status_code=200);response.__enter__.return_value=response
        response.json.return_value={'id':'123','type':1,'name':'Team'}
        with patch.object(control_plane.requests,'get',return_value=response):
            result=self.client.post('/api/miniapp/channels',json={'url':'https://discord.com/api/webhooks/123/secret-test'})
        self.assertEqual(result.status_code,200)

    def test_webhook_is_encrypted_and_owner_scoped(self):
        self.add_channel()
        c=self.db();stored=c.execute('SELECT secret FROM webhook_channels').fetchone()[0];c.close()
        self.assertNotIn('secret-test',stored)
        data=self.client.get('/api/miniapp/control').json
        self.assertNotIn('secret-test',json.dumps(data))
        self.assertEqual(len(data['channels']),1)
        self.owner='bob'
        self.assertEqual(self.client.get('/api/miniapp/control').json['channels'],[])
        self.assertEqual(self.client.post('/api/miniapp/notifications',json={'channels':['123'],'content':'hello'}).status_code,400)

    def test_submission_control_and_incremental_events(self):
        self.add_channel()
        result=self.client.post('/api/miniapp/notifications',json={'channels':['123'],'content':'hello'})
        self.assertEqual(result.status_code,202)
        task=result.json['ids'][0]
        self.assertEqual(self.client.post('/api/miniapp/notification_control',json={'id':task,'action':'pause'}).json['status'],'PAUSED')
        data=self.client.get('/api/miniapp/control').json
        self.assertEqual([e['status'] for e in data['events']],['QUEUED','PAUSED'])
        self.assertEqual(self.client.get('/api/miniapp/control?cursor='+str(data['cursor'])).json['events'],[])
        self.owner='bob'
        self.assertEqual(self.client.post('/api/miniapp/notification_control',json={'id':task,'action':'stop'}).status_code,409)

    def test_invalid_urls_never_trigger_network(self):
        with patch.object(control_plane.requests,'get') as get:
            for url in ['http://localhost','https://discord.com.evil.test/api/webhooks/1/token','https://discord.com/api/webhooks/1/token?redirect=evil','https://discord.com/api/webhooks/1/token/../../other']:
                self.assertEqual(self.client.post('/api/miniapp/channels',json={'url':url}).status_code,400)
            get.assert_not_called()

    def test_bad_channel_types_are_rejected(self):
        self.assertEqual(self.client.post('/api/miniapp/notifications',json={'channels':[{}],'content':'hello'}).status_code,400)

    def test_batch_capacity_is_atomic(self):
        self.queue.limit=1
        with self.assertRaises(ValueError):self.queue.submit_many('a',['1','2'],'hello')
        self.assertEqual(self.queue.list('a'),[])

    def test_lost_event_window_signals_resync(self):
        self.queue.submit('alice','one','fixture')
        self.queue.submit('alice','two','fixture')
        c=self.db();c.execute('DELETE FROM notification_events WHERE seq=(SELECT MIN(seq) FROM notification_events)');c.commit();c.close()
        snapshot=self.client.get('/api/miniapp/control?cursor=0').json
        self.assertFalse(snapshot['reset'])
        # A returning client at a deleted cursor must rebuild its timeline.
        c=self.db();c.execute('UPDATE notification_events SET seq=seq+10');c.commit();c.close()
        gap=self.client.get('/api/miniapp/control?cursor=1').json
        self.assertTrue(gap['reset'])
        self.assertEqual(len(gap['events']),1)
