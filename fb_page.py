import sys
import os
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, launch_browser, close_browser, add_feeling, add_checkin, scrape_post_link

STATE_FILE = "state.json"

def post_to_page(page_url, content, image_path=None, account_id=None, gpm_api_url=None, feeling=False, checkin=False):
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
                print(f"⚠️ Cảnh báo tải trang Fanpage: {nav_err}. Tiếp tục tìm ô đăng bài...")
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
            time.sleep(random.uniform(2.0, 3.5))

            # Chờ Dialog modal hiện lên
            dialog = page.locator("div[role='dialog']").first
            textbox = None

            if dialog.is_visible():
                textbox = dialog.locator("div[role='textbox']").first
            else:
                textbox = page.locator("div[role='textbox']").first
            
            # Đính kèm ảnh nếu có
            if image_path and os.path.exists(image_path):
                print(f"📸 Đang đính kèm hình ảnh: {image_path}")
                try:
                    file_input = page.locator("input[type='file'][accept*='image']").first
                    file_input.set_input_files(image_path)
                    print("⏳ Đang chờ ảnh tải lên...")
                    time.sleep(random.uniform(4.0, 7.0))
                except Exception as e:
                    print(f"⚠️ Cảnh báo: Không thể đính kèm ảnh: {e}")
            
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
                post_button.click()
            else:
                page.get_by_role("button", name=re.compile(r"^(Đăng|Post)$", re.IGNORECASE)).first.click()

            time.sleep(random.uniform(4.0, 6.0))
            
            # Quét tìm liên kết bài đăng vừa tạo
            scrape_post_link(page)
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
