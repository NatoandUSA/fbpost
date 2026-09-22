import unittest

from certification.pending_resolver import (
    NavigationBudget, PendingState, resolve_pending_read_only, validate_candidate,
)


class Body:
    def __init__(self, value=None, error=None):
        self.value, self.error = value, error
    def inner_text(self, timeout=0):
        if self.error:
            raise self.error
        return self.value


class Page:
    def __init__(self, value=None, error=None):
        self.body = Body(value, error)
    def locator(self, selector):
        self.assert_body_selector = selector
        return self.body


class CertificationPendingResolverTests(unittest.TestCase):
    def test_explicit_zero_is_confirmed(self):
        result = resolve_pending_read_only(Page("Pending admin approval\n0 posts"))
        self.assertEqual(result.state, PendingState.ZERO_CONFIRMED)
        self.assertEqual(result.count, 0)
        self.assertTrue(result.eligible)

    def test_positive_count_is_confirmed_but_not_eligible(self):
        result = resolve_pending_read_only(Page("Đang chờ quản trị viên phê duyệt\n2 bài viết"))
        self.assertEqual(result.state, PendingState.COUNT_CONFIRMED)
        self.assertEqual(result.count, 2)
        self.assertFalse(result.eligible)

    def test_absent_surface_fails_closed(self):
        result = resolve_pending_read_only(Page("Nhóm công khai · 75,9K thành viên"))
        self.assertEqual(result.state, PendingState.UNKNOWN)
        self.assertFalse(result.eligible)

    def test_body_read_failure_is_unknown(self):
        result = resolve_pending_read_only(Page(error=RuntimeError("boom")))
        self.assertEqual(result.state, PendingState.UNKNOWN)

    def test_non_string_body_is_unknown(self):
        result = resolve_pending_read_only(Page(123))
        self.assertEqual(result.state, PendingState.UNKNOWN)

    def test_invalid_candidate_rejected_before_navigation(self):
        budget = NavigationBudget(1)
        with self.assertRaisesRegex(ValueError, "candidate_id_not_numeric"):
            validate_candidate("15983141139l358", {"15983141139l358"})
        self.assertEqual(budget.used, 0)

    def test_locked_pool_and_exclusion_guards(self):
        with self.assertRaisesRegex(ValueError, "candidate_id_not_in_locked_pool"):
            validate_candidate("123", {"456"})
        with self.assertRaisesRegex(ValueError, "candidate_id_excluded"):
            validate_candidate("123", {"123"}, {"123"})
        self.assertEqual(validate_candidate("123", {"123"}), "123")

    def test_navigation_budget(self):
        budget = NavigationBudget(1)
        budget.authorize("123")
        self.assertEqual(budget.used, 1)
        with self.assertRaisesRegex(RuntimeError, "navigation_budget_exhausted"):
            budget.authorize("456")


if __name__ == "__main__":
    unittest.main()
