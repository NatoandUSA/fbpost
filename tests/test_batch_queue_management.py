import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from db import init_db
from repositories.campaign_repo import CampaignRepository
from services.job_executor import execute_automation_task
import server


class BatchLimitValidationTests(unittest.TestCase):
    def test_post_task_batch_limit_over_999(self):
        lines = []
        def capture(line):
            lines.append(line)

        tasks_1000 = [{'target': f'https://facebook.com/groups/{i}', 'content': 'test'} for i in range(1000)]
        result = execute_automation_task(
            'test-job-1', 'group', {'tasks': tasks_1000},
            on_line=capture, process_runner=MagicMock()
        )
        self.assertFalse(result)
        self.assertTrue(any('Batch must contain between 1 and 999 tasks' in line for line in lines))

    def test_thread_task_batch_limit_over_999(self):
        lines = []
        def capture(line):
            lines.append(line)

        tasks_1000 = [{'target': f'user_{i}', 'content': 'test'} for i in range(1000)]
        result = execute_automation_task(
            'test-job-2', 'thread', {'tasks': tasks_1000},
            on_line=capture, process_runner=MagicMock()
        )
        self.assertFalse(result)
        self.assertTrue(any('Thread batch must contain 1-999 tasks' in line for line in lines))


class CampaignRepoBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'test_app.db'
        self.old_db = os.environ.get('FB_POST_DB_PATH')
        os.environ['FB_POST_DB_PATH'] = str(self.db_path)
        init_db(self.db_path)
        self.repo = CampaignRepository(db_file=str(self.db_path))

    def tearDown(self):
        if self.old_db:
            os.environ['FB_POST_DB_PATH'] = self.old_db
        else:
            os.environ.pop('FB_POST_DB_PATH', None)
        self.tmp.cleanup()

    def test_approve_all_drafts(self):
        item1 = {'id': 'item-10', 'target': 'https://fb.com/groups/10', 'content': 'A', 'state': 'draft'}
        item2 = {'id': 'item-20', 'target': 'https://fb.com/groups/20', 'content': 'B', 'state': 'draft'}
        item3 = {'id': 'item-30', 'target': 'https://fb.com/groups/30', 'content': 'C', 'state': 'manual_review'}
        self.repo.insert_queue_item(item1)
        self.repo.insert_queue_item(item2)
        self.repo.insert_queue_item(item3)

        updated = self.repo.approve_all_drafts()
        self.assertEqual(updated, 2)

        q1 = self.repo.get_queue_item('item-10')
        q2 = self.repo.get_queue_item('item-20')
        q3 = self.repo.get_queue_item('item-30')
        self.assertEqual(q1['state'], 'approved')
        self.assertEqual(q2['state'], 'approved')
        self.assertEqual(q3['state'], 'manual_review')

    def test_cancel_all_queue(self):
        self.repo.insert_queue_item({'id': 'item-11', 'target': 'https://fb.com/groups/11', 'content': 'A', 'state': 'approved'})
        self.repo.insert_queue_item({'id': 'item-12', 'target': 'https://fb.com/groups/12', 'content': 'B', 'state': 'draft'})
        self.repo.insert_queue_item({'id': 'item-13', 'target': 'https://fb.com/groups/13', 'content': 'C', 'state': 'posted'})

        cancelled = self.repo.cancel_all_queue(states=['approved', 'draft'])
        self.assertEqual(cancelled, 2)

        items = self.repo.list_queue()
        for item in items:
            if item['target'] in ('https://fb.com/groups/11', 'https://fb.com/groups/12'):
                self.assertEqual(item['state'], 'cancelled')
            elif item['target'] == 'https://fb.com/groups/13':
                self.assertEqual(item['state'], 'posted')

    def test_delete_queue_items_by_scope(self):
        self.repo.insert_queue_item({'id': 'item-21', 'target': 'https://fb.com/groups/21', 'content': 'A', 'state': 'cancelled'})
        self.repo.insert_queue_item({'id': 'item-22', 'target': 'https://fb.com/groups/22', 'content': 'B', 'state': 'failed'})
        self.repo.insert_queue_item({'id': 'item-23', 'target': 'https://fb.com/groups/23', 'content': 'C', 'state': 'approved'})

        # Delete cancelled and failed
        deleted = self.repo.delete_queue_items(states=['cancelled', 'failed'])
        self.assertEqual(deleted, 2)

        remaining = self.repo.list_queue()
        rem_ids = [x['id'] for x in remaining]
        self.assertNotIn('item-21', rem_ids)
        self.assertNotIn('item-22', rem_ids)
        self.assertIn('item-23', rem_ids)

        # Clear all
        deleted_all = self.repo.delete_queue_items(clear_all=True)
        self.assertEqual(deleted_all, 1)
        self.assertEqual(len(self.repo.list_queue()), 0)


