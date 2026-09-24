import unittest
from unittest.mock import patch

import utils


class _FakeChromium:
    def __init__(self):
        self.calls = 0
    def connect_over_cdp(self, endpoint, timeout=0):
        self.calls += 1
        return {"endpoint": endpoint, "timeout": timeout}


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()


class V6131RuntimeRecoveryTests(unittest.TestCase):
    def test_cdp_waits_for_open_port_before_attach(self):
        fake = _FakePlaywright()
        states = iter([False, False, True])
        with patch("utils._endpoint_open", side_effect=lambda endpoint: next(states)),              patch("utils.time.sleep", return_value=None):
            browser = utils.connect_over_cdp_when_ready(fake, "http://127.0.0.1:9222", timeout_seconds=2)
        self.assertEqual(fake.chromium.calls, 1)
        self.assertEqual(browser["endpoint"], "http://127.0.0.1:9222")

    def test_recovery_sources_preserve_fail_closed_contracts(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        group = (root / "fb_group.py").read_text(encoding="utf-8")
        comment = (root / "fb_comment.py").read_text(encoding="utf-8")
        executor = (root / "services" / "job_executor.py").read_text(encoding="utf-8")
        sheet = (root / "services" / "sheet_sync.py").read_text(encoding="utf-8")
        self.assertIn("joined evidence=post_composer_capability", group)
        self.assertIn("exact-route-comment-dialog", comment)
        self.assertIn("profile_runtime_quarantine", executor)
        self.assertIn("GROUP_REGISTRY_PERSIST_FAILED", sheet)
        self.assertNotIn("comment_on_group_root", comment)


if __name__ == "__main__":
    unittest.main()
