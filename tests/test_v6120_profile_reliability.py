import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from repositories.job_repo import JobRepository
from repositories.workflow_repo import WorkflowRepository


class ProfileReliabilityTests(unittest.TestCase):
    def test_plural_gemini_keys_are_redacted_from_job_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.db"
            from db import init_db
            init_db(db_path)
            repo = JobRepository(str(db_path))
            repo.create_job({"id": "redact-keys", "payload": {"geminiApiKeys": ["secret-a", "secret-b"], "brandKey": "umee"}})
            payload = repo.get_job("redact-keys")["payload"]
            self.assertEqual(payload["geminiApiKeys"], "***REDACTED***")
            self.assertEqual(payload["brandKey"], "umee")

    def test_workflow_api_resolves_gpm_display_name(self):
        fake_rows = [{"id": "task-1", "profile_id": "uuid-m21", "state": "published"}]
        with patch.object(WorkflowRepository, "list_tasks", return_value=fake_rows), \
             patch.object(server, "load_accounts", return_value=[{"id": "uuid-m21", "name": "M21"}]):
            data = server.app.test_client().get("/api/workflows/tasks").get_json()
        self.assertEqual(data["tasks"][0]["profile_name"], "M21")

    def test_profile_performance_endpoint_keeps_pending_separate(self):
        row = {"profile_id": "uuid-m4", "total": 3, "published": 1, "pending": 1,
               "unverified": 1, "failed": 0, "active": 0, "published_rate": 33.3,
               "avg_seconds": 12.0, "last_activity": "2026-09-14"}
        with patch.object(WorkflowRepository, "profile_posting_performance", return_value=[row]), \
             patch.object(server, "load_accounts", return_value=[{"profile_path_or_id": "uuid-m4", "name": "M4"}]):
            data = server.app.test_client().get("/api/workflows/profile-performance").get_json()
        self.assertEqual(data["profiles"][0]["profile_name"], "M4")
        self.assertEqual(data["profiles"][0]["pending"], 1)
        self.assertEqual(data["profiles"][0]["published_rate"], 33.3)

    def test_workspace_contains_performance_panel_and_display_name_renderer(self):
        html = Path("static/index.html").read_text(encoding="utf-8")
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('id="profile-performance-body"', html)
        self.assertIn("t.profile_name || t.profile_id", js)
        self.assertIn("loadProfilePerformance", js)


if __name__ == "__main__":
    unittest.main()
