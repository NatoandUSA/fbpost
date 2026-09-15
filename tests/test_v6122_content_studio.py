import unittest
from unittest.mock import patch

from content_studio import similarity_gate, score_content, topic_catalog, _local_master, writing_option_catalog
from fb_group import _pending_admin_posts_count
from services.job_executor import _resume_rotation_after_last_post

class _Body:
    def __init__(self, text): self.text=text
    def inner_text(self, timeout=0): return self.text
class _Page:
    def __init__(self, text): self.text=text
    def locator(self, selector): return _Body(self.text)

class ContentStudioV6122Tests(unittest.TestCase):
    def test_topics_cover_operational_intents(self):
        ids={x['id'] for x in topic_catalog()}
        self.assertTrue({'room_sale','hourly','event','rain','hue_info','custom'} <= ids)

    def test_writing_options_catalog(self):
        opts=writing_option_catalog(); self.assertIn("tone",opts); self.assertIn("length",opts); self.assertIn("cta",opts)

    def test_local_fallback_honors_options(self):
        a=_local_master("umee","room_sale","homestay Huế","couple","local guide","", "concise","short","question")
        b=_local_master("umee","room_sale","homestay Huế","gia đình","conversion","", "story","long","save")
        self.assertIn("couple",a); self.assertIn("Bạn đang ưu tiên",a); self.assertIn("gia đình",b); self.assertIn("lưu lại",b); self.assertNotEqual(a,b)

    def test_similarity_gate_rejects_duplicate(self):
        text='UMEE Homestay Huế riêng tư ngay trung tâm, nhắn mình để hỏi phòng.'
        self.assertFalse(similarity_gate(text,[text])['pass'])
        self.assertTrue(similarity_gate(text,['Một bài hoàn toàn khác về ẩm thực địa phương'])['pass'])

    def test_quality_score_is_bounded(self):
        score=score_content('homestay Huế ' + ('trải nghiệm địa phương ' * 50) + ' nhắn mình để hỏi thêm','homestay Huế',True)
        self.assertGreaterEqual(score,70); self.assertLessEqual(score,100)

    def test_pending_counter_vietnamese(self):
        page=_Page('Đang chờ quản trị viên phê duyệt\n3 bài viết Tìm hiểu thêm')
        self.assertEqual(_pending_admin_posts_count(page),3)

    def test_pending_counter_zero_when_not_present(self):
        self.assertEqual(_pending_admin_posts_count(_Page('Nhóm công khai · 75,9K thành viên')),0)

    @patch('services.job_executor.ActivityRepository.list_posted_links')
    def test_rotation_resumes_after_last_profile(self, mocked):
        mocked.return_value=[{'account_id':'p2'}]
        pool=[{'id':'p1'},{'id':'p2'},{'id':'p3'}]
        self.assertEqual([x['id'] for x in _resume_rotation_after_last_post(pool)], ['p3','p1','p2'])

if __name__ == '__main__':
    unittest.main()
