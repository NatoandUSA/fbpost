import unittest
from unittest.mock import patch
import ai_spinner
from content_studio import similarity_gate
from services.job_executor import _published_content_history

class GateBContentSafetyTests(unittest.TestCase):
    def test_campaign_quality_accepts_concise_actionable_copy(self):
        text = "Tim homestay Huế cho lich trinh gon nhe?\n\nUMEE Homestay co thong tin ro rang de ban can nhac cho chuyen di.\n\nNhắn UMEE Homestay de hỏi phong phu hop voi lich trinh nhe."
        self.assertTrue(ai_spinner._campaign_quality_accepts(text, "UMEE Homestay"))

    def test_campaign_quality_rejects_verbose_copy(self):
        base = "Tim homestay Huế?\n\nUMEE Homestay de ban can nhac.\n\nNhắn UMEE Homestay de hỏi phong."
        self.assertFalse(ai_spinner._campaign_quality_accepts(base + (" Thong tin tham khao." * 80), "UMEE Homestay"))

    def test_similarity_gate_rejects_near_duplicate(self):
        old = "Tim homestay Hue cho lich trinh gon nhe. UMEE Homestay co thong tin ro rang. Nhan UMEE Homestay de hoi phong."
        candidate = "Tim homestay Hue cho lich trinh gon nhe! UMEE Homestay co thong tin ro rang. Nhan UMEE Homestay de hoi phong."
        self.assertFalse(similarity_gate(candidate, [old], threshold=0.82)["pass"])

    def test_published_history_excludes_unverified(self):
        rows = [
            {"content":"published copy","publish_state":"published"},
            {"content":"uncertain copy","publish_state":"submitted_unverified"},
            {"content":"failed copy","publish_state":"failed"},
        ]
        with patch("services.job_executor.ActivityRepository") as repo:
            repo.return_value.list_posted_links.return_value = rows
            self.assertEqual(_published_content_history(), ["published copy"])

if __name__ == "__main__":
    unittest.main()
