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
        self.assertIn("/api/security/overview", routes)

    def test_security_overview_never_returns_page_token(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.json"
            state_file = Path(directory) / "state.json"
            config_file.write_text(json.dumps({
                "page_access_token": "private-page-token",
                "page_name": "Lacasa",
                "sheets_csv_url": "https://example.com/feed.csv",
            }), encoding="utf-8")
            state_file.write_text("{}", encoding="utf-8")
            with patch.object(server, "CONFIG_FILE", str(config_file)), \
                 patch.object(server, "STATE_FILE", str(state_file)):
                response = self.client.get("/api/security/overview")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["page_token_configured"])
        self.assertTrue(payload["browser_session_saved"])
        self.assertNotIn("page_access_token", payload)
        self.assertNotIn("private-page-token", json.dumps(payload))

    def test_profile_activity_is_scoped_and_does_not_claim_publication(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "ACTIVITY_LOG_FILE", str(Path(directory) / "activity.json")):
            server.record_profile_activity("profile-a", "group", target="https://www.facebook.com/groups/example", content="Approved content")
            response = self.client.get("/api/profile-activity?profile_id=profile-a")

        self.assertEqual(response.status_code, 200)
        entry = response.get_json()[0]
        self.assertEqual(entry["profile_id"], "profile-a")
        self.assertEqual(entry["action"], "group")
        self.assertEqual(entry["outcome"], "finished")
        self.assertNotIn("published", entry)

    def test_group_registry_is_manual_and_validates_facebook_links(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "GROUPS_FILE", str(Path(directory) / "groups.json")):
            invalid = self.client.post("/api/groups", json={"url": "https://example.com/group"})
            self.assertEqual(invalid.status_code, 400)

            created = self.client.post("/api/groups", json={
                "url": "https://www.facebook.com/groups/example",
                "name": "Example Group",
                "group_type": "public",
                "member_count": 12000,
            })
            self.assertEqual(created.status_code, 201)
            group = created.get_json()
            self.assertEqual(group["status"], "not_requested")
            self.assertEqual(group["group_type"], "public")
            self.assertEqual(group["member_count"], 12000)

            updated = self.client.patch(f"/api/groups/{group['id']}", json={
                "status": "requested_manually", "rating": 4, "notes": "Requested by team member.",
            })
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.get_json()["rating"], 4)

    def test_offline_vault_tracks_password_change_date(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "VAULT_FILE", str(Path(directory) / "vault.json")):
            created = self.client.post("/api/vault", json={
                "platform": "Facebook", "account_name": "Shop account",
                "email": "shop@example.com", "password": "first-secret",
                "date_added": "2026-09-01",
            })
            self.assertEqual(created.status_code, 201)
            entry = created.get_json()
            self.assertEqual(entry["date_added"], "2026-09-01")
            updated = self.client.patch(f"/api/vault/{entry['id']}", json={"password": "next-secret"})
            self.assertEqual(updated.status_code, 200)
            payload = updated.get_json()
            self.assertTrue(payload["password_changed_at"])
            self.assertEqual(payload["password_history"][0]["event"], "Đã cập nhật mật khẩu")
            self.assertEqual(len(self.client.get("/api/vault?q=shop@example").get_json()), 1)

    def test_manual_group_queue_never_runs_browser_actions(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(server, "GROUPS_FILE", str(Path(directory) / "groups.json")), \
             patch.object(server, "MANUAL_GROUP_QUEUE_FILE", str(Path(directory) / "manual-queue.json")), \
             patch.object(server, "ACTIVITY_LOG_FILE", str(Path(directory) / "activity.json")):
            group = self.client.post("/api/groups", json={
                "url": "https://www.facebook.com/groups/example", "name": "Example Group",
            }).get_json()
            created = self.client.post("/api/manual-group-queue", json={
                "group_id": group["id"], "profile_id": "profile-a",
                "content": "Approved content that a staff member will post manually.",
                "planned_at": "2026-09-03T09:00",
            })
            self.assertEqual(created.status_code, 201)
            item = created.get_json()
            self.assertEqual(item["state"], "planned")
            self.assertNotIn("run", item)

            self.assertEqual(self.client.post(f"/api/manual-group-queue/{item['id']}/mark-ready").status_code, 200)
            completed = self.client.post(f"/api/manual-group-queue/{item['id']}/mark-completed")
            self.assertEqual(completed.status_code, 200)
            self.assertEqual(completed.get_json()["state"], "completed")
            activity = self.client.get("/api/profile-activity").get_json()[0]
            self.assertEqual(activity["action"], "manual_group_confirmation")
            self.assertNotIn("published", activity)

    def test_app_info_exposes_build_identity_without_secrets(self):
        response = self.client.get("/api/app-info")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["version"], server.APP_VERSION)
        self.assertTrue(response.get_json()["group_manager_available"])

    def test_invalid_scheduler_interval_is_rejected(self):
        response = self.client.post(
            "/api/page/sheets",
            json={"url": "https://docs.google.com/spreadsheets/d/example/pub?output=csv", "interval": 1},
        )
        self.assertEqual(response.status_code, 400)

    def test_scheduler_random_spacing_requires_at_least_five_minutes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "CONFIG_FILE", str(Path(directory) / "config.json")):
            valid = self.client.post(
                "/api/page/sheets",
                json={
                    "url": "https://docs.google.com/spreadsheets/d/example/pub?output=csv",
                    "interval": 5,
                    "post_delay_min": 5,
                    "post_delay_max": 10,
                },
            )
            self.assertEqual(valid.status_code, 200)
            saved = json.loads((Path(directory) / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["post_delay_min_minutes"], 5)
            self.assertEqual(saved["post_delay_max_minutes"], 10)

            too_short = self.client.post(
                "/api/page/sheets",
                json={
                    "url": "https://docs.google.com/spreadsheets/d/example/pub?output=csv",
                    "interval": 5,
                    "post_delay_min": 4,
                    "post_delay_max": 10,
                },
            )
            self.assertEqual(too_short.status_code, 400)

    def test_invalid_upload_is_rejected(self):
        response = self.client.post(
            "/api/upload",
            data={"image": (tempfile.SpooledTemporaryFile(), "not-an-image.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)

    def test_comment_command_is_allowed_and_validates_input(self):
        self.assertIn("comment", server.ALLOWED_COMMANDS)
        # Test empty tasks rejection
        response = self.client.post(
            "/api/run",
            json={"command": "comment", "tasks": []}
        )
        self.assertEqual(response.status_code, 200)
        output = response.get_data(as_text=True)
        self.assertIn("Error", output)


class SchedulerTests(unittest.TestCase):
    def test_scheduler_skips_structural_headers(self):
        csv_data = "ID,Content,Image URL,Scheduled Time,Status\n123,Hello,,2020-01-01 00:00,pending\n"

        class FakeResponse:
            text = csv_data

            def raise_for_status(self):
                return None

        with patch("scheduler.requests.get", return_value=FakeResponse()):
            rows = scheduler.fetch_sheets_data("https://example.com/feed.csv")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["page_id"], "123")

    def test_scheduler_skips_vietnamese_headers_with_d_stroke(self):
        csv_data = "Page ID,Nội dung,Đường dẫn ảnh,Thời gian đăng,Trạng thái\n123,Chào Huế,,2020-01-01 00:00,pending\n"

        class FakeResponse:
            text = csv_data

            def raise_for_status(self):
                return None

        with patch("scheduler.requests.get", return_value=FakeResponse()):
            rows = scheduler.fetch_sheets_data("https://example.com/feed.csv")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["content"], "Chào Huế")

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


class ReleasePackagingTests(unittest.TestCase):
    def test_english_page_scheduler_template_is_ascii_and_has_expected_headers(self):
        template = Path("static/page_scheduler_template_en.csv").read_bytes()
        self.assertEqual(template.decode("ascii").splitlines()[0], "Page ID,Content,Image URL,Scheduled Time,Status")

    def test_portable_launcher_uses_absolute_runtime_paths(self):
        launcher = Path("RUN_FB_AUTOMATION.bat").read_text(encoding="utf-8")
        self.assertIn('set "VENV_DIR=%CD%\\runtime\\venv"', launcher)
        self.assertIn('set "PYTHON_INSTALLER=%CD%\\runtime\\python-3.12.10-amd64.exe"', launcher)

    def test_build_excludes_local_secrets_and_runtime_artifacts(self):
        build_script = Path("BUILD_PORTABLE.ps1").read_text(encoding="utf-8")
        for filename in ("config.json", "accounts.json", "publication_queue.json"):
            self.assertIn(filename, build_script)
        self.assertIn("__pycache__", build_script)
        self.assertIn(".pyc", build_script)
        self.assertIn("'.log'", build_script)


if __name__ == "__main__":
    unittest.main()
