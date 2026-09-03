import sys
import os
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import process_spintax, human_type, load_accounts, launch_browser, close_browser, add_feeling, add_checkin, scrape_post_link

STATE_FILE = "state.json"

def post_to_group(group_url, content, image_path=None, account_id=None, gpm_api_url=None, feeling=False, checkin=False):
    print(f"👉 Bắt đầu mở Group và đăng bài: {group_url}")
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

            # Mô phỏng di chuyển chuột và vào nhóm
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            try:
                page.goto(group_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as nav_err:
                print(f"⚠️ Cảnh báo tải trang Group: {nav_err}. Đang kiểm tra bỏ qua cảnh báo SSL...")
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
            
            # Cuộn trang nhẹ nhàng
            page.mouse.wheel(0, random.randint(200, 500))
            time.sleep(random.uniform(1.0, 2.0))
            page.mouse.wheel(0, -random.randint(100, 250))
            time.sleep(random.uniform(1.0, 2.0))
            
            print("🔍 Đang tìm ô đăng bài trong Group...")
            # Danh sách các pattern tìm ô đăng bài Group cả tiếng Việt & tiếng Anh
            composer_box = None
            composer_patterns = [
                r"Bạn viết gì đi",
                r"Tạo bài viết công khai",
                r"Viết gì đó",
                r"Tạo bài viết",
                r"Tạo bài đăng",
                r"Write something",
                r"Create a public post",
                r"What's on your mind"
            ]

            combined_regex = re.compile("|".join(composer_patterns), re.IGNORECASE)

            # Cách 1: Tìm qua role button có text phù hợp
            buttons = page.locator("div[role='button']").filter(has_text=combined_regex)
            if buttons.count() > 0:
                for idx in range(buttons.count()):
                    btn = buttons.nth(idx)
                    if btn.is_visible():
                        composer_box = btn
                        break

            # Cách 2: Fallback tìm get_by_text
            if not composer_box:
                try:
                    fallback_box = page.get_by_text(combined_regex).first
                    if fallback_box.is_visible():
                        composer_box = fallback_box
                except Exception:
                    pass

            # Cách 3: Fallback qua aria-label
            if not composer_box:
                fallback_aria = page.locator("div[aria-label*='Tạo bài viết' i], div[aria-label*='Create a post' i]").first
                if fallback_aria.is_visible():
                    composer_box = fallback_aria

            if not composer_box:
                print("❌ Không tìm thấy ô đăng bài. Hãy kiểm tra bạn đã tham gia nhóm hoặc nhóm có yêu cầu quyền duyệt thành viên hay không.")
                return

            print("👉 Click mở ô soạn thảo bài viết...")
            composer_box.click()
            time.sleep(random.uniform(2.0, 3.5))

            # Chờ hộp thoại soạn bài (Dialog modal)
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
            
            # Thêm Feeling nếu được chọn
            if feeling:
                add_feeling(page)
                
            # Thêm Check-in nếu được chọn
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
                # Fallback role button
                page.get_by_role("button", name=re.compile(r"^(Đăng|Post)$", re.IGNORECASE)).first.click()

            time.sleep(random.uniform(3.0, 5.0))

            # Xử lý nếu xuất hiện popup Quy tắc nhóm / Nội quy
            try:
                rules_dialog = page.locator("div[role='dialog']").filter(has_text=re.compile(r"Quy tắc nhóm|Group rules|Tôi đồng ý|I agree", re.IGNORECASE)).first
                if rules_dialog.is_visible():
                    print("⚠️ Phát hiện popup quy tắc nhóm. Đang tự động tích đồng ý và gửi...")
                    checkbox = rules_dialog.locator("input[type='checkbox'], div[role='checkbox']").first
                    if checkbox.is_visible():
                        checkbox.click()
                        time.sleep(1.0)
                    submit_btn = rules_dialog.locator("div[role='button']").filter(has_text=re.compile(r"Gửi|Submit|Đồng ý|Agree", re.IGNORECASE)).first
                    if submit_btn.is_visible():
                        submit_btn.click()
                        time.sleep(2.0)
            except Exception:
                pass
            
            # Quét tìm liên kết bài đăng vừa tạo
            scrape_post_link(page)
            print("✅ Đã đăng bài vào Group thành công!")
            
    except Exception as e:
        print(f"❌ Xảy ra lỗi khi đăng bài vào Group: {e}")
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
    
    post_to_group(args.url, args.content, args.image, args.account_id, args.gpm_api, args.feeling, args.checkin)
