"""Unit and Integration Tests for Google Sheet Group Synchronization & Deduplication."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.sheet_sync import (
    to_csv_export_url,
    parse_member_count,
    parse_privacy_type,
    is_active_flag,
    parse_group_sheet,
    sync_to_group_registry,
    DEFAULT_SHEET_URL,
)


SAMPLE_SHEET_CSV = """STT,Group Link,Group Name,Nhóm Public/Private,Số thành viên làm tròn lên,Đăng bài tự động (Y/N)
1,https://www.facebook.com/groups/515843159057118,Homestay tại Huế (Check phòng trống hôm nay),Nhóm Công khai,"76,000",
2,https://www.facebook.com/groups/1384618231608931/,"Review Khách Sạn, Homestay giá rẻ ở Huế",Nhóm Công khai,"110,000",
3,https://www.facebook.com/groups/554201948309518,Homestay Huế giá rẻ,Nhóm Công khai,"29,000",
4,https://www.facebook.com/groups/199590627629924/,Homestay & Villa Huế,Nhóm Công khai,"49,200",
5,https://www.facebook.com/groups/554201948309518/,Homestay Huế giá rẻ lặp lại 1,Nhóm công khai,"37,800",
6,https://www.facebook.com/groups/BookingHue,Homestay Huế giá rẻ,Nhóm công khai,"13,800",
7,https://www.facebook.com/groups/BookingHue/,Homestay Huế trùng lặp,Nhóm công khai,"13,900",
8,https://www.facebook.com/groups/554201948309518?ref=share,Homestay Huế lặp lại 2,Nhóm công khai,"37,900",
9,https://www.facebook.com/groups/privategroup,Nhóm Kín Homestay,Nhóm Riêng tư,"15,000",
10,https://invalid-site.com/not-fb,Không phải FB,Nhóm công khai,"5,000",
"""


class GoogleSheetUrlTests(unittest.TestCase):
    def test_to_csv_export_url_conversion(self):
        # View URL with gid
        url1 = "https://docs.google.com/spreadsheets/d/10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k/edit?gid=0#gid=0"
        exp1 = to_csv_export_url(url1)
        self.assertEqual(exp1, "https://docs.google.com/spreadsheets/d/10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k/export?format=csv&gid=0")

        # Edit URL with different gid
        url2 = "https://docs.google.com/spreadsheets/d/10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k/edit#gid=12345"
        exp2 = to_csv_export_url(url2)
        self.assertEqual(exp2, "https://docs.google.com/spreadsheets/d/10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k/export?format=csv&gid=12345")

        # Edit URL without gid
        url3 = "https://docs.google.com/spreadsheets/d/10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k/edit"
        exp3 = to_csv_export_url(url3)
        self.assertEqual(exp3, "https://docs.google.com/spreadsheets/d/10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k/export?format=csv&gid=0")

    def test_rejects_non_google_sheet_urls(self):
        for url in ("http://docs.google.com/spreadsheets/d/test/edit", "https://evil.example/spreadsheets/d/test/edit", "https://docs.google.com.evil.example/spreadsheets/d/test/edit"):
            with self.assertRaises(ValueError):
                to_csv_export_url(url)


class DataParsingTests(unittest.TestCase):
    def test_parse_member_count(self):
        self.assertEqual(parse_member_count("76,000"), 76000)
        self.assertEqual(parse_member_count("110.000"), 110000)
        self.assertEqual(parse_member_count("692,800"), 692800)
        self.assertEqual(parse_member_count("25k"), 25000)
        self.assertEqual(parse_member_count("1.2M"), 1200000)
        self.assertEqual(parse_member_count("1,2 nghìn"), 1200)
        self.assertEqual(parse_member_count("2 triệu"), 2000000)
        self.assertIsNone(parse_member_count(""))
        self.assertIsNone(parse_member_count(None))
        self.assertIsNone(parse_member_count("abc"))

    def test_parse_privacy_type(self):
        self.assertEqual(parse_privacy_type("Nhóm Công khai"), "public")
        self.assertEqual(parse_privacy_type("Công khai"), "public")
        self.assertEqual(parse_privacy_type("Public"), "public")
        self.assertEqual(parse_privacy_type("Nhóm Riêng tư"), "private")
        self.assertEqual(parse_privacy_type("Kín"), "private")
        self.assertEqual(parse_privacy_type("Unknown"), "unknown")

    def test_is_active_flag(self):
        for val in ["Y", "y", "yes", "có", "co", "1", "true", "x", "OK"]:
            self.assertTrue(is_active_flag(val))
        for val in ["N", "n", "no", "không", "0", "false", "", None]:
            self.assertFalse(is_active_flag(val))


class SheetSyncPipelineTests(unittest.TestCase):
    def test_deduplication_and_normalization(self):
        res = parse_group_sheet(SAMPLE_SHEET_CSV, filter_active_only=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_rows"], 10)
        # Unique valid Facebook groups in SAMPLE_SHEET_CSV:
        # 1. 515843159057118
        # 2. 1384618231608931
        # 3. 554201948309518 (appears 3 times -> 1 unique + 2 duplicates)
        # 4. 199590627629924
        # 5. BookingHue (appears 2 times -> 1 unique + 1 duplicate)
        # 6. privategroup
        # Row 10 (invalid-site.com) is excluded.
        self.assertEqual(res["unique_count"], 6)
        self.assertEqual(res["duplicates_count"], 3)
        self.assertEqual(len(res["groups"]), 6)

        # Check canonical format of URLs
        urls = [g["url"] for g in res["groups"]]
        self.assertIn("https://facebook.com/groups/515843159057118", urls)
        self.assertIn("https://facebook.com/groups/1384618231608931", urls)
        self.assertIn("https://facebook.com/groups/554201948309518", urls)
        self.assertIn("https://facebook.com/groups/bookinghue", urls)

        # Ensure no trailing slashes or query parameters in canonical urls
        for u in urls:
            self.assertFalse(u.endswith("/"))
            self.assertNotIn("?ref=", u)

    def test_active_filter_when_flags_present(self):
        csv_with_flags = """STT,Group Link,Group Name,Privacy,Members,Auto Post
