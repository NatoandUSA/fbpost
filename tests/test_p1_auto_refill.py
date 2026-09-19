import unittest
from unittest.mock import patch

from services.auto_refill import AutoRefillController


class _Manager:
    def __init__(self, capacity):
        self.capacity = dict(capacity)
    def full_capacity_snapshot(self):
        return dict(self.capacity)


class AutoRefillTests(unittest.TestCase):
    def _capacity(self, worker_max=4, worker_active=0, queue_depth=0):
        return {
            'worker_max': worker_max,
            'worker_active': worker_active,
            'queue_depth': queue_depth,
        }

    def test_drained_when_no_active_campaign_has_approved_items(self):
        ctl = AutoRefillController(_Manager(self._capacity()), interval_seconds=5)
        with patch('services.auto_refill.CampaignRepository.list_campaigns', return_value=[]), \
             patch('services.auto_refill.CampaignRepository.list_queue', return_value=[]):
            result = ctl.tick()
        self.assertEqual(result['decision'], 'DRAINED')
        self.assertEqual(result['dispatched_shards'], 0)

    def test_wait_when_backpressure_budget_is_full(self):
        ctl = AutoRefillController(_Manager(self._capacity(worker_max=4, worker_active=4, queue_depth=0)), interval_seconds=5)
        campaigns = [{'id':'C1','state':'active','name':'One'}]
        queue = [{'id':'I1','campaign_id':'C1','state':'approved'}]
        with patch('services.auto_refill.CampaignRepository.list_campaigns', return_value=campaigns), \
             patch('services.auto_refill.CampaignRepository.list_queue', return_value=queue):
            result = ctl.tick()
        self.assertEqual(result['decision'], 'WAIT')
        self.assertEqual(result['budget'], 0)

    def test_refill_respects_global_budget_across_campaigns(self):
        ctl = AutoRefillController(_Manager(self._capacity(worker_max=3, worker_active=1, queue_depth=0)), interval_seconds=5)
        campaigns = [
            {'id':'C1','state':'active','name':'One','brand':'umee'},
            {'id':'C2','state':'active','name':'Two','brand':'lacasa'},
        ]
        queue = [
            {'id':'I1','campaign_id':'C1','state':'approved'},
            {'id':'I2','campaign_id':'C2','state':'approved'},
        ]
        calls = []
        def fake_dispatch(_self, campaign_id, **kwargs):
            calls.append((campaign_id, kwargs['max_shards']))
            count = 1
            return {'dispatched_shards':count,'remaining_after_wave':0,'dispatched_jobs':[{'job_id':f'J{campaign_id}'}], 'approved_items':1,'eligible_items':1,'skipped':[]}
        with patch('services.auto_refill.CampaignRepository.list_campaigns', return_value=campaigns), \
             patch('services.auto_refill.CampaignRepository.list_queue', return_value=queue), \
             patch('services.auto_refill.DeliveryShardingPlanner.dispatch', new=fake_dispatch):
            result = ctl.tick()
        self.assertEqual(result['decision'], 'REFILL')
        self.assertEqual(result['budget'], 2)
        self.assertEqual(result['dispatched_shards'], 2)
        self.assertEqual(calls, [('C1', 2), ('C2', 1)])

    def test_blocked_when_campaign_exists_but_no_eligible_shards(self):
        ctl = AutoRefillController(_Manager(self._capacity()), interval_seconds=5)
        campaigns = [{'id':'C1','state':'active','name':'One'}]
        queue = [{'id':'I1','campaign_id':'C1','state':'approved'}]
        blocked = {'dispatched_shards':0,'approved_items':1,'eligible_items':0,'skipped':[{'id':'I1','reason':'RECENT_POST'}], 'dispatched_jobs':[]}
        with patch('services.auto_refill.CampaignRepository.list_campaigns', return_value=campaigns), \
             patch('services.auto_refill.CampaignRepository.list_queue', return_value=queue), \
             patch('services.auto_refill.DeliveryShardingPlanner.dispatch', return_value=blocked):
            result = ctl.tick()
        self.assertEqual(result['decision'], 'BLOCKED')
        self.assertEqual(result['dispatched_shards'], 0)
        self.assertEqual(result['blocked'][0]['eligible_items'], 0)

    def test_paused_campaign_is_not_considered(self):
        ctl = AutoRefillController(_Manager(self._capacity()), interval_seconds=5)
        campaigns = [{'id':'C1','state':'paused','name':'Paused'}]
        queue = [{'id':'I1','campaign_id':'C1','state':'approved'}]
        with patch('services.auto_refill.CampaignRepository.list_campaigns', return_value=campaigns), \
             patch('services.auto_refill.CampaignRepository.list_queue', return_value=queue):
            result = ctl.tick()
        self.assertEqual(result['decision'], 'DRAINED')


if __name__ == '__main__':
    unittest.main()
