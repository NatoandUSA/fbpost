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


if __name__ == "__main__":
    unittest.main()


