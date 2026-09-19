import unittest
from unittest.mock import patch

from services.capacity_intelligence import CapacityIntelligence


class _Capacity:
    def snapshot(self):
        return {'reserved_profile_ids': ['P2']}


class CapacityIntelligenceTests(unittest.TestCase):
    def test_profile_states_and_group_eligibility(self):
        accounts = [
            {'id':'P1','name':'Good','status':'Sẵn sàng (Facebook GPM)'},
            {'id':'P2','name':'Busy','status':'Sẵn sàng (Facebook GPM)'},
            {'id':'P3','name':'Weak','status':'Sẵn sàng (Facebook GPM)'},
            {'id':'P4','name':'Auth','status':'Login required'},
        ]
        perf = [
            {'profile_id':'P1','published':8,'pending':1,'unverified':1,'failed':0,'membership_unverified':0,'published_rate':80.0,'avg_seconds':120.0,'last_activity':'2026-09-19T10:00:00+00:00'},
            {'profile_id':'P2','published':6,'pending':1,'unverified':1,'failed':0,'membership_unverified':0,'published_rate':75.0,'avg_seconds':150.0,'last_activity':'2026-09-19T10:00:00+00:00'},
            {'profile_id':'P3','published':1,'pending':1,'unverified':10,'failed':0,'membership_unverified':0,'published_rate':8.3,'avg_seconds':180.0,'last_activity':'2026-09-19T10:00:00+00:00'},
        ]
        groups = [
            {'url':'https://facebook.com/groups/1','status':'approved','is_active':True},
            {'url':'https://facebook.com/groups/2','status':'approved','is_active':True},
            {'url':'https://facebook.com/groups/3','status':'approved','is_active':True},
            {'url':'https://facebook.com/groups/4','status':'paused','is_active':True},
        ]
        moderated = [
            {'group_url':'https://www.facebook.com/groups/2','pending_count':2,'skip_threshold':2},
        ]
        posted = []
        with patch('services.capacity_intelligence.AccountRepository.list_accounts', return_value=accounts), \
             patch('services.capacity_intelligence.WorkflowRepository.profile_posting_performance', return_value=perf), \
             patch('services.capacity_intelligence.GroupRepository.list_groups', return_value=groups), \
             patch('services.capacity_intelligence.ModerationRepository.list_moderated_groups', return_value=moderated), \
             patch('services.capacity_intelligence.ActivityRepository.list_posted_links', return_value=posted):
            data = CapacityIntelligence(_Capacity()).snapshot({'worker_max': 4})
        self.assertEqual(data['READY'], 1)
        self.assertEqual(data['BUSY'], 1)
        self.assertEqual(data['DEGRADED'], 1)
        self.assertEqual(data['AUTH_REQUIRED'], 1)
        self.assertEqual(data['groups_approved_active'], 3)
        self.assertEqual(data['groups_pending_blocked'], 1)
        self.assertEqual(data['groups_eligible'], 2)
        self.assertEqual(data['profiles_schedulable'], 2)
        self.assertEqual(data['effective_parallelism'], 2)
        self.assertGreater(data['estimated_tasks_per_hour'], 0)

    def test_recent_post_blocks_group(self):
        groups = [{'url':'https://facebook.com/groups/1','status':'approved','is_active':True}]
        posted = [{'target':'https://facebook.com/groups/1','publish_state':'published','created_at':'2999-01-01 00:00:00'}]
        with patch('services.capacity_intelligence.AccountRepository.list_accounts', return_value=[]), \
             patch('services.capacity_intelligence.WorkflowRepository.profile_posting_performance', return_value=[]), \
             patch('services.capacity_intelligence.GroupRepository.list_groups', return_value=groups), \
             patch('services.capacity_intelligence.ModerationRepository.list_moderated_groups', return_value=[]), \
             patch('services.capacity_intelligence.ActivityRepository.list_posted_links', return_value=posted):
            data = CapacityIntelligence(_Capacity()).snapshot({'worker_max': 4})
        self.assertEqual(data['groups_recent_blocked'], 1)
        self.assertEqual(data['groups_eligible'], 0)


if __name__ == '__main__':
    unittest.main()
