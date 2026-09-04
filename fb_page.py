import sys
import os
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import (
    process_spintax, human_type, load_accounts, launch_browser,
    close_browser, add_feeling, add_checkin, scrape_post_link,
    attach_image_to_composer, pick_random_photos, is_recently_posted
)
from ai_spinner import generate_unique_variant

STATE_FILE = "state.json"

def post_to_page(page_url, content, image_path=None, account_id=None, gpm_api_url=None, feeling=False, checkin=False,
                 photos_folder=None, photo_count="2-4", auto_spin=False, gemini_key=None, skip_duplicate=False):
    # 1. Kiểm tra lọc trùng lặp 24h nếu bật
    if skip_duplicate:
        is_dup, hours_ago, posted_at = is_recently_posted(page_url)
        if is_dup:
            print(f"⏭️ [Bỏ qua trùng lặp 24h] Trang {page_url} đã được đăng lúc {posted_at} ({hours_ago}h trước). Bỏ qua theo cài đặt bảo vệ tài khoản.")
            return

    # 2. Xào bài viết qua AI Content Spinner nếu bật
    if auto_spin:
        print("🤖 [AI Spinner] Đang tạo biến thể bài viết mới lạ, chống trùng lặp spam...")
        content = generate_unique_variant(content, gemini_key)

    # 3. Bốc ảnh ngẫu nhiên từ thư mục nếu có chỉ định
    if photos_folder and not image_path:
        image_path = pick_random_photos(photos_folder, photo_count)

    print(f"👉 Bắt đầu mở Page quản trị và đăng bài: {page_url}")
    content = process_spintax(content)
    
    # Load account if provided
    account = None
    if account_id:
        accounts = load_accounts()
        account = next((a for a in accounts if a["id"] == account_id), None)
        if not account:
            print(f"❌ Error: Account ID '{account_id}' not found in accounts.json.")
            return

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

            page.set_default_timeout(45000)

            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as nav_err:
                print(f"⚠️ Cảnh báo tải trang Fanpage: {nav_err}. Đang kiểm tra bỏ qua cảnh báo SSL...")
                time.sleep(1.5)
                try:
                    if page.locator("#details-button").is_visible(timeout=2000):
                        page.click("#details-button")
                        time.sleep(1)
                        if page.locator("#proceed-link").is_visible(timeout=2000):
                            page.click("#proceed-link")
                            time.sleep(2)
                except Exception:
                    pass
            time.sleep(random.uniform(3.0, 5.0))
            
            # 1. Kiểm tra New Page Experience: Có nút "Chuyển sang trang" / "Switch now" hay không
            try:
                switch_button = page.locator("div[role='button']").filter(
                    has_text=re.compile(r"Chuyển ngay|Chuyển sang|Switch now|Switch into page|Tương tác với vai trò", re.IGNORECASE)
                ).first
                if switch_button.is_visible(timeout=4000):
                    print("🔄 Phát hiện Fanpage New Page Experience. Đang bấm chuyển đổi danh tính sang Trang quản trị...")
                    switch_button.click()
                    time.sleep(random.uniform(4.0, 6.0))
                    page.wait_for_load_state("domcontentloaded")
            except Exception as e:
                pass

            # Cuộn trang nhẹ nhàng
            page.mouse.wheel(0, random.randint(200, 500))
            time.sleep(random.uniform(1.0, 2.0))
            page.mouse.wheel(0, -random.randint(100, 250))
            time.sleep(random.uniform(1.0, 2.0))
            
            print("🔍 Đang tìm ô đăng bài trên Fanpage...")
            composer_box = None
            page_composer_patterns = [
                r"Bạn đang nghĩ gì",
                r"Tạo bài viết",
                r"Tạo bài đăng",
                r"Viết gì đó",
                r"What's on your mind",
                r"Create post",
                r"Write something"
            ]
            combined_regex = re.compile("|".join(page_composer_patterns), re.IGNORECASE)

            # Tìm qua button hoặc text
            buttons = page.locator("div[role='button']").filter(has_text=combined_regex)
            if buttons.count() > 0:
                for idx in range(buttons.count()):
                    btn = buttons.nth(idx)
                    if btn.is_visible():
                        composer_box = btn
                        break

            if not composer_box:
                try:
                    fallback_box = page.get_by_text(combined_regex).first
                    if fallback_box.is_visible():
                        composer_box = fallback_box
                except Exception:
                    pass

            if not composer_box:
                fallback_aria = page.locator("div[aria-label*='Tạo bài viết' i], div[aria-label*='Create post' i]").first
                if fallback_aria.is_visible():
                    composer_box = fallback_aria

            if not composer_box:
                print("❌ Không tìm thấy ô đăng bài trên Page. Vui lòng đảm bảo tài khoản đã được cấp quyền Quản trị viên hoặc Biên tập viên trên Page này.")
                return
            
            print("👉 Click mở ô soạn thảo bài viết...")
            composer_box.click()
            time.sleep(random.uniform(2.5, 4.0))

            # Chờ Dialog modal mở hoàn toàn
            dialog = None
            try:
                page.wait_for_selector("div[role='dialog']", state="visible", timeout=10000)
                dialog = page.locator("div[role='dialog']").first
            except Exception:
                dialog = page.locator("div[role='dialog']").first

            textbox = None
            if dialog and dialog.is_visible():
                candidates = dialog.locator("div[role='textbox']")
                for idx in range(candidates.count()):
                    c = candidates.nth(idx)
                    label = (c.get_attribute("aria-label") or "") + " " + (c.get_attribute("aria-placeholder") or "")
                    if "bình luận" not in label.lower() and "comment" not in label.lower():
                        textbox = c
                        break
                if not textbox and candidates.count() > 0:
                    textbox = candidates.first

            # Fallback nếu không có dialog: quét textbox trên trang và loại bỏ ô bình luận
            if not textbox:
                candidates = page.locator("div[role='textbox']")
                for idx in range(candidates.count()):
                    c = candidates.nth(idx)
                    label = (c.get_attribute("aria-label") or "") + " " + (c.get_attribute("aria-placeholder") or "")
                    if "bình luận" not in label.lower() and "comment" not in label.lower() and c.is_visible():
                        textbox = c
                        break
            
            # Đính kèm ảnh nếu có
            if image_path:
                attach_image_to_composer(page, dialog, image_path)
            
            print("✍️ Đang nhập nội dung bài viết...")
            if textbox and textbox.is_visible():
                human_type(page, textbox, content)
            else:
                page.keyboard.type(content)
            time.sleep(random.uniform(1.5, 2.5))
            
            # Thêm Feeling
            if feeling:
                add_feeling(page)
                
            # Thêm Check-in
            if checkin:
                add_checkin(page)
            
            # Tạm dừng 5 - 10s mô phỏng người dùng đọc lại bài viết trước khi bấm đăng (Anti-bot)
            review_delay = random.uniform(5.0, 10.0)
            print(f"👀 Tạm dừng {review_delay:.1f}s kiểm tra lại bài viết trước khi đăng...")
            time.sleep(review_delay)

            print("🚀 Đang bấm nút 'Đăng' bài viết...")
            post_button = None
            post_selectors = [
                "div[role='dialog'] div[aria-label='Đăng']",
                "div[role='dialog'] div[aria-label='Post']",
                "div[role='dialog'] div[role='button']:has-text('Đăng')",
                "div[role='dialog'] div[role='button']:has-text('Post')",
                "div[aria-label='Đăng']",
                "div[aria-label='Post']"
            ]

            for btn_sel in post_selectors:
                btn = page.locator(btn_sel).first
                if btn.is_visible() and btn.is_enabled():
                    post_button = btn
                    break

            if post_button:
                try:
                    post_button.click(force=True)
                except Exception:
                    post_button.click()
            else:
                # Fallback role button
                page.get_by_role("button", name=re.compile(r"^(Đăng|Post)$", re.IGNORECASE)).first.click(force=True)

            # Chờ 6 - 10s để Facebook upload hoàn tất bài đăng lên máy chủ
            wait_uploaded = random.uniform(6.0, 10.0)
            print(f"⏳ Đang chờ {wait_uploaded:.1f}s để Facebook lưu và hoàn tất bài đăng...")
            time.sleep(wait_uploaded)
            
            # Quét tìm và tự động lưu liên kết bài đăng vừa tạo
            scrape_post_link(page, target=page_url, content=content)
            print("✅ Đã đăng bài lên Fanpage quản trị thành công!")
            
    except Exception as e:
        print(f"❌ Xảy ra lỗi khi đăng bài lên Page: {e}")
    finally:
        if account:
            close_browser(browser_obj if browser_obj else context, account, gpm_api_url)
        else:
            if browser_obj:
                try:
                    browser_obj.close()
                except Exception:
                    pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("content")
    parser.add_argument("--image", default=None)
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    parser.add_argument("--feeling", action="store_true")
    parser.add_argument("--checkin", action="store_true")
    args = parser.parse_args()
    
    post_to_page(args.url, args.content, args.image, args.account_id, args.gpm_api, args.feeling, args.checkin)
