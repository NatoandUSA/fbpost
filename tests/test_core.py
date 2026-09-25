import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="fb-auto-tests-")
os.environ.setdefault("FB_AUTOMATION_DATA_DIR", _TEST_DATA_DIR)

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

    def test_build_uses_allowlist_and_excludes_runtime_artifacts(self):
        build_script = Path("BUILD_PORTABLE.ps1").read_text(encoding="utf-8")
        self.assertIn("$dirs = @(", build_script)
        self.assertIn("$files = @(", build_script)
        self.assertIn("'modules'", build_script)
        self.assertIn("$requiredEngineFiles", build_script)
        self.assertIn("Portable bundle is missing ADVANCED_HUMAN_ENGINE component", build_script)
        self.assertIn("__pycache__", build_script)
        self.assertIn(".pyc", build_script)
        self.assertIn("'.log'", build_script)
        for runtime_name in ("app.db", "config.json", "accounts.json", "publication_queue.json"):
            self.assertNotIn(runtime_name, build_script)


class NclProInspiredFeatureTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    def test_ai_spinner_local_preserves_contact_and_spins_content(self):
        from ai_spinner import spin_content_local
        original = "Homestay Huế siêu xinh view Sông Hương! Giá chỉ từ 350k/đêm. Hotline: 0905555317. Địa chỉ: Số 3 kiệt 17 Trần Phú, Huế."
        spun = spin_content_local(original)
        self.assertIn("0905555317", spun)
        self.assertIn("Trần Phú", spun)
        self.assertIn("350k", spun)
        self.assertIn("#", spun)
        self.assertNotEqual(original.strip(), spun.strip())

    def test_pick_random_photos_from_folder(self):
        from utils import pick_random_photos
        with tempfile.TemporaryDirectory() as directory:
            for i in range(5):
                (Path(directory) / f"photo_{i}.jpg").write_bytes(b"fake-image")
            (Path(directory) / "notes.txt").write_text("not an image")

            picked_2_4 = pick_random_photos(directory, "2-4")
            self.assertTrue(2 <= len(picked_2_4) <= 4)
            for p in picked_2_4:
                self.assertTrue(p.endswith(".jpg"))

            picked_1 = pick_random_photos(directory, "1")
            self.assertEqual(len(picked_1), 1)

    def test_is_recently_posted_detection(self):
        import time
        from utils import is_recently_posted
        with tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / "posted_links.json"
            items = [
                {
                    "id": "1",
                    "timestamp": time.time() - 3600, # 1 hour ago
                    "target": "https://www.facebook.com/groups/homestayhue/",
                    "url": "https://www.facebook.com/groups/homestayhue/posts/111",
                    "posted_at": "2026-09-04 06:00:00"
                },
                {
                    "id": "2",
                    "timestamp": time.time() - 100000, # ~28 hours ago
                    "target": "https://www.facebook.com/groups/oldgroup/",
                    "url": "https://www.facebook.com/groups/oldgroup/posts/222",
                    "posted_at": "2026-09-02 00:00:00"
                }
            ]
            db_file.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

            with patch("utils.POSTED_LINKS_FILE", str(db_file)):
                is_dup, hours_ago, posted_at = is_recently_posted("https://www.facebook.com/groups/homestayhue", hours=24.0)
                self.assertTrue(is_dup)
                self.assertAlmostEqual(hours_ago, 1.0, delta=0.5)

                is_dup_old, _, _ = is_recently_posted("https://www.facebook.com/groups/oldgroup", hours=24.0)
                self.assertFalse(is_dup_old)

                is_dup_never, _, _ = is_recently_posted("https://www.facebook.com/groups/neverposted", hours=24.0)
                self.assertFalse(is_dup_never)

    def test_ai_spin_endpoint_returns_variant(self):
        response = self.client.post("/api/ai/spin", json={
            "content": "Phòng đẹp giá rẻ tại trung tâm Huế, liên hệ 0905123456"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("0905123456", data.get("spun_content", ""))

    def test_ai_spin_endpoint_reports_unchanged_truthfully(self):
        response = self.client.post("/api/ai/spin", json={
            "content": "Nội dung giữ nguyên."
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("success"))
        self.assertFalse(data.get("changed"))
        self.assertEqual(data.get("mode"), "unchanged")

    def test_photos_list_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "test1.png").write_bytes(b"image")
            (Path(directory) / "test2.jpg").write_bytes(b"image")
            response = self.client.get(f"/api/photos/list?folder={directory}")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data.get("exists"))
            self.assertEqual(data.get("count"), 2)

    def test_inject_zero_width_chars_and_spintax(self):
        import hashlib
        from ai_spinner import inject_zero_width_chars, spin_two_tier
        from utils import process_spintax

        original = "Homestay Huế giá rẻ 350k tại 0905123456 xem tại https://example.com"
        injected = inject_zero_width_chars(original, frequency=0.8)
        
        # 1. Bảo toàn số điện thoại và URL không bị chia cắt
        self.assertIn("0905123456", injected)
        self.assertIn("https://example.com", injected)
        
        # 2. Chứa ít nhất một ký tự tàng hình Zero-Width
        zero_width_chars = {'\u200B', '\u200C', '\u200D', '\uFEFF'}
        self.assertTrue(any(c in injected for c in zero_width_chars))
        
        # 3. Mã băm SHA256 thay đổi
        hash_orig = hashlib.sha256(original.encode('utf-8')).hexdigest()
        hash_inj = hashlib.sha256(injected.encode('utf-8')).hexdigest()
        self.assertNotEqual(hash_orig, hash_inj)

        # 4. Spintax kết hợp anti_hash: khi loại bỏ ký tự tàng hình thì chuỗi đọc được giữ nguyên
        spintax_res = process_spintax("{Chào bạn|Hello}", anti_hash=True)
        self.assertTrue(any(c in spintax_res for c in zero_width_chars))
        clean_res = "".join(c for c in spintax_res if c not in zero_width_chars)
        self.assertTrue("Chào bạn" in clean_res or "Hello" in clean_res)

    def test_clean_and_randomize_image(self):
        from PIL import Image
        from utils import clean_and_randomize_image
        with tempfile.TemporaryDirectory() as temp_dir:
            # Tạo 1 ảnh JPEG thật kích thước 150x150
            src_img_path = Path(temp_dir) / "source_photo.jpg"
            img = Image.new("RGB", (150, 150), color="blue")
            img.save(src_img_path, format="JPEG", quality=95)

            out_dir = Path(temp_dir) / "cleaned"
            cleaned_path = clean_and_randomize_image(str(src_img_path), output_dir=str(out_dir))

            self.assertTrue(Path(cleaned_path).exists())
            self.assertNotEqual(str(src_img_path), cleaned_path)

            # Đọc lại ảnh đã làm sạch
            with Image.open(cleaned_path) as cleaned_img:
                w, h = cleaned_img.size
                # Kích thước vi chỉnh nhẹ xung quanh 150 (±2 px)
                self.assertTrue(148 <= w <= 152)
                self.assertTrue(148 <= h <= 152)
                # EXIF metadata trống
                exif_data = cleaned_img.getexif()
                self.assertEqual(len(exif_data), 0)

            # Ảnh nguồn ban đầu vẫn giữ nguyên vẹn
            self.assertTrue(src_img_path.exists())

    def test_fetch_gpm_profiles_connected(self):
        from utils import fetch_gpm_profiles
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "data": [
                {"id": "uuid-1", "name": "M14", "browser_type": "Chrome", "raw_proxy": "14.241.72.253:28165"},
                {"id": "uuid-2", "name": "M4", "browser_type": "Chrome", "raw_proxy": ""}
            ],
            "pagination": {"total": 2}
        }
        with patch("requests.get", return_value=mock_resp):
            res = fetch_gpm_profiles("http://127.0.0.1:19995")
            self.assertTrue(res["connected"])
            self.assertEqual(len(res["profiles"]), 2)
            self.assertEqual(res["total"], 2)
            self.assertEqual(res["profiles"][0]["name"], "M14")

    def test_gpm_start_timeout_allows_slow_profiles(self):
        from utils import GPM_START_TIMEOUT_SECONDS
        self.assertGreaterEqual(GPM_START_TIMEOUT_SECONDS, 30)

    def test_brand_signature_exact_and_idempotent(self):
        from brand_profiles import apply_brand_signature, BRAND_SIGNATURES
        base = "Nội dung quảng cáo thử nghiệm"
        once = apply_brand_signature(base, "umee", True)
        twice = apply_brand_signature(once, "umee", True)
        self.assertEqual(once, twice)
        self.assertTrue(once.endswith(BRAND_SIGNATURES["umee"]["signatureText"]))
        self.assertIn("Zalo: https://zalo.me/0905555317", once)
        self.assertIn("facebook.com/lacasahomestayinvietnam", once)

    def test_brand_signature_switches_projects(self):
        from brand_profiles import apply_brand_signature
        base = "Nội dung quảng cáo thử nghiệm"
        umee = apply_brand_signature(base, "umee", True)
        lacasa = apply_brand_signature(umee, "lacasa", True)
        self.assertIn("lacasahomestayinvietnam", lacasa)
        self.assertIn("facebook.com/umeehomestay", lacasa)
        self.assertLess(
            lacasa.index("facebook.com/lacasahomestayinvietnam"),
            lacasa.index("facebook.com/umeehomestay"),
        )

    def test_fetch_gpm_profiles_offline(self):
        from utils import fetch_gpm_profiles
        with patch("requests.get", side_effect=Exception("Connection refused")):
            res = fetch_gpm_profiles("http://127.0.0.1:19995")
            self.assertFalse(res["connected"])
            self.assertEqual(res["profiles"], [])
            self.assertEqual(res["total"], 0)

    def test_resolve_account(self):
        from utils import resolve_account
        from unittest.mock import MagicMock

        # 1. Resolve from accounts.json
        with patch("utils.load_accounts", return_value=[{"id": "acc-1", "name": "Nick 1", "type": "gpm"}]):
            acc = resolve_account("acc-1")
            self.assertIsNotNone(acc)
            self.assertEqual(acc["name"], "Nick 1")

        # 2. Resolve on-the-fly from GPM API
        mock_gpm = {
            "connected": True,
            "profiles": [{"id": "8e7342b5-4385-4ff4-8038-b669c60bd3fd", "name": "M14", "browser_type": "Chrome", "raw_proxy": "1.2.3.4:80"}]
        }
        with patch("utils.load_accounts", return_value=[]), patch("utils.fetch_gpm_profiles", return_value=mock_gpm):
            acc = resolve_account("8e7342b5-4385-4ff4-8038-b669c60bd3fd")
            self.assertIsNotNone(acc)
            self.assertEqual(acc["name"], "M14")
            self.assertEqual(acc["type"], "gpm")
            self.assertEqual(acc["proxy"], "1.2.3.4:80")

    def test_api_gpm_endpoints(self):
        mock_gpm = {
            "connected": True,
            "profiles": [{"id": "uuid-1", "name": "M14", "raw_proxy": ""}],
            "total": 1,
            "base_url": "http://127.0.0.1:19995"
        }
        with patch("utils.fetch_gpm_profiles", return_value=mock_gpm):
            # Test /api/gpm/profiles
            resp = self.client.get("/api/gpm/profiles")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data["connected"])
            self.assertEqual(len(data["profiles"]), 1)

            # Test /api/gpm/status
            resp_status = self.client.get("/api/gpm/status")
            self.assertEqual(resp_status.status_code, 200)
            status_data = resp_status.get_json()
            self.assertTrue(status_data["connected"])
            self.assertEqual(status_data["total_profiles"], 1)

    def test_batch_import_accounts(self):
        saved_accounts = []
        def mock_load():
            return list(saved_accounts)
        def mock_save(accs):
            saved_accounts.clear()
            saved_accounts.extend(accs)
            return True

        with patch("utils.load_accounts", side_effect=mock_load), patch("utils.save_accounts", side_effect=mock_save):
            # 1. Nhập 2 profiles
            payload = {
                "profiles": [
                    {"id": "uuid-fb-1", "name": "M14 Facebook", "raw_proxy": "14.241.72.253:28165", "browser_type": "Chrome"},
                    {"id": "uuid-fb-2", "name": "M4 Facebook", "raw_proxy": "", "browser_type": "Chrome"}
                ]
            }
            res = self.client.post("/api/accounts/batch-import", json=payload)
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["added_count"], 2)
            self.assertEqual(len(saved_accounts), 2)
            self.assertEqual(saved_accounts[0]["name"], "M14 Facebook")

            # 2. Thử nhập lại (chống trùng lặp)
            res_dup = self.client.post("/api/accounts/batch-import", json=payload)
            self.assertEqual(res_dup.status_code, 200)
            data_dup = res_dup.get_json()
            self.assertEqual(data_dup["added_count"], 0)
            self.assertEqual(len(saved_accounts), 2)

    def test_can_create_page_rate_limit(self):
        import fb_create_page
        from datetime import datetime, timedelta

        # Giả lập chưa tạo trang nào
        with patch("fb_create_page.load_created_pages", return_value=[]):
            allowed, count, msg = fb_create_page.can_create_page(max_per_day=2)
            self.assertTrue(allowed)
            self.assertEqual(count, 0)

        # Giả lập đã tạo 1 trang trong 24h
        one_page = [{"name": "Page 1", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        with patch("fb_create_page.load_created_pages", return_value=one_page):
            allowed, count, msg = fb_create_page.can_create_page(max_per_day=2)
            self.assertTrue(allowed)
            self.assertEqual(count, 1)

        # Giả lập đã tạo 2 trang trong 24h -> Phải bị chặn
        two_pages = [
            {"name": "Page 1", "created_at": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")},
            {"name": "Page 2", "created_at": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")}
        ]
        with patch("fb_create_page.load_created_pages", return_value=two_pages):
            allowed, count, msg = fb_create_page.can_create_page(max_per_day=2)
            self.assertFalse(allowed)
            self.assertEqual(count, 2)
            self.assertIn("Tạm dừng để bảo vệ tài khoản an toàn", msg)

        # Trang cũ tạo hơn 24h trước không tính vào quota
        old_pages = [
            {"name": "Old Page", "created_at": (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")}
        ]
        with patch("fb_create_page.load_created_pages", return_value=old_pages):
            allowed, count, msg = fb_create_page.can_create_page(max_per_day=2)
            self.assertTrue(allowed)
            self.assertEqual(count, 0)

    def test_joined_groups_persistence(self):
        import fb_join_group
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir) / "joined_groups.json"
            with patch("fb_join_group.JOINED_GROUPS_FILE", str(temp_file)):
                self.assertEqual(fb_join_group.load_joined_groups(), [])
                test_records = [{"name": "Group A", "url": "https://facebook.com/groups/123", "joined_at": "2026-09-04 16:00:00"}]
                fb_join_group.save_joined_groups(test_records)
                loaded = fb_join_group.load_joined_groups()
                self.assertEqual(len(loaded), 1)
                self.assertEqual(loaded[0]["name"], "Group A")

    def test_allowed_commands_include_new_features(self):
        self.assertIn("join-group", server.ALLOWED_COMMANDS)
        self.assertIn("create-page", server.ALLOWED_COMMANDS)

    def test_settings_api(self):
        client = server.app.test_client()
        orig_config = server.SettingsRepository().get_config()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_config = Path(temp_dir) / "config.json"
                with patch("server.CONFIG_FILE", temp_config):
                    # Test GET default settings
                    res = client.get("/api/settings")
                    self.assertEqual(res.status_code, 200)
                    data = json.loads(res.data)
                    self.assertIn("gpm_api_url", data)
                    self.assertIn("delay_preset", data)
                    self.assertIn("gemini_api_key_configured", data)

                    # Test POST update settings
                    post_payload = {
                        "gpm_api_url": "http://127.0.0.1:20000",
                        "gemini_api_key": "AIzaSyTestKey1234567890",
                        "delay_preset": "test",
                        "delay_min": 10,
                        "delay_max": 20,
                        "auto_join_groups": True,
                        "group_keywords": "Test Group 1, Test Group 2"
                    }
                    res = client.post("/api/settings", json=post_payload)
                    self.assertEqual(res.status_code, 200)
                    resp_data = json.loads(res.data)
                    self.assertTrue(resp_data["success"])
                    self.assertEqual(resp_data["settings"]["gpm_api_url"], "http://127.0.0.1:20000")
                    self.assertEqual(resp_data["settings"]["delay_preset"], "test")

                    # Verify GET returns updated masked key
                    res = client.get("/api/settings")
                    data = json.loads(res.data)
                    self.assertEqual(data["gpm_api_url"], "http://127.0.0.1:20000")
                    self.assertTrue(data["gemini_api_key_configured"])
                    self.assertTrue(data["gemini_api_key_masked"].startswith("..."))
                    self.assertTrue(data["gemini_api_key_masked"].endswith("7890"))
                    self.assertTrue(data["auto_join_groups"])
                    self.assertEqual(data["group_keywords"], "Test Group 1, Test Group 2")
        finally:
            safe_restore = orig_config if "Test Group" not in orig_config.get("group_keywords", "") else {
                "gpm_api_url": "http://127.0.0.1:19995",
                "gemini_api_key": "",
                "delay_preset": "safe",
                "delay_min": 300,
                "delay_max": 600,
                "auto_join_groups": False,
                "group_keywords": "Homestay Huế, Du lịch Huế",
            }
            server.SettingsRepository().save_config(safe_restore)

    def test_click_post_publish_button_ignores_anonymous_toggle(self):
        from unittest.mock import MagicMock
        from utils import click_post_publish_button

        mock_page = MagicMock()
        mock_page.locator.return_value.first.is_visible.return_value = False
        mock_dialog = MagicMock()

        # Giả lập nút "Đăng ẩn danh" (top) và nút "Đăng" (bottom)
        anon_btn = MagicMock()
        anon_btn.is_visible.return_value = True
        anon_btn.inner_text.return_value = "Đăng ẩn danh"
        anon_btn.get_attribute.side_effect = lambda attr: "Đăng ẩn danh" if attr == "aria-label" else "false"

        real_post_btn = MagicMock()
        real_post_btn.is_visible.return_value = True
        real_post_btn.inner_text.return_value = "Đăng"
        real_post_btn.get_attribute.side_effect = lambda attr: "Đăng" if attr == "aria-label" else "false"

        # Giả lập locator của dialog
        buttons = [anon_btn, real_post_btn]
        mock_buttons_locator = MagicMock()
        mock_buttons_locator.count.return_value = 2
        mock_buttons_locator.nth.side_effect = lambda idx: buttons[idx]

        mock_dialog.is_visible.return_value = True
        def fake_locator(sel):
            loc = MagicMock()
            if "aria-label='đăng'" in sel.lower():
                loc.first = real_post_btn
            elif "div[role='button']" in sel:
                return mock_buttons_locator
            else:
                loc.first.is_visible.return_value = False
            return loc

        mock_dialog.locator.side_effect = fake_locator
        # Giả lập sau khi click dialog đóng lại
        visibility = [True, True, True, True, False]
        mock_dialog.is_visible.side_effect = lambda: visibility.pop(0) if visibility else False

        result = click_post_publish_button(mock_page, mock_dialog)
        self.assertTrue(result)
        anon_btn.click.assert_not_called()
        real_post_btn.click.assert_called_once()

    def test_joined_groups_api_lifecycle(self):
        client = server.app.test_client()
        with tempfile.TemporaryDirectory() as directory:
            test_file = str(Path(directory) / "joined_groups.json")
            with patch.object(server, "JOINED_GROUPS_FILE", test_file):
                # Empty initially
                res = client.get("/api/joined-groups")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.get_json(), [])

                # Save sample groups
                sample_data = [{"group_name": "Homestay Huế", "keyword": "Huế", "account_id": "M14"}]
                with open(test_file, "w", encoding="utf-8") as f:
                    json.dump(sample_data, f)

                res = client.get("/api/joined-groups")
                self.assertEqual(res.status_code, 200)
                self.assertEqual(len(res.get_json()), 1)
                self.assertEqual(res.get_json()[0]["group_name"], "Homestay Huế")

                # Delete clears file
                res_del = client.delete("/api/joined-groups")
                self.assertEqual(res_del.status_code, 200)
                self.assertEqual(res_del.get_json()["status"], "cleared")

                res_after = client.get("/api/joined-groups")
                self.assertEqual(res_after.get_json(), [])

    def test_record_posted_link_records_status_and_target(self):
        from utils import record_posted_link, POSTED_LINKS_FILE
        with tempfile.TemporaryDirectory() as directory:
            test_links_file = str(Path(directory) / "posted_links.json")
            with patch("utils.POSTED_LINKS_FILE", test_links_file):
                record_posted_link(
                    target="https://www.facebook.com/groups/hue/",
                    post_url="https://www.facebook.com/groups/hue/",
                    content="Bài viết chờ duyệt",
                    account_id="M14",
                    status="Đang chờ admin duyệt"
                )
                with open(test_links_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["status"], "Đang chờ admin duyệt")
                self.assertEqual(records[0]["account_id"], "M14")

    def test_api_run_join_group_with_rotate_and_single_account(self):
        client = server.app.test_client()
        mock_accounts = [
            {"id": "acc-1", "name": "Nick 1", "type": "gpm"},
            {"id": "acc-2", "name": "Nick 2", "type": "gpm"}
        ]

        class DummyProcess:
            def __init__(self):
                self.stdout = io.StringIO("Mock join group output\n")
            def wait(self):
                return 0

        with patch("server.load_accounts", return_value=mock_accounts), \
             patch("server.record_profile_activity") as mock_record, \
             patch("time.sleep", return_value=None):
            
            with patch("subprocess.Popen", return_value=DummyProcess()):
                # Test 1: rotate accounts
                res_rotate = client.post("/api/run", json={
                    "command": "join-group",
                    "accountId": "__rotate__",
                    "mode": "keywords",
                    "keywords": "Homestay Huế, Review Huế",
                    "limit": 1
                })
                self.assertEqual(res_rotate.status_code, 200)
                text_rotate = res_rotate.get_data(as_text=True)
                self.assertNotIn("500 Internal Server Error", text_rotate)
                self.assertIn("RUN_RESULT:finished", text_rotate)

                # Test 2: URLs mode with direct account
                res_url = client.post("/api/run", json={
                    "command": "join-group",
                    "accountId": "acc-1",
                    "mode": "urls",
                    "urls": "https://www.facebook.com/groups/hue1\nhttps://www.facebook.com/groups/hue2",
                    "limit": 2
                })
                self.assertEqual(res_url.status_code, 200)
                text_url = res_url.get_data(as_text=True)
                self.assertNotIn("500 Internal Server Error", text_url)
                self.assertIn("RUN_RESULT:finished", text_url)


class V604QueueAndHistoryTests(unittest.TestCase):
    def test_queue_active_filter_hides_cancelled_and_limits(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "QUEUE_FILE", str(Path(directory) / "queue.json")):
            items = [
                {"id":"1","target":"a","content":"x","state":"approved","updated_at":"2026-01-01T00:00:03"},
                {"id":"2","target":"b","content":"x","state":"processing","updated_at":"2026-01-01T00:00:02"},
                {"id":"3","target":"c","content":"x","state":"cancelled","updated_at":"2026-01-01T00:00:01"},
            ]
            Path(server.QUEUE_FILE).write_text(json.dumps(items), encoding="utf-8")
            res = server.app.test_client().get("/api/queue?active=1&limit=2")
            self.assertEqual(res.status_code, 200)
            payload = res.get_json()
            self.assertEqual(len(payload), 2)
            self.assertNotIn("cancelled", {x["state"] for x in payload})

    def test_posted_link_reconciles_unverified_record(self):
        from db import init_db
        from repositories.activity_repo import ActivityRepository
        with tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / "app.db"
            init_db(db_file)
            repo = ActivityRepository(db_file)
            target = "https://facebook.com/groups/example"
            content = "Same exact post content"
            repo.record_posted_link(target, target, content, "unverified", "M4", "unverified", "group", "submitted_unverified")
            repo.record_posted_link(target, target + "/posts/999", content, "Đã xuất bản", "M4", "Đã xuất bản", "post", "published")
            rows = repo.list_posted_links()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["publish_state"], "published")
            self.assertTrue(rows[0]["url"].endswith("/posts/999"))

    def test_permalink_group_key_guard(self):
        from utils import _group_key_from_url
        self.assertEqual(_group_key_from_url("https://facebook.com/groups/hue/posts/123"), "hue")
        self.assertNotEqual(_group_key_from_url("https://facebook.com/groups/other/posts/123"), "hue")


class Phase1ArchitectureTests(unittest.TestCase):
    def test_paths_and_version(self):
        from paths import get_version, DATA_DIR, UPLOAD_DIR, BACKUP_DIR, LOG_DIR
        self.assertEqual(get_version(), "6.1.32")
        self.assertTrue(DATA_DIR.exists())
        self.assertTrue(UPLOAD_DIR.exists())
        self.assertTrue(BACKUP_DIR.exists())
        self.assertTrue(LOG_DIR.exists())

    def test_sqlite_wal_mode_and_foreign_keys(self):
        from db import connect_db, init_db
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_db = Path(temp_dir) / "test.db"
            init_db(temp_db)
            conn = connect_db(temp_db)
            try:
                journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
                fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                self.assertEqual(journal.lower(), "wal")
                self.assertEqual(fk, 1)
            finally:
                conn.close()

    def test_repositories_crud(self):
        from db import init_db
        from repositories.account_repo import AccountRepository
        from repositories.settings_repo import SettingsRepository
        from repositories.group_repo import GroupRepository
        from repositories.campaign_repo import CampaignRepository
        from repositories.activity_repo import ActivityRepository

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_db = Path(temp_dir) / "test.db"
            init_db(temp_db)

            # Account repo
            acc_repo = AccountRepository(db_file=str(temp_db))
            acc_repo.save_account({"id": "acc-test", "name": "Test Acc", "type": "gpm"})
            self.assertEqual(len(acc_repo.list_accounts()), 1)
            self.assertEqual(acc_repo.get_account("acc-test")["name"], "Test Acc")

            # Settings repo
            settings_repo = SettingsRepository(db_file=str(temp_db))
            settings_repo.save_config({"gemini_api_key": "secret-123"})
            self.assertEqual(settings_repo.get_config().get("gemini_api_key"), "secret-123")

            # Group repo
            group_repo = GroupRepository(db_file=str(temp_db))
            group_repo.save_groups([{"id": "g-1", "name": "Hue Group", "url": "https://fb.com/g/1"}])
            self.assertEqual(len(group_repo.list_groups()), 1)
            group_repo.save_joined_groups([{"group_name": "Hue 1", "keyword": "Homestay", "url": "https://fb.com/g/1"}])
            self.assertEqual(len(group_repo.list_joined_groups()), 1)

            # Campaign repo
            campaign_repo = CampaignRepository(db_file=str(temp_db))
            campaign_repo.save_campaigns([{"id": "camp-1", "name": "Campaign 1", "status": "active"}])
            self.assertEqual(len(campaign_repo.list_campaigns()), 1)

            # Activity repo
            act_repo = ActivityRepository(db_file=str(temp_db))
            act_repo.record_activity("acc-test", "join-group", target="Hue Group")
            self.assertEqual(len(act_repo.list_activities()), 1)
            act_repo.record_posted_link("https://fb.com/g/1", "https://fb.com/p/1", "Post Content")
            self.assertEqual(len(act_repo.list_posted_links()), 1)

    def test_api_backup_database_endpoint(self):
        client = server.app.test_client()
        res = client.post("/api/backup")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertTrue(Path(data.get("backup_file")).exists())


class Phase2JobManagerTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    def test_job_submission_and_query_endpoints(self):
        # Endpoint contract uses an allowed production command; execution is mocked.
        fake_id = "jobtest123"
        fake_job = {"id": fake_id, "command": "auth", "state": "queued", "payload": {}}
        with patch("api.jobs.job_manager.submit_job", return_value=fake_id), \
             patch("api.jobs.job_manager.get_job", return_value=fake_job), \
             patch("api.jobs.job_manager.list_jobs", return_value=[fake_job]), \
             patch("api.jobs.job_manager.get_job_logs", return_value="hello"), \
             patch("api.jobs.job_manager.cancel_job", return_value=True):
            res = self.client.post("/api/jobs", json={"command": "auth", "accountId": "test-acc-1"})
            self.assertEqual(res.status_code, 201)
            self.assertEqual(res.get_json()["job_id"], fake_id)

            res_get = self.client.get(f"/api/jobs/{fake_id}")
            self.assertEqual(res_get.status_code, 200)
            self.assertEqual(res_get.get_json()["job"]["command"], "auth")

            res_list = self.client.get("/api/jobs")
            self.assertEqual(res_list.status_code, 200)
            self.assertEqual(len(res_list.get_json()["jobs"]), 1)

            res_logs = self.client.get(f"/api/jobs/{fake_id}/logs")
            self.assertEqual(res_logs.status_code, 200)
            self.assertEqual(res_logs.get_json()["logs"], "hello")

            res_cancel = self.client.post(f"/api/jobs/{fake_id}/cancel")
            self.assertEqual(res_cancel.status_code, 200)

    def test_cancel_active_endpoint_when_no_active_job(self):
        res = self.client.post("/api/cancel")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("success", data)


class FacebookPostUrlAndExitCodeTests(unittest.TestCase):
    def test_clean_facebook_post_url_permalink_preserves_id(self):
        from utils import clean_facebook_post_url
        raw_url = "https://www.facebook.com/permalink.php?story_fbid=123456789&id=987654321&__cft__[0]=AZX&__tn__=%2CO%2CP-R"
        cleaned = clean_facebook_post_url(raw_url)
        self.assertIn("story_fbid=123456789", cleaned)
        self.assertIn("id=987654321", cleaned)
        self.assertNotIn("__cft__", cleaned)
        self.assertNotIn("__tn__", cleaned)

    def test_clean_facebook_post_url_standard_posts_strips_query(self):
        from utils import clean_facebook_post_url
        raw_url = "https://www.facebook.com/groups/homestayhue/posts/101010101/?mibextid=6aamW6"
        cleaned = clean_facebook_post_url(raw_url)
        self.assertEqual(cleaned, "https://www.facebook.com/groups/homestayhue/posts/101010101/")

    def test_clean_facebook_post_url_relative_link_prepends_domain(self):
        from utils import clean_facebook_post_url
        raw_url = "/groups/homestayhue/posts/101010101/"
        cleaned = clean_facebook_post_url(raw_url)
        self.assertTrue(cleaned.startswith("https://www.facebook.com/"))


class AuditReliabilityV581Tests(unittest.TestCase):
    def test_action_result_contract_and_bool_behavior(self):
        from utils import ActionResult
        res_ok = ActionResult(success=True, code="SUCCESS", state="published", target_url="https://fb.com/1", result_url="https://fb.com/posts/1", url_type="post")
        res_fail = ActionResult(success=False, code="PUBLISH_FAILED", message="Blocked", target_url="https://fb.com/1")

        self.assertTrue(bool(res_ok))
        self.assertFalse(bool(res_fail))
        self.assertTrue(res_ok)
        self.assertFalse(res_fail)

        d = res_ok.to_dict()
        self.assertEqual(d["code"], "SUCCESS")
        self.assertEqual(d["state"], "published")
        self.assertEqual(d["url_type"], "post")
        self.assertEqual(d["result_url"], "https://fb.com/posts/1")

    def test_text_similarity_match(self):
        from utils import text_similarity_match
        draft = "Homestay Huế siêu đẹp view sông Hương giá chỉ 350k/đêm phòng đầy đủ tiện nghi"
        feed_text = "Homestay Huế siêu đẹp view sông Hương giá chỉ 350k/đêm phòng đầy đủ tiện nghi\nĐăng bởi Nguyễn Văn A 5 phút trước"
        unrelated = "Bán đất mặt tiền đường Nguyễn Huệ diện tích 100m2 sổ đỏ chính chủ"

        self.assertTrue(text_similarity_match(draft, feed_text))
        self.assertFalse(text_similarity_match(draft, unrelated))

    def test_job_repo_mark_running_race_condition(self):
        from repositories.job_repo import JobRepository
        repo = JobRepository()
        job_id = "test-race-job-1"
        repo.create_job({
            "id": job_id,
            "command": "group",
            "state": "queued",
            "payload": {"target": "hue"},
            "created_at": "2026-09-05T12:00:00Z"
        })

        # When queued, mark_running must succeed
        self.assertTrue(repo.mark_running(job_id, pid=1234))
        job = repo.get_job(job_id)
        self.assertEqual(job["state"], "running")

        # When job is cancelled, mark_finished marks it cancelled
        repo.mark_finished(job_id, state="cancelled", error_message="User stopped")
        job = repo.get_job(job_id)
        self.assertEqual(job["state"], "cancelled")

        # Calling mark_running on cancelled job must return False and stay cancelled
        self.assertFalse(repo.mark_running(job_id, pid=5678))
        job = repo.get_job(job_id)
        self.assertEqual(job["state"], "cancelled")

    def test_page_repository_and_rate_limit(self):
        from repositories.page_repo import PageRepository
        repo = PageRepository()
        acc = "test-page-acc-audit"

        repo.add_created_page("Homestay Test 1", category="Blogger", page_url="https://fb.com/page1", account_id=acc)
        self.assertGreaterEqual(repo.count_recent_pages(acc, hours=24), 1)

        pages = repo.list_created_pages(acc)
        self.assertGreaterEqual(len(pages), 1)
        self.assertEqual(pages[0]["page_name"], "Homestay Test 1")
        self.assertEqual(pages[0]["account_id"], acc)

    def test_record_posted_link_updates_within_60s(self):
        from utils import record_posted_link
        import tempfile
        import json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir) / "posted_links.json"
            with patch("utils.POSTED_LINKS_FILE", str(temp_file)):
                record_posted_link(target="https://fb.com/groups/hue-test", post_url="https://fb.com/groups/hue-test", url_type="group", publish_state="pending")
                record_posted_link(target="https://fb.com/groups/hue-test", post_url="https://fb.com/groups/hue-test/posts/999", url_type="post", publish_state="published")

                with open(temp_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
                self.assertGreaterEqual(len(items), 1)
                self.assertEqual(items[0]["url_type"], "post")
                self.assertEqual(items[0]["publish_state"], "published")


class AuditV582RegressionTests(unittest.TestCase):
    """Regression suite covering all 36 audit findings for v5.8.2 correctness release."""

    def test_post_submitted_unverified_semantic_failure(self):
        from utils import scrape_post_link, ActionResult
        class FakeLocator:
            def all(self):
                return []
        class FakePage:
            url = "https://facebook.com/groups/hue-audit"
            def locator(self, *args, **kwargs):
                return FakeLocator()

        # Without permalink or pending confirmation, result must be success=False
        res = scrape_post_link(FakePage(), target="https://facebook.com/groups/hue-audit", content="Hello Hue")
        self.assertFalse(res.success)
        self.assertEqual(res.code, "POST_SUBMITTED_UNVERIFIED")
        self.assertEqual(res.state, "submitted_unverified")

    def test_membership_uncertainty_never_claims_post_submission(self):
        from services.job_executor import is_post_pending, is_submit_uncertain

        membership_unknown = {"state": "unverified", "code": "GROUP_MEMBERSHIP_UNVERIFIED"}
        membership_pending = {"state": "pending", "code": "GROUP_MEMBERSHIP_PENDING"}
        self.assertFalse(is_submit_uncertain(membership_unknown))
        self.assertFalse(is_submit_uncertain(membership_pending))
        self.assertFalse(is_post_pending(membership_pending))
        self.assertTrue(is_submit_uncertain({
            "state": "submitted_unverified", "code": "POST_SUBMITTED_UNVERIFIED"
        }))
        self.assertTrue(is_post_pending({"state": "pending", "code": "POST_PENDING"}))

    def test_local_spinner_resolves_spintax_and_reports_provenance(self):
        from ai_spinner import generate_unique_variant_with_evidence

        result = generate_unique_variant_with_evidence(
            "{Xin chào cả nhà|Chào mọi người}! Nội dung thật.", api_key=""
        )
        self.assertTrue(result["changed"])
        self.assertEqual(result["mode"], "local_fallback")
        self.assertNotIn("{", result["content"])
        self.assertNotIn("|", result["content"])

    def test_spinner_does_not_claim_change_for_plain_content(self):
        from ai_spinner import generate_unique_variant_with_evidence

        result = generate_unique_variant_with_evidence("Nội dung giữ nguyên.", api_key="")
        self.assertFalse(result["changed"])
        self.assertEqual(result["mode"], "unchanged")

    def test_click_post_publish_button_dialog_remains_open(self):
        from utils import click_post_publish_button
        class FakeBtn:
            def is_visible(self, timeout=1000):
                return True
            def is_enabled(self):
                return True
            def get_attribute(self, attr):
                if attr == "aria-label":
                    return "Đăng"
                return "false"
            def inner_text(self):
                return "Đăng"
            def scroll_into_view_if_needed(self, timeout=1000):
                pass
            def click(self, force=True, timeout=1000):
                pass
            def evaluate(self, expr):
                pass

        class FakeSubLoc:
            def __init__(self, items=None):
                self._items = items or [FakeBtn()]
            def count(self):
                return len(self._items)
            def nth(self, idx):
                return self._items[idx]
            def all(self):
                return self._items
            @property
            def first(self):
                return self._items[0] if self._items else FakeBtn()
            @property
            def last(self):
                return self._items[-1] if self._items else FakeBtn()
            def filter(self, *a, **kw):
                return self

        class FakeDialog:
            def is_visible(self, timeout=1000):
                # Dialog remains open indefinitely
                return True
            def locator(self, selector, **kw):
                return FakeSubLoc()
            def get_by_role(self, role, **kw):
                return FakeSubLoc()
            def inner_text(self):
                return "Đang tạo bài viết..."

        class FakePage:
            def locator(self, selector, **kw):
                return FakeSubLoc([FakeDialog()])

        # Must return False if dialog does not close within timeout
        with patch("time.sleep", return_value=None):
            res = click_post_publish_button(FakePage(), dialog=FakeDialog())
            self.assertFalse(res)

    def test_normalize_target_url_canonical_equality(self):
        from utils import normalize_target_url
        norm_a = normalize_target_url("https://www.facebook.com/groups/123/?ref=share")
        norm_b = normalize_target_url("http://m.facebook.com/groups/123/")
        norm_c = normalize_target_url("https://facebook.com/groups/123")
        norm_d = normalize_target_url("https://facebook.com/groups/1234")

        self.assertEqual(norm_a, "https://facebook.com/groups/123")
        self.assertEqual(norm_b, "https://facebook.com/groups/123")
        self.assertEqual(norm_a, norm_b)
        self.assertEqual(norm_b, norm_c)
        # Substring collision prevention (123 vs 1234)
        self.assertNotEqual(norm_c, norm_d)

    def test_is_recently_posted_blocks_unverified_to_prevent_duplicate(self):
        import uuid
        from utils import is_recently_posted, record_posted_link
        target = f"https://facebook.com/groups/audit-retry-{uuid.uuid4().hex[:8]}"
        
        # Unverified may already exist on Facebook, so auto-retry must be blocked.
        record_posted_link(target, target, "Draft post", url_type="group", publish_state="submitted_unverified")
        recent, _, _ = is_recently_posted(target, hours=24.0)
        self.assertTrue(recent)

        # When published, retry IS blocked
        record_posted_link(target, f"{target}/posts/888", "Published post", url_type="post", publish_state="published")
        recent_pub, hours_ago, _ = is_recently_posted(target, hours=24.0)
        self.assertTrue(recent_pub)
        self.assertGreaterEqual(hours_ago, 0.0)

    def test_text_similarity_match_multi_checkpoint(self):
        from utils import text_similarity_match
        post_a = "Chào mọi người trong nhóm! Mình có căn homestay xinh xắn tại thành phố Huế cần cho thuê theo ngày giá hạt dẻ chỉ 350k."
        post_b = "Chào mọi người trong nhóm! Mình đang cần tìm mua xe máy cũ biển số 75 còn chạy tốt giá tầm 5 triệu để đi làm."
        
        # Both share same first 30 chars ("Chào mọi người trong nhóm! Mình ") but different middle/suffix
        self.assertFalse(text_similarity_match(post_a, post_b))

        # Real post with slight whitespace / formatting variation must match
        post_a_variant = "Chào mọi người trong nhóm!\n\nMình có căn homestay xinh xắn tại thành phố Huế cần cho thuê theo ngày giá hạt dẻ chỉ 350k."
        self.assertTrue(text_similarity_match(post_a, post_a_variant))

    def test_media_attach_failure_aborts_posting(self):
        from unittest.mock import MagicMock, patch
        from fb_group import post_to_group

        mock_p = MagicMock()
        mock_page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.count.return_value = 1
        mock_loc.is_visible.return_value = True
        mock_loc.get_attribute.return_value = ""
        mock_loc.first = mock_loc
        mock_loc.last = mock_loc
        mock_loc.nth.return_value = mock_loc
        mock_loc.filter.return_value = mock_loc
        mock_page.locator.return_value = mock_loc
        mock_page.get_by_text.return_value = mock_loc
        mock_p.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page

        with patch("fb_group.sync_playwright") as mock_sp, \
             patch("fb_group.find_post_composer_textbox", return_value=mock_loc), \
             patch("fb_group.navigate_facebook_surface", return_value=True), \
             patch("fb_group._ensure_group_membership", return_value="joined"), \
             patch("fb_group.attach_image_to_composer", return_value=False), \
             patch("fb_group.is_recently_posted", return_value=(False, 0, None)), \
             patch("time.sleep", return_value=None):
            mock_sp.return_value.__enter__.return_value = mock_p
            res = post_to_group("https://facebook.com/groups/test-attach", "Hello", image_path="photo.jpg")
            self.assertFalse(res.success)
            self.assertEqual(res.code, "MEDIA_ATTACH_FAILED")

    def test_comment_on_post_requires_dom_verification(self):
        from unittest.mock import MagicMock, patch
        from fb_comment import comment_on_post
        
        mock_p = MagicMock()
        mock_page = MagicMock()
        mock_page.url = "https://www.facebook.com/groups/1/posts/2"
        mock_input = MagicMock()
        mock_input.is_visible.return_value = True
        mock_input.inner_text.return_value = ""
        mock_spam = MagicMock()
        mock_spam.is_visible.return_value = False
        mock_page.wait_for_function.side_effect = Exception("Timeout waiting for comment")
        
        def locator_mock(sel, *a, **kw):
            if "tạm thời" in sel or "hạn chế" in sel or "something went wrong" in sel:
                m = MagicMock()
                m.first = mock_spam
                return m
            elif "textbox" in sel or "data-lexical-editor" in sel or "contenteditable" in sel or "bình luận" in sel or "comment" in sel:
                m = MagicMock()
                m.count.return_value = 1
                m.nth.return_value = mock_input
                m.first = mock_input
                return m
            else:
                m = MagicMock()
                m.is_visible.return_value = False
                m.first = m
                m.filter.return_value = m
                m.count.return_value = 0
                return m
        
        mock_page.locator.side_effect = locator_mock
        mock_p.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page

        with patch("fb_comment.sync_playwright") as mock_sp, patch("time.sleep", return_value=None):
            mock_sp.return_value.__enter__.return_value = mock_p
            res = comment_on_post("https://facebook.com/groups/1/posts/2", "Test comment")
            self.assertFalse(res.success)
            self.assertIn(res.code, {"POST_IDENTITY_NOT_FOUND", "COMMENT_UNVERIFIED"})

    def test_comment_on_list_returns_aggregate_action_result(self):
        from fb_comment import comment_on_list
        from utils import ActionResult
        # 1 success, 1 fail
        responses = [
            ActionResult(success=True, code="SUCCESS", message="Commented"),
            ActionResult(success=False, code="COMMENT_UNVERIFIED", message="Failed"),
        ]
        with patch("fb_comment.comment_on_post", side_effect=responses):
            res = comment_on_list(["https://fb.com/p/1", "https://fb.com/p/2"], "Nice post!", min_delay=0, max_delay=0)
            self.assertFalse(res.success)
            self.assertEqual(res.code, "COMMENT_LIST_PARTIAL_FAIL")
            self.assertEqual(res.data["total"], 2)
            self.assertEqual(res.data["success"], 1)
            self.assertEqual(res.data["failed"], 1)

    def test_process_runner_cancel_race_prepare_job(self):
        from services.process_runner import ProcessRunner
        runner = ProcessRunner()
        job_id = "test-race-prepare"
        runner.prepare_job(job_id)
        self.assertFalse(runner.is_cancelled(job_id))
        runner.cancel(job_id)
        self.assertTrue(runner.is_cancelled(job_id))
        # Running sync on pre-cancelled job must abort with -1
        ret = runner.run_command_sync(["cmd.exe", "/c", "echo", "hi"], job_id=job_id)
        self.assertEqual(ret, -1)

    def test_process_runner_cleanup_job(self):
        from services.process_runner import ProcessRunner
        runner = ProcessRunner()
        job_id = "test-cleanup-runner"
        runner.prepare_job(job_id)
        runner.add_listener(job_id, lambda line: None)
        runner.cleanup_job(job_id)
        self.assertNotIn(job_id, runner._listeners)
        self.assertNotIn(job_id, runner._cancellation_requested)

    def test_process_runner_get_log_path_path_traversal_prevention(self):
        from services.process_runner import ProcessRunner
        runner = ProcessRunner()
        with self.assertRaises(ValueError):
            runner.get_log_path("../../etc/passwd")
        with self.assertRaises(ValueError):
            runner.get_log_path("job/with/forward/slashes")
        with self.assertRaises(ValueError):
            runner.get_log_path("job\\with\\backslashes")
        # Valid alphanumeric / hyphen ID must work
        valid_path = runner.get_log_path("valid-job-id-123")
        self.assertTrue(str(valid_path).endswith("valid-job-id-123.log"))

    def test_job_repo_mark_finished_state_machine_guard(self):
        from repositories.job_repo import JobRepository
        repo = JobRepository()
        job_id = "test-terminal-guard-audit"
        repo.create_job({"id": job_id, "state": "queued"})
        repo.mark_running(job_id)
        repo.mark_finished(job_id, state="cancelled")
        self.assertEqual(repo.get_job(job_id)["state"], "cancelled")
        
        # Overwrite attempt with success/failed must be rejected
        ret = repo.mark_finished(job_id, state="success")
        self.assertFalse(ret)
        self.assertEqual(repo.get_job(job_id)["state"], "cancelled")

    def test_job_repo_reconcile_running_and_queued_jobs(self):
        from repositories.job_repo import JobRepository
        repo = JobRepository()
        q_id = "test-zombie-queued"
        r_id = "test-zombie-running"
        repo.create_job({"id": q_id, "state": "queued"})
        repo.create_job({"id": r_id, "state": "running"})

        reconciled = repo.reconcile_running_jobs()
        self.assertGreaterEqual(reconciled, 1)
        self.assertEqual(repo.get_job(q_id)["state"], "queued")
        self.assertEqual(repo.get_job(r_id)["state"], "interrupted")

    def test_job_manager_cancel_terminal_job_guard(self):
        from services.job_manager import JobManager
        jm = JobManager()
        job_id = "test-terminal-cancel-guard"
        jm.job_repo.create_job({"id": job_id, "state": "success"})
        self.assertFalse(jm.cancel_job(job_id))

    def test_job_repo_payload_redaction(self):
        from repositories.job_repo import JobRepository
        repo = JobRepository()
        job_id = "test-secret-redact"
        repo.create_job({
            "id": job_id,
            "state": "queued",
            "payload": {
                "target": "hue",
                "geminiApiKey": "AIzaSySecretKey999",
                "pageAccessToken": "EAASecretToken123",
                "password": "MySuperSecretPassword!"
            }
        })
        saved = repo.get_job(job_id)
        self.assertEqual(saved["payload"]["geminiApiKey"], "***REDACTED***")
        self.assertEqual(saved["payload"]["pageAccessToken"], "***REDACTED***")
        self.assertEqual(saved["payload"]["password"], "***REDACTED***")

    def test_vault_api_redacts_passwords(self):
        client = server.app.test_client()
        res = client.get("/api/vault")
        self.assertEqual(res.status_code, 200)
        for item in res.get_json():
            self.assertNotIn("password", item)
            self.assertIn("has_password", item)

    def test_posted_links_api_reads_from_sqlite(self):
        from repositories.activity_repo import ActivityRepository
        repo = ActivityRepository()
        repo.record_posted_link(
            target="https://facebook.com/groups/sql-group",
            post_url="https://facebook.com/groups/sql-group/posts/999888",
            content="SQL post test",
            url_type="post",
            publish_state="published"
        )
        client = server.app.test_client()
        res = client.get("/api/posted-links")
        self.assertEqual(res.status_code, 200)
        urls = [item.get("url") for item in res.get_json()]
        self.assertIn("https://facebook.com/groups/sql-group/posts/999888", urls)

    def test_photos_list_directory_traversal_prevention(self):
        client = server.app.test_client()
        # Unauthorized traversal path outside allowed dirs must return 403
        res = client.get("/api/photos/list?folder=C:/Windows/System32")
        self.assertEqual(res.status_code, 403)

    def test_page_config_masks_short_tokens(self):
        client = server.app.test_client()
        with patch.object(server, "load_config", return_value={"page_access_token": "12345"}):
            res = client.get("/api/page/config")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data["token_masked"], "...2345")

    def test_group_join_button_confirmation_rejects_unknown_state(self):
        from fb_join_group import search_and_join_groups
        class FakeAfterClickElement:
            def is_visible(self, *a, **kw): return True
            def inner_text(self): return "Yêu cầu xác minh danh tính"
            def get_attribute(self, attr): return ""

        class FakePage:
            def set_default_timeout(self, *a, **kw): pass
            def goto(self, *a, **kw): pass
            def locator(self, *a, **kw):
                class SubLoc:
                    def all(self): return [FakeAfterClickElement()]
                    def first(self): return FakeAfterClickElement()
                    def count(self): return 0
                    def is_visible(self, *a, **kw): return False
                return SubLoc()

        with patch("fb_join_group.sync_playwright"):
            cnt = search_and_join_groups("https://facebook.com/groups/unknown-state", max_groups=1)
            self.assertEqual(cnt, 0)

    def test_interact_with_group_feed_safe(self):
        from fb_join_group import interact_with_group_feed
        class MockArticle:
            def scroll_into_view_if_needed(self): pass
            def locator(self, sel):
                class MockBtn:
                    def filter(self, *a, **kw): return self
                    def first(self): return self
                    def is_visible(self, *a, **kw): return True
                    def is_enabled(self): return True
                    def click(self): pass
                return MockBtn()

        class MockPage:
            def evaluate(self, code): pass
            def locator(self, sel):
                class MockLoc:
                    def all(self): return [MockArticle()]
                return MockLoc()
            @property
            def keyboard(self):
                class MockKB:
                    def press(self, key): pass
                return MockKB()

        # Test execution does not throw
        with patch("time.sleep", return_value=None), patch("fb_join_group.safe_mouse_wheel"):
            interact_with_group_feed(MockPage())

    def test_join_group_chunks_urls_max_two_per_profile(self):
        import server
        client = server.app.test_client()
        mock_accounts = [
            {"id": "acc-1", "name": "Profile 1", "type": "local"},
            {"id": "acc-2", "name": "Profile 2", "type": "local"}
        ]
        with patch("services.job_executor.load_accounts", return_value=mock_accounts), \
             patch("services.job_executor.record_profile_activity"), \
             patch("time.sleep", return_value=None), \
             patch("subprocess.Popen") as mock_popen:
            class DummyProc:
                def __init__(self):
                    self.stdout = io.StringIO("Batch completed\n")
                def poll(self): return 0
                def wait(self, timeout=None): return 0
                def kill(self): pass
            mock_popen.side_effect = lambda *a, **kw: DummyProc()

            res = client.post("/api/run", json={
                "command": "join-group",
                "accountId": "__rotate__",
                "mode": "urls",
                "urls": "https://fb.com/g/1\nhttps://fb.com/g/2\nhttps://fb.com/g/3\nhttps://fb.com/g/4",
                "limit": 2
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_data(as_text=True)
            self.assertIn("RUN_RESULT:finished", data)
            # Profile-first invariant: both selected profiles run independently; each child receives --limit 2.
            self.assertEqual(mock_popen.call_count, 2)
            for call in mock_popen.call_args_list:
                args = call.args[0]
                self.assertIn("--limit", args)
                self.assertEqual(args[args.index("--limit") + 1], "2")


if __name__ == "__main__":
    unittest.main()





class V601RegressionTests(unittest.TestCase):
    def test_mutable_runtime_paths_live_under_data_dir(self):
        from paths import DATA_DIR
        for value in (server.CONFIG_FILE, server.QUEUE_FILE, server.CAMPAIGNS_FILE, server.ACTIVITY_LOG_FILE, server.POSTED_LINKS_FILE, server.JOINED_GROUPS_FILE):
            self.assertTrue(Path(value).resolve().is_relative_to(DATA_DIR.resolve()))

    def test_gemini_default_model_and_api_key_header(self):
        import ai_spinner
        self.assertEqual(ai_spinner.GEMINI_MODEL, "gemini-3.6-flash")
        captured = {}
        def fake(req, timeout=20, attempts=3):
            captured["url"] = req.full_url
            captured["key"] = req.headers.get("X-goog-api-key") or req.headers.get("x-goog-api-key")
            return {"candidates":[{"content":{"parts":[{"text":"Homestay Huế mới. Hotline: 0905555317. Giá 350k/đêm. https://example.com"}]}}]}
        original = "Homestay Huế. Hotline: 0905555317. Giá 350k/đêm. https://example.com"
        with patch("ai_spinner._urlopen_json", side_effect=fake):
            out = ai_spinner.spin_content_gemini(original, "secret-api-key-123")
        self.assertIn("gemini-3.6-flash:generateContent", captured["url"])
        self.assertNotIn("secret-api-key-123", captured["url"])
        self.assertEqual(captured["key"], "secret-api-key-123")
        self.assertIn("0905555317", out)

    def test_spinner_accepts_phone_formatting_but_rejects_changed_digits(self):
        import ai_spinner

        original = "Hotline: 0905 555 317. Giá 350k/đêm."
        self.assertEqual(ai_spinner.extract_core_info(original)["phones"], ["0905 555 317"])
        self.assertTrue(ai_spinner._preserves_core_info(
            original, "Giá 350k/đêm. Hotline: 0905.555.317."
        ))
        self.assertFalse(ai_spinner._preserves_core_info(
            original, "Giá 350k/đêm. Hotline: 0905.555.318."
        ))
        self.assertFalse(ai_spinner._preserves_core_info(
            original, "Giá 350k/đêm. Hotline: 0905.555.317, cách trung tâm 5 phút."
        ))

    def test_spinner_rejects_numbers_not_present_in_source(self):
        import ai_spinner

        original = "Bên mình còn phòng homestay xinh xắn tại TP Huế. Hotline: 0905 555 317."
        gemini_umee = "Phòng SH44 Manor Crown 62 Tố Hữu Huế, máy chiếu 100 inch, 24/7. Hotline: 0905 555 317."
        self.assertFalse(ai_spinner._preserves_core_info(original, gemini_umee, brand_key="umee"))
        gemini_lacasa = "Homestay số 3 kiệt 17 Trần Phú TP Huế, dorm 4 giường. Hotline: 0905 555 317."
        self.assertFalse(ai_spinner._preserves_core_info(original, gemini_lacasa, brand_key="lacasa"))

    def test_gemini_falls_back_only_when_model_is_unavailable(self):
        import urllib.error
        import ai_spinner

        called = []
        def fake(req, timeout=20, attempts=3):
            called.append(req.full_url)
            if len(called) == 1:
                raise urllib.error.HTTPError(req.full_url, 404, "not found", {}, None)
            return {"candidates":[{"content":{"parts":[{"text":"Hotline 0905-555-317"}]}}]}

        with patch.object(ai_spinner, "GEMINI_MODEL", "missing-model"), \
             patch.object(ai_spinner, "GEMINI_FALLBACK_MODELS", ("gemini-3.6-flash",)), \
             patch("ai_spinner._urlopen_json", side_effect=fake):
            text, model = ai_spinner.spin_content_gemini_with_model(
                "Hotline 0905 555 317", "secret-api-key-123"
            )
        self.assertEqual(model, "gemini-3.6-flash")
        self.assertIn("0905-555-317", text)
        self.assertEqual(len(called), 2)

    def test_local_comment_fallback_never_invents_promotional_facts(self):
        import ai_spinner

        original = "{Xin chào|Chào bạn}, mình cần hỏi phòng."
        with patch("ai_spinner.random.choice", side_effect=lambda values: values[0]):
            result = ai_spinner.spin_comment(original, api_key="")
        self.assertEqual(result, "Xin chào, mình cần hỏi phòng.")
        self.assertNotIn("Sông Hương", result)
        self.assertNotIn("ưu đãi", result)

    def test_build_reads_version_dynamically(self):
        script = Path("BUILD_PORTABLE.ps1").read_text(encoding="utf-8")
        self.assertIn("Get-Content (Join-Path $root 'VERSION')", script)
        self.assertNotIn("FB-Automation-Portable-v5.", script)


class V604ArchitectureInvariantTests(unittest.TestCase):
    def test_jobs_api_rejects_unsupported_command_and_bad_pagination(self):
        client = server.app.test_client()
        bad_cmd = client.post('/api/jobs', json={'command': 'not-allowed'})
        self.assertEqual(bad_cmd.status_code, 400)
        bad_limit = client.get('/api/jobs?limit=abc')
        self.assertEqual(bad_limit.status_code, 400)
        with patch("api.jobs.job_manager.get_job", return_value={"id": "safejob"}):
            bad_offset = client.get('/api/jobs/safejob/logs?offset=abc')
        self.assertEqual(bad_offset.status_code, 400)

    def test_queue_transition_is_atomic_and_single_claim(self):
        from db import init_db
        from repositories.campaign_repo import CampaignRepository
        with tempfile.TemporaryDirectory() as directory:
            db_file = str(Path(directory) / 'queue.db')
            init_db(db_file)
            repo = CampaignRepository(db_file=db_file)
            item = {'id':'q1','target':'https://facebook.com/groups/x','content':'hello valid content','state':'approved','created_at':'2026-09-07T00:00:00+00:00','audit':[]}
            self.assertTrue(repo.insert_queue_item(item))
            first = repo.transition_queue_item('q1', ('approved',), 'processing', {}, 'processing')
            second = repo.transition_queue_item('q1', ('approved',), 'processing', {}, 'processing')
            self.assertEqual(first['state'], 'processing')
            self.assertIsNone(second)

    def test_canonical_queue_prefers_sqlite_over_stale_json(self):
        from repositories.campaign_repo import CampaignRepository
        original = CampaignRepository.list_queue
        try:
            CampaignRepository.list_queue = lambda self: [{'id':'db','state':'approved'}]
            with patch.object(server, 'QUEUE_FILE', str(server.DATA_DIR / 'publication_queue.json')):
                got = server.load_queue()
            self.assertEqual(got[0]['id'], 'db')
        finally:
            CampaignRepository.list_queue = original


    def test_processing_queue_recovery_is_idempotent(self):
        from db import init_db
        from repositories.campaign_repo import CampaignRepository
        with tempfile.TemporaryDirectory() as directory:
            db_file = str(Path(directory) / 'reconcile.db')
            init_db(db_file)
            repo = CampaignRepository(db_file=db_file)
            item = {'id':'q2','target':'https://facebook.com/groups/y','content':'hello valid content','state':'processing','created_at':'2026-09-07T00:00:00+00:00','audit':[]}
            self.assertTrue(repo.insert_queue_item(item))
            self.assertEqual(repo.reconcile_processing_queue(), 1)
            self.assertEqual(repo.reconcile_processing_queue(), 0)
            recovered = repo.get_queue_item('q2')
            self.assertEqual(recovered['state'], 'unverified')
            self.assertIn('không tự động retry', recovered['error'].lower())

    def test_ui_bulk_path_handles_group_and_page_and_terminal_truth(self):
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn("if (groupTasks.length > 0)", js)
        self.assertIn("if (pageTasks.length > 0)", js)
        self.assertIn("terminalRunResult === 'failed'", js)
        self.assertIn("terminalRunResult === 'cancelled'", js)


class V604FinalProductionInvariantTests(unittest.TestCase):
    def test_unverified_queue_is_reconcile_only(self):
        from db import init_db
        from repositories.campaign_repo import CampaignRepository
        with tempfile.TemporaryDirectory() as directory:
            db_file = str(Path(directory) / 'queue-final.db')
            init_db(db_file)
            repo = CampaignRepository(db_file=db_file)
            item = {'id':'u1','target':'https://facebook.com/groups/x','content':'original submitted content','state':'unverified','created_at':'2026-09-07T00:00:00+00:00','audit':[]}
            self.assertTrue(repo.insert_queue_item(item))
            self.assertIsNone(repo.transition_queue_item('u1', ('approved',), 'processing', {}, 'processing'))
            claimed = repo.transition_queue_item('u1', ('unverified',), 'reconciling', {}, 'reconciling')
            self.assertEqual(claimed['state'], 'reconciling')
            self.assertIsNone(repo.transition_queue_item('u1', ('unverified',), 'reconciling', {}, 'reconciling'))
            back = repo.transition_queue_item('u1', ('reconciling',), 'unverified', {}, 'reconcile_not_found')
            self.assertEqual(back['state'], 'unverified')

    def test_release_build_includes_reconcile_module(self):
        script = Path('BUILD_PORTABLE.ps1').read_text(encoding='utf-8')
        self.assertIn("'fb_reconcile.py'", script)
        self.assertIn('reconcile-post', Path('api/jobs.py').read_text(encoding='utf-8'))
        self.assertIn('reconcile-post', Path('main.py').read_text(encoding='utf-8'))

    def test_join_optional_engagement_defaults_off(self):
        main = Path('main.py').read_text(encoding='utf-8')
        executor = Path('services/job_executor.py').read_text(encoding='utf-8')
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('interact-feed", action="store_true", default=False', main)
        self.assertIn('data.get("interactFeed", False)', executor)
        self.assertNotIn('id="join-group-interact-feed" checked', html)
        self.assertNotIn('id="join-group-auto-rules" checked', html)

    def test_reconcile_no_match_is_zero_write(self):
        import fb_reconcile
        class FakePage:
            def set_default_timeout(self, *_): pass
            def goto(self, *_args, **_kwargs): pass
            def reload(self, *_args, **_kwargs): pass
        class FakeCM:
            def __enter__(self): return object()
            def __exit__(self, *args): return False
        account = {'id':'acc1','type':'local','profile_path_or_id':'acc1'}
        with patch('fb_reconcile.sync_playwright', return_value=FakeCM()), \
             patch('fb_reconcile.resolve_account', return_value=account), \
             patch('fb_reconcile.launch_browser', return_value=(object(), object(), FakePage())), \
             patch('fb_reconcile.close_browser'), \
             patch('fb_reconcile._scan_post_permalink_once', return_value=''), \
             patch('fb_reconcile._has_pending_post_notice', return_value=False), \
             patch('fb_reconcile.record_posted_link') as record, \
             patch('fb_reconcile.time.sleep', return_value=None):
            result = fb_reconcile.reconcile_existing_post('https://facebook.com/groups/x', 'original submitted content', 'acc1')
        self.assertFalse(result.success)
        self.assertEqual(result.state, 'unverified')
        self.assertEqual(result.code, 'RECONCILE_NOT_FOUND')
        record.assert_not_called()

    def test_reconcile_match_updates_existing_lifecycle(self):
        import fb_reconcile
        class FakePage:
            def set_default_timeout(self, *_): pass
            def goto(self, *_args, **_kwargs): pass
            def reload(self, *_args, **_kwargs): pass
        class FakeCM:
            def __enter__(self): return object()
            def __exit__(self, *args): return False
        account = {'id':'acc1','type':'local','profile_path_or_id':'acc1'}
        permalink = 'https://www.facebook.com/groups/x/posts/999'
        with patch('fb_reconcile.sync_playwright', return_value=FakeCM()), \
             patch('fb_reconcile.resolve_account', return_value=account), \
             patch('fb_reconcile.launch_browser', return_value=(object(), object(), FakePage())), \
             patch('fb_reconcile.close_browser'), \
             patch('fb_reconcile._scan_post_permalink_once', return_value=permalink), \
             patch('fb_reconcile.record_posted_link') as record, \
             patch('fb_reconcile.time.sleep', return_value=None):
            result = fb_reconcile.reconcile_existing_post('https://facebook.com/groups/x', 'original submitted content', 'acc1')
        self.assertTrue(result.success)
        self.assertEqual(result.state, 'published')
        self.assertEqual(result.result_url, permalink)
        record.assert_called_once()

    def test_submit_timeout_after_click_is_unverified_not_retryable(self):
        from utils import click_post_publish_button, ActionResult
        class Textbox:
            def get_attribute(self, name): return "Write something" if name == "aria-label" else ""
        class Textboxes:
            def count(self): return 1
            def nth(self, _): return Textbox()
        class Dialog:
            def is_visible(self, timeout=None): return True
            def inner_text(self): return ''
            def locator(self, selector): return Textboxes()
        class Loc:
            def all(self): return [Dialog()]
        class Page:
            def evaluate(self, *_): return {'clicked': True, 'text': 'Post'}
            def locator(self, *_args, **_kwargs): return Loc()
        with patch('time.sleep', return_value=None):
            result = click_post_publish_button(Page(), Dialog())
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertEqual(result.state, 'submitted_unverified')
        self.assertEqual(result.code, 'SUBMIT_TRIGGERED_UNVERIFIED')

    def test_accounts_api_masks_proxy_credentials(self):
        client = server.app.test_client()
        fake = [{'id':'a1','name':'A','type':'local','profile_path_or_id':'p','proxy':'user:secret@10.0.0.1:9000'}]
        with patch('utils.load_accounts', return_value=fake):
            data = client.get('/api/accounts').get_json()
        self.assertEqual(data[0]['proxy'], '10.0.0.1:9000')
        self.assertNotIn('secret', str(data))

    def test_gpm_profiles_api_never_exposes_raw_proxy(self):
        client = server.app.test_client()
        fake = {
            'connected': True,
            'profiles': [{'id':'g1','name':'G1','raw_proxy':'user:pass@1.2.3.4:5555','browser_type':'Chrome'}],
            'total': 1,
            'base_url': 'http://127.0.0.1:19995'
        }
        with patch('utils.fetch_gpm_profiles', return_value=fake):
            data = client.get('/api/gpm/profiles').get_json()
        profile = data['profiles'][0]
        self.assertNotIn('raw_proxy', profile)
        self.assertNotIn('proxy', profile)
        self.assertEqual(profile['proxy_hint'], '1.2.3.4:5555')
        self.assertNotIn('pass', str(data))
    def test_runtime_identity_uses_absolute_main_path(self):
        src = Path('services/job_executor.py').read_text(encoding='utf-8')
        self.assertIn('RUNTIME_IDENTITY:', src)
        self.assertIn('str((BASE_DIR / "main.py").resolve())', src)

    def test_interact_failure_uses_fast_recovery_and_summary(self):
        src = Path('services/job_executor.py').read_text(encoding='utf-8')
        self.assertIn('delay = 5 if ret != 0 else random.randint(delay_min, delay_max)', src)
        self.assertIn('[Interact Summary]', src)

    def test_launcher_preflight_requires_runtime_root(self):
        src = Path('launcher_preflight.py').read_text(encoding='utf-8')
        self.assertIn("runtime_root = str(info.get('runtime_root') or '').strip()", src)
        self.assertIn('same_root = bool(runtime_root)', src)
        build = Path('BUILD_PORTABLE.ps1').read_text(encoding='utf-8')
        self.assertIn('launcher_preflight.py', build)


class V606JoinRotationTests(unittest.TestCase):
    def test_url_mode_runs_every_selected_profile(self):
        import services.job_executor as executor
        accounts = [{"id": f"acc-{i}", "name": f"M{i}"} for i in range(1, 9)]
        urls = [f"https://facebook.com/groups/{i}" for i in range(1, 6)]

        class Runner:
            def __init__(self): self.calls = []
            def is_cancelled(self, _job_id): return False
            def run_command_sync(self, cmd, **kwargs):
                self.calls.append(cmd)
                return 0

        runner = Runner()
        logs = []
        with patch.object(executor, "load_accounts", return_value=accounts), \
             patch.object(executor, "load_config", return_value={}), \
             patch.object(executor, "record_profile_activity"), \
             patch.object(executor.time, "sleep", return_value=None), \
             patch.object(executor.random, "randint", return_value=5):
            ok = executor.execute_automation_task(
                "job-v606", "join-group",
                {"rotateAccounts": True, "mode": "urls", "urls": "\n".join(urls), "limit": 2},
                logs.append, runner,
            )

        self.assertTrue(ok)
        self.assertEqual(len(runner.calls), 8)
        for call in runner.calls:
            joined = " ".join(call)
            for url in urls:
                self.assertIn(url, joined)
            self.assertIn("--limit 2", joined)
        self.assertTrue(any("Profiles hoàn tất: 8/8" in line for line in logs))

    def test_joined_group_identity_is_profile_plus_url(self):
        from db import init_db
        from repositories.group_repo import GroupRepository
        with tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / "app.db"
            init_db(db_file)
            repo = GroupRepository(db_file)
            base = {"group_name": "Hue Group", "url": "https://facebook.com/groups/123/", "state": "pending"}
            repo.add_joined_group({**base, "account_id": "M4", "joined_at": "2026-09-07 16:00:00"})
            repo.add_joined_group({**base, "account_id": "M14", "joined_at": "2026-09-07 16:01:00"})
            rows = repo.list_joined_groups()
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["account_id"] for r in rows}, {"M4", "M14"})

    def test_joined_groups_api_prefers_sqlite_authority(self):
        client = server.app.test_client()
        with patch.object(server, "GroupRepository") as repo_cls:
            repo_cls.return_value.list_joined_groups.return_value = [
                {"group_name": "DB Group", "url": "https://facebook.com/groups/db", "account_id": "M4", "state": "joined"}
            ]
            res = client.get("/api/joined-groups")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()[0]["group_name"], "DB Group")


class V606ReviewP1RegressionTests(unittest.TestCase):
    def test_joined_group_url_variants_collapse_per_profile(self):
        from db import init_db
        from repositories.group_repo import GroupRepository
        with tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / "app.db"
            init_db(db_file)
            repo = GroupRepository(db_file)
            variants = [
                "https://www.facebook.com/groups/123/",
                "https://facebook.com/groups/123?ref=share",
                "https://m.facebook.com/groups/123/#top",
            ]
            for idx, url in enumerate(variants):
                repo.add_joined_group({
                    "account_id": "M4", "url": url, "group_name": "Group 123",
                    "state": "joined" if idx == 0 else "pending",
                })
            rows = repo.list_joined_groups()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["account_id"], "M4")
            self.assertEqual(rows[0]["url"], "https://facebook.com/groups/123")
            repo.add_joined_group({
                "account_id": "M14", "url": variants[1], "group_name": "Group 123",
                "state": "joined",
            })
            rows = repo.list_joined_groups()
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["account_id"] for r in rows}, {"M4", "M14"})

    def test_windows_portable_launcher_uses_bundled_runtime_fast_path(self):
        root = Path(__file__).resolve().parents[1]
        wrapper = (root / "start_portable.bat").read_text(encoding="utf-8").lower()
        canonical = (root / "RUN_FB_AUTOMATION.bat").read_text(encoding="utf-8").lower()
        self.assertIn("call run_fb_automation.bat", wrapper)
        self.assertNotIn("python --version", wrapper)
        self.assertNotIn("pip", wrapper)
        self.assertNotIn("playwright", wrapper)
        runtime_check = 'if exist "%venv_dir%\\scripts\\python.exe"'
        path_fallback = "where py"
        self.assertIn(runtime_check, canonical)
        self.assertIn(path_fallback, canonical)
        self.assertLess(canonical.index(runtime_check), canonical.index(path_fallback))
        check_libs = canonical.split("\n:check_libs\n", 1)[1].split("\n:run\n", 1)[0]
        self.assertIn('if not exist "%venv_dir%\\lib\\site-packages\\flask"', check_libs)
        self.assertNotIn("playwright.exe install chromium", check_libs)


