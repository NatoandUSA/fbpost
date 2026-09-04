import sys
import os
import time
import random
import re
import json
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright
from utils import resolve_account, launch_browser, close_browser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JOINED_GROUPS_FILE = os.path.join(BASE_DIR, "joined_groups.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")


def load_joined_groups():
    if not os.path.exists(JOINED_GROUPS_FILE):
        return []
    try:
        with open(JOINED_GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_joined_groups(groups):
    try:
        with open(JOINED_GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def search_and_join_groups(keywords, max_groups=1, account_id=None, gpm_api_url=None):
    """
    Tìm kiếm nhóm theo từ khóa và tự động xin gia nhập nhóm an toàn.
    Chỉ gia nhập tối đa max_groups nhóm mỗi lượt để tránh checkpoint.
    """
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

                search_url = f"https://www.facebook.com/groups/search/groups/?q={urllib.parse.quote(kw)}"
                print(f"\n🔍 Đang tìm kiếm nhóm Facebook với từ khóa: '{kw}'...")
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
                    time.sleep(random.uniform(3.0, 5.0))
                except Exception as e:
                    print(f"⚠️ Lỗi tải trang tìm kiếm: {e}")
                    continue

                # Cuộn nhẹ để nạp danh sách kết quả
                page.mouse.wheel(0, 400)
                time.sleep(random.uniform(1.5, 2.5))

                # Tìm các nút "Tham gia" / "Join"
                join_buttons = page.locator('div[role="button"]:has-text("Tham gia"), div[role="button"]:has-text("Tham gia nhóm"), div[role="button"]:has-text("Join"), div[role="button"]:has-text("Join group")').all()

                candidates = []
                for btn in join_buttons:
                    try:
                        text = btn.inner_text().strip()
                        if text in ("Tham gia", "Tham gia nhóm", "Join", "Join group"):
                            candidates.append(btn)
                    except Exception:
                        continue

                if not candidates:
                    print(f"ℹ️ Không có nhóm mới nào chưa tham gia cho từ khóa '{kw}'.")
                    continue

                print(f"📋 Tìm thấy {len(candidates)} nhóm tiềm năng cho từ khóa '{kw}'.")
                btn_to_click = candidates[0]

                try:
                    group_name = f"Nhóm liên quan '{kw}'"
                    try:
                        parent_card = btn_to_click.locator("xpath=ancestor::div[contains(@class, 'x1yztbdb') or contains(@class, 'x1q0g3np')][1]")
                        name_elem = parent_card.locator('a[role="link"]').first
                        if name_elem.count() > 0:
                            group_name = name_elem.inner_text().strip().split("\n")[0]
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
                        print("📝 Phát hiện bảng câu hỏi / nội quy nhóm, đang tự động xử lý...")
                        rule_checkbox = rule_dialog.locator('input[type="checkbox"], div[role="checkbox"]')
                        if rule_checkbox.count() > 0:
                            for i in range(min(rule_checkbox.count(), 3)):
                                try:
                                    rule_checkbox.nth(i).click()
                                    time.sleep(0.5)
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

                    joined_records.append({
                        "group_name": group_name,
                        "keyword": kw,
                        "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "account_id": account_id or "default"
                    })
                    save_joined_groups(joined_records)
                    joined_count += 1
                    print(f"🎉 Đã gửi yêu cầu tham gia thành công: {group_name}!")

                except Exception as click_err:
                    print(f"⚠️ Không thể bấm tham gia nhóm: {click_err}")

    except Exception as err:
        print(f"❌ Lỗi trong quá trình tìm và gia nhập nhóm: {err}")
    finally:
        close_browser(browser_obj, context, account)

    return joined_count
