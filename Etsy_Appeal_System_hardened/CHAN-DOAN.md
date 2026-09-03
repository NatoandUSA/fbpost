# Chẩn đoán an toàn

## Submit bị từ chối

- **“Hoàn tất xác minh chống bot”**: chưa cấu hình site key trong HTML, widget
  chưa tải, hoặc chưa hoàn thành Turnstile.
- **“Xác minh chống bot không thành công”**: kiểm tra `TURNSTILE_SECRET` có
  thuộc đúng widget/site key/domain hay không. Không in secret ra Console.
- **“Mã nhóm không hợp lệ”**: đặt lại `TEAM_CODE` bằng `wrangler secret put`;
  không gửi mã qua kênh công khai.
- **429 / “tạm từ chối request”**: rate limit đã kích hoạt. Chờ một phút rồi
  thử lại; không tắt rate limit để “sửa nhanh”.
- **403 / “Không được phép”**: trang đang được mở từ sai domain, HTTP, hoặc
  `APP_ORIGIN` không khớp tuyệt đối với URL HTTPS đang dùng.

## Quản lý không xem được hồ sơ

Master Key phải được đặt bằng `wrangler secret put MASTER_KEY`, rồi nhập ở ô
quản lý. Browser gửi key qua header Authorization; key không được lưu vào D1
hay localStorage. Nếu nghi lộ key, thay ngay secret và deploy lại.

## Kiểm tra service

Mở từ chính trang đã deploy:

```
https://appeal.theglobalserviceteam.site/api/health
```

Kết quả hợp lệ là `{"ok":true}`. Endpoint cố ý không tiết lộ binding, cấu hình
secrets hoặc số lượng hồ sơ.

## Database

Nếu API trả “Máy chủ gặp lỗi”, chỉ quản trị viên mới chạy:

```powershell
npx wrangler d1 execute etsy-appeals --remote --command="SELECT name FROM sqlite_master WHERE type='table'"
```

Phải thấy `submissions`. Tạo bảng nếu cần:

```powershell
npx wrangler d1 execute etsy-appeals --remote --file=schema.sql
```

Không dán output chứa thông tin hồ sơ, secrets, CCCD, email hoặc nội dung appeal
vào chat/ticket. Chỉ chia sẻ request ID/thời điểm và lỗi đã được che dữ liệu.
