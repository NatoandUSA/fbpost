import unittest
from ai_spinner import spin_content_hub_local
from content_studio import similarity_gate

class V6131RecoveryTests(unittest.TestCase):
    def test_content_hub_fallback_is_deterministic_and_diverse(self):
        source = "UMEE Homestay gửi bạn thông tin đã xác nhận để dễ cân nhắc."
        seeds = [f"group-1|fallback-{i}" for i in range(1, 9)]
        candidates = [spin_content_hub_local(source, "umee", seed) for seed in seeds]
        self.assertEqual(candidates[0], spin_content_hub_local(source, "umee", seeds[0]))
        self.assertEqual(len(set(candidates)), 8)
        history = [candidates[0]]
        self.assertTrue(any(similarity_gate(item, history, 0.82)["pass"] for item in candidates[1:]))
        for candidate in candidates:
            self.assertIn("UMEE Homestay", candidate)
            self.assertNotIn("group-1", candidate)

if __name__ == "__main__":
    unittest.main()