class ServerQueueApiTests(unittest.TestCase):
    def setUp(self):
        server.app.config['TESTING'] = True
        self.client = server.app.test_client()
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'test_app.db'
        self.queue_json = Path(self.tmp.name) / 'publication_queue.json'
        self.old_db = os.environ.get('FB_POST_DB_PATH')
        os.environ['FB_POST_DB_PATH'] = str(self.db_path)
        init_db(self.db_path)

        self.patch_queue = patch.object(server, 'QUEUE_FILE', self.queue_json)
        self.patch_queue.start()

    def tearDown(self):
        self.patch_queue.stop()
        if self.old_db:
            os.environ['FB_POST_DB_PATH'] = self.old_db
        else:
            os.environ.pop('FB_POST_DB_PATH', None)
        self.tmp.cleanup()

    def test_queue_duplicate_prevention(self):
        # First enqueue
        res1 = self.client.post('/api/queue', json={
            'target': 'https://facebook.com/groups/homestay999',
            'content': 'Test duplicate check',
            'mode': 'group'
        })
        self.assertEqual(res1.status_code, 201)

        # Second enqueue with EXACT SAME target and content -> 409 Conflict
        res2 = self.client.post('/api/queue', json={
            'target': 'https://facebook.com/groups/homestay999',
            'content': 'Test duplicate check',
            'mode': 'group'
        })
        self.assertEqual(res2.status_code, 409)
        data = res2.get_json()
        self.assertTrue(data.get('duplicate'))

        # Enqueue with allow_duplicate=True -> 201 Created
        res3 = self.client.post('/api/queue', json={
            'target': 'https://facebook.com/groups/homestay999',
            'content': 'Test duplicate check',
            'mode': 'group',
            'allow_duplicate': True
        })
        self.assertEqual(res3.status_code, 201)

    def test_queue_duplicate_prevention_normalizes_target_url(self):
        res1 = self.client.post('/api/queue', json={
            'target': 'https://www.facebook.com/groups/homestay999/',
            'content': 'Same normalized target',
        })
        self.assertEqual(res1.status_code, 201)
        res2 = self.client.post('/api/queue', json={
            'target': 'https://facebook.com/groups/homestay999?ref=share',
            'content': 'Same normalized target',
        })
        self.assertEqual(res2.status_code, 409)

    def test_approve_all_endpoint(self):
        self.client.post('/api/queue', json={'target': 'https://facebook.com/groups/101', 'content': 'A'})
        self.client.post('/api/queue', json={'target': 'https://facebook.com/groups/102', 'content': 'B'})

        res = self.client.post('/api/queue/approve-all')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('approved'), 2)

    def test_cancel_all_endpoint(self):
        self.client.post('/api/queue', json={'target': 'https://facebook.com/groups/201', 'content': 'A'})
        self.client.post('/api/queue/approve-all')

        res = self.client.post('/api/queue/cancel-all', json={'states': ['approved']})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('cancelled'), 1)

    def test_cancel_all_rejects_unsafe_states(self):
        for states in (['processing'], ['published'], 'approved'):
            res = self.client.post('/api/queue/cancel-all', json={'states': states})
            self.assertEqual(res.status_code, 400)

    def test_clear_endpoint_with_scopes(self):
        self.client.post('/api/queue', json={'target': 'https://facebook.com/groups/301', 'content': 'A'})
        self.client.post('/api/queue/approve-all')
        self.client.post('/api/queue/cancel-all', json={'states': ['approved']})

        # Clear cancelled
        res = self.client.post('/api/queue/clear', json={'scope': 'cancelled_or_failed'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('deleted'), 1)

        # Invalid scope returns 400 Bad Request
        res_invalid = self.client.post('/api/queue/clear', json={'scope': 'invalid_scope'})
        self.assertEqual(res_invalid.status_code, 400)

        # Missing scope returns 400 Bad Request
        res_empty = self.client.post('/api/queue/clear', json={})
        self.assertEqual(res_empty.status_code, 400)

    def test_queue_dates_endpoint(self):
        self.client.post('/api/queue', json={'target': 'https://facebook.com/groups/401', 'content': 'A'})
        res = self.client.get('/api/queue/dates')
        self.assertEqual(res.status_code, 200)
        dates = res.get_json()
        self.assertIsInstance(dates, list)
        self.assertGreaterEqual(len(dates), 1)

    def test_queue_date_filters_require_iso_dates(self):
        self.assertEqual(self.client.get('/api/queue?date=12-09-2026').status_code, 400)
        self.assertEqual(self.client.get('/api/queue-summary?date=bad').status_code, 400)
        self.assertEqual(self.client.post('/api/queue/clear', json={'scope': 'date'}).status_code, 400)
        self.assertEqual(self.client.post('/api/queue/clear', json={
            'scope': 'date', 'date_from': '2026-09-13', 'date_to': '2026-09-12'
        }).status_code, 400)


if __name__ == '__main__':
    unittest.main()
