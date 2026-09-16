import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
class HubNavigationSpinQualityTests(unittest.TestCase):
    def test_content_hub_quick_action_uses_real_tab_dispatch(self):
        html=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
        self.assertIn('class="composer-tab btn btn-secondary btn-sm" type="button" data-target="content-hub"', html)
    def test_manual_spin_does_not_append_signature_preview(self):
        from server import app
        good=("Lacasa Homestay là lựa chọn homestay Huế cho chuyến đi cần thông tin rõ ràng.\n\n"
              "Phòng riêng có giường Queen; dorm có lựa chọn 4 và 8 giường.\n\n"
              "Bạn có thể nhắn Lacasa Homestay để hỏi loại phòng phù hợp với lịch trình.")
        with patch('ai_spinner.spin_content_gemini_with_model', return_value=(good,'model-test')):
            r=app.test_client().post('/api/ai/spin',json={'content':'Tìm homestay Huế.','mode':'post','brandKey':'lacasa','apiKeys':['key-12345678901234567890'],'includeSignature':False})
        data=r.get_json(); self.assertEqual(r.status_code,200)
        self.assertNotIn('━━━━━━━━',data['spun_content'])
    def test_runtime_executor_still_enforces_signature(self):
        src=(ROOT/'services'/'job_executor.py').read_text(encoding='utf-8')
        self.assertIn('include_signature = bool(brand_key)',src)
        self.assertIn('FINAL_CONTENT_SIGNATURE_MISSING',src)
if __name__ == '__main__': unittest.main()
