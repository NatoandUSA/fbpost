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
    click_post_publish_button, safe_mouse_wheel, ActionResult, verify_entered_content, find_post_composer_textbox, navigate_facebook_surface
)
from ai_spinner import generate_unique_variant
from paths import DATA_DIR

STATE_FILE = str(DATA_DIR / "state.json")


def _browse_group_context(page, phase):
    """Perform bounded, read-only group browsing before/after posting."""
    try:
        if not page:
            return False
        is_closed = getattr(page, "is_closed", None)
        if callable(is_closed) and is_closed():
            return False
        print(f"👀 [Group Flow] phase={phase} action=browse")
        safe_mouse_wheel(page, 0, random.randint(220, 460))
        time.sleep(random.uniform(0.8, 1.5))
        safe_mouse_wheel(page, 0, -random.randint(80, 180))
        time.sleep(random.uniform(0.8, 1.5))
        return True
    except Exception as exc:
        print(f"⚠️ [Group Flow] phase={phase} action=browse status=skipped reason={type(exc).__name__}")
        return False


def _ensure_group_membership(page, group_url):
    """Require confirmed membership before posting. Never treat pending/unverified as joined."""
    joined_markers = ("đã tham gia", "joined", "rời khỏi nhóm", "leave group")
    pending_markers = ("đã yêu cầu", "yêu cầu đã gửi", "requested", "hủy yêu cầu", "cancel request")

    def _scan_state():
        try:
            controls = page.locator('div[role="banner"] div[role="button"], div[role="main"] div[role="button"], button').all()
        except Exception:
            controls = []
        join_button = None
        for control in controls:
            try:
                if not control.is_visible():
                    continue
                combined = f"{control.inner_text() or ''} {control.get_attribute('aria-label') or ''}".strip().lower()
                if any(m in combined for m in joined_markers):
                    return "joined", None
                if any(m in combined for m in pending_markers):
                    return "pending", None
                if join_button is None and any(m in combined for m in ("tham gia", "join")):
                    if not any(m in combined for m in ("chia sẻ", "share", "nhắn tin", "message")):
                        join_button = control
            except Exception:
                continue
        return "unknown", join_button

    for _ in range(3):
        state, join_button = _scan_state()
        if state != "unknown":
            return state
        if join_button is not None:
            try:
                join_button.scroll_into_view_if_needed()
                join_button.click(timeout=4000)
            except Exception:
                return "unverified"
            # Membership dialogs may require rules acknowledgement. Never invent answers
            # to free-text membership questions during join-before-post.
            try:
                dialogs = page.locator('div[role="dialog"]')
                for di in range(min(dialogs.count(), 8)):
                    dlg = dialogs.nth(di)
                    if not dlg.is_visible(timeout=250):
                        continue
                    text_inputs = dlg.locator('textarea, input[type="text"]')
                    checks = dlg.locator('input[type="checkbox"], div[role="checkbox"]')
                    if text_inputs.count() > 0:
                        print("[Group Membership] membership questions require manual answers; fail closed.")
                        return "unverified"
                    if checks.count() > 0:
                        for ci in range(min(checks.count(), 4)):
                            try:
                                cb = checks.nth(ci)
                                if cb.is_visible(timeout=200): cb.click()
                            except Exception:
                                pass
                        submit = dlg.locator('div[role="button"], button').filter(
                            has_text=re.compile(r"^(Gửi|Xác nhận|Hoàn tất|Submit|Confirm|Agree)$", re.I)
                        ).first
                        if submit.is_visible(timeout=800):
                            submit.click()
                            page.wait_for_timeout(1000)
                            break
            except Exception:
                pass
            for _ in range(5):
                page.wait_for_timeout(1200)
                state, _ = _scan_state()
                if state != "unknown":
                    return state
            return "unverified"
        page.wait_for_timeout(1200)

    try:
        page.reload(wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
        state, _ = _scan_state()
        return state if state != "unknown" else "unverified"
    except Exception:
        return "unverified"


def post_to_group(group_url, content, image_path=None, account_id=None, gpm_api_url=None, feeling=False, checkin=False,
                  photos_folder=None, photo_count="2-4", auto_spin=False, gemini_key=None, skip_duplicate=False,
                  anti_hash_text=False, clean_exif=True, brand_key=None):
    if not brand_key:
        c_low = (content or "").lower()
        if "lacasa" in c_low:
            brand_key = "lacasa"
        elif "umee" in c_low:
            brand_key = "umee"

    # 1. Kiểm tra lọc trùng lặp 24h nếu bật
    if skip_duplicate:
        is_dup, hours_ago, posted_at = is_recently_posted(group_url)
        if is_dup:
            print(f"⏭️ [Bỏ qua trùng lặp 24h] Nhóm {group_url} đã được đăng lúc {posted_at} ({hours_ago}h trước). Bỏ qua theo cài đặt bảo vệ tài khoản.")
            return ActionResult(success=True, code="SKIPPED_DUPLICATE", state="skipped_duplicate", message=f"Nhóm {group_url} đã được đăng lúc {posted_at}.", target_url=group_url)

    # 2. Xào bài viết qua AI Content Spinner nếu bật
    if auto_spin:
        print("🤖 [AI Spinner] Đang tạo biến thể bài viết mới lạ, chống trùng lặp spam...")
        content = generate_unique_variant(content, gemini_key, brand_key=brand_key)

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
            if not navigate_facebook_surface(page, group_url, prewarm=True, rounds=3, timeout=45000, label="Group"):
                return ActionResult(success=False, code="FACEBOOK_SURFACE_NOT_HYDRATED",
                                    message="Facebook không tải được bề mặt mục tiêu sau các lần khôi phục read-only.",
                                    target_url=group_url)
            time.sleep(random.uniform(1.0, 2.0))
            _browse_group_context(page, "arrival")

            membership_state = _ensure_group_membership(page, group_url)
            print(f"[Group Membership] state={membership_state}")
            if membership_state != "joined":
                code = "GROUP_MEMBERSHIP_PENDING" if membership_state == "pending" else "GROUP_MEMBERSHIP_UNVERIFIED"
                message = "Nhóm đang chờ duyệt thành viên." if membership_state == "pending" else "Không xác minh được trạng thái đã tham gia nhóm; dừng trước khi đăng."
                return ActionResult(success=False, code=code, state=membership_state, message=message, target_url=group_url)
            
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

            # Confirmed members browse a little more before opening the composer.
            _browse_group_context(page, "before-post")
            
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
            def _pick_interactable(locator):
                try:
                    viewport = page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
                except Exception:
                    viewport = {"w": 1920, "h": 1080}
                fallback = None
                for idx in range(locator.count()):
                    item = locator.nth(idx)
                    try:
                        if not item.is_visible():
                            continue
                        if fallback is None:
                            fallback = item
                        box = item.bounding_box()
                        if not box:
                            continue
                        if (box["x"] + box["width"] > 0 and box["x"] < viewport["w"]
                                and box["y"] + box["height"] > 0 and box["y"] < viewport["h"]):
                            return item
                    except Exception:
                        continue
                return fallback

            buttons = page.locator("div[role='button']").filter(has_text=combined_regex)
            composer_box = _pick_interactable(buttons)

            if not composer_box:
                try:
                    composer_box = _pick_interactable(page.get_by_text(combined_regex))
                except Exception:
                    pass

            if not composer_box:
                try:
                    composer_box = _pick_interactable(page.locator("div[aria-label*='T?o b?i vi?t' i], div[aria-label*='Create a post' i]"))
                except Exception:
                    pass

            if not composer_box:
                print("❌ Không tìm thấy ô đăng bài. Hãy kiểm tra bạn đã tham gia nhóm hoặc nhóm có yêu cầu quyền duyệt thành viên hay không.")
                return ActionResult(success=False, code="COMPOSER_NOT_FOUND", message="Không tìm thấy ô đăng bài. Hãy kiểm tra bạn đã tham gia nhóm hoặc nhóm có yêu cầu quyền duyệt thành viên hay không.", target_url=group_url)

            print("Opening post composer...")
            composer_opened = False
            click_errors = []
            try:
                composer_box.click(timeout=3500)
                composer_opened = True
            except Exception as click_err:
                click_errors.append(str(click_err))
                print(f"Standard composer click blocked ({click_err}); using trusted fallback...")
            if not composer_opened:
                try:
                    composer_box.evaluate("el => el.scrollIntoView({block: 'center', inline: 'center', behavior: 'instant'})")
                    time.sleep(0.4)
                    composer_box.click(force=True, timeout=3500)
                    composer_opened = True
                except Exception as force_err:
                    click_errors.append(str(force_err))
            if not composer_opened:
                try:
                    box = composer_box.bounding_box()
                    if box:
                        page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                        composer_opened = True
                except Exception as mouse_err:
                    click_errors.append(str(mouse_err))
            if not composer_opened:
                try:
                    composer_box.evaluate("el => el.click()")
                    composer_opened = True
                except Exception as dom_err:
                    click_errors.append(str(dom_err))
            if not composer_opened:
                raise RuntimeError("COMPOSER_CLICK_FAILED: " + " | ".join(click_errors[-3:]))
            time.sleep(random.uniform(2.0, 3.0))

            def _composer_editor_visible():
                try:
                    editors = page.locator("div[role='textbox'], div[contenteditable='true'][data-lexical-editor='true']")
                    for ei in range(min(editors.count(), 12)):
                        e = editors.nth(ei)
                        if not e.is_visible():
                            continue
                        label = ((e.get_attribute("aria-label") or "") + " " + (e.get_attribute("aria-placeholder") or "")).lower()
                        if "bình luận" not in label and "comment" not in label:
                            return True
                except Exception:
                    pass
                return False

            # Một số Group render nhiều opener giống nhau; click đầu có thể trúng
            # element ghost/stale dù Playwright báo thành công. Chỉ chấp nhận opener
            # khi editor thật xuất hiện, nếu chưa thì thử các candidate còn lại bằng DOM click.
            if not _composer_editor_visible():
                for ci in range(min(buttons.count(), 10)):
                    candidate = buttons.nth(ci)
                    try:
                        if not candidate.is_visible():
                            continue
                        candidate.evaluate("el => el.click()")
                        time.sleep(1.2)
                        if _composer_editor_visible():
                            print(f"[Composer] Editor verified after candidate {ci + 1}.")
                            break
                    except Exception:
                        continue
            time.sleep(random.uniform(1.0, 1.8))

            # Chờ hộp thoại soạn bài (Dialog modal) mở hoàn toàn
            dialog = None
            try:
                page.wait_for_selector("div[role='dialog']", state="visible", timeout=10000)
                dialog = page.locator("div[role='dialog']").last
            except Exception:
                dialog = page.locator("div[role='dialog']").last

            # Shared scoped resolver: never fall back to arbitrary page-level chat/search/comment editors.
            textbox = find_post_composer_textbox(page, dialog)

            # 1. Nhập nội dung bài viết trước để tránh bị nuốt phím khi gắn ảnh
            print("✍️ Đang nhập nội dung bài viết...")
            if not textbox or not textbox.is_visible():
                print("❌ Không tìm thấy textbox soạn bài đáng tin cậy; dừng trước khi submit.")
                return ActionResult(success=False, code="COMPOSER_TEXTBOX_NOT_FOUND", message="Không tìm thấy ô soạn bài.", target_url=group_url)
            from utils import human_type_with_page_mention
            human_type_with_page_mention(page, textbox, content, brand_key=brand_key)
            time.sleep(0.6)
            if not verify_entered_content(textbox, content):
                print("❌ Nội dung composer thiếu chữ ký/hashtag bắt buộc; dừng trước khi submit.")
                return ActionResult(success=False, code="CONTENT_ENTRY_INCOMPLETE", message="Nội dung composer không khớp nội dung chuẩn bị đăng.", target_url=group_url)
            print(f"✅ Đã xác minh nội dung composer: {len(content)} ký tự · chữ ký/hashtag đầy đủ.")

            def composer_checkpoint(label, allow_restore=True):
                """Bounded checkpoint: detect Facebook composer loss before waiting for Publish."""
                try:
                    live_dialog = page.locator("div[role='dialog']").last
                    live_box = find_post_composer_textbox(page, live_dialog)
                    if live_box and live_box.is_visible(timeout=1200):
                        if verify_entered_content(live_box, content):
                            print(f"✅ [Composer Checkpoint] {label}: nội dung còn nguyên.")
                            return live_dialog, live_box
                        if allow_restore:
                            print(f"⚠️ [Composer Recovery] {label}: nội dung bị mất; khôi phục một lần trước khi đăng.")
                            human_type_with_page_mention(page, live_box, content, brand_key=brand_key)
                            if verify_entered_content(live_box, content):
                                return live_dialog, live_box
                except Exception:
                    pass
                print(f"❌ [COMPOSER_LOST_BEFORE_SUBMIT] {label}: composer đóng hoặc không giữ nội dung; dừng ngay, không chờ/không submit.")
                return None, None

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
                dialog, textbox = composer_checkpoint("sau khi tải ảnh")
                if textbox is None:
                    return ActionResult(success=False, code="COMPOSER_LOST_BEFORE_SUBMIT", message="Composer bị mất sau khi tải ảnh.", target_url=group_url)
            
            # Thêm Feeling nếu được chọn
            if feeling:
                add_feeling(page)
                dialog, textbox = composer_checkpoint("sau cảm xúc")
                if textbox is None:
                    return ActionResult(success=False, code="COMPOSER_LOST_BEFORE_SUBMIT", message="Composer bị mất sau khi thêm cảm xúc.", target_url=group_url)
                
            # Thêm Check-in nếu được chọn
            if checkin:
                add_checkin(page, brand_key=brand_key)
                dialog, textbox = composer_checkpoint("sau check-in")
                if textbox is None:
                    return ActionResult(success=False, code="COMPOSER_LOST_BEFORE_SUBMIT", message="Composer bị mất sau check-in.", target_url=group_url)
            
            # Tạm dừng 5 - 10s mô phỏng người dùng đọc lại bài viết trước khi bấm đăng (Anti-bot)
            review_delay = random.uniform(5.0, 10.0)
            print(f"👀 Tạm dừng {review_delay:.1f}s kiểm tra lại bài viết trước khi đăng...")
            time.sleep(review_delay)
            dialog, textbox = composer_checkpoint("trước nút Đăng", allow_restore=False)
            if textbox is None:
                return ActionResult(success=False, code="COMPOSER_LOST_BEFORE_SUBMIT", message="Composer bị mất trước khi bấm Đăng.", target_url=group_url)

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

            # Keep the group open briefly and browse after submission before closing the profile.
            _browse_group_context(page, "after-post")
            print("✅ [Group Flow] phase=after-post action=settled-before-close")
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