1,https://facebook.com/groups/g1,Group 1,Public,10000,Y
2,https://facebook.com/groups/g2,Group 2,Public,20000,N
3,https://facebook.com/groups/g3,Group 3,Public,30000,Y
"""
        res_all = parse_group_sheet(csv_with_flags, filter_active_only=False)
        self.assertEqual(res_all["unique_count"], 3)

        res_active = parse_group_sheet(csv_with_flags, filter_active_only=True)
        self.assertEqual(res_active["unique_count"], 3)
        self.assertEqual(res_active["selected_count"], 2)
        self.assertEqual(len(res_active["groups"]), 2)
        urls = [g["url"] for g in res_active["groups"]]
        self.assertIn("https://facebook.com/groups/g1", urls)
        self.assertIn("https://facebook.com/groups/g3", urls)
        self.assertNotIn("https://facebook.com/groups/g2", urls)

    def test_empty_csv_handling(self):
        res = parse_group_sheet("")
        self.assertFalse(res["success"])
        self.assertEqual(res["unique_count"], 0)

    def test_sync_real_user_sheet_dataset(self):
        from pathlib import Path
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "user_sheet_dataset.csv"
        if not fixture_path.exists():
            # Fallback to local brain path if available
            fixture_path = Path(r"C:\Users\Admin\.gemini\antigravity\brain\2060a8be-1e2c-434a-9c05-d14b2225c67a\.system_generated\steps\10615\content.md")
        self.assertTrue(fixture_path.exists(), "User sheet fixture must exist for regression verification")
        text = fixture_path.read_text(encoding="utf-8")
        csv_content = text if "1,https" in text else "\n".join(text.splitlines()[8:])
        res = parse_group_sheet(csv_content)
        self.assertTrue(res["success"])
        self.assertEqual(res["rows_with_urls"], 95)
        self.assertEqual(res["unique_count"], 84)
        self.assertEqual(res["duplicates_count"], 11)


class RegistryMergeTests(unittest.TestCase):
    def test_sheet_import_preserves_existing_registry_items(self):
        class FakeRepo:
            saved = None
            def list_groups(self): return []
            def save_groups(self, groups): FakeRepo.saved = groups
        with tempfile.TemporaryDirectory() as directory, \
             patch("services.sheet_sync.DATA_DIR", Path(directory)), \
             patch("repositories.group_repo.GroupRepository", FakeRepo):
            existing = [{"id":"old","url":"https://facebook.com/groups/existing","name":"Existing"}]
            (Path(directory) / "group_registry.json").write_text(json.dumps(existing), encoding="utf-8")
            result = sync_to_group_registry([{"id":"new","url":"https://facebook.com/groups/new","name":"New"}])
            stored = json.loads((Path(directory) / "group_registry.json").read_text(encoding="utf-8"))
            self.assertEqual({g["id"] for g in stored}, {"old", "new"})
            self.assertEqual(result["imported_count"], 1)
            self.assertEqual(result["registry_count"], 2)
            self.assertEqual(len(FakeRepo.saved), 2)


class ApiEndpointTests(unittest.TestCase):
    def setUp(self):
        from server import app
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_get_sheet_config(self):
        res = self.client.get("/api/groups/sheet-config")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("default_sheet_url", data)
        self.assertIn("10kZe1_oYgdUWPua16jN59xaPBwR2WsK86bjNFHpGz2k", data["default_sheet_url"])

    @patch("services.sheet_sync.fetch_sheet_csv", return_value=SAMPLE_SHEET_CSV)
    def test_post_sync_sheet_endpoint(self, mock_fetch):
        res = self.client.post("/api/groups/sync-sheet", json={
            "sheet_url": "https://docs.google.com/spreadsheets/d/test/edit",
            "filter_active_only": False,
            "save_registry": False
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["unique_count"], 6)
        self.assertEqual(data["duplicates_count"], 3)

    @patch("services.sheet_sync.fetch_sheet_csv", side_effect=RuntimeError("Google Sheet unreachable"))
    def test_post_sync_sheet_network_error_handled(self, mock_fetch):
        res = self.client.post("/api/groups/sync-sheet", json={
            "sheet_url": "https://docs.google.com/spreadsheets/d/test/edit"
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Google Sheet unreachable", data["error"])

    @patch("services.sheet_sync.sync_to_group_registry", side_effect=OSError("disk full"))
    @patch("services.sheet_sync.fetch_sheet_csv", return_value=SAMPLE_SHEET_CSV)
    def test_post_sync_sheet_registry_error_is_fail_closed(self, mock_fetch, mock_sync):
        res = self.client.post("/api/groups/sync-sheet", json={
            "sheet_url": "https://docs.google.com/spreadsheets/d/test/edit",
            "save_registry": True,
        })
        self.assertEqual(res.status_code, 500)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("không thể lưu kho Group", data["error"])
        self.assertEqual(data["sheet"]["unique_count"], 6)


if __name__ == "__main__":
    unittest.main()
