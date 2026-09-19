import unittest
from unittest.mock import patch

import server


class DeliveryShardingApiTests(unittest.TestCase):
    def setUp(self):
        server.app.config['TESTING'] = True
        self.client = server.app.test_client()
        self.campaign = {'id':'C1','state':'active','brand':'umee'}

    def test_plan_requires_active_campaign(self):
        with patch('api.jobs.CampaignRepository.list_campaigns', return_value=[]):
            res = self.client.post('/api/delivery/shards/plan', json={'campaignId':'missing'})
        self.assertEqual(res.status_code, 404)

    def test_plan_returns_preview(self):
        preview = {'campaign_id':'C1','shards':[],'approved_items':0,'eligible_items':0}
        with patch('api.jobs.CampaignRepository.list_campaigns', return_value=[self.campaign]), \
             patch('api.jobs.DeliveryShardingPlanner.plan', return_value=preview):
            res = self.client.post('/api/delivery/shards/plan', json={'campaignId':'C1','batchSize':10})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

    def test_plan_passes_explicit_queue_item_selector(self):
        preview = {'campaign_id':'C1','shards':[],'approved_items':3,'eligible_items':2}
        captured = {}
        def fake_plan(_self, campaign_id, **kwargs):
            captured.update(kwargs)
            return preview
        with patch('api.jobs.CampaignRepository.list_campaigns', return_value=[self.campaign]), \
             patch('api.jobs.DeliveryShardingPlanner.plan', new=fake_plan):
            res = self.client.post('/api/delivery/shards/plan', json={'campaignId':'C1','queueItemIds':['I2','I1']})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(captured['queue_item_ids'], ['I2','I1'])

    def test_plan_rejects_invalid_queue_item_selector(self):
        with patch('api.jobs.CampaignRepository.list_campaigns', return_value=[self.campaign]):
            res = self.client.post('/api/delivery/shards/plan', json={'campaignId':'C1','queueItemIds':'I1'})
        self.assertEqual(res.status_code, 400)

    def test_dispatch_whitelists_payload_options(self):
        captured = {}
        def fake_dispatch(_self, campaign_id, **kwargs):
            captured.update(kwargs)
            return {'campaign_id':campaign_id,'shards':[],'dispatched_jobs':[],'dispatched_shards':0}
        body = {
            'campaignId':'C1','batchSize':10,'brandKey':'lacasa','autoSpin':True,
            'tasks':[{'target':'evil'}],'accountIds':['evil'],'shardId':'evil','command':'page'
        }
        with patch('api.jobs.CampaignRepository.list_campaigns', return_value=[self.campaign]), \
             patch('api.jobs.DeliveryShardingPlanner.dispatch', new=fake_dispatch):
            res = self.client.post('/api/delivery/shards/dispatch', json=body)
        self.assertEqual(res.status_code, 200)
        base = captured['base_payload']
        self.assertEqual(base['brandKey'], 'lacasa')
        self.assertTrue(base['autoSpin'])
        self.assertNotIn('tasks', base)
        self.assertNotIn('accountIds', base)
        self.assertNotIn('shardId', base)
        self.assertNotIn('command', base)


if __name__ == '__main__':
    unittest.main()
