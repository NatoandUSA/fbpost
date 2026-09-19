import unittest

from services.profile_capacity import ProfileCapacityManager


class ProfileCapacityTests(unittest.TestCase):
    def setUp(self):
        self.accounts = [
            {'id': 'P1', 'type': 'gpm'},
            {'id': 'P2', 'type': 'gpm'},
            {'id': 'P3', 'type': 'gpm'},
        ]
        self.capacity = ProfileCapacityManager(lambda: self.accounts)

    def test_explicit_profiles_can_run_when_disjoint(self):
        self.assertTrue(self.capacity.try_reserve('j1', 'group', {'accountId': 'P1'}))
        self.assertTrue(self.capacity.try_reserve('j2', 'group', {'accountId': 'P2'}))
        snap = self.capacity.snapshot()
        self.assertEqual(snap['profiles_reserved'], 2)
        self.assertEqual(snap['profiles_ready'], 1)

    def test_same_profile_is_rejected_until_release(self):
        self.assertTrue(self.capacity.try_reserve('j1', 'group', {'accountId': 'P1'}))
        self.assertFalse(self.capacity.try_reserve('j2', 'group', {'accountId': 'P1'}))
        self.capacity.release('j1')
        self.assertTrue(self.capacity.try_reserve('j2', 'group', {'accountId': 'P1'}))

    def test_rotate_all_reserves_entire_pool(self):
        self.assertTrue(self.capacity.try_reserve('wide', 'group', {'rotateAccounts': True}))
        self.assertFalse(self.capacity.try_reserve('single', 'group', {'accountId': 'P2'}))
        snap = self.capacity.snapshot()
        self.assertEqual(snap['profiles_reserved'], 3)
        self.assertEqual(snap['profiles_ready'], 0)

    def test_explicit_rotation_subset_only_reserves_subset(self):
        payload = {'rotateAccounts': True, 'accountIds': ['P1', 'P2']}
        self.assertTrue(self.capacity.try_reserve('subset', 'group', payload))
        self.assertTrue(self.capacity.try_reserve('other', 'group', {'accountId': 'P3'}))


if __name__ == '__main__':
    unittest.main()
