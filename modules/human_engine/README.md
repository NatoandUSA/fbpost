# High-Tech Human Behavior Simulation & Anti-Checkpoint Engine

## 1. Giới thiệu Sub-project
Module `modules/human_engine/` là một dự án con độc lập được thiết kế nhằm thay thế các thao tác tự động hóa thô sơ (như `locator.fill()`, `page.mouse.move(x,y)` nhảy cóc, cuộn trang không quán tính) bằng một hệ sinh thái mô phỏng hành vi sinh trắc học người thật.

Mục tiêu cao nhất: **Bảo vệ tài khoản Facebook / GPM khỏi các cơ chế gắn cờ (flagging) và checkpoint của Meta (Behavioral Telemetry & Bot Detection)**.

## 2. Kiến trúc Module
- **`behavioral_profile.py`**:
  - Tạo ra "Dấu ấn sinh trắc học" (Persona) riêng biệt cho từng Account ID / Profile GPM dựa trên SHA-256 seed.
  - Đảm bảo mỗi nick có tốc độ gõ (WPM), thói quen rê chuột và nhịp nghỉ riêng, không bị trùng lặp công thức giữa các tài khoản nhưng nhất quán qua từng ngày.
- **`kinematic_mouse.py`**:
  - Quỹ đạo chuột đường cong Bézier bậc 3 (Cubic Bézier).
  - Biến thiên gia tốc sinh lý hình chuông (Ease-in, Ease-out Sigmoid).
  - Nhiễu rung tay tự nhiên (Physiological Tremor 8 - 12 Hz).
  - Hiện tượng lố đà và vi chỉnh ngược (Overshoot & Correction tuân thủ Fitts's Law).
- **`biometric_typing.py`**:
  - Khoảng thời gian giữa các phím (IKI) theo phân phối Log-Normal.
  - Phân loại độ trễ dựa trên khoảng cách phím vật lý QWERTY.
  - Dừng tư duy ngẫu nhiên sau dấu câu và ngắt đoạn.
  - Mô phỏng gõ nhầm phím lân cận và tự xóa sửa (1-2%), bảo toàn 100% nội dung gốc.
- **`kinetic_scroll.py`**:
  - Cuộn trang có xung lực và giảm tốc quán tính vật lý ($v_t = v_0 \cdot 0.82^t$).
  - Khoảng nghỉ đọc bài ngẫu nhiên.
  - 15% xác suất cuộn ngược nhẹ như người xem lại chi tiết.
- **`engine.py`**: Facade tổng hợp cung cấp các phương thức cấp cao (`click`, `type_into`, `natural_scroll`, `warm_up`).
- **`adapter.py`**: Cầu nối tương thích 100% với các hàm trong `utils.py` (`human_type`, `safe_mouse_wheel`), giúp tích hợp vào main sau này chỉ với 1 dòng import.

## 3. Cách chạy kiểm thử độc lập
```powershell
.\runtime\venv\Scripts\python.exe -m unittest discover -s modules/human_engine/tests -p "test_*.py"
```

## 4. Hướng dẫn Merge / Review vào Main
Khi người dùng/quản trị viên phê duyệt:
Chỉ cần cập nhật trong `utils.py`:
```python
from modules.human_engine.adapter import human_type_advanced as human_type, kinetic_mouse_wheel as safe_mouse_wheel
```
Không cần thay đổi bất kỳ file nghiệp vụ nào khác (`fb_group.py`, `fb_page.py`, `fb_comment.py`, `fb_interact.py`).
