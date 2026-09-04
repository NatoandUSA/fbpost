import sys
import os
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, resolve_account, launch_browser, close_browser

STATE_FILE = "state.json"

def comment_on_post(post_url, comment_content, account_id=None, gpm_api_url=None, like_post=True, anti_hash_text=True):
    """
    Tự động mở một bài viết Facebook (trong Group public hoặc Fanpage public) và để lại bình luận.
    Hỗ trợ Spintax, human typing, like trước khi comment, và xử lý các loại giao diện Facebook.
    """
    print(f"🔗 Đang mở bài viết để bình luận: {post_url}")
    parsed_comment = process_spintax(comment_content, anti_hash=anti_hash_text)
    
    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Lỗi: Không thể khởi tạo cấu hình cho Account ID '{account_id}'.")
            return False
        print(f"👤 Khởi chạy profile: {account.get('name', account_id)} ({account.get('type', 'local')})")

    browser_obj = None
    context = None
    try:
        with sync_playwright() as p:
            if account:
                browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            else:
                print("Dùng session mặc định (state.json).")
                browser_obj = p.chromium.launch(headless=False)
                state_arg = STATE_FILE if os.path.exists(STATE_FILE) else None
                context = browser_obj.new_context(storage_state=state_arg)
                page = context.new_page()

            page.set_default_timeout(25000)
            
            # Di chuyển chuột ngẫu nhiên
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            page.goto(post_url, wait_until="domcontentloaded")
            time.sleep(random.uniform(3.0, 5.0))

            # Cuộn trang nhẹ nhàng mô phỏng hành vi đọc bài viết
            page.mouse.wheel(0, random.randint(250, 550))
            time.sleep(random.uniform(1.5, 3.0))
            page.mouse.wheel(0, -random.randint(100, 250))
            time.sleep(random.uniform(1.0, 2.0))

            # 1. Tương tác Thích / Thả Tim nếu được yêu cầu
            if like_post:
                try:
                    like_btn = page.locator("div[role='button']").filter(
                        has_text=re.compile(r"^(Thích|Like)$", re.IGNORECASE)
                    ).first
                    if like_btn.is_visible(timeout=3500):
                        aria_pressed = like_btn.get_attribute("aria-pressed")
                        if aria_pressed != "true":
                            reacted = False
                            # Tỷ lệ 70% thả Tim (Love), 30% Thích (Like)
                            if random.random() < 0.70:
                                try:
                                    print("❤️ Đang hover để thả Tim (Love) bài viết...")
                                    like_btn.hover()
                                    time.sleep(random.uniform(0.8, 1.4))
                                    # Tìm icon Yêu thích trong popover reactions
                                    love_btn = page.locator("div[aria-label*='Yêu thích' i], div[aria-label*='Love' i], div[role='toolbar'] div[role='button']").nth(1)
                                    if love_btn.is_visible(timeout=2000):
                                        love_btn.click(force=True)
                                        reacted = True
                                        print("❤️ Đã thả Tim (Love) bài viết thành công!")
                                        time.sleep(random.uniform(2.0, 3.5))
                                except Exception:
                                    pass
                            
                            if not reacted:
                                print("👍 Đang bấm Thích (Like) bài viết...")
                                like_btn.click(force=True)
                                print("👍 Đã thả Like bài viết thành công!")
                                time.sleep(random.uniform(1.5, 3.0))
                except Exception as e:
                    print(f"⚠️ Bỏ qua bước tương tác cảm xúc: {e}")

            # 2. Tìm ô nhập bình luận
            print("🔍 Đang tìm ô bình luận...")
            comment_input = None

            # Danh sách các bộ chọn tìm ô comment linh hoạt cho FB 2026
            selectors = [
                "div[role='textbox'][aria-label*='bình luận' i]",
                "div[role='textbox'][aria-label*='comment' i]",
                "div[role='textbox'][aria-placeholder*='bình luận' i]",
                "div[role='textbox'][aria-placeholder*='comment' i]",
                "div[role='textbox'][data-lexical-editor='true']",
                "div[contenteditable='true'][role='textbox']"
            ]

            for selector in selectors:
                candidates = page.locator(selector)
                count = candidates.count()
                for i in range(count):
                    el = candidates.nth(i)
                    if el.is_visible():
                        comment_input = el
                        break
                if comment_input:
                    break

            # Nếu chưa thấy ô textbox, có thể cần click nút "Viết bình luận" hoặc "Bình luận"
            if not comment_input:
                open_comment_buttons = [
                    "div[role='button']:has-text('Viết bình luận')",
                    "div[role='button']:has-text('Write a comment')",
                    "div[role='button']:has-text('Bình luận')",
                    "div[role='button']:has-text('Comment')",
                    "div[aria-label*='bình luận' i][role='button']",
                    "div[aria-label*='comment' i][role='button']"
                ]
                for btn_sel in open_comment_buttons:
                    btn = page.locator(btn_sel).first
                    if btn.is_visible():
                        print("👉 Click mở ô bình luận...")
                        btn.click()
                        time.sleep(random.uniform(1.5, 3.0))
                        break

                # Thử tìm lại ô textbox sau khi click
                for selector in selectors:
                    el = page.locator(selector).first
                    if el.is_visible():
                        comment_input = el
                        break

            if not comment_input or not comment_input.is_visible():
                print("❌ Không tìm thấy ô bình luận trên bài viết này (Bài viết có thể bị tắt tính năng bình luận hoặc yêu cầu phê duyệt).")
                return False

            # 3. Focus và gõ nội dung bình luận
            print(f"💬 Đang gõ nội dung bình luận: \"{parsed_comment}\"")
            comment_input.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.8, 1.5))
            comment_input.click()
            time.sleep(random.uniform(0.5, 1.0))
            
            human_type(page, comment_input, parsed_comment)
            time.sleep(random.uniform(1.0, 2.0))

            # 4. Nhấn Enter để gửi bình luận
            print("🚀 Nhấn Enter gửi bình luận...")
            page.keyboard.press("Enter")
            time.sleep(random.uniform(3.0, 5.0))

            # Kiểm tra nhanh lỗi spam cảnh báo từ Facebook
            spam_warning = page.locator("text='Bạn tạm thời bị chặn'").first
            if spam_warning.is_visible():
                print("⚠️ Cảnh báo Facebook: Bạn tạm thời bị hạn chế tính năng bình luận.")
                return False

            print("✅ Đã bình luận bài viết thành công!")
            return True

    except Exception as e:
        print(f"❌ Xảy ra lỗi khi bình luận vào bài viết: {e}")
        return False
    finally:
        if account:
            close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
        else:
            if browser_obj:
                try:
                    browser_obj.close()
                except Exception:
                    pass

