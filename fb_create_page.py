import sys
import os
import time
import random
import re
import json
import urllib.parse
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from utils import resolve_account, launch_browser, close_browser, ActionResult

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREATED_PAGES_FILE = os.path.join(BASE_DIR, "created_pages.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")


def load_created_pages(account_id=None):
    try:
        from repositories.page_repo import PageRepository
        rows = PageRepository().list_created_pages(account_id=account_id)
        if rows:
            return rows
    except Exception:
        pass
    if not os.path.exists(CREATED_PAGES_FILE):
        return []
    try:
        with open(CREATED_PAGES_FILE, "r", encoding="utf-8") as f:
            pages = json.load(f)
            if account_id:
                return [p for p in pages if p.get("account_id") == account_id]
            return pages
    except Exception:
        return []


def save_created_pages(pages):
    try:
        with open(CREATED_PAGES_FILE, "w", encoding="utf-8") as f:
            json.dump(pages, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def can_create_page(account_id=None, max_per_day=2):
    """
    Kiểm tra hạn mức tạo Page: Tối đa 2 Page / ngày (24 giờ) để bảo vệ tài khoản chống checkpoint.
    """
    records = load_created_pages(account_id=account_id)
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
    allowed, count, reason = can_create_page(account_id=account_id, max_per_day=2)
    if not allowed:
        print(f"🛑 [Hạn chế An Toàn] {reason}")
        return ActionResult(success=False, code="RATE_LIMIT", message=reason)

    print(f"🚩 Bắt đầu quy trình tạo Fanpage cá nhân: '{page_name}' (Hạng mục: {category})")

    account = None
    if account_id:
        account = resolve_account(account_id, gpm_api_url)
        if not account:
            print(f"❌ Không thể tìm thấy cấu hình tài khoản: {account_id}")
            return ActionResult(success=False, code="ACCOUNT_NOT_FOUND", message=f"Không thể tìm thấy cấu hình tài khoản: {account_id}")
        print(f"👤 Sử dụng Profile: {account.get('name', account_id)}")

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

            # Kiểm tra xem Facebook có báo lỗi ngay sau khi bấm Tạo Trang không
            time.sleep(2.5)
            err_alert = page.locator("div[role='alert'], div[role='dialog']").filter(
                has_text=re.compile(r"(quá nhiều|không thể tạo|không hợp lệ|bị chặn|too many|cannot create|invalid|something went wrong)", re.IGNORECASE)
            ).first
            if err_alert.is_visible(timeout=3000):
                msg = err_alert.inner_text().strip().split("\n")[0]
                print(f"❌ Facebook từ chối tạo trang: {msg}")
                return ActionResult(success=False, code="PAGE_CREATION_REJECTED", message=msg)

            print("⏳ Đang chờ Facebook xử lý khởi tạo trang mới (10 - 14 giây)...")
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

            time.sleep(random.uniform(3.0, 5.0))

            # 7. Xác thực kết quả tạo trang thực tế
            curr_url = page.url
            created_page_url = ""
            is_verified = False

            # Bỏ qua các URL không hợp lệ: trang chủ, checkpoint, login, trang tạo
            invalid_paths = ["/pages/creation", "/checkpoint", "/login", "/home.php", "/recover"]
            parsed_u = urllib.parse.urlparse(curr_url)
            is_generic_root = parsed_u.path.strip("/") in ("", "home.php")
            is_invalid_path = any(inv in parsed_u.path.lower() for inv in invalid_paths) or is_generic_root

            # Kiểm tra tiêu đề trang hoặc h1/h2 khớp với tên page_name
            try:
                header_elem = page.locator('h1, div[role="main"] h1, div[role="main"] h2').first
                if header_elem.is_visible(timeout=3000):
                    txt = (header_elem.inner_text() or "").strip().lower()
                    if page_name.lower() in txt:
                        is_verified = True
            except Exception:
                pass

            # Nếu chưa verify qua header, kiểm tra page title
            if not is_verified:
                try:
                    title = page.title().lower()
                    if page_name.lower() in title and "facebook" in title:
                        is_verified = True
                except Exception:
                    pass

            if is_verified and not is_invalid_path and "facebook.com/" in curr_url:
                created_page_url = curr_url.split("?")[0]
            elif not is_invalid_path and "facebook.com/" in curr_url and ("/pages/" in curr_url or "/profile.php" in curr_url):
                created_page_url = curr_url.split("?")[0]
                is_verified = True

            if not is_verified:
                print("⚠️ Không thể xác thực Fanpage đã được tạo thành công trên giao diện Facebook.")
                return ActionResult(success=False, code="UNVERIFIED", message="Không thể xác thực Fanpage đã được tạo thành công trên giao diện Facebook.")

            # Lưu vào CSDL SQLite
            try:
                from repositories.page_repo import PageRepository
                PageRepository().add_created_page(
                    page_name=page_name,
                    category=category,
                    page_url=created_page_url,
                    account_id=account_id or "default",
                    state="created",
                )
            except Exception as pe:
                print(f"⚠️ Lỗi lưu page vào SQLite: {pe}")

            # Lưu vào JSON (tránh duplicate)
            pages = load_created_pages()
            if not any(p.get("page_url") == created_page_url and p.get("page_name") == page_name for p in pages):
                pages.append({
                    "page_name": page_name,
                    "category": category,
                    "page_url": created_page_url,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "account_id": account_id or "default"
                })
                save_created_pages(pages)

            print(f"\n🎉 [THÀNH CÔNG] Đã tạo xong Fanpage cá nhân: '{page_name}'!")
            return ActionResult(
                success=True,
                code="SUCCESS",
                state="created",
                message=f"Đã tạo xong Fanpage cá nhân: '{page_name}'!",
                result_url=created_page_url,
                url_type="page",
            )

    except Exception as e:
        print(f"❌ Lỗi trong quá trình tạo Fanpage: {e}")
        return ActionResult(success=False, code="ERROR", message=str(e))
    finally:
        close_browser(browser_obj if browser_obj else context, account, gpm_api_url)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tự động tạo Facebook Fanpage")
    parser.add_argument("--name", required=True, help="Tên Fanpage cần tạo")
    parser.add_argument("--category", default="Blogger", help="Hạng mục Fanpage")
    parser.add_argument("--bio", default="", help="Tiểu sử trang")
    parser.add_argument("--avatar", default=None, help="Đường dẫn ảnh đại diện")
    parser.add_argument("--cover", default=None, help="Đường dẫn ảnh bìa")
    parser.add_argument("--account-id", default=None, help="ID tài khoản")
    parser.add_argument("--gpm-api", default=None, help="URL GPM API")
    args = parser.parse_args()

    res = create_facebook_page(
        page_name=args.name,
        category=args.category,
        bio=args.bio,
        avatar_path=args.avatar,
        cover_path=args.cover,
        account_id=args.account_id,
        gpm_api_url=args.gpm_api,
    )
    sys.exit(0 if res else 1)
