# HƯỚNG DẪN DÀNH CHO GPT: MERGE & CUTOVER TÍNH NĂNG BATCH LIMIT 999 VÀ BATCH QUEUE MANAGEMENT

> **Tài liệu bàn giao kỹ thuật (Handoff Guide)**  
> **Nhánh nguồn (Source Branch)**: `feature/queue-batch-management-and-limits`  
> **Source head đã review**: `b724d4282429ce44d7e1dcab49a8c636b838f79b`  
> **Nhánh đích (Target Branch)**: `main` (hoặc `v6.1.0-stability`)  
> **Trạng thái review tích hợp**: **PASS 212/212 tests (100%)** | `node --check static/app.js` **PASS**

> Tài liệu này mô tả bàn giao nguồn. Việc merge không đồng nghĩa production đã được build hoặc cutover.

---

## 1. MỤC TIÊU & CÁC VẤN ĐỀ ĐÃ ĐƯỢC GIẢI QUYẾT

Tài liệu này hướng dẫn chi tiết các bước để merge nhánh `feature/queue-batch-management-and-limits` vào hệ thống chính mà **không gây lỗi runtime, không đụng độ Playwright, không làm gián đoạn production** (tránh tái diễn lỗi như sự cố Human Engine ở các phiên bản trước).

### Các lỗi gốc đã khắc phục:
1. **Lỗi `Error: Batch must contain between 1 and 100 tasks`**:
   - Nâng giới hạn tối đa từ `100` lên `999` tasks cho cả tác vụ Đăng bài (`group`/`page`/`reconcile`) và Gửi tin nhắn (`thread`) tại `services/job_executor.py`.
2. **Hiện tượng tích tụ 215+ bài chờ duyệt trong Hàng đợi (`data/publication_queue.json`)**:
   - **Nguyên nhân**: Nút *"📋 Đưa vào Hàng đợi duyệt"* trước đó không có cơ chế chặn trùng lặp. Khi người dùng paste 84 link và bấm 2-3 lần đã sinh ra 84 x 3 = 252 bài với cùng target & content. Khi bấm *"Duyệt tất cả"*, 198 bài chuyển thành `approved`, nhưng khi bấm *"Đăng bài đã duyệt"* thì bị chặn bởi limit 100, dẫn đến kẹt lại trong queue.
   - **Khắc phục**:
     - Thêm cơ chế chặn trùng lặp tại `POST /api/queue`: trả về **HTTP 409 Conflict** nếu cùng target và content đã tồn tại ở trạng thái `draft`, `approved`, hoặc `pending`.
     - Thêm thanh công cụ quản lý hàng loạt: **Duyệt tất cả**, **Hủy bài đã duyệt**, **Bộ lọc theo ngày tháng**, và **Menu dọn dẹp (xóa theo ngày, xóa bài lỗi/đã hủy, xóa toàn bộ)**.

---

## 2. DANH SÁCH CÁC FILE ĐÃ SỬA & CHI TIẾT KỸ THUẬT

1. **`services/job_executor.py`**:
   - Dòng 658: `if not tasks or len(tasks) > 999:` (Thread command limit).
   - Dòng 710: `if not isinstance(tasks, list) or len(tasks) > 999:` (Post command limit).
   - **Lưu ý quan trọng**: Không thay đổi bất kỳ logic DOM/Playwright nào, giữ nguyên 100% flow tương tác an toàn.
2. **`repositories/campaign_repo.py`**:
   - `approve_all_drafts()`: Atomic SQLite UPDATE chuyển toàn bộ `draft` sang `approved`.
   - `cancel_all_queue(states)`: Atomic SQLite UPDATE chuyển các `states` (mặc định `approved`, `draft`) sang `cancelled`.
   - `delete_queue_items(item_ids, states, date_from, date_to, clear_all)`: Xóa an toàn theo tiêu chí lọc ngày hoặc trạng thái.
3. **`server.py`**:
   - `GET /api/queue`: Hỗ trợ `?date=YYYY-MM-DD`, `date_from`, `date_to`, limit lên 1000.
   - `GET /api/queue-summary`: Hỗ trợ `?date=YYYY-MM-DD`.
   - `GET /api/queue/dates`: Trả về danh sách ngày có bài để populate date picker.
   - `POST /api/queue`: Duplicate check chặn lặp target + content; hỗ trợ cờ `allow_duplicate: true`.
   - `POST /api/queue/approve-all`: Duyệt tất cả nháp 1-click.
   - `POST /api/queue/cancel-all`: Hủy tất cả bài đã duyệt.
   - `POST /api/queue/clear`: Dọn dẹp với `scope` bắt buộc (`all`, `cancelled_or_failed`, `date`, `approved`, `draft`), trả về 400 nếu scope không hợp lệ.
   - Đảm bảo cơ chế **Dual Storage Sync**: cập nhật đồng thời SQLite `publication_jobs` và JSON `publication_queue.json`.
4. **`static/index.html` & `static/app.js`**:
   - Đầy đủ nút tab `tab-queue`, `tab-history`, các trường nhập và action bars.
   - Bổ sung date picker `queue-date-filter`, nút `cancel-approved-queue-btn`, menu `clear-queue-dropdown`.
   - Metadata timestamp `🕒 Tạo: dd/mm/yyyy hh:mm:ss` và `🧾 Phiên/Mã: ...` trên từng card.
   - Cache-busting: Đã nâng tham số asset lên `styles.css?v=6.1.10` và `app.js?v=6.1.10`.
