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

def post_to_group(group_url, content, image_path=None, account_id=None, gpm_api_url=None, feeling=False, checkin=False,
                  photos_folder=None, photo_count="2-4", auto_spin=False, gemini_key=None, skip_duplicate=False,
                  anti_hash_text=False, clean_exif=True):
    # 1. Kiểm tra lọc trùng lặp 24h nếu bật
    if skip_duplicate:
        is_dup, hours_ago, posted_at = is_recently_posted(group_url)
        if is_dup:
            print(f"⏭️ [Bỏ qua trùng lặp 24h] Nhóm {group_url} đã được đăng lúc {posted_at} ({hours_ago}h trước). Bỏ qua theo cài đặt bảo vệ tài khoản.")
            return ActionResult(success=True, code="SKIPPED_DUPLICATE", message=f"Nhóm {group_url} đã được đăng lúc {posted_at}.", target_url=group_url)

    # 2. Xào bài viết qua AI Content Spinner nếu bật
    if auto_spin:
        print("🤖 [AI Spinner] Đang tạo biến thể bài viết mới lạ, chống trùng lặp spam...")
        content = generate_unique_variant(content, gemini_key)

    # 3. Bốc ảnh ngẫu nhiên từ thư mục nếu có chỉ định
    if photos_folder and not image_path:
        image_path = pick_random_photos(photos_folder, photo_count, clean_exif=clean_exif)

    print(f"👉 Bắt đầu mở Group và đăng bài: {group_url}")
    content = process_spintax(content, anti_hash=anti_hash_text)
    
    # Load account if provided
    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Error: Không thể khởi tạo cấu hình cho Account ID '{account_id}'.")
            return ActionResult(success=False, code="ACCOUNT_NOT_FOUND", message=f"Không thể khởi tạo cấu hình cho Account ID '{account_id}'.", target_url=group_url)
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
            
            # Tự động đóng popup / thông báo che khuất giao diện nếu có
            try:
                popup_close = page.locator("div[role='dialog'] div[aria-label*='Đóng' i], div[role='dialog'] div[aria-label*='Close' i]").first
                if popup_close.is_visible(timeout=1000):
                    dialog_text = page.locator("div[role='dialog']").first.inner_text().lower()
                    if "tạo bài viết" not in dialog_text and "create post" not in dialog_text and "bạn viết gì" not in dialog_text:
                        print("🧹 Tự động đóng thông báo / popup che khuất màn hình...")
                        popup_close.click(force=True)
                        time.sleep(1.0)
            except Exception:
                pass

            # Nhóm Mua & Bán: Tự động chuyển từ tab Bán hàng sang tab Thảo luận
            try:
                discussion_tab = page.locator("a[role='tab'], div[role='tab']").filter(
                    has_text=re.compile(r"^(Thảo luận|Discussion)$", re.IGNORECASE)
                ).first
                if discussion_tab.is_visible(timeout=1500):
                    aria_selected = discussion_tab.get_attribute("aria-selected")
                    if aria_selected != "true":
                        print("ℹ️ Nhóm Mua & Bán: Chuyển sang tab 'Thảo luận' để tìm khung đăng bài...")
                        discussion_tab.click()
                        time.sleep(random.uniform(2.0, 3.5))
            except Exception:
                pass

            # Cuộn trang nhẹ nhàng (an toàn, không crash khi ngắt kết nối)
            safe_mouse_wheel(page, 0, random.randint(200, 500))
            time.sleep(random.uniform(1.0, 2.0))
            safe_mouse_wheel(page, 0, -random.randint(100, 250))
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
                r"Bắt đầu cuộc thảo luận",
                r"Write something",
                r"Create a public post",
                r"What's on your mind",
                r"Start discussion",
                r"Create post"
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
                return ActionResult(success=False, code="COMPOSER_NOT_FOUND", message="Không tìm thấy ô đăng bài. Hãy kiểm tra bạn đã tham gia nhóm hoặc nhóm có yêu cầu quyền duyệt thành viên hay không.", target_url=group_url)

            print("👉 Click mở ô soạn thảo bài viết...")
            try:
                composer_box.click(timeout=6000)
            except Exception as click_err:
                if "intercepts pointer events" not in str(click_err):
                    raise
                print("⚠️ Thanh điều hướng đang che ô soạn thảo; căn giữa phần tử và thử lại...")
                try:
                    composer_box.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
                    time.sleep(0.5)
                except Exception:
                    pass
                composer_box.click(force=True, timeout=5000)
            time.sleep(random.uniform(2.5, 4.0))

            # Chờ hộp thoại soạn bài (Dialog modal) mở hoàn toàn
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
                # Tìm textbox bên trong dialog
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
                return ActionResult(success=False, code="COMPOSER_TEXTBOX_NOT_FOUND", message="Không tìm thấy ô soạn bài.", target_url=group_url)
            human_type(page, textbox, content)
            time.sleep(0.6)
            if not verify_entered_content(textbox, content):
                print("❌ Nội dung composer thiếu chữ ký/hashtag bắt buộc; dừng trước khi submit.")
                return ActionResult(success=False, code="CONTENT_ENTRY_INCOMPLETE", message="Nội dung composer không khớp nội dung chuẩn bị đăng.", target_url=group_url)
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
                        target_url=group_url
                    )
            
            # Thêm Feeling nếu được chọn
            if feeling:
                add_feeling(page)
                
            # Thêm Check-in nếu được chọn
            if checkin:
                add_checkin(page)
            
            # Tạm dừng 5 - 10s mô phỏng người dùng đọc lại bài viết trước khi bấm đăng (Anti-bot)
            review_delay = random.uniform(5.0, 10.0)
            print(f"👀 Tạm dừng {review_delay:.1f}s kiểm tra lại bài viết trước khi đăng...")
            time.sleep(review_delay)

            # 3. Tìm và bấm chính xác nút 'Đăng' (loại bỏ 'Đăng ẩn danh' và xác nhận dialog đóng)
            print("🚀 Đang bấm nút 'Đăng' bài viết...")
            published = click_post_publish_button(page, dialog)
            if not published and getattr(published, "state", "") != "submitted_unverified":
                print("❌ Chưa trigger được submit hoặc Facebook trả lỗi xác định trước khi tiếp nhận.")
                return ActionResult(success=False, code="PUBLISH_FAILED", message="Chưa trigger được submit hoặc Facebook trả lỗi xác định.", target_url=group_url)
            if getattr(published, "state", "") == "submitted_unverified":
                print("⚠️ Submit đã được trigger nhưng terminal state chưa rõ; chỉ đối soát, không gửi lại.")

            # Chờ 3 - 5s để Facebook cập nhật feed
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
            
            # Quét tìm và tự động lưu liên kết bài đăng vừa tạo
            action_res = scrape_post_link(page, target=group_url, content=content, account_id=account_id)
            if action_res.state == "published":
                print("✅ Bài đăng Group đã được xác minh và có permalink.")
            elif action_res.state == "pending":
                print("⏳ Bài viết đã gửi và đang chờ Quản trị viên duyệt.")
            else:
                print(f"⚠️ Bài đã được gửi nhưng chưa xác minh được permalink ({action_res.code}). Không tự động đăng lại.")
            return action_res
            
    except Exception as e:
        print(f"❌ Xảy ra lỗi khi đăng bài vào Group: {e}")
        try:
            if 'page' in locals() and page and not page.is_closed():
                page.evaluate("window.onbeforeunload = null;")
        except Exception:
            pass
        return ActionResult(success=False, code="ERROR", message=str(e), target_url=group_url)
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
    
    ok = post_to_group(args.url, args.content, args.image, args.account_id, args.gpm_api, args.feeling, args.checkin)
    sys.exit(0 if ok else 1)
