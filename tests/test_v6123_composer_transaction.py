import unittest
from composer_guard import audit_final_content, dedupe_content_blocks, normalize_single_cta, page_entity
from brand_profiles import apply_brand_signature

class ComposerTransactionTests(unittest.TestCase):
    def test_page_registry_is_canonical_for_both_projects(self):
        self.assertEqual(page_entity("umee")["handle"], "umeehomestay")
        self.assertEqual(page_entity("lacasa")["handle"], "lacasahomestayinvietnam")

    def test_dedupe_is_idempotent(self):
        raw = "Mở đầu\n\nMở đầu\n\n#UMEEHomestay #LacasaHomestay\n\n#UMEEHomestay"
        once = dedupe_content_blocks(raw)
        self.assertEqual(once, dedupe_content_blocks(once))
        self.assertEqual(once.count("Mở đầu"), 1)
        self.assertEqual(once.lower().count("#umeehomestay"), 1)

    def test_audit_blocks_duplicate_input_instead_of_silently_submitting(self):
        raw = "UMEE Homestay\n\nInbox Page UMEE Homestay để nhận phòng.\n\nInbox Page UMEE Homestay để nhận phòng."
        result = audit_final_content(raw, "umee", linkless=True)
        self.assertFalse(result["pass"])
        self.assertIn("DUPLICATE_BLOCKS", result["issues"])

    def test_audit_blocks_urls_in_main_post(self):
        raw = "Lacasa Homestay\n\nInbox Page Lacasa Homestay để nhận phòng.\n\nhttps://example.com"
        result = audit_final_content(raw, "lacasa", linkless=True)
        self.assertIn("URL_IN_MAIN_POST", result["issues"])

    def test_audit_requires_single_cta_for_project(self):
        zero = audit_final_content("UMEE Homestay\n\nThông tin phòng.", "umee")
        self.assertIn("CTA_COUNT:0", zero["issues"])
        two = audit_final_content(
            "UMEE Homestay\n\nInbox Page UMEE Homestay để nhận phòng.\n\nLiên hệ UMEE Homestay để nhận phòng.",
            "umee",
        )
        self.assertIn("CTA_COUNT:2", two["issues"])

    def test_receive_room_phrase_is_not_misclassified_as_cta(self):
        base = (
            "UMEE phù hợp khách đi ô tô đến Huế: có chỗ đỗ xe trước nhà, tự check-in "
            "và có thể nhận phòng riêng tư mà không cần chờ lễ tân. Một số phòng có "
            "máy chiếu lớn để xem phim buổi tối."
        )
        signed = apply_brand_signature(base, "umee", True, mode="linkless")
        normalized = normalize_single_cta(signed, "umee")
        self.assertIn("nhận phòng riêng tư", normalized)
        self.assertIn("máy chiếu lớn", normalized)
        result = audit_final_content(normalized, "umee", linkless=True)
        self.assertTrue(result["pass"], result)
        self.assertEqual(result["cta_count"], 1)

    def test_group_and_page_use_same_resolver_and_gate(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        group = root.joinpath("fb_group.py").read_text(encoding="utf-8")
        page = root.joinpath("fb_page.py").read_text(encoding="utf-8")
        for source in (group, page):
            self.assertIn("human_type_with_page_mention", source)
            self.assertIn("audit_final_content", source)
            self.assertIn("MENTION_ENTITY_LOST", source)

if __name__ == "__main__":
    unittest.main()
