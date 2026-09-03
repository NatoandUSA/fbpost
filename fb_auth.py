import json
import time
import os
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

STATE_FILE = "state.json"
AUTH_STATUS_FILE = "auth_status.json"


def facebook_session_detected(context):
    """Check for Facebook's signed-in session marker without exporting GPM cookies."""
    try:
        return any(cookie.get("name") == "c_user" and cookie.get("value") for cookie in context.cookies("https://www.facebook.com"))
    except Exception:
        return False


def wait_for_facebook_session(context, timeout_seconds=300):
    print("Waiting for Facebook sign-in in the opened browser window (up to 5 minutes)...")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if facebook_session_detected(context):
            return True
        time.sleep(2)
    return False


def save_auth_status(account_id=None, account_type="local"):
    """Keep UI status only; never copy GPM cookies or proxy credentials."""
    payload = {
        "authenticated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "account_id": account_id or "default",
        "account_type": account_type,
    }
    with open(AUTH_STATUS_FILE, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False)

def login():
    """
    Opens an interactive browser window for the user to log in manually.
    Saves the session state (cookies, etc.) to state.json.
    """
    print("Starting Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("Navigating to Facebook...")
        page.goto("https://www.facebook.com/")
        
        print("\n" + "="*50)
        print("*** ACTION REQUIRED ***")
        print("1. Please log into Facebook in the opened browser window.")
        print("2. If you have 2-Factor Authentication (2FA) enabled, please complete it.")
        print("3. Wait until you are fully logged in and see your News Feed.")
        print("="*50 + "\n")
        
        if not wait_for_facebook_session(context):
            raise RuntimeError("Timed out waiting for Facebook sign-in. Complete login in the opened browser, then try again.")
        context.storage_state(path=STATE_FILE)
        save_auth_status()
        print(f"Session state saved to '{STATE_FILE}'. You can now run the automation scripts.")
        browser.close()

def login_account(account_id=None, gpm_api_url=None):
    """
    Launches browser for a specific account so the user can authenticate manually.
    """
    if not account_id:
        login()
        return
        
    from utils import load_accounts, launch_browser, close_browser
    accounts = load_accounts()
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        print(f"❌ Error: Account ID '{account_id}' not found in accounts.json.")
        return
        
    print(f"Bắt đầu đăng nhập cho tài khoản: {account.get('name')} ({account.get('type')})")
    
    browser_obj = None
    context = None
    with sync_playwright() as p:
        try:
            browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            
            print("Đang mở Facebook...")
            try:
                page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=45000)
            except Exception as goto_err:
                print(f"⚠️ Cảnh báo kết nối Facebook: {goto_err}. Đang kiểm tra màn hình SSL...")
                time.sleep(2)
                try:
                    if page.locator("#details-button").is_visible(timeout=3000):
                        page.click("#details-button")
                        time.sleep(1)
                        if page.locator("#proceed-link").is_visible(timeout=3000):
                            page.click("#proceed-link")
                            time.sleep(3)
                except Exception:
                    pass
            
            print("\n" + "="*50)
            print("*** YÊU CẦU THAO TÁC HÀNH ĐỘNG ***")
            print("1. Hãy tiến hành đăng nhập tài khoản Facebook trên trình duyệt vừa mở.")
            print("2. Hoàn tất xác thực 2FA (nếu có).")
            print("3. Đợi đến khi Bảng tin tải xong và hiển thị hoàn toàn.")
            print("="*50 + "\n")
            
            if not wait_for_facebook_session(context):
                raise RuntimeError("Hết thời gian chờ đăng nhập Facebook. Hãy hoàn tất đăng nhập trong cửa sổ GPM rồi thử lại.")
            if account.get("type") == "gpm":
                save_auth_status(account_id, "gpm")
                print("Đã xác thực GPM profile. Cookie vẫn chỉ nằm trong GPM, không được sao chép vào tool.")
            else:
                context.storage_state(path=STATE_FILE)
                save_auth_status(account_id, "local")
                print("Đã lưu phiên đăng nhập thành công!")
            
        except Exception as e:
            print(f"❌ Đã xảy ra lỗi đăng nhập: {e}")
            raise
        finally:
            if browser_obj or context:
                close_browser(browser_obj if browser_obj else context, account, gpm_api_url)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    args = parser.parse_args()
    
    login_account(args.account_id, args.gpm_api)
