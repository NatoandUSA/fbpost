# 🤖 FB Automation Tool

Công cụ tự động hóa Facebook với Dashboard Web, hỗ trợ đăng bài hàng loạt lên Groups, Pages và gửi tin nhắn Threads — với đầy đủ cơ chế chống phát hiện Bot.

## ✨ Tính Năng

| Tính năng | Mô tả |
|-----------|-------|
| 🎯 Bulk Posting | Đăng 1 nội dung lên hàng chục Group/Page cùng lúc |
| 📊 Google Sheets | Kéo danh sách target + nội dung từ Google Sheets CSV |
| 🔀 Spintax | Tự động xáo trộn nội dung `{Xin chào\|Hello\|Hi}` |
| ⌨️ Human Typing | Giả lập gõ phím như người thật, có typo ngẫu nhiên |
| 🖱️ Mouse Simulation | Di chuột, cuộn trang ngẫu nhiên |
| ⏱️ Anti-Spam Delay | Nghỉ ngẫu nhiên 30-60s giữa các bài đăng |
| 📸 Image Upload | Đăng kèm hình ảnh |
| 🖥️ Live Dashboard | Theo dõi tiến trình real-time trên giao diện Web |

---

## 🚀 Cài Đặt & Khởi Động (1-Click)

> **Yêu cầu duy nhất:** Máy cần cài sẵn **Python 3** (tải tại [python.org](https://www.python.org/downloads/))

### 🍎 macOS
1. `git clone https://github.com/NatoandUSA/fbpost.git`
2. Mở thư mục `fbpost` trong Finder
3. **Double-click** vào file `START_MAC.command`
4. Nếu bị chặn bởi Gatekeeper: Chuột phải → Open → Open

### 🪟 Windows
1. `git clone https://github.com/NatoandUSA/fbpost.git`
2. Mở thư mục `fbpost`
3. **Double-click** vào file `START_WINDOWS.bat`

### 🐧 Linux
```bash
git clone https://github.com/NatoandUSA/fbpost.git
cd fbpost
bash START_LINUX.sh
```

> Script sẽ tự động tạo môi trường ảo, cài thư viện, cài Chromium và mở Dashboard tại **http://127.0.0.1:5000** 🎉

---

## 📋 Hướng Dẫn Sử Dụng

### Bước 1: Đăng nhập Facebook
- Mở Dashboard → Bấm nút **"Authenticate (Login)"**
- Một cửa sổ Chromium sẽ xuất hiện
- Đăng nhập Facebook, vượt 2FA nếu có
- Quay lại Terminal bấm **Enter** → Session được lưu vào `state.json`

### Bước 2: Chọn loại đăng
- **Group / Page / Thread** (chọn tab tương ứng)

### Bước 3: Nhập dữ liệu
**Chế độ Manual:**
- Dán danh sách link (mỗi link 1 dòng)
- Nhập nội dung (hỗ trợ Spintax)

**Chế độ Google Sheets:**
1. Tạo Google Sheet với 3 cột:
   - Cột A: Link Group/Page/Thread ID
   - Cột B: Nội dung bài (hỗ trợ Spintax `{...}`)
   - Cột C: Đường dẫn ảnh trên máy (tùy chọn)
2. File → Share → **Publish to web** → Dạng CSV → Copy link
3. Dán link CSV vào Dashboard

### Bước 4: Post Now!

---

## 📁 Cấu Trúc Project

```
fbpost/
├── START_MAC.command      # 1-click launcher cho macOS
├── START_WINDOWS.bat      # 1-click launcher cho Windows
├── START_LINUX.sh         # 1-click launcher cho Linux
├── server.py              # Flask backend API
├── main.py                # CLI entrypoint
├── fb_auth.py             # Quản lý đăng nhập & session
├── fb_group.py            # Đăng bài vào Group
├── fb_page.py             # Đăng bài vào Page
├── fb_thread.py           # Gửi tin nhắn Thread
├── fb_interact.py         # Tương tác (Like, Comment...)
├── fb_scraper.py          # Scrape dữ liệu
├── utils.py               # Spintax + Human Typing
├── requirements.txt       # Python dependencies
├── sample_import.csv      # File CSV mẫu
└── static/                # Dashboard UI (HTML/CSS/JS)
```

---

## ⚠️ Lưu Ý Quan Trọng

> **File `state.json` (Session đăng nhập) KHÔNG được commit lên GitHub.** Trên mỗi máy mới cần chạy bước Authenticate lại một lần.

> Công cụ này vi phạm Điều khoản Dịch vụ của Facebook. Sử dụng có trách nhiệm và chịu rủi ro về tài khoản.
