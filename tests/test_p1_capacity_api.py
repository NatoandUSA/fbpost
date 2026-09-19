import unittest
from unittest.mock import patch

import server
import api.jobs as jobs_api


class CapacityApiTests(unittest.TestCase):
    def setUp(self):
        server.app.config['TESTING'] = True
        self.client = server.app.test_client()

    def test_capacity_endpoint_exposes_worker_and_profile_capacity(self):
        snapshot = {
            'worker_max': 4, 'worker_active': 2, 'worker_available': 2,
            'queue_depth': 3, 'active_job_ids': ['a', 'b'],
            'profiles_total': 19, 'profiles_reserved': 2, 'profiles_ready': 17,
            'reserved_profile_ids': ['P1', 'P2'],
            'profile_reservations': {'a': ['P1'], 'b': ['P2']},
        }
        with patch.object(jobs_api.job_manager, 'capacity_snapshot', return_value=snapshot):
            res = self.client.get('/api/capacity')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['worker_available'], 2)
        self.assertEqual(data['profiles_ready'], 17)
        self.assertEqual(data['profile_reservations']['a'], ['P1'])


if __name__ == '__main__':
    unittest.main()
