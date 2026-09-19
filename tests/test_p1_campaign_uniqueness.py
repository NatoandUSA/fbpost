import unittest
from unittest.mock import patch

from ai_spinner import spin_content_hub_local
from content_studio import similarity_gate, similarity_projection


BASE = """Ở Huế có những buổi chỉ muốn tìm một căn phòng riêng tư để nghỉ ngơi thật chậm.

UMEE có một số phòng phù hợp cho kỳ nghỉ ngắn hoặc qua đêm với bồn tắm riêng, khu bếp tiện dụng và Netflix ngay tại phòng.

Tình trạng phòng thay đổi theo thời điểm; Home sẽ kiểm tra đúng ngày và khung giờ trước khi xác nhận.

UMEE Homestay · SH44 Manor Crown, 62 Tố Hữu, Huế
Inbox hoặc Zalo 0905 555 317 để Home kiểm tra phòng phù hợp.
"""


class CampaignUniquenessTests(unittest.TestCase):
    def test_target_seeded_content_hub_variants_have_real_semantic_spread(self):
        targets = [f"https://facebook.com/groups/{1000+i}" for i in range(20)]
        projected = [
            similarity_projection(spin_content_hub_local(BASE, "umee", variant_seed=target))
            for target in targets
        ]
        passed = 0
        accepted = []
        for candidate in projected:
            gate = similarity_gate(candidate, accepted, threshold=0.82)
            if gate["pass"]:
                accepted.append(candidate)
                passed += 1
        self.assertGreaterEqual(passed, 18, "fallback variant space is too small for a 20-target campaign")

    def test_fallback_preserves_phone_invariant_without_copying_source_body(self):
        variant = spin_content_hub_local(BASE, "umee", variant_seed="group-a")
        self.assertIn("0905 555 317", variant)
        self.assertNotIn("Ở Huế có những buổi chỉ muốn tìm một căn phòng riêng tư để nghỉ ngơi thật chậm.", variant)


if __name__ == "__main__":
    unittest.main()