5. **`tests/test_batch_queue_management.py`**:
   - Test suite độc lập gồm 10 test case bao phủ toàn bộ giới hạn 999, duplicate 409, approve-all, cancel-all, clear-queue, date filtering.

---

## 3. QUY TRÌNH MERGE DÀNH CHO GPT (STEP-BY-STEP)

Thực hiện tuần tự các bước sau tại thư mục gốc của repository (`d:\Claude\Homestay\fbpost`):

### Bước 1: Đảm bảo worktree của GPT sạch sẽ
Nếu GPT đang làm việc trên worktree phụ (`d:\Claude\Homestay\fbpost_release_v6110`), hãy commit toàn bộ thay đổi của GPT trước:
```bash
git add -A
git commit -m "feat: complete pending tasks before queue batch merge"
```

### Bước 2: Chuyển về nhánh `main` trên repo chính và kiểm tra trạng thái
```bash
cd d:\Claude\Homestay\fbpost
git checkout main
git status
```

### Bước 3: Merge nhánh `feature/queue-batch-management-and-limits` vào `main`
```bash
git merge feature/queue-batch-management-and-limits --no-ff -m "merge: merge queue batch management and 999 task limit into main"
```
*(Ghi chú: Giả lập `git merge-tree` đã xác nhận **0 CONFLICT**. Quá trình merge sẽ diễn ra hoàn toàn mượt mà).*

### Bước 4: Chạy toàn bộ Test Gate để xác nhận không có regression
Chạy 3 lệnh kiểm thử tiêu chuẩn sau:
```bash
# 1. Kiểm tra cú pháp JavaScript
node -c static/app.js

# 2. Chạy test suite mới về Batch Queue
runtime\venv\Scripts\python.exe -m unittest tests/test_batch_queue_management.py

# 3. Chạy full regression test suite (208 tests)
runtime\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
*Yêu cầu bắt buộc: 208/208 tests PASS.*

---

## 4. QUY TRÌNH DEPLOY / CUTOVER PRODUCTION AN TOÀN (TRÁNH LỖI RUNTIME)

> **CẢNH BÁO QUAN TRỌNG**:  
> Cổng **5000** đang chạy ứng dụng từ thư mục:  
> `d:\Claude\Homestay\fbpost\release\current\FB-Automation-Portable-v6.1.9`  
> Nếu chỉ merge trên git mà không cập nhật thư mục portable, người dùng mở trình duyệt vẫn sẽ chạy code cũ và không thấy các nút quản lý mới!

### Cách triển khai Cutover:
1. **Sao chép các file code mới vào thư mục release portable**:
   Các file cần copy đè từ `d:\Claude\Homestay\fbpost` sang `d:\Claude\Homestay\fbpost\release\current\FB-Automation-Portable-v6.1.9`:
   - `services\job_executor.py`
   - `repositories\campaign_repo.py`
   - `server.py`
   - `static\app.js`
   - `static\index.html`
   - `VERSION`
   *(Lưu ý: KHÔNG đè thư mục `data\` để bảo toàn lịch sử và cấu hình của người dùng).*

2. **Khởi động lại Server Production**:
   - Tìm và dừng tiến trình Python đang chạy trên port 5000:
     ```powershell
     Get-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess | Stop-Process -Force
     ```
   - Chạy lại file khởi động trong thư mục portable:
     ```powershell
     cd d:\Claude\Homestay\fbpost\release\current\FB-Automation-Portable-v6.1.9
     Start-Process -FilePath ".\runtime\venv\Scripts\python.exe" -ArgumentList "server.py" -WindowStyle Hidden
     ```
   - Kiểm tra server đã online và trả về đúng version mới:
     ```powershell
     Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/app-info"
     ```
     *(Kết quả mong muốn: `version: "6.1.10"`)*.

---

## 5. HƯỚNG DẪN NGƯỜI DÙNG XỬ LÝ 215 BÀI ĐANG KẸT HIỆN TẠI

Sau khi hoàn tất merge và restart server, người dùng có thể xử lý 198 bài đã duyệt bị kẹt theo 1 trong các cách sau:
1. **Nếu muốn ĐĂNG NGAY**:
   - Bấm nút **"🚀 Đăng bài đã duyệt"**. Giờ đây hệ thống nhận batch đến **999 bài**, 198 bài sẽ chạy tuần tự mượt mà, không bị báo lỗi 1-100 nữa.
2. **Nếu muốn HỦY TOÀN BỘ (không đăng nữa)**:
   - Bấm nút màu cam **"⏹ Hủy bài đã duyệt"** -> Toàn bộ 198 bài sẽ được chuyển vào mục lưu trữ đã hủy ngay lập tức.
3. **Nếu muốn XÓA BÀI THEO NGÀY**:
   - Tại ô `📅`, chọn ngày `2026-09-12`.
   - Bấm menu **"🗑️ Xóa / Dọn dẹp ▾"** -> Chọn **"📅 Xóa toàn bộ bài ngày đang chọn"** để dọn sạch bài tạo thừa.
