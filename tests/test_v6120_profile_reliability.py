import json
import re
import urllib.error
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from repositories.job_repo import JobRepository
from repositories.workflow_repo import WorkflowRepository
from repositories.moderation_repo import ModerationRepository
from brand_profiles import BRAND_FIRST_COMMENTS, get_first_comment_text
from fb_comment import COMMENT_REJECTION_RE
import ai_spinner


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
               "comment_rejected": 2, "avg_seconds": 12.0, "last_activity": "2026-09-14"}
        with patch.object(WorkflowRepository, "profile_posting_performance", return_value=[row]), \
             patch.object(server, "load_accounts", return_value=[{"profile_path_or_id": "uuid-m4", "name": "M4"}]):
            data = server.app.test_client().get("/api/workflows/profile-performance").get_json()
        self.assertEqual(data["profiles"][0]["profile_name"], "M4")
        self.assertEqual(data["profiles"][0]["pending"], 1)
        self.assertEqual(data["profiles"][0]["comment_rejected"], 2)
        self.assertEqual(data["profiles"][0]["published_rate"], 33.3)

    def test_first_comment_templates_have_one_url_and_rotate_deterministically(self):
        for brand_key, variants in BRAND_FIRST_COMMENTS.items():
            self.assertGreaterEqual(len(variants), 3)
            for text in variants:
                self.assertEqual(len(re.findall(r"https?://\S+", text)), 1)
                self.assertNotIn("zalo.me/", text.lower())
                self.assertIn("0905 555 317", text)
            chosen = [get_first_comment_text(brand_key, f"group-{i}") for i in range(20)]
            self.assertGreaterEqual(len(set(chosen)), 2)
            self.assertEqual(chosen, [get_first_comment_text(brand_key, f"group-{i}") for i in range(20)])

    def test_rejected_comment_creates_24h_group_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.db"
            from db import init_db
            init_db(db_path)
            repo = ModerationRepository(str(db_path))
            group = "https://facebook.com/groups/123/?ref=share"
            repo.record_comment_delivery(
                group, "https://facebook.com/groups/123/posts/456", "profile-1",
                "umee", "rejected", "Page: https://facebook.com/umeehomestay", "evidence.png",
            )
            cooldown = repo.comment_cooldown(group)
            self.assertIsNotNone(cooldown)
            self.assertEqual(cooldown["rejected_count"], 1)
            conn = repo.get_conn()
            try:
                event = conn.execute("SELECT * FROM comment_delivery_events").fetchone()
                self.assertEqual(event["status"], "rejected")
                self.assertEqual(event["url_count"], 1)
            finally:
                conn.close()

    def test_vietnamese_and_english_rejection_labels_are_recognized(self):
        for label in ("Bị từ chối", "Xem ý kiến đóng góp", "Declined", "Rejected", "See feedback"):
            self.assertRegex(label, COMMENT_REJECTION_RE)

    def test_workspace_contains_performance_panel_and_display_name_renderer(self):
        html = Path("static/index.html").read_text(encoding="utf-8")
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('id="profile-performance-body"', html)
        self.assertIn("Comment bị từ chối", html)
        self.assertIn("p.comment_rejected", js)
        self.assertIn("t.profile_name || t.profile_id", js)
        self.assertIn("loadProfilePerformance", js)

    def test_campaign_spinner_passes_audited_brand_content_hub(self):
        captured = {}
        def fake_spin(content, key, **kwargs):
            captured.update(kwargs)
            return (
                "Bạn cần tìm homestay Huế cho lịch trình sắp tới? 🌿\n\n"
                "UMEE Homestay có bãi đỗ ô tô miễn phí ngay trước cửa, thuận tiện khi bạn chủ động phương tiện.\n\n"
                "Không gian nghỉ riêng tư cùng hình thức self check-in/out 24/7 giúp kế hoạch nhận phòng linh hoạt hơn.\n\n"
                "Bạn muốn xem loại phòng phù hợp? Hãy inbox để nhận thông tin chi tiết nhé!"
            ), "model-test"
        with patch("ai_spinner.spin_content_gemini_with_model", side_effect=fake_spin):
            result = ai_spinner.generate_unique_variant_with_evidence(
                "Đang tìm homestay Huế, nhắn mình để hỏi phòng.",
                ["campaign-key-999999999999"], brand_key="umee", include_signature=True,
                signature_mode="linkless",
            )
        self.assertIn("SH44", captured["truth_context"])
        self.assertIn("bãi đỗ ô tô miễn phí", captured["truth_context"])
        self.assertEqual(result["key_pool_size"], 1)
        self.assertEqual(result["keys_attempted"], 1)
        self.assertEqual(result["mode"], "gemini")
        self.assertTrue(ai_spinner._campaign_quality_accepts(
            result["content"].split("#UMEEHomestay", 1)[0].strip(), "UMEE Homestay"
        ))

    def test_campaign_quality_rejects_truncated_copy(self):
        truncated = (
            "Bạn đang tìm homestay Huế?\n\nUMEE Homestay có không gian riêng tư.\n\n"
            "Nội dung đang được giới thiệu nhưng câu cuối bị"
        )
        self.assertFalse(ai_spinner._campaign_quality_accepts(truncated, "UMEE Homestay"))

    def test_hub_numbers_are_allowed_only_when_context_is_supplied(self):
        original = "UMEE Homestay tại Huế. Inbox để hỏi phòng."
        generated = "UMEE Homestay ở SH44, có máy chiếu 100 inch và self check-in 24/7. Inbox để hỏi phòng."
        self.assertFalse(ai_spinner._preserves_core_info(original, generated, brand_key="umee"))
        self.assertTrue(ai_spinner._preserves_core_info(
            original, generated, brand_key="umee",
            truth_context=ai_spinner.content_reference_context("umee"),
        ))

    def test_http_429_rotates_without_retrying_same_key(self):
        req = object()
        error = urllib.error.HTTPError("https://example.invalid", 429, "quota", {}, None)
        with patch("urllib.request.urlopen", side_effect=error) as mocked:
            with self.assertRaises(urllib.error.HTTPError):
                ai_spinner._urlopen_json(req, attempts=3)
        self.assertEqual(mocked.call_count, 1)

    def test_all_keys_429_uses_audited_content_hub_fallback(self):
        error = urllib.error.HTTPError("https://example.invalid", 429, "quota", {}, None)
        with patch("ai_spinner.spin_content_gemini_with_model", side_effect=error):
            result = ai_spinner.generate_unique_variant_with_evidence(
                "Đang tìm homestay Huế. Nhắn mình để hỏi phòng UMEE Homestay.",
                ["key-111111111111", "key-222222222222"], brand_key="umee",
                include_signature=True, signature_mode="linkless", variant_seed="group-123",
            )
        self.assertEqual(result["mode"], "content_hub_fallback")
        self.assertTrue(result["changed"])
        self.assertIn("thông tin đã được xác nhận", result["content"])
        self.assertIn("HTTP 429", result["error"])
        self.assertNotIn("https://", result["content"])

    def test_umee_mention_and_publish_error_detection_are_strict(self):
        source = Path("utils.py").read_text(encoding="utf-8")
        self.assertIn("from composer_guard import page_entity, mention_entity_committed", source)
        self.assertIn("[role='alert'], [aria-live='assertive']", source)
        self.assertNotIn('if any(err_kw in dlg_text', source)


if __name__ == "__main__":
    unittest.main()
