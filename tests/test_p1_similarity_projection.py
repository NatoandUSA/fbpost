import unittest

from content_studio import similarity_gate, similarity_projection


FOOTER = '''#UMEEHomestay #LacasaHomestay

━━━━━━━━━━━━━━━━━━━━
🏡 UMEE HOMESTAY × LACASA HOMESTAY
📍 Homestay tại Huế
📩 Tìm UMEE Homestay trên Facebook hoặc inbox để nhận thông tin.'''


class SimilarityProjectionTests(unittest.TestCase):
    def test_required_boilerplate_does_not_create_false_duplicate(self):
        a = 'Phòng có bồn tắm riêng và máy chiếu cho buổi tối thư giãn.\n\n' + FOOTER
        b = 'Không gian có bếp tiện dụng, phù hợp khách cần kỳ nghỉ linh hoạt.\n\n' + FOOTER
        result = similarity_gate(similarity_projection(a), [similarity_projection(b)], threshold=0.82)
        self.assertTrue(result['pass'])

    def test_identical_variable_body_still_rejected(self):
        body = 'Phòng có bồn tắm riêng và máy chiếu cho buổi tối thư giãn.'
        a = body + '\n\n' + FOOTER
        b = body + '\n\n' + FOOTER
        result = similarity_gate(similarity_projection(a), [similarity_projection(b)], threshold=0.82)
        self.assertFalse(result['pass'])
        self.assertEqual(result['max_similarity'], 1.0)

    def test_hashtags_and_cta_are_removed_from_projection(self):
        value = 'Nội dung biến thể A.\n\n#UMEEHomestay #LacasaHomestay\n\n' + FOOTER
        projected = similarity_projection(value)
        self.assertIn('Nội dung biến thể A.', projected)
        self.assertNotIn('#UMEEHomestay', projected)
        self.assertNotIn('inbox', projected.casefold())


if __name__ == '__main__':
    unittest.main()
