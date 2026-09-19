import unittest
from services.job_executor import _take_profile_round

class GateCProfileSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.accounts=[{"id":"M6"},{"id":"M21"},{"id":"M30"}]

    def test_each_profile_once_before_round_reset(self):
        q=["M6","M21","M30"]
        used=[_take_profile_round(q,self.accounts)["id"] for _ in range(3)]
        self.assertEqual(used,["M6","M21","M30"])
        self.assertEqual(q,[])
        self.assertEqual(_take_profile_round(q,self.accounts)["id"],"M6")

    def test_target_exclusion_does_not_consume_slot(self):
        q=["M6","M21","M30"]
        self.assertEqual(_take_profile_round(q,self.accounts,excluded={"M6"})["id"],"M21")
        self.assertIn("M6",q)
        self.assertEqual(_take_profile_round(q,self.accounts,scores={"M30":5})["id"],"M30")
        self.assertEqual(_take_profile_round(q,self.accounts)["id"],"M6")

    def test_group_score_only_orders_unused_eligible_profiles(self):
        q=["M6","M21","M30"]
        self.assertEqual(_take_profile_round(q,self.accounts,scores={"M30":8,"M21":3})["id"],"M30")
        self.assertEqual(_take_profile_round(q,self.accounts,scores={"M30":8,"M21":3})["id"],"M21")
        self.assertEqual(_take_profile_round(q,self.accounts,scores={"M30":8,"M21":3})["id"],"M6")

    def test_all_remaining_excluded_returns_none_without_reset(self):
        q=["M6"]
        self.assertIsNone(_take_profile_round(q,self.accounts,excluded={"M6"}))
        self.assertEqual(q,["M6"])

if __name__=="__main__":
    unittest.main()
