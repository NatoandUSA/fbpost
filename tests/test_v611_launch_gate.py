import tempfile
import unittest
from pathlib import Path

from db import init_db
from repositories.campaign_repo import CampaignRepository
from repositories.reconcile_repo import ReconcileRepository


class LaunchGateDurableReconcileTests(unittest.TestCase):
    def test_reconcile_schedule_and_restart_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "launch.db")
            init_db(db)
            repo = ReconcileRepository(db)
            rid = repo.enqueue("https://facebook.com/groups/1", "hello", "M21", "q1", delay_seconds=0)
            claimed = repo.claim_due(limit=5)
            self.assertEqual([x["id"] for x in claimed], [rid])
            self.assertEqual(repo.get_item(rid)["status"], "running")
            self.assertEqual(repo.recover_running(), 1)
            self.assertEqual(repo.get_item(rid)["status"], "pending")

    def test_reconcile_resolves_or_escalates_without_repost(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "launch.db")
            init_db(db)
            repo = ReconcileRepository(db)
            rid = repo.enqueue("https://facebook.com/groups/1", "hello", "M21", delay_seconds=0)
            self.assertEqual(repo.finish_attempt(rid, "unverified"), "pending")
            self.assertEqual(repo.finish_attempt(rid, "unverified"), "pending")
            self.assertEqual(repo.finish_attempt(rid, "unverified"), "manual_review")

class LaunchGateQueueSyncTests(unittest.TestCase):
    def test_durable_result_updates_linked_publication_queue(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "launch.db")
            init_db(db)
            campaigns = CampaignRepository(db_file=db)
            item = {
                "id": "q1", "target": "https://facebook.com/groups/1", "content": "hello",
                "state": "unverified", "account_id": "M21"
            }
            self.assertTrue(campaigns.insert_queue_item(item))
            updated = campaigns.apply_reconcile_result("q1", "published", "https://facebook.com/groups/1/posts/99")
            self.assertEqual(updated["state"], "published")
            self.assertTrue(updated["result_url"].endswith("/posts/99"))


class LaunchGateStaticContracts(unittest.TestCase):
    def test_runtime_paths_and_thread_account_binding(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("fb_group.py", "fb_page.py", "fb_comment.py", "fb_interact.py", "fb_auth.py"):
            src = (root / name).read_text(encoding="utf-8-sig")
            self.assertNotIn('STATE_FILE = "state.json"', src)
        ui = (root / "static" / "app.js").read_text(encoding="utf-8-sig")
        self.assertIn("runCommand('thread', { tasks, accountId:", ui)
        self.assertIn("accountSelector ? accountSelector.value", ui)
        executor = (root / "services" / "job_executor.py").read_text(encoding="utf-8-sig")
        self.assertIn("cmd in (\"group\", \"page\")", executor)
        self.assertIn("reconcileRecordId", executor)

    def test_reconcile_prefers_durable_published_evidence(self):
        root = Path(__file__).resolve().parents[1]
        src = (root / "fb_reconcile.py").read_text(encoding="utf-8-sig")
        self.assertIn('evidence_source": "sqlite_posted_links"', src)
        self.assertIn('row.get("publish_state") == "published"', src)
        self.assertIn('_normalize_content(row.get("content")) == _normalize_content(content)', src)
        self.assertIn('_normalize_target(row.get("target")) == expected_target', src)



if __name__ == "__main__":
    unittest.main()

