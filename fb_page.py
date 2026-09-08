import sys
import os
import time
import random
import re
from playwright.sync_api import sync_playwright
from utils import (
    process_spintax, human_type, load_accounts, resolve_account, launch_browser,
    close_browser, add_feeling, add_checkin, scrape_post_link,
    attach_image_to_composer, pick_random_photos, is_recently_posted,
    click_post_publish_button, safe_mouse_wheel, ActionResult, verify_entered_content
)
from ai_spinner import generate_unique_variant

STATE_FILE = "state.json"

def post_to_page(page_url, content, image_path=None, account_id=None, gpm_api_url=None, feeling=False, checkin=False,
                 photos_folder=None, photo_count="2-4", auto_spin=False, gemini_key=None, skip_duplicate=False,
                 anti_hash_text=False, clean_exif=True):
    # 1. Kiểm tra lọc trùng lặp 24h nếu bật
    if skip_duplicate:
        is_dup, hours_ago, posted_at = is_recently_posted(page_url)
        if is_dup:
            print(f"⏭️ [Bỏ qua trùng lặp 24h] Trang {page_url} đã được đăng lúc {posted_at} ({hours_ago}h trước). Bỏ qua theo cài đặt bảo vệ tài khoản.")
            return ActionResult(success=True, code="SKIPPED_DUPLICATE", message=f"Trang {page_url} đã được đăng lúc {posted_at}.", target_url=page_url)

    # 2. Xào bài viết qua AI Content Spinner nếu bật
    if auto_spin:
        print("🤖 [AI Spinner] Đang tạo biến thể bài viết mới lạ, chống trùng lặp spam...")
        content = generate_unique_variant(content, gemini_key)

    # 3. Bốc ảnh ngẫu nhiên từ thư mục nếu có chỉ định
    if photos_folder and not image_path:
        image_path = pick_random_photos(photos_folder, photo_count, clean_exif=clean_exif)

    print(f"👉 Bắt đầu mở Page quản trị và đăng bài: {page_url}")
    content = process_spintax(content, anti_hash=anti_hash_text)
    
    # Load account if provided
    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Error: Không thể khởi tạo cấu hình cho Account ID '{account_id}'.")
            return ActionResult(success=False, code="ACCOUNT_NOT_FOUND", message=f"Không thể khởi tạo cấu hình cho Account ID '{account_id}'.", target_url=page_url)
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

            # Tự động đóng popup che khuất màn hình nếu có
            try:
                popup_close = page.locator("div[role='dialog'] div[aria-label*='Đóng' i], div[role='dialog'] div[aria-label*='Close' i]").first
                if popup_close.is_visible(timeout=1000):
                    dialog_text = page.locator("div[role='dialog']").first.inner_text().lower()
                    if "tạo bài viết" not in dialog_text and "create post" not in dialog_text and "bạn đang nghĩ gì" not in dialog_text:
                        print("🧹 Tự động đóng popup che khuất màn hình...")
                        popup_close.click(force=True)
                        time.sleep(1.0)
            except Exception:
                pass

            # Cuộn trang nhẹ nhàng (an toàn)
            safe_mouse_wheel(page, 0, random.randint(200, 500))
            time.sleep(random.uniform(1.0, 2.0))
            safe_mouse_wheel(page, 0, -random.randint(100, 250))
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
                return ActionResult(success=False, code="COMPOSER_NOT_FOUND", message="Không tìm thấy ô đăng bài trên Page.", target_url=page_url)
            
            print("👉 Click mở ô soạn thảo bài viết...")
            composer_box.click()
            time.sleep(random.uniform(2.5, 4.0))

            # Chờ Dialog modal mở hoàn toàn
            dialog = None
            try:
                page.wait_for_selector("div[role='dialog']", state="visible", timeout=10000)
                dialog = page.locator("div[role='dialog']").last
            except Exception:
                dialog = page.locator("div[role='dialog']").last

            textbox = None
            if dialog and dialog.is_visible():
                try:
                    dialog.wait_for_selector("div[role='textbox']", timeout=4000)
                except Exception:
                    pass
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
            
            # 1. Nhập nội dung bài viết trước để tránh bị nuốt phím khi gắn ảnh
            print("✍️ Đang nhập nội dung bài viết...")
            if not textbox or not textbox.is_visible():
                print("❌ Không tìm thấy textbox soạn bài đáng tin cậy; dừng trước khi submit.")
                return ActionResult(success=False, code="COMPOSER_TEXTBOX_NOT_FOUND", message="Không tìm thấy ô soạn bài.", target_url=page_url)
            human_type(page, textbox, content)
            time.sleep(0.6)
            if not verify_entered_content(textbox, content):
                print("❌ Nội dung composer thiếu chữ ký/hashtag bắt buộc; dừng trước khi submit.")
                return ActionResult(success=False, code="CONTENT_ENTRY_INCOMPLETE", message="Nội dung composer không khớp nội dung chuẩn bị đăng.", target_url=page_url)
            print(f"✅ Đã xác minh nội dung composer: {len(content)} ký tự · chữ ký/hashtag đầy đủ.")

            # 2. Đính kèm ảnh nếu có (sau khi đã có nội dung văn bản)
            if image_path:
                img_ok = attach_image_to_composer(page, dialog, image_path, clean_exif=clean_exif)
                if not img_ok:
                    print(f"❌ Không thể đính kèm ảnh: {image_path}")
                    return ActionResult(
                        success=False,
                        code="MEDIA_ATTACH_FAILED",
                        message=f"Không thể đính kèm ảnh vào bài viết: {image_path}",
                        target_url=page_url
                    )
            
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

            # 3. Tìm và bấm chính xác nút 'Đăng' (loại bỏ các nút sai và xác nhận dialog đóng)
            print("🚀 Đang bấm nút 'Đăng' / 'Chia sẻ' bài viết...")
            published = click_post_publish_button(page, dialog)
            if not published and getattr(published, "state", "") != "submitted_unverified":
                print("❌ Chưa trigger được submit hoặc Facebook trả lỗi xác định trước khi tiếp nhận.")
                return ActionResult(success=False, code="PUBLISH_FAILED", message="Chưa trigger được submit hoặc Facebook trả lỗi xác định.", target_url=page_url)
            if getattr(published, "state", "") == "submitted_unverified":
                print("⚠️ Submit đã được trigger nhưng terminal state chưa rõ; chỉ đối soát, không gửi lại.")

            # Chờ 3 - 5s để Facebook cập nhật feed
            time.sleep(random.uniform(3.0, 5.0))

            # Chờ 4 - 6s để Facebook upload hoàn tất bài đăng lên máy chủ
            wait_uploaded = random.uniform(4.0, 6.0)
            print(f"⏳ Đang chờ {wait_uploaded:.1f}s để Facebook lưu và hoàn tất bài đăng...")
            time.sleep(wait_uploaded)
            
            # Quét tìm và tự động lưu liên kết bài đăng vừa tạo
            action_res = scrape_post_link(page, target=page_url, content=content, account_id=account_id)
            if action_res.state == "published":
                print("✅ Bài đăng Page đã được xác minh và có permalink.")
            elif action_res.state == "pending":
                print("⏳ Bài viết đã gửi và đang chờ duyệt.")
            else:
                print(f"⚠️ Bài đã được gửi nhưng chưa xác minh được permalink ({action_res.code}). Không tự động đăng lại.")
            return action_res
            
    except Exception as e:
        print(f"❌ Xảy ra lỗi khi đăng bài lên Page: {e}")
        try:
            if 'page' in locals() and page and not page.is_closed():
                page.evaluate("window.onbeforeunload = null;")
        except Exception:
            pass
        return ActionResult(success=False, code="ERROR", message=str(e), target_url=page_url)
    finally:
        try:
            if 'page' in locals() and page and not page.is_closed():
                page.evaluate("window.onbeforeunload = null;")
        except Exception:
            pass
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
    
    ok = post_to_page(args.url, args.content, args.image, args.account_id, args.gpm_api, args.feeling, args.checkin)
    sys.exit(0 if ok else 1)
