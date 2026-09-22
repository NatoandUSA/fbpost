import unittest

from certification.pending_resolver import (
    NavigationBudget, PendingState, resolve_pending_read_only, validate_candidate,
)


class Surface:
    def __init__(self, value=None, error=None):
        self.value, self.error = value, error

    def inner_text(self, timeout=0):
        if self.error:
            raise self.error
        return self.value


class CertificationPendingResolverTests(unittest.TestCase):
    def test_explicit_authoritative_zero(self):
        result = resolve_pending_read_only([Surface("0 posts pending")])
        self.assertEqual((result.state, result.count, result.eligible),
                         (PendingState.ZERO_CONFIRMED, 0, True))

    def test_explicit_authoritative_two(self):
        result = resolve_pending_read_only([Surface("2 bài viết đang chờ")])
        self.assertEqual((result.state, result.count, result.eligible),
                         (PendingState.COUNT_CONFIRMED, 2, False))

    def test_no_authoritative_surface_is_unknown(self):
        result = resolve_pending_read_only([])
        self.assertEqual(result.state, PendingState.UNKNOWN)
        self.assertFalse(result.eligible)

    def test_surface_read_failure_is_unknown(self):
        result = resolve_pending_read_only([Surface(error=RuntimeError("boom"))])
        self.assertEqual(result.state, PendingState.UNKNOWN)

    def test_non_string_surface_is_unknown(self):
        self.assertEqual(resolve_pending_read_only([Surface(2)]).state, PendingState.UNKNOWN)

    def test_zero_then_two_conflict_is_unknown(self):
        result = resolve_pending_read_only([Surface("0 posts"), Surface("2 posts")])
        self.assertEqual(result.state, PendingState.UNKNOWN)
        self.assertFalse(result.eligible)

    def test_two_then_zero_conflict_is_unknown(self):
        result = resolve_pending_read_only([Surface("2 posts"), Surface("0 posts")])
        self.assertEqual(result.state, PendingState.UNKNOWN)

    def test_arbitrary_body_mimic_is_not_an_authoritative_surface(self):
        body_text = "User comment: Pending admin approval\n0 posts"
        result = resolve_pending_read_only([])
        self.assertIn("0 posts", body_text)
        self.assertEqual(result.state, PendingState.UNKNOWN)

    def test_duplicate_consistent_zero_surfaces(self):
        result = resolve_pending_read_only([Surface("0 posts"), Surface("0 bài viết")])
        self.assertEqual((result.state, result.count), (PendingState.ZERO_CONFIRMED, 0))

    def test_duplicate_consistent_positive_surfaces(self):
        result = resolve_pending_read_only([Surface("2 posts"), Surface("2 bài viết")])
        self.assertEqual((result.state, result.count), (PendingState.COUNT_CONFIRMED, 2))

    def test_ambiguous_single_surface_is_unknown(self):
        result = resolve_pending_read_only([Surface("0 posts; 2 posts")])
        self.assertEqual(result.state, PendingState.UNKNOWN)

    def test_nonnumeric_candidate_rejected_before_navigation(self):
        budget = NavigationBudget(1)
        with self.assertRaisesRegex(ValueError, "candidate_id_not_numeric"):
            budget.authorize("15983141139l358", {"15983141139l358"})
        self.assertEqual(budget.used, 0)

    def test_outside_locked_pool_rejected_before_navigation(self):
        budget = NavigationBudget(1)
        with self.assertRaisesRegex(ValueError, "candidate_id_not_in_locked_pool"):
            budget.authorize("123", {"456"})
        self.assertEqual(budget.used, 0)

    def test_excluded_candidate_rejected_before_navigation(self):
        budget = NavigationBudget(1)
        with self.assertRaisesRegex(ValueError, "candidate_id_excluded"):
            budget.authorize("123", {"123"}, {"123"})
        self.assertEqual(budget.used, 0)

    def test_candidate_validation(self):
        self.assertEqual(validate_candidate("123", {"123"}), "123")

    def test_navigation_budget(self):
        budget = NavigationBudget(1)
        self.assertEqual(budget.authorize("123", {"123"}), "123")
        with self.assertRaisesRegex(RuntimeError, "navigation_budget_exhausted"):
            budget.authorize("456", {"456"})
        self.assertEqual(budget.used, 1)


if __name__ == "__main__":
    unittest.main()
