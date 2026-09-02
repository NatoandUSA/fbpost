import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scheduler
import server


class ServerApiTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    def test_queue_requires_approval_before_state_changes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "QUEUE_FILE", str(Path(directory) / "queue.json")):
            created = self.client.post("/api/queue", json={"target": "123", "content": "Nội dung bài đăng hợp lệ."})
            self.assertEqual(created.status_code, 201)
            item = created.get_json()
            approved = self.client.post(f"/api/queue/{item['id']}/approve")
            self.assertEqual(approved.status_code, 200)
            self.assertEqual(approved.get_json()["state"], "approved")

    def test_paused_campaign_rejects_new_queue_item(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(server, "QUEUE_FILE", str(Path(directory) / "queue.json")), \
             patch.object(server, "CAMPAIGNS_FILE", str(Path(directory) / "campaigns.json")):
            created = self.client.post("/api/campaigns", json={"name": "Lacasa September", "brand": "Lacasa", "target": "123"})
            self.assertEqual(created.status_code, 201)
            campaign = created.get_json()
            paused = self.client.post(f"/api/campaigns/{campaign['id']}/toggle")
            self.assertEqual(paused.status_code, 200)
            response = self.client.post("/api/queue", json={
                "target": "123", "content": "Nội dung bài đăng hợp lệ.", "campaign_id": campaign["id"],
            })
            self.assertEqual(response.status_code, 409)

    def test_campaign_can_approve_all_its_drafts(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(server, "QUEUE_FILE", str(Path(directory) / "queue.json")), \
             patch.object(server, "CAMPAIGNS_FILE", str(Path(directory) / "campaigns.json")):
            campaign = self.client.post("/api/campaigns", json={"name": "UMEE September"}).get_json()
            for suffix in ("Một", "Hai"):
                response = self.client.post("/api/queue", json={
                    "target": "page-1", "content": f"Nội dung bài {suffix} hợp lệ.", "campaign_id": campaign["id"],
                })
                self.assertEqual(response.status_code, 201)
            approved = self.client.post(f"/api/campaigns/{campaign['id']}/approve-drafts")
            self.assertEqual(approved.status_code, 200)
            self.assertEqual(approved.get_json()["approved"], 2)

    def test_scheduler_routes_are_registered(self):
        routes = {rule.rule for rule in server.app.url_map.iter_rules()}
        self.assertIn("/api/page/config", routes)
        self.assertIn("/api/scheduler/status", routes)

    def test_invalid_scheduler_interval_is_rejected(self):
        response = self.client.post(
            "/api/page/sheets",
            json={"url": "https://docs.google.com/spreadsheets/d/example/pub?output=csv", "interval": 1},
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_upload_is_rejected(self):
        response = self.client.post(
            "/api/upload",
            data={"image": (tempfile.SpooledTemporaryFile(), "not-an-image.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)


class SchedulerTests(unittest.TestCase):
    def test_successful_row_is_only_posted_once(self):
        csv_data = "page_id,content,image_url,scheduled_time,status\n123,Hello,,2020-01-01 00:00,pending\n"

        class FakeResponse:
            text = csv_data

            def raise_for_status(self):
                return None

        with tempfile.TemporaryDirectory() as directory:
            state_file = str(Path(directory) / "state.json")
            with patch.object(scheduler, "STATE_FILE", state_file), \
                 patch.object(scheduler, "load_config", return_value={"page_access_token": "token", "sheets_csv_url": "https://example.com/feed.csv"}), \
                 patch("scheduler.requests.get", return_value=FakeResponse()), \
                 patch("scheduler.post_to_page", return_value=(True, {"post_id": "post-1", "content_preview": "Hello"})) as post:
                scheduler.run_scheduler_job()
                scheduler.run_scheduler_job()

            self.assertEqual(post.call_count, 1)
            saved = json.loads(Path(state_file).read_text(encoding="utf-8"))
            self.assertEqual(len(saved["posted"]), 1)


if __name__ == "__main__":
    unittest.main()
