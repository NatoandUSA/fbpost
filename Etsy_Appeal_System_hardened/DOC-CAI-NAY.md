# Deploy an toàn — Etsy Appeal System

Worker phục vụ form tĩnh và API cùng origin. Hệ thống chỉ nhận hồ sơ sau khi
đã xác minh Turnstile, kiểm tra mã nhóm và qua rate limit. Hồ sơ tự xóa sau 90
ngày, trừ khi bạn thay `RETENTION_DAYS` trong `wrangler.toml` (7–365 ngày).

## Trước khi deploy

1. Tạo một Turnstile widget cho đúng domain `appeal.theglobalserviceteam.site`.
2. Thay `REPLACE_WITH_YOUR_TURNSTILE_SITE_KEY` trong `public/index.html` bằng
   **site key** của widget. Site key là thông tin public.
3. Kiểm tra `APP_ORIGIN` trong `wrangler.toml` là đúng domain HTTPS đang phục
   vụ app. Không dùng `null`, `file://`, wildcard hay domain tạm.
4. Đặt ba secrets, bằng các giá trị dài, riêng biệt và không đưa vào source:

```powershell
npx wrangler secret put MASTER_KEY
npx wrangler secret put TEAM_CODE
npx wrangler secret put TURNSTILE_SECRET
```

`MASTER_KEY` chỉ dành cho quản lý. `TEAM_CODE` là mã chia sẻ để nộp hồ sơ;
đổi ngay khi nhân sự rời nhóm. `TURNSTILE_SECRET` là secret của widget, không
bao giờ đặt vào HTML hay `wrangler.toml`.

## Cài database và deploy

```powershell
npx wrangler d1 execute etsy-appeals --remote --file=schema.sql
npx wrangler deploy
```

`wrangler.toml` đã có binding rate limit và cron cleanup. Không bỏ hai phần
này: Worker sẽ fail closed và từ chối API nếu rate limiter không được deploy.

## Kiểm tra tối thiểu sau deploy

1. Mở domain HTTPS; trang phải tải được và Turnstile phải hiện trong phần gửi.
2. Dùng dữ liệu giả, tick consent và gửi thử; chỉ thành công khi Turnstile hợp
   lệ và đúng mã nhóm.
3. Mở quản lý, nhập Master Key, xem hồ sơ test, rồi bấm **Xóa** để kiểm tra
   luồng xóa dữ liệu.
4. Kiểm tra `/api/health` chỉ từ chính trang domain. Endpoint chỉ trả
   `{"ok":true}`; không còn tiết lộ DB, secrets hay số hồ sơ.

## Quy tắc vận hành dữ liệu

- Chỉ thu thập thông tin thật sự cần để review appeal.
- Thông báo rõ cho người gửi rằng quản lý sẽ thấy hồ sơ và hệ thống sẽ lưu tối
  đa theo số ngày đã công bố.
- Không gửi Master Key qua chat/email; không lưu trong browser hoặc file.
- Xóa hồ sơ ngay khi không còn mục đích xử lý; cron là lớp dự phòng, không phải
  lý do để giữ dữ liệu lâu hơn.
- Không bật log request body hay sao chép CCCD/sao kê vào log/ticket.

## Lưu ý policy

Tool chỉ giúp cấu trúc thông tin. Người dùng phải đối chiếu email suspension và
form Appeals Centre đang hiện trên chính tài khoản của mình. Không tự nhận đã
vi phạm hoặc đã khắc phục nếu không có sự kiện thật và bằng chứng phù hợp.
