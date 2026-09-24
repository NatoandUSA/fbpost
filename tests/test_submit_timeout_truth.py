import unittest
from pathlib import Path

from services.job_executor import (
    SUBMIT_TRIGGERED_MARKER,
    line_confirms_submit_triggered,
    ensure_submit_uncertain_from_runtime_marker,
    is_submit_uncertain,
)


class SubmitTimeoutTruthTests(unittest.TestCase):
    def test_submit_runtime_marker_promotes_lost_action_result_to_typed_unverified(self):
        result = {}
        self.assertTrue(line_confirms_submit_triggered(f"noise {SUBMIT_TRIGGERED_MARKER} noise"))
        changed = ensure_submit_uncertain_from_runtime_marker(result, True)
        self.assertTrue(changed)
        self.assertEqual(result["state"], "submitted_unverified")
        self.assertEqual(result["code"], "SUBMIT_TRIGGERED_UNVERIFIED")
        self.assertTrue(is_submit_uncertain(result))

    def test_submit_runtime_marker_does_not_override_existing_typed_truth(self):
        published = {"state": "published", "code": "POST_PUBLISHED", "result_url": "https://www.facebook.com/groups/1/posts/2"}
        before = dict(published)
        self.assertFalse(ensure_submit_uncertain_from_runtime_marker(published, True))
        self.assertEqual(published, before)

        empty = {}
        self.assertFalse(ensure_submit_uncertain_from_runtime_marker(empty, False))
        self.assertEqual(empty, {})

    def test_every_publish_activation_path_emits_machine_marker(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "utils.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('print("SUBMIT_TRIGGERED_MARKER:POST_BUTTON_ACTIVATED")'), 4)


if __name__ == "__main__":
    unittest.main()