def comment_on_list(urls, comment_content, account_id=None, gpm_api_url=None, like_post=True, min_delay=25, max_delay=45, anti_hash_text=True):
    """
    Duyệt qua danh sách link bài viết và bình luận lần lượt.
    """
    total = len(urls)
    print(f"\n=======================================================")
    print(f"🚀 BẮT ĐẦU CHẠY BÌNH LUẬN VÀO {total} BÀI VIẾT ĐÃ CHỌN")
    print(f"=======================================================\n")

    success_count = 0
    fail_count = 0

    for idx, url in enumerate(urls, 1):
        url = url.strip()
        if not url:
            continue

        print(f"\n[{idx}/{total}] Đang xử lý: {url}")
        ok = comment_on_post(
            post_url=url,
            comment_content=comment_content,
            account_id=account_id,
            gpm_api_url=gpm_api_url,
            like_post=like_post,
            anti_hash_text=anti_hash_text
        )

        if ok:
            success_count += 1
        else:
            fail_count += 1

        if idx < total:
            delay = random.randint(min_delay, max_delay)
            print(f"\n⏳ [Anti-Spam] Nghỉ {delay} giây trước khi chuyển sang link tiếp theo...")
            for sec in range(delay, 0, -1):
                if sec % 10 == 0 or sec <= 5:
                    print(f"... còn {sec}s")
                time.sleep(1)

    print(f"\n🎉 HOÀN THÀNH TẤT CẢ! Thành công: {success_count} | Thất bại: {fail_count}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tự động bình luận vào bài viết Group / Fanpage Facebook")
    parser.add_argument("url", nargs="?", help="URL bài viết cần comment")
    parser.add_argument("content", nargs="?", help="Nội dung comment (hỗ trợ Spintax)")
    parser.add_argument("--urls-file", help="Đường dẫn file chứa danh sách link (mỗi dòng 1 link)")
    parser.add_argument("--account-id", default=None, help="ID tài khoản trong accounts.json")
    parser.add_argument("--gpm-api", default=None, help="URL GPM API")
    parser.add_argument("--like", action="store_true", default=True, help="Tự động like trước khi comment")
    parser.add_argument("--min-delay", type=int, default=25, help="Thời gian nghỉ tối thiểu (giây)")
    parser.add_argument("--max-delay", type=int, default=45, help="Thời gian nghỉ tối đa (giây)")
    parser.add_argument("--anti-hash-text", action="store_true", default=True, help="Chèn ký tự tàng hình chống quét trùng lặp")
    parser.add_argument("--no-anti-hash-text", dest="anti_hash_text", action="store_false")
    args = parser.parse_args()

    if args.urls_file and os.path.exists(args.urls_file):
        with open(args.urls_file, "r", encoding="utf-8") as f:
            target_urls = [line.strip() for line in f if line.strip()]
        content = args.content or "Bài viết rất hữu ích!"
        comment_on_list(target_urls, content, args.account_id, args.gpm_api, args.like, args.min_delay, args.max_delay, anti_hash_text=args.anti_hash_text)
    elif args.url and args.content:
        comment_on_post(args.url, args.content, args.account_id, args.gpm_api, args.like, anti_hash_text=args.anti_hash_text)
    else:
        parser.print_help()