class V607JobLifecycleRegressionTests(unittest.TestCase):
    def test_job_executor_import_does_not_import_server_module(self):
        import subprocess, sys
        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as td:
            env["FB_AUTOMATION_DATA_DIR"] = td
            code = "import sys; import services.job_executor; assert 'server' not in sys.modules, list(sys.modules)"
            result = subprocess.run([sys.executable, "-c", code], cwd=str(Path(__file__).resolve().parents[1]), env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_api_run_stream_starts_with_job_id(self):
        import api.jobs as jobs_api
        with patch.object(jobs_api.job_manager, "submit_job", return_value="jobabc123"), \
             patch.object(jobs_api.job_manager, "subscribe_logs", return_value=iter(["RUN_RESULT:finished\n"])):
            response = server.app.test_client().post("/api/run", json={"command": "interact", "limit": 1})
            body = response.get_data(as_text=True)
            self.assertTrue(body.startswith("JOB_ID:jobabc123\n"), body)
            self.assertIn("RUN_RESULT:finished", body)
    def test_ui_does_not_treat_missing_terminal_result_as_success(self):
        src = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Luồng log đã đóng trước terminal result", src)
        self.assertIn("terminalRunResult = 'failed'", src)
        self.assertIn("currentJobId = null", src)
        self.assertIn("Đang có một Job hoạt động; từ chối gửi Job mới", src)

    def test_join_group_quota_is_based_on_verified_joined_memberships(self):
        src = (Path(__file__).resolve().parents[1] / "fb_join_group.py").read_text(encoding="utf-8")
        self.assertIn("target_joined = min(max(1, int(max_groups)), 2)", src)
        self.assertIn("if joined_count >= target_joined", src)
        self.assertIn("join_attempts += 1", src)
        self.assertIn('"quota_met": joined_count >= target_joined', src)
        self.assertNotIn("if join_attempts >= max_groups", src)


class V608UiAndContentRegressionTests(unittest.TestCase):
    def test_comment_button_submits_comment_job_without_post_button_bridge(self):
        src = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        block = src[src.index("if (commentSubmitBtn)"):src.index("if (threadSubmitBtn)")]
        self.assertIn("submitCommentJob()", block)
        self.assertNotIn("postBtn.click()", block)
        submit = src[src.index("async function submitCommentJob"):src.index("// ---- Post Button ----")]
        self.assertIn("runCommand('comment'", submit)

    def test_queue_is_dedicated_full_width_workspace_with_archive_filters(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        js = (root / "static" / "app.js").read_text(encoding="utf-8")
        css = (root / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('data-target="queue"', html)
        self.assertIn('id="queue-section"', html)
        self.assertIn('.workspace-grid.queue-focus', css)
        self.assertIn("currentMode === 'queue'", js)
        self.assertTrue(
            "queueSection.appendChild(approvalQueueCard)" in js or
            "queueSection.insertBefore(approvalQueueCard, queueSection.firstChild)" in js
        )
        for state in ('published', 'failed', 'cancelled'):
            self.assertIn(f'value="{state}"', html)

    def test_join_group_profile_scope_is_separate_from_per_profile_limit(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        js = (root / "static" / "app.js").read_text(encoding="utf-8")
        executor = (root / "services" / "job_executor.py").read_text(encoding="utf-8")
        self.assertIn('id="join-group-max-profiles"', html)
        self.assertIn("maxProfiles", js)
        self.assertIn('data.get("maxProfiles"', executor)
        self.assertIn('min(max(1, int(data.get("limit", 2))), 2)', executor)

    def test_all_posts_keep_both_global_homestay_hashtags_and_project_signature(self):
        from brand_profiles import apply_brand_signature
        lacasa = apply_brand_signature("Nội dung thử", "lacasa", True)
        umee = apply_brand_signature("Nội dung thử", "umee", True)
        for text in (lacasa, umee):
            self.assertIn("#UMEEHomestay", text)
            self.assertIn("#LacasaHomestay", text)
            self.assertIn("━━━━━━━━━━━━━━━━━━━━", text)
        self.assertTrue("lacasa" in lacasa.lower())
        self.assertTrue("umee" in umee.lower())

    def test_v609_assets_are_cache_busted_to_current_release(self):
        html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('styles.css?v=6.1.32', html)
        self.assertIn('app.js?v=6.1.32', html)
        self.assertNotIn('app.js?v=5.8.0', html)

    def test_composer_verifier_requires_full_signature_block_when_expected(self):
        from utils import verify_entered_content
        class Fake:
            def __init__(self, text): self.text = text
            def inner_text(self): return self.text
            def text_content(self): return self.text
        from brand_profiles import apply_brand_signature
        expected = apply_brand_signature("Nội dung thử", "lacasa", True)
        self.assertTrue(verify_entered_content(Fake(expected), expected))
        broken = expected.replace("https://www.lacasahomestay.com/", "")
        self.assertFalse(verify_entered_content(Fake(broken), expected))

class V618QueueVisibilityAndArchiveTests(unittest.TestCase):
    def test_queue_loads_all_supported_rows_and_reports_visible_count(self):
        js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("?active=1&limit=999", js)
        self.assertIn("đang hiển thị ${visibleItems.length}", js)
        self.assertIn("queueFilter.value = 'active'", js)
        self.assertIn("await loadQueue();", js)

    def test_duplicate_lock_archives_verified_publication(self):
        executor = (Path(__file__).resolve().parents[1] / "services" / "job_executor.py").read_text(encoding="utf-8")
        self.assertIn('queue_item_id = str(task.get("queueItemId")', executor)
        self.assertIn('"published": "published", "pending": "pending", "submitted_unverified": "unverified"', executor)
        self.assertIn('duplicate_lock_synced_{synced_state}', executor)
        self.assertIn('loadQueue();', (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8"))


class V619QueueStateSeparationTests(unittest.TestCase):
    def test_active_queue_excludes_post_submit_states_and_counts_reconcile(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server, "QUEUE_FILE", str(Path(directory) / "queue.json")):
            items = [
                {"id":"a","target":"a","content":"x","state":"approved"},
                {"id":"p","target":"p","content":"x","state":"pending"},
                {"id":"u","target":"u","content":"x","state":"unverified"},
                {"id":"m","target":"m","content":"x","state":"manual_review"},
                {"id":"d","target":"d","content":"x","state":"published"},
            ]
            Path(server.QUEUE_FILE).write_text(json.dumps(items), encoding="utf-8")
            client = server.app.test_client()
            self.assertEqual([x["id"] for x in client.get("/api/queue?active=1").get_json()], ["a"])
            self.assertEqual({x["id"] for x in client.get("/api/queue?state=reconcile").get_json()}, {"u", "m"})
            summary = client.get("/api/queue-summary").get_json()
            self.assertEqual(summary["active"], 1)
            self.assertEqual(summary["needs_reconcile"], 2)
            self.assertEqual(summary["pending"], 1)


class V6110QueueWorkspaceUiTests(unittest.TestCase):
    def test_queue_and_history_have_a_separate_workspace_sidebar_block(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        js = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="tab-queue"'), 1)
        self.assertIn("🗂️ KHÔNG GIAN LÀM VIỆC", html)
        self.assertIn("📋 Hàng Đợi Đăng Bài", html)
        self.assertIn("Lịch Sử & Đối Soát Bài Đăng", js)
        self.assertLess(html.index("id=\"tab-comment\""), html.index("🗂️ KHÔNG GIAN LÀM VIỆC"))
        self.assertLess(html.index("🗂️ KHÔNG GIAN LÀM VIỆC"), html.index("⚡ TỰ ĐỘNG & TIỆN ÍCH"))

    def test_queue_cards_show_created_time_and_session_identifier(self):
        js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("queue-item-meta", js)
        self.assertIn("item.created_at ? 'Tạo' : (item.updated_at ? 'Cập nhật' : 'Thời gian')", js)
        self.assertIn("🧾 Phiên/Mã:", js)
        self.assertIn("item.created_at || item.updated_at", js)
        self.assertIn("item.campaign_id || item.session_id || item.id", js)


class V609SecurityLinkageRegressionTests(unittest.TestCase):
    def test_frontend_never_reads_raw_proxy(self):
        src = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("raw_proxy", src)
        self.assertIn("proxy_hint", src)

class V609ServerAuthoritativeJobUiTests(unittest.TestCase):
    def test_ui_uses_server_as_job_state_authority(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("async function syncActiveJobState()", js)
        self.assertIn("fetch('/api/jobs/active'", js)
        self.assertIn("const serverState = await syncActiveJobState();", js)
        self.assertIn("if (serverState.active)", js)
        self.assertIn("window.setInterval(() => syncActiveJobState(), 3000)", js)

    def test_stop_button_is_always_visible_and_server_enabled(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "static" / "index.html").read_text(encoding="utf-8")
        js = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="cancel-log-btn"', html)
        self.assertIn('disabled style="display: inline-flex;', html)
        self.assertIn("cancelBtn.disabled = !isRunning", js)
        self.assertIn("await syncActiveJobState();", js)


class V6010JoinDispatchRegressionTests(unittest.TestCase):
    def test_removed_bottom_post_control_is_not_referenced(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("postBtnBottom", js)
        self.assertIn("const serverState = await syncActiveJobState();", js)
        self.assertIn("await runCommand('join-group'", js)


class V617ConfigurablePostingFlowTests(unittest.TestCase):
    def test_duplicate_window_accepts_only_supported_choices(self):
        from services.job_executor import resolve_duplicate_window_hours
        for hours in (0.5, 1, 2, 3, 4, 5, 6, 7, 8):
            self.assertEqual(resolve_duplicate_window_hours(hours), hours)
        for invalid in (None, "", -1, 9, 12, 16, 24, 25, "bad"):
            self.assertEqual(resolve_duplicate_window_hours(invalid), 3)

    def test_ui_wires_configurable_duplicate_window(self):
        html = Path("static/index.html").read_text(encoding="utf-8")
        app = Path("static/app.js").read_text(encoding="utf-8")
        for hours in (0.5, 1, 2, 3, 4, 5, 6, 7, 8):
            self.assertIn(f'<option value="{hours}"', html)
        self.assertIn("payload.skipDuplicateHours", app)
        self.assertIn("hours=float(skip_duplicate_hours)", Path("services/job_executor.py").read_text(encoding="utf-8"))

    def test_content_hub_reference_is_loaded_by_brand(self):
        from ai_spinner import content_reference_context, load_content_reference
        reference = load_content_reference()
        self.assertEqual(reference["source"]["sha256"], "e0b200df3fad9df1e24ae5fa618b7b64f5b408ac9b54e2a84dd74a96f84f2a80")
        umee = content_reference_context("umee")
        self.assertIn("SH44", umee)
        self.assertIn("không tự bịa", umee.casefold())
        self.assertNotIn("Số 3 kiệt 17", umee)
        self.assertIn("content_reference.json", Path("BUILD_PORTABLE.ps1").read_text(encoding="utf-8"))

    def test_group_flow_browses_before_join_post_and_close(self):
        source = Path("fb_group.py").read_text(encoding="utf-8")
        arrival = source.index('_browse_group_context(page, "arrival")')
        membership = source.index("membership_state = _ensure_group_membership")
        before_post = source.index('_browse_group_context(page, "before-post")')
        publish = source.index("published = click_post_publish_button")
        after_post = source.index('_browse_group_context(page, "after-post")')
        close = source.index("close_browser(", after_post)
        self.assertLess(arrival, membership)
        self.assertLess(membership, before_post)
        self.assertLess(before_post, publish)
        self.assertLess(publish, after_post)
        self.assertLess(after_post, close)


class V6118SearchLinklessModerationTests(unittest.TestCase):
    def test_linkless_signature_has_search_terms_and_no_urls(self):
        from brand_profiles import apply_brand_signature, validate_brand_signature
        original = "Xem phòng https://example.com và fb.com/test\nHomestay ở Huế"
        result = apply_brand_signature(original, "lacasa", True, mode="linkless")
        self.assertIn("LACASA HOMESTAY", result)
        self.assertIn("Homestay tại Huế", result)
        self.assertNotRegex(result, r"(?i)https?://|fb\.com/")
        self.assertEqual(validate_brand_signature(result, "lacasa", mode="linkless"), (True, []))

    def test_fixed_photo_folder_table_lists_all_six_paths(self):
        html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
        for brand in ("LACASA", "UMEE"):
            for slot in ("1", "2", "3"):
                self.assertIn(f"D:\\Claude\\Factcheck\\Photo\\{brand}\\{slot}", html)
        self.assertIn('id="fixed-photo-folder-table"', html)

    def test_v6118_migration_and_registry_are_durable(self):
        from db import init_db
        from repositories.moderation_repo import ModerationRepository
        with tempfile.TemporaryDirectory() as directory:
            db_file = Path(directory) / "v6118.db"
            init_db(db_file)
            repo = ModerationRepository(str(db_file))
            url = "https://facebook.com/groups/123/?ref=share"
            repo.mark_requires_approval(url, "POST_PENDING", "M6")
            self.assertTrue(repo.requires_approval("https://www.facebook.com/groups/123"))
            rid = repo.defer_first_comment(url, "Nội dung", "M6", "lacasa", "Link chi tiết")
            item = repo.get_deferred(url, "Nội dung", "M6")
            self.assertEqual(item["id"], rid)
            self.assertEqual(item["status"], "pending")
            repo.resolve_deferred(rid, "https://facebook.com/groups/123/posts/456", True)
            self.assertIsNone(repo.get_deferred(url, "Nội dung", "M6"))

    def test_spinner_prompt_is_linkless_and_uses_search_strategy(self):
        source = Path(__file__).resolve().parents[1].joinpath("ai_spinner.py").read_text(encoding="utf-8")
        self.assertIn("CHIẾN LƯỢC BIÊN TẬP", source)
        self.assertIn("Bài chính tuyệt đối không chứa URL", source)
        self.assertNotIn('brand_fb_links = {', source)

    def test_executor_known_moderated_path_requires_submit_evidence(self):
        source = Path(__file__).resolve().parents[1].joinpath("services", "job_executor.py").read_text(encoding="utf-8")
        self.assertIn("known_moderated and is_submit_uncertain(structured_result)", source)
        self.assertIn("current outcome remains SUBMITTED_UNVERIFIED", source)
        guarded = source.split("if known_moderated and is_submit_uncertain(structured_result):", 1)[1].split("# A submit can succeed", 1)[0]
        self.assertNotIn('"state": "pending"', guarded)
        self.assertNotIn('"code": "POST_PENDING"', guarded)
        self.assertIn('reconcile_kind="moderation"', source)
        self.assertIn("defer_first_comment", source)
        submit_idx = source.index("durable_reconcile_id = None")
        wait_idx = source.index("for reconcile_attempt, wait_seconds", submit_idx)
        enqueue_idx = source.index("ReconcileRepository().enqueue(", submit_idx)
        self.assertLess(enqueue_idx, wait_idx)
        self.assertIn("READ_ONLY / NO REPOST", source[submit_idx:wait_idx])

    def test_spinner_rejects_new_unverified_promotional_claims(self):
        import ai_spinner
        original = "Bạn đang tìm homestay tại Huế? Inbox để nhận thông tin."
        for claim in ("điểm dừng chân lý tưởng", "hỗ trợ ngay lập tức", "giá cực ưu đãi"):
            generated = f"Homestay tại Huế là {claim}. Inbox để nhận thông tin."
            self.assertFalse(ai_spinner._preserves_core_info(original, generated), claim)
