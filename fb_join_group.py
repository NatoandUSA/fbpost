import sys
import os
import time
import random
import re
import json
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright
from utils import (
    resolve_account,
    launch_browser,
    close_browser,
    safe_mouse_wheel,
    human_type,
    process_spintax,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOINED_GROUPS_FILE = os.path.join(BASE_DIR, "joined_groups.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")

COMMUNITY_GROUP_COMMENTS = [
    "Nhóm hoạt động sôi nổi và hữu ích quá ạ!",
    "Cảm ơn bài viết chia sẻ rất hay và chi tiết!",
    "Chào mọi người trong nhóm nhé, chúc cả nhà ngày mới an lành!",
    "Thông tin hữu ích quá, cảm ơn admin và bạn đã chia sẻ!",
    "Bài viết chất lượng quá, chúc nhóm ngày càng phát triển ạ!",
    "Tuyệt vời quá bạn ơi, đúng thông tin mình đang quan tâm!",
    "Hay quá ạ, mình xin phép lưu lại bài viết khi cần nhé!",
    "Không gian và hình ảnh đẹp quá ạ!",
    "Cảm ơn chia sẻ bổ ích của bạn nha!",
    "Thả tim cho bài viết chất lượng này nha ❤️",
]


def interact_with_group_feed(page, gemini_key=None):
    """
    Tự động lướt bảng tin nhóm và tương tác Like/Bình luận AI vào bài viết,
    giúp nuôi nick, tạo hành vi người dùng thật tự nhiên và chống checkpoint.
    """
    try:
        print("👀 [Group Feed] Đang lướt xem các bài viết trên bảng tin nhóm...")
        # Cuộn tự nhiên 1-2 lần
        for _ in range(random.randint(1, 2)):
            scroll_y = random.randint(300, 600)
            try:
                safe_mouse_wheel(page, 0, scroll_y)
            except Exception:
                try:
                    page.evaluate(f"window.scrollBy(0, {scroll_y})")
                except Exception:
                    pass
            time.sleep(random.uniform(2.0, 3.5))

        articles = []
        try:
            articles = page.locator("div[role='article']").all()
            if not articles:
                articles = page.locator("div[role='feed'] > div, div[data-ad-preview='message']").all()
        except Exception:
            pass

        if not articles or len(articles) == 0:
            print("ℹ️ [Group Feed] Chưa tìm thấy bài viết khả dụng để tương tác.")
            return

        # Chọn ngẫu nhiên 1 bài viết trong top 4 bài đầu
        sample_pool = [a for a in articles[:min(len(articles), 4)] if a]
        if not sample_pool:
            return
        target_article = random.choice(sample_pool)
        try:
            target_article.scroll_into_view_if_needed()
            time.sleep(random.uniform(1.0, 2.0))
        except Exception:
            pass

        # 70% cơ hội thả Like bài viết
        if random.random() < 0.70:
            try:
                like_btn = target_article.locator("div[role='button']").filter(
                    has_text=re.compile(r"^(Thích|Like)$", re.IGNORECASE)
                ).first
                if like_btn.is_visible(timeout=2000) and like_btn.is_enabled():
                    print("👍 [Group Feed] Thả Like bài viết cộng đồng trong nhóm...")
                    like_btn.click()
                    time.sleep(random.uniform(1.5, 2.5))
            except Exception:
                pass

        # 40% cơ hội viết bình luận AI / spintax
        if random.random() < 0.40:
            try:
                comment_input = target_article.locator("div[role='textbox']").first
                if not comment_input.is_visible(timeout=1500):
                    comment_btn = target_article.locator("div[role='button']").filter(
                        has_text=re.compile(r"^(Bình luận|Comment)$", re.IGNORECASE)
                    ).first
                    if comment_btn.is_visible(timeout=1500):
                        comment_btn.click()
                        time.sleep(random.uniform(1.5, 2.5))
                        comment_input = target_article.locator("div[role='textbox']").first

                if comment_input.is_visible(timeout=2000) and comment_input.is_enabled():
                    base_cmt = random.choice(COMMUNITY_GROUP_COMMENTS)
                    try:
                        from ai_spinner import spin_two_tier
                        comment_text = spin_two_tier(base_cmt, frequency=0.3)
                    except Exception:
                        comment_text = base_cmt

                    print(f"💬 [Group Feed] Viết bình luận tương tác: \"{comment_text}\"")
                    human_type(page, comment_input, comment_text)
                    time.sleep(random.uniform(1.0, 2.0))
                    page.keyboard.press("Enter")
                    time.sleep(random.uniform(2.5, 4.0))
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ [Group Feed] Bỏ qua tương tác bảng tin nhóm: {e}")


def load_joined_groups():
    if os.path.exists(JOINED_GROUPS_FILE):
        try:
            with open(JOINED_GROUPS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    import paths
    default_file = str(paths.BASE_DIR / "joined_groups.json")
    if os.path.abspath(JOINED_GROUPS_FILE) != os.path.abspath(default_file):
        return []
    try:
        from repositories.group_repo import GroupRepository
        rows = GroupRepository().list_joined_groups()
        if rows:
            return rows
    except Exception:
        pass
    return []


def save_joined_groups(groups):
    try:
        with open(JOINED_GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def search_and_join_groups(
    keywords,
    max_groups=2,
    account_id=None,
    gpm_api_url=None,
    delay_min=60,
    delay_max=180,
    interact_feed=False,
    gemini_key=None,
    auto_rules=False,
):
    """
    Tìm kiếm nhóm theo từ khóa và tự động xin gia nhập nhóm an toàn.
    Chỉ gia nhập tối đa 2 nhóm mỗi lượt mở profile để tránh checkpoint.
    """
    # Cố định tối đa 2 nhóm mỗi lần mở profile
    max_groups = min(max(1, int(max_groups)), 2)
    if isinstance(keywords, str):
        kw_list = [k.strip() for k in re.split(r"[,;\n]", keywords) if k.strip()]
    else:
        kw_list = list(keywords)

    if not kw_list:
        print("⚠️ Không có từ khóa tìm kiếm nhóm.")
        return 0

    random.shuffle(kw_list)
    joined_records = load_joined_groups()

    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Không thể tìm thấy cấu hình tài khoản: {account_id}")
            return 0
        print(f"👤 Khởi chạy profile: {account.get('name', account_id)}")

    joined_count = 0
    browser_obj = None
    context = None

    try:
        with sync_playwright() as p:
            if account:
                browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            else:
                browser_obj = p.chromium.launch(headless=False)
                state_arg = STATE_FILE if os.path.exists(STATE_FILE) else None
                context = browser_obj.new_context(storage_state=state_arg)
                page = context.new_page()

            page.set_default_timeout(35000)

            for kw in kw_list:
                if joined_count >= max_groups:
                    break

                is_direct_url = kw.lower().startswith("http")
                if is_direct_url:
                    target_url = kw
                    print(f"\n👉 Đang mở trực tiếp nhóm Facebook để xin tham gia: {target_url}...")
                    try:
                        page.goto(target_url, wait_until="domcontentloaded", timeout=35000)
                        time.sleep(random.uniform(3.0, 4.5))
                    except Exception as e:
                        print(f"⚠️ Lỗi tải trang nhóm: {e}")
                        continue

                    # Trong khi xem nhóm: lướt bảng tin và Like/Bình luận AI tự nhiên
                    if interact_feed:
                        interact_with_group_feed(page, gemini_key=gemini_key)
                else:
                    search_url = f"https://www.facebook.com/search/groups/?q={urllib.parse.quote(kw)}"
                    print(f"\n🔍 Đang tìm kiếm nhóm Facebook với từ khóa: '{kw}'...")
                    try:
                        page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
                        time.sleep(random.uniform(3.0, 5.0))
                    except Exception as e:
                        print(f"⚠️ Lỗi tải trang tìm kiếm: {e}")
                        continue

                # Cuộn trang nạp thêm các nhóm mới (kết hợp PageDown và scrollBy)
                try:
                    for _ in range(3):
                        try:
                            page.keyboard.press("PageDown")
                        except Exception:
                            pass
                        try:
                            page.evaluate("window.scrollBy(0, 800)")
                        except Exception:
                            pass
                        time.sleep(1.0)
                except Exception:
                    pass

                def _is_join_button(elem):
                    try:
                        if not elem.is_visible():
                            return False
                        txt = (elem.inner_text() or "").strip().lower()
                        aria = (elem.get_attribute("aria-label") or "").strip().lower()
                        combined = f"{txt} {aria}"
                        
                        # Loại trừ các nút đã gia nhập, đã gửi yêu cầu hoặc hành động khác
                        negatives = [
                            "đã tham gia", "đã yêu cầu", "yêu cầu đã gửi", "truy cập", 
                            "joined", "requested", "rời khỏi", "leave", "hủy yêu cầu", 
                            "cancel request", "chia sẻ", "share", "nhắn tin", "message"
                        ]
                        if any(neg in combined for neg in negatives):
                            return False
                            
                        # Khớp từ khóa tham gia tích cực
                        positives = ["tham gia", "join"]
                        return any(pos in combined for pos in positives)
                    except Exception:
                        return False

                candidates = []
                # Cách 1: Quét toàn bộ nút trên trang
                try:
                    all_btns = page.locator('div[role="button"], button').all()
                    for btn in all_btns:
                        if _is_join_button(btn):
                            candidates.append(btn)
                except Exception:
                    pass

                # Cách 2: Fallback nếu trên trang nhóm trực tiếp (nút ở ảnh bìa / header)
                if not candidates and is_direct_url:
                    try:
                        header_btns = page.locator("div[role='main'] div[role='button'], div[role='banner'] div[role='button']").all()
                        for btn in header_btns:
                            if _is_join_button(btn):
                                candidates.append(btn)
                    except Exception:
                        pass

                if not candidates:
                    if is_direct_url:
                        # Direct URL mode: distinguish an existing membership/request from a true missing control.
                        existing_state = False
                        try:
                            for state_btn in page.locator('div[role="button"], button').all():
                                if not state_btn.is_visible():
                                    continue
                                state_text = f"{state_btn.inner_text() or ''} {state_btn.get_attribute('aria-label') or ''}".lower()
                                if any(marker in state_text for marker in ["đã tham gia", "đã yêu cầu", "yêu cầu đã gửi", "joined", "requested", "rời khỏi", "leave", "hủy yêu cầu", "cancel request"]):
                                    existing_state = True
                                    break
                        except Exception:
                            existing_state = False
                        if existing_state:
                            joined_count += 1
                            print(f"ℹ️ Nhóm đã ở trạng thái thành viên/chờ duyệt; tính là đã xử lý: {kw}")
                        else:
                            print(f"⚠️ Không tìm thấy nút Tham gia hoặc trạng thái thành viên/chờ duyệt tại nhóm: {kw}")
                    else:
                        print(f"ℹ️ Không có nhóm mới nào chưa tham gia cho từ khóa '{kw}'.")
                    continue

                if is_direct_url:
                    print(f"📋 Đã tìm thấy nút tham gia tại nhóm: {kw}")
                else:
                    print(f"📋 Tìm thấy {len(candidates)} nhóm tiềm năng cho từ khóa '{kw}'.")
                btn_to_click = candidates[0]

                try:
                    group_name = f"Nhóm liên quan '{kw}'"
                    group_url = target_url if is_direct_url else ""
                    parent_card = None
                    if is_direct_url:
                        try:
                            h1_elem = page.locator('h1').first
                            if h1_elem.is_visible(timeout=2000):
                                group_name = h1_elem.inner_text().strip().split("\n")[0]
                            else:
                                group_name = page.title().replace(" | Facebook", "").strip()
                        except Exception:
                            group_name = kw
                    else:
                        try:
                            parent_card = btn_to_click.locator("xpath=ancestor::div[contains(@class, 'x1yztbdb') or contains(@class, 'x1q0g3np') or @role='feed' or @role='article'][1]")
                            name_elem = parent_card.locator('a[role="link"]').first
                            if name_elem.count() > 0:
                                group_name = name_elem.inner_text().strip().split("\n")[0]
                            link_elem = parent_card.locator('a[href*="/groups/"]').first
                            if link_elem.count() > 0:
                                href = link_elem.get_attribute("href") or ""
                                if href:
                                    group_url = href.split("?")[0]
                                    if not group_url.startswith("http"):
                                        group_url = f"https://www.facebook.com{group_url}"
                        except Exception:
                            pass

                    print(f"👉 Đang bấm 'Tham gia' nhóm: {group_name}...")
                    btn_to_click.scroll_into_view_if_needed()
                    time.sleep(random.uniform(0.5, 1.2))
                    btn_to_click.click()
                    time.sleep(random.uniform(2.5, 4.0))

                    # Kiểm tra xem có dialog nội quy/câu hỏi nhóm hiện ra không
                    rule_dialog = page.locator('div[role="dialog"]')
                    if rule_dialog.is_visible(timeout=3000):
                        if not auto_rules:
                            print("📝 Nhóm yêu cầu nội quy/câu hỏi. Chế độ tự trả lời đang tắt; bỏ qua để người dùng xử lý thủ công.")
                            try:
                                close_dlg = rule_dialog.locator('div[aria-label="Đóng"], div[aria-label="Close"]').first
                                if close_dlg.is_visible(timeout=1000):
                                    close_dlg.click()
                            except Exception:
                                pass
                            continue
                        print("📝 Phát hiện bảng câu hỏi / nội quy nhóm, đang xử lý theo tùy chọn người dùng...")
                        rule_checkbox = rule_dialog.locator('input[type="checkbox"], div[role="checkbox"]')
                        if rule_checkbox.count() > 0:
                            for i in range(min(rule_checkbox.count(), 3)):
                                try:
                                    rule_checkbox.nth(i).click()
                                    time.sleep(0.5)
                                except Exception:
                                    pass

                        # Tự động điền câu trả lời mẫu nếu nhóm bắt buộc trả lời câu hỏi
                        try:
                            textboxes = rule_dialog.locator('textarea, input[type="text"]').all()
                            for tb in textboxes:
                                if tb.is_visible():
                                    try:
                                        tb.fill("Tôi xin tuân thủ mọi nội quy của nhóm.")
                                        time.sleep(0.5)
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                        submit_btn = rule_dialog.locator('div[role="button"]:has-text("Gửi"), div[role="button"]:has-text("Xác nhận"), div[role="button"]:has-text("Hoàn tất"), div[role="button"]:has-text("Submit"), div[role="button"]:has-text("Confirm")').first
                        if submit_btn.is_visible(timeout=2000):
                            submit_btn.click()
                            time.sleep(random.uniform(1.5, 2.5))
                            print("✅ Đã gửi câu trả lời/đồng ý quy tắc nhóm!")
                        else:
                            close_dlg = rule_dialog.locator('div[aria-label="Đóng"], div[aria-label="Close"]').first
                            if close_dlg.is_visible(timeout=1000):
                                close_dlg.click()

                    # Kiểm tra cảnh báo lỗi / bị chặn
                    block_alert = page.locator("div[role='alert'], div[role='dialog']").filter(
                        has_text=re.compile(r"(bị chặn|tạm thời|không thể thực hiện|bị hạn chế|something went wrong)", re.IGNORECASE)
                    ).first
                    if block_alert.is_visible(timeout=1500):
                        print(f"❌ Facebook báo lỗi khi tham gia nhóm: {block_alert.inner_text()[:100]}")
                        continue

                    # Xác thực nút bấm đã chuyển trạng thái thành công
                    time.sleep(random.uniform(1.5, 2.5))
                    state = "pending"
                    is_confirmed = False
                    try:
                        btn_text = (btn_to_click.inner_text() or "").strip().lower()
                        btn_aria = (btn_to_click.get_attribute("aria-label") or "").strip().lower()
                        combined_after = f"{btn_text} {btn_aria}"
                        if any(kw_sub in combined_after for kw_sub in ["đã tham gia", "joined", "truy cập", "rời khỏi", "leave"]):
                            state = "joined"
                            is_confirmed = True
                        elif any(kw_sub in combined_after for kw_sub in ["đã gửi", "requested", "hủy yêu cầu", "cancel request", "đã yêu cầu"]):
                            state = "pending"
                            is_confirmed = True
                        elif any(kw_sub in combined_after for kw_sub in ["tham gia", "join"]) and not any(kw_sub in combined_after for kw_sub in ["hủy", "cancel"]):
                            print(f"⚠️ Nút vẫn hiển thị 'Tham gia', thao tác chưa được ghi nhận.")
                            is_confirmed = False
                        else:
                            is_confirmed = False
                    except Exception:
                        is_confirmed = False

                    if not is_confirmed:
                        continue

                    record = {
                        "group_name": group_name,
                        "keyword": kw,
                        "url": group_url,
                        "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "account_id": account_id or "default",
                        "state": state
                    }
                    try:
                        from repositories.group_repo import GroupRepository
                        GroupRepository().add_joined_group(record)
                    except Exception as repo_err:
                        print(f"⚠️ Lỗi lưu nhóm vào DB: {repo_err}")

                    try:
                        with open(JOINED_GROUPS_FILE, "r", encoding="utf-8") as f:
                            current_json = json.load(f)
                            if not isinstance(current_json, list):
                                current_json = []
                    except Exception:
                        current_json = []
                    if not any(j.get("url") == group_url and j.get("group_name") == group_name for j in current_json):
                        current_json.append(record)
                        try:
                            with open(JOINED_GROUPS_FILE, "w", encoding="utf-8") as f:
                                json.dump(current_json, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                    joined_count += 1
                    status_lbl = "thành viên" if state == "joined" else "chờ duyệt"
                    print(f"🎉 Đã tham gia nhóm ({status_lbl}): {group_name}!")

                    # Nếu không phải mở link trực tiếp (đã tương tác trước đó) và đã vào nhóm: lướt tương tác bảng tin nhóm
                    if not is_direct_url and interact_feed:
                        interact_with_group_feed(page, gemini_key=gemini_key)

                    # Giãn cách an toàn ngẫu nhiên 1 - 3 phút (60 - 180s) nếu còn nhóm tiếp theo
                    if joined_count < max_groups:
                        cooldown = random.randint(max(10, delay_min), max(delay_min, delay_max))
                        print(f"\n⏳ [Anti-Spam] Nghỉ an toàn {cooldown}s ({cooldown//60}p {cooldown%60}s) trước khi xử lý nhóm tiếp theo...")
                        for sec in range(cooldown, 0, -1):
                            if sec % 15 == 0 or sec <= 5:
                                print(f"⏳ ... còn {sec//60}p {sec%60}s ({sec}s)")
                            time.sleep(1)

                except Exception as click_err:
                    print(f"⚠️ Không thể bấm tham gia nhóm: {click_err}")

    except Exception as err:
        print(f"❌ Lỗi trong quá trình tìm và gia nhập nhóm: {err}")
    finally:
        close_browser(browser_obj if browser_obj else context, account, gpm_api_url)

    return joined_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tự động tìm kiếm và tham gia nhóm Facebook")
    parser.add_argument("--keywords", default="Homestay Huế", help="Từ khóa tìm nhóm hoặc danh sách URL")
    parser.add_argument("--limit", type=int, default=2, help="Số lượng nhóm tối đa cần tham gia (Tối đa 2 nhóm/profile)")
    parser.add_argument("--account-id", default=None, help="ID tài khoản")
    parser.add_argument("--gpm-api", default=None, help="URL GPM API")
    parser.add_argument("--delay-min", type=int, default=60, help="Thời gian nghỉ tối thiểu giữa các nhóm (giây)")
    parser.add_argument("--delay-max", type=int, default=180, help="Thời gian nghỉ tối đa giữa các nhóm (giây)")
    parser.add_argument("--interact-feed", action="store_true", default=False, help="Tùy chọn tương tác bảng tin nhóm; mặc định tắt")
    parser.add_argument("--no-interact-feed", action="store_false", dest="interact_feed", help="Tắt tương tác bảng tin nhóm")
    parser.add_argument("--gemini-key", default=None, help="Gemini API Key")
    args = parser.parse_args()

    cnt = search_and_join_groups(
        args.keywords,
        max_groups=args.limit,
        account_id=args.account_id,
        gpm_api_url=args.gpm_api,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        interact_feed=args.interact_feed,
        gemini_key=args.gemini_key,
    )
    sys.exit(0 if cnt > 0 else 1)
