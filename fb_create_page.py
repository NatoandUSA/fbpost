import sys
import os
import time
import random
import re
import json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from utils import resolve_account, launch_browser, close_browser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREATED_PAGES_FILE = os.path.join(BASE_DIR, "created_pages.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")


def load_created_pages():
    if not os.path.exists(CREATED_PAGES_FILE):
        return []
    try:
        with open(CREATED_PAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_created_pages(pages):
    try:
        with open(CREATED_PAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(pages, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def can_create_page(max_per_day=2):
    """
    Kiểm tra hạn mức tạo Page: Tối đa 2 Page / ngày (24 giờ) để bảo vệ tài khoản chống checkpoint.
    """
    records = load_created_pages()
    cutoff = datetime.now() - timedelta(hours=24)
    recent = []
    for r in records:
        dt_str = r.get("created_at", "")
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            if dt > cutoff:
                recent.append(r)
        except Exception:
            pass

    if len(recent) >= max_per_day:
        return False, len(recent), f"Đã tạo {len(recent)}/{max_per_day} Page trong 24 giờ qua. Tạm dừng để bảo vệ tài khoản an toàn."
    return True, len(recent), f"Đã tạo {len(recent)}/{max_per_day} Page trong 24 giờ qua."


def create_facebook_page(page_name, category="Blogger", bio=None, avatar_path=None, cover_path=None, account_id=None, gpm_api_url=None):
    """
    Tự động tạo Fanpage cá nhân theo tên chỉ định, có upload avatar và cover như Profile thật.
    Tuân thủ giới hạn tối đa 2 Page / ngày.
    """
    allowed, count, reason = can_create_page(max_per_day=2)
    if not allowed:
        print(f"🛑 [Hạn chế An Toàn] {reason}")
        return False

    print(f"🚩 Bắt đầu quy trình tạo Fanpage cá nhân: '{page_name}' (Hạng mục: {category})")

    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Không thể tìm thấy cấu hình tài khoản: {account_id}")
            return False
        print(f"👤 Sử dụng Profile: {account.get('name', account_id)}")

    browser_obj = None
    context = None
    success = False

    try:
        with sync_playwright() as p:
            if account:
                browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            else:
                browser_obj = p.chromium.launch(headless=False)
                state_arg = STATE_FILE if os.path.exists(STATE_FILE) else None
                context = browser_obj.new_context(storage_state=state_arg)
                page = context.new_page()

            page.set_default_timeout(45000)

            print("🌐 Đang truy cập trang tạo Page: https://www.facebook.com/pages/creation/...")
            page.goto("https://www.facebook.com/pages/creation/", wait_until="domcontentloaded", timeout=45000)
            time.sleep(random.uniform(4.0, 6.0))

            # 1. Điền Tên trang (Bắt buộc)
            print(f"📝 Đang điền Tên trang: {page_name}...")
            name_input = page.locator('input[type="text"]').first
            name_input.click()
            time.sleep(0.5)
            name_input.fill(page_name)
            time.sleep(random.uniform(1.0, 1.8))

            # 2. Điền Hạng mục (Bắt buộc)
            print(f"🏷️ Đang chọn Hạng mục: {category}...")
            cat_input = page.locator('input[aria-autocomplete="list"], input[aria-haspopup="listbox"], input[type="text"]').nth(1)
            cat_input.click()
            time.sleep(0.5)
            cat_input.fill(category)
            time.sleep(random.uniform(1.8, 2.8))

            # Chọn lựa chọn đầu tiên trong danh sách gợi ý hạng mục
            try:
                first_option = page.locator('div[role="option"], ul[role="listbox"] li').first
                if first_option.is_visible(timeout=3000):
                    first_option.click()
                    print(f"✅ Đã chọn hạng mục gợi ý thành công.")
                else:
                    page.keyboard.press("ArrowDown")
                    time.sleep(0.4)
                    page.keyboard.press("Enter")
            except Exception:
                page.keyboard.press("Enter")

            time.sleep(random.uniform(1.0, 2.0))

            # 3. Điền Tiểu sử (Nếu có)
            if bio:
                print(f"📄 Đang điền Tiểu sử: {bio[:30]}...")
                try:
                    bio_input = page.locator('textarea').first
                    if bio_input.is_visible(timeout=2000):
                        bio_input.fill(bio)
                        time.sleep(1.0)
                except Exception:
                    pass

            # 4. Bấm nút Tạo trang
            print("🚀 Đang bấm nút 'Tạo trang'...")
            create_btn = page.locator('div[role="button"]:has-text("Tạo Trang"), div[role="button"]:has-text("Tạo trang"), div[role="button"]:has-text("Create Page"), div[role="button"]:has-text("Create page")').first
            create_btn.scroll_into_view_if_needed()
            create_btn.click()

            print("⏳ Đang chờ Facebook xử lý khởi tạo trang mới (10 - 15 giây)...")
            time.sleep(random.uniform(10.0, 14.0))

            # 5. Upload Avatar & Cover nếu có file ảnh
            file_inputs = page.locator('input[type="file"]')
            if avatar_path and os.path.exists(avatar_path):
                print(f"🖼️ Đang tải lên ảnh đại diện: {avatar_path}...")
                try:
                    if file_inputs.count() > 0:
                        file_inputs.first.set_input_files(avatar_path)
                        time.sleep(random.uniform(3.0, 5.0))
                        print("✅ Đã đính kèm ảnh đại diện!")
                except Exception as av_err:
                    print(f"⚠️ Lỗi upload avatar: {av_err}")

            if cover_path and os.path.exists(cover_path):
                print(f"🌄 Đang tải lên ảnh bìa (Cover): {cover_path}...")
                try:
                    if file_inputs.count() > 1:
                        file_inputs.nth(1).set_input_files(cover_path)
                        time.sleep(random.uniform(3.0, 5.0))
                        print("✅ Đã đính kèm ảnh bìa!")
                except Exception as cv_err:
                    print(f"⚠️ Lỗi upload cover: {cv_err}")

            # 6. Bấm các nút "Tiếp" / "Next" -> "Xong" / "Done"
            print("👉 Đang hoàn tất các bước thiết lập trang...")
            for step in range(4):
                time.sleep(random.uniform(1.5, 2.5))
                next_btn = page.locator('div[role="button"]:has-text("Tiếp"), div[role="button"]:has-text("Next"), div[role="button"]:has-text("Xong"), div[role="button"]:has-text("Done")').first
                if next_btn.is_visible(timeout=3000):
                    next_btn.click()
                else:
                    break

            time.sleep(3.0)

            # Lưu vào danh sách created_pages.json
            pages = load_created_pages()
            pages.append({
                "page_name": page_name,
                "category": category,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account_id": account_id or "default"
            })
            save_created_pages(pages)

            print(f"\n🎉 [THÀNH CÔNG] Đã tạo xong Fanpage cá nhân: '{page_name}'!")
            success = True

    except Exception as e:
        print(f"❌ Lỗi trong quá trình tạo Fanpage: {e}")
    finally:
        close_browser(browser_obj, context, account)

    return success
