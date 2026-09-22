import unittest
from certification.harness import CertificationHarness, SurfaceSpec
from certification.pending_resolver import PendingState

class Surface:
    def __init__(self, text): self.text=text
    def inner_text(self, timeout=0): return self.text

SPECS=(SurfaceSpec("pending_header","div[role='main'] [data-e4-pending-control='header']"),SurfaceSpec("pending_counter","div[role='main'] [data-e4-pending-control='counter']"))

class CertificationHarnessTests(unittest.TestCase):
    def harness(self, limit=3): return CertificationHarness({"123","456"},{"999"},limit,SPECS)
    def test_candidate_guard_precedes_budget(self):
        h=self.harness()
        with self.assertRaises(ValueError): h.authorize_navigation("12x")
        self.assertEqual(h.budget.used,0)
    def test_locked_pool_guard_precedes_budget(self):
        h=self.harness()
        with self.assertRaises(ValueError): h.authorize_navigation("777")
        self.assertEqual(h.budget.used,0)
    def test_excluded_guard_precedes_budget(self):
        h=CertificationHarness({"123"},{"123"},1,SPECS)
        with self.assertRaises(ValueError): h.authorize_navigation("123")
        self.assertEqual(h.budget.used,0)
    def test_broad_body_selector_forbidden(self):
        with self.assertRaisesRegex(ValueError,"broad_surface_selector_forbidden"): CertificationHarness({"123"},(),1,(SurfaceSpec("bad","body"),))
    def test_unapproved_authority_forbidden(self):
        with self.assertRaisesRegex(ValueError,"unsupported_surface_authority"): CertificationHarness({"123"},(),1,(SurfaceSpec("x","#x","content"),))
    def test_authorize_without_record_rejects_evaluation(self):
        h=self.harness(); h.authorize_navigation("123")
        with self.assertRaisesRegex(RuntimeError,"candidate_not_navigated"): h.evaluate_after_navigation("123",{"pending_counter":Surface("0 posts")})
    def test_recorded_navigation_receipt_count_one(self):
        h=self.harness(); h.authorize_navigation("123"); h.record_navigation("123")
        r=h.evaluate_after_navigation("123",{"pending_counter":Surface("0 posts")})
        self.assertEqual(r.navigation_count,1)
    def test_two_authorizations_one_navigation_count_one(self):
        h=self.harness(); h.authorize_navigation("123"); h.authorize_navigation("123"); h.record_navigation("123")
        r=h.evaluate_after_navigation("123",{"pending_counter":Surface("0 posts")})
        self.assertEqual(r.navigation_count,1)
    def test_record_without_authorization_rejected(self):
        h=self.harness()
        with self.assertRaisesRegex(RuntimeError,"navigation_not_authorized"): h.record_navigation("123")
        self.assertEqual(h._navigation_counts.get("123",0),0)
    def test_authorize_123_record_456_rejected(self):
        h=self.harness(); h.authorize_navigation("123")
        with self.assertRaisesRegex(RuntimeError,"navigation_not_authorized"): h.record_navigation("456")
        self.assertEqual(h._navigation_counts.get("456",0),0)
    def test_failed_actual_navigation_not_recorded(self):
        h=self.harness(); h.authorize_navigation("123")
        self.assertEqual(h._navigation_counts.get("123",0),0)
    def test_two_authorizations_two_records_count_two(self):
        h=self.harness(); h.authorize_navigation("123"); h.authorize_navigation("123"); h.record_navigation("123"); h.record_navigation("123")
        r=h.evaluate_after_navigation("123",{"pending_counter":Surface("0 posts")})
        self.assertEqual(r.navigation_count,2)
    def test_per_candidate_counts_independent(self):
        h=self.harness(); h.authorize_navigation("123"); h.record_navigation("123"); h.authorize_navigation("456"); h.record_navigation("456")
        self.assertEqual(h.evaluate_after_navigation("123",{"pending_counter":Surface("0 posts")}).navigation_count,1)
        self.assertEqual(h.evaluate_after_navigation("456",{"pending_counter":Surface("0 posts")}).navigation_count,1)
    def test_failed_validation_changes_no_state(self):
        h=self.harness()
        with self.assertRaises(ValueError): h.authorize_navigation("bad")
        self.assertEqual(h.budget.used,0); self.assertEqual(dict(h._authorization_counts),{}); self.assertEqual(dict(h._navigation_counts),{})
    def test_exhausted_budget_no_phantom_authorization(self):
        h=self.harness(1); h.authorize_navigation("123")
        with self.assertRaisesRegex(RuntimeError,"navigation_budget_exhausted"): h.authorize_navigation("456")
        self.assertEqual(h.budget.used,1); self.assertEqual(h._authorization_counts.get("456",0),0)
    def test_receipt_provenance(self):
        h=self.harness(); h.authorize_navigation("123"); h.record_navigation("123")
        r=h.evaluate_after_navigation("123",{"pending_counter":Surface("0 posts")})
        self.assertEqual(r.source_ids,("pending_counter",)); self.assertEqual(r.selectors,(SPECS[1].selector,)); self.assertEqual(r.pending_state,PendingState.ZERO_CONFIRMED)
    def test_missing_surface_fails_closed(self):
        h=self.harness(); h.authorize_navigation("123"); h.record_navigation("123"); r=h.evaluate_after_navigation("123",{})
        self.assertEqual(r.pending_state,PendingState.UNKNOWN); self.assertFalse(r.eligible)
    def test_conflict_fails_closed(self):
        h=self.harness(); h.authorize_navigation("123"); h.record_navigation("123")
        r=h.evaluate_after_navigation("123",{"pending_header":Surface("0 posts"),"pending_counter":Surface("2 posts")})
        self.assertEqual(r.pending_state,PendingState.UNKNOWN); self.assertFalse(r.eligible)
