import unittest
from unittest.mock import patch

import server
import api.jobs as jobs_api


class AutoRefillApiTests(unittest.TestCase):
    def setUp(self):
        server.app.config['TESTING'] = True
        self.client = server.app.test_client()

    def test_status_endpoint(self):
        status = {'enabled':False,'interval_seconds':15,'queue_multiplier':1,'last_tick_at':None,'last_error':None,'last_result':None}
        with patch.object(jobs_api.auto_refill_controller, 'status', return_value=status):
            res = self.client.get('/api/delivery/refill/status')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()['enabled'])

    def test_tick_endpoint(self):
        result = {'decision':'WAIT','reason':'BACKPRESSURE_LIMIT_REACHED','budget':0,'dispatched_shards':0}
        with patch.object(jobs_api.auto_refill_controller, 'tick', return_value=result) as tick:
            res = self.client.post('/api/delivery/refill/tick', json={'batchSize':9})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['decision'], 'WAIT')
        tick.assert_called_once_with(batch_size=9)

    def test_start_stop_endpoints(self):
        status = {'enabled':True,'interval_seconds':15,'queue_multiplier':1,'last_tick_at':None,'last_error':None,'last_result':None}
        with patch.object(jobs_api.auto_refill_controller, 'start', return_value=True), \
             patch.object(jobs_api.auto_refill_controller, 'status', return_value=status):
            res = self.client.post('/api/delivery/refill/start')
        self.assertTrue(res.get_json()['started'])
        status2 = {**status, 'enabled':False}
        with patch.object(jobs_api.auto_refill_controller, 'stop', return_value=True), \
             patch.object(jobs_api.auto_refill_controller, 'status', return_value=status2):
            res = self.client.post('/api/delivery/refill/stop')
        self.assertTrue(res.get_json()['stopped'])
        self.assertFalse(res.get_json()['enabled'])


if __name__ == '__main__':
    unittest.main()
