import unittest
from unittest.mock import patch

from services.delivery_sharding import DeliveryShardingPlanner


class _Manager:
    def __init__(self, capacity):
        self.capacity = capacity
        self.submitted = []
        self.jobs = []
    def full_capacity_snapshot(self):
        return self.capacity
    def submit_job(self, command, payload, account_id=None):
        job_id = f'job{len(self.submitted)+1}'
        self.submitted.append((job_id, command, payload, account_id))
        return job_id
    def list_jobs(self, limit=1000, state=None):
        return list(self.jobs)


def _capacity(n_profiles=3, n_groups=30):
    profiles = []
    for i in range(n_profiles):
        profiles.append({
            'id': f'P{i+1}', 'name': f'Profile {i+1}', 'state': 'READY',
            'published_rate': 90-i, 'failed': 0, 'unverified': 0, 'last_activity': '',
        })
    targets = [f'https://www.facebook.com/groups/{i+1}' for i in range(n_groups)]
    return {
        'effective_parallelism': n_profiles,
        'worker_max': n_profiles,
        'profiles_schedulable': n_profiles,
        'groups_eligible': n_groups,
        'profiles': profiles,
        'group_block_reasons': {},
        'group_approved_targets': targets,
        'group_eligible_targets': targets,
    }


def _items(count, campaign='C1'):
    return [
        {
            'id': f'I{i+1}', 'campaign_id': campaign, 'state': 'approved',
            'target': f'https://facebook.com/groups/{i+1}', 'content': f'content {i+1}',
        }
        for i in range(count)
    ]


class DeliveryShardingTests(unittest.TestCase):
    def test_wave_splits_25_into_10_10_5_with_distinct_profiles(self):
        manager = _Manager(_capacity(3, 30))
        with patch('services.delivery_sharding.CampaignRepository.list_queue', return_value=_items(25)):
            plan = DeliveryShardingPlanner(manager).plan('C1', batch_size=10)
        self.assertEqual([s['taskCount'] for s in plan['shards']], [10, 10, 5])
        self.assertEqual(len({s['profileId'] for s in plan['shards']}), 3)
        task_targets = [t['target'] for s in plan['shards'] for t in s['tasks']]
        self.assertEqual(len(task_targets), len(set(task_targets)))
        self.assertEqual(plan['remaining_after_wave'], 0)

    def test_wave_refill_leaves_remaining_approved_items(self):
        manager = _Manager(_capacity(2, 40))
        with patch('services.delivery_sharding.CampaignRepository.list_queue', return_value=_items(35)):
            plan = DeliveryShardingPlanner(manager).plan('C1', batch_size=10)
        self.assertEqual(plan['wave_items'], 20)
        self.assertEqual(plan['remaining_after_wave'], 15)
        self.assertEqual([s['taskCount'] for s in plan['shards']], [10, 10])

    def test_unknown_and_blocked_groups_are_excluded(self):
        cap = _capacity(2, 4)
        cap['group_block_reasons'] = {'https://www.facebook.com/groups/2': 'PENDING_LIMIT'}
        cap['group_eligible_targets'] = ['https://www.facebook.com/groups/1', 'https://www.facebook.com/groups/3']
        items = _items(4) + [{'id':'IX','campaign_id':'C1','state':'approved','target':'https://facebook.com/groups/999','content':'x'}]
        with patch('services.delivery_sharding.CampaignRepository.list_queue', return_value=items):
            plan = DeliveryShardingPlanner(_Manager(cap)).plan('C1', batch_size=10)
        self.assertEqual(plan['eligible_items'], 2)
        reasons = {row['reason'] for row in plan['skipped']}
        self.assertIn('PENDING_LIMIT', reasons)
        self.assertIn('GROUP_NOT_ELIGIBLE', reasons)
        self.assertIn('GROUP_NOT_APPROVED_ACTIVE', reasons)

    def test_batch_size_is_clamped_to_8_12(self):
        manager = _Manager(_capacity(2, 30))
        with patch('services.delivery_sharding.CampaignRepository.list_queue', return_value=_items(20)):
            low = DeliveryShardingPlanner(manager).plan('C1', batch_size=1)
            high = DeliveryShardingPlanner(manager).plan('C1', batch_size=99)
        self.assertEqual(low['batch_size'], 8)
        self.assertEqual(high['batch_size'], 12)

    def test_dispatch_is_idempotent_for_active_shard(self):
        manager = _Manager(_capacity(1, 10))
        items = _items(8)
        planner = DeliveryShardingPlanner(manager)
        with patch('services.delivery_sharding.CampaignRepository.list_queue', return_value=items):
            plan = planner.plan('C1', batch_size=8)
            sid = plan['shards'][0]['shardId']
            manager.jobs = [{'state':'queued','payload':{'shardId':sid}}]
            result = planner.dispatch('C1', batch_size=8)
        self.assertEqual(result['dispatched_shards'], 0)
        self.assertEqual(result['skipped_active_shards'], [sid])
        self.assertEqual(manager.submitted, [])

    def test_inflight_items_and_profiles_are_reserved_before_executor_claim(self):
        manager = _Manager(_capacity(2, 20))
        items = _items(16)
        manager.jobs = [{
            'state':'queued',
            'payload':{
                'shardId':'older-shard',
                'accountIds':['P1'],
                'tasks':[{'queueItemId':f'I{i+1}'} for i in range(8)],
            }
        }]
        with patch('services.delivery_sharding.CampaignRepository.list_queue', return_value=items):
            plan = DeliveryShardingPlanner(manager).plan('C1', batch_size=8)
        self.assertEqual(plan['active_shard_item_ids'], [f'I{i+1}' for i in range(8)])
        self.assertEqual(plan['active_shard_profile_ids'], ['P1'])
        self.assertEqual([s['profileId'] for s in plan['shards']], ['P2'])
        planned_ids = [t['queueItemId'] for s in plan['shards'] for t in s['tasks']]
        self.assertEqual(planned_ids, [f'I{i+1}' for i in range(8,16)])
        reasons = [x['reason'] for x in plan['skipped']]
        self.assertEqual(reasons.count('ALREADY_IN_FLIGHT'), 8)

    def test_dispatch_payload_is_profile_specific(self):
        manager = _Manager(_capacity(2, 20))
        with patch('services.delivery_sharding.CampaignRepository.list_queue', return_value=_items(16)):
            result = DeliveryShardingPlanner(manager).dispatch('C1', batch_size=8, base_payload={'brandKey':'umee'})
        self.assertEqual(result['dispatched_shards'], 2)
        profile_sets = []
        for _, command, payload, account_id in manager.submitted:
            self.assertEqual(command, 'group')
            self.assertEqual(payload['accountIds'], [account_id])
            self.assertTrue(payload['rotateAccounts'])
            self.assertEqual(payload['brandKey'], 'umee')
            self.assertEqual(len(payload['tasks']), 8)
            profile_sets.append(tuple(payload['accountIds']))
        self.assertEqual(len(set(profile_sets)), 2)


if __name__ == '__main__':
    unittest.main()
