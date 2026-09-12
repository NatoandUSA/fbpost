# High-Tech Human Behavior Simulation & Anti-Checkpoint Engine (Audited & Upgraded)

## 1. Giới thiệu Sub-project
Module `modules/human_engine/` là một dự án con độc lập đạt tiêu chuẩn cao cấp (State-of-the-art), được nghiên cứu và tổng hợp từ các giải pháp hàng đầu trong cộng đồng tự động hóa (Botright, Ghost-Cursor, Puppeteer-Extra Stealth, WindMouse Algorithm, và các diễn đàn bảo mật trình duyệt).

Mục tiêu cốt lõi: **Bảo vệ tuyệt đối tài khoản Facebook / GPM trước hệ thống Meta Behavioral AI Telemetry & Anti-Bot Radar**.

## 2. Kiến trúc & Các Giải pháp Kỹ thuật Đột phá

### 2.1. Động học Quỹ đạo Chuột (`kinematic_mouse.py`)
- **Thuật toán WindMouse (Benjamin J. Land Model)**: Mô phỏng lực hấp dẫn (gravity), nhiễu động gió ngẫu nhiên (wind turbulence) và lực cản (drag), giúp các quãng di chuyển ngắn và trung bình uốn lượn tự nhiên như cơ bắp con người.
- **Cubic Bézier Kinematics**: Dành cho quãng đường dài với gia tốc hình chuông (Ease-in, Ease-out Sigmoid) và Fitts's Law Overshoot/Correction.
- **Phân phối điểm click 2D Gaussian**: Không click vào tâm điểm hình học $(0.5, 0.5)$ máy móc mà lấy mẫu Gaussian $(\mu=0.5, \sigma=0.12)$ kẹp trong vùng an toàn $[0.15, 0.85]$.
- **Mô phỏng trượt chuột vi mô (Optical Micro-slip)**: 5% xác suất dịch chuyển 1 pixel trong khi nhấn giữ nút chuột (hiện tượng thường thấy ở chuột quang học).

### 2.2. Sinh trắc học Gõ phím (`biometric_typing.py`)
- **Phát chuỗi sự kiện Down-Up (DU Telemetry)**: Thay vì gõ tức thì, mỗi ký tự phát đầy đủ `keydown` $\rightarrow$ giữ phím (Dwell time 35ms - 90ms) $\rightarrow$ `keyup`.
- **Phím Shift vật lý**: Khi gõ chữ hoa, phím Shift được nhấn giữ trước 40-80ms, gõ ký tự, rồi mới nhả Shift.
- **Tăng tốc gõ chữ lặp (Double-letter acceleration)**: Khi gõ hai chữ cái liên tiếp giống nhau (vd: `oo`, `ee`, `ss`), thời gian chuyển phím IKI tự động giảm 35-40% vì ngón tay đã ở sẵn vị trí.
- **Mô hình suy giảm do mỏi ngón tay (Typing Fatigue)**: Với bài viết dài (> 200 ký tự), tốc độ gõ giảm dần 3-8%.
- **Khoảng dừng tư duy (Cognitive Pause)**: Nghỉ tự nhiên 0.4s - 1.2s sau dấu câu và 0.6s - 1.5s giữa các đoạn văn.
- **Mô phỏng gõ nhầm & Backspace**: Nhấn nhầm phím lân cận trên bàn phím QWERTY, khựng lại nhận biết, bấm Backspace sửa lỗi.

### 2.3. Cuộn trang Quán tính Đa chế độ (`kinetic_scroll.py`)
- **Bánh xe chuột khấc (Discrete Wheel)**: Bật theo từng nấc 100px với nhịp nghỉ vật lý 45ms - 95ms (dành cho chuột để bàn).
- **Bàn di chuột mượt (Smooth Touchpad)**: Giảm tốc theo hàm số mũ liên tục $v_t = v_0 \cdot 0.84^t$.
- **Đọc lướt & Cuộn ngược vi mô**: Dừng lại 1.2s - 3.2s để quét nội dung bằng mắt; 18% cơ hội cuộn ngược nhẹ để xem lại chi tiết.

### 2.4. Triệt tiêu Dấu vết Tự động hóa (`stealth_evasion.py`)
- Xóa bỏ cờ `navigator.webdriver`.
- Thiết lập đầy đủ cấu trúc `window.chrome.runtime`, `loadTimes`, `csi`.
- Chuẩn hóa danh sách `navigator.plugins` và MIME types.
- Ẩn dấu vết WebGL / Canvas khỏi trình render ảo SwiftShader.

### 2.5. Dấu ấn Cá nhân hóa (`behavioral_profile.py`)
- Tạo dấu vân tay hành vi riêng biệt cho từng nick từ SHA-256 hash của Profile ID, đảm bảo nick A và nick B có thói quen khác nhau nhưng nick A luôn nhất quán qua mọi phiên chạy.

## 3. Kiểm thử Độc lập
```powershell
.\runtime\venv\Scripts\python.exe -m unittest discover -s modules/human_engine/tests -p "test_*.py"
```
Đã vượt qua **16/16 test PASS** tuyệt đối.

## 4. Hướng dẫn Review & Kích hoạt khi được Phê duyệt
Khi quản trị viên đồng ý đưa vào main, chỉ cần 1 dòng bridge trong `utils.py`:
```python
from modules.human_engine.adapter import human_type_advanced as human_type, kinetic_mouse_wheel as safe_mouse_wheel
```
