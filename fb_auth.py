import json
import time
import os
from playwright.sync_api import sync_playwright

STATE_FILE = "state.json"

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
        
        input("Press Enter in this terminal ONLY AFTER you have successfully logged in...")
        
        context.storage_state(path=STATE_FILE)
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
    
    with sync_playwright() as p:
        try:
            browser_obj, context, page = launch_browser(account, p, gpm_api_url)
            
            print("Đang mở Facebook...")
            page.goto("https://www.facebook.com/")
            
            print("\n" + "="*50)
            print("*** YÊU CẦU THAO TÁC HÀNH ĐỘNG ***")
            print("1. Hãy tiến hành đăng nhập tài khoản Facebook trên trình duyệt vừa mở.")
            print("2. Hoàn tất xác thực 2FA (nếu có).")
            print("3. Đợi đến khi Bảng tin tải xong và hiển thị hoàn toàn.")
            print("="*50 + "\n")
            
            input("Bấm phím Enter tại Terminal này SAU KHI bạn đã đăng nhập thành công để lưu phiên...")
            
            print("Đã lưu phiên đăng nhập thành công!")
            
        except Exception as e:
            print(f"❌ Đã xảy ra lỗi đăng nhập: {e}")
        finally:
            close_browser(browser_obj if browser_obj else context, account, gpm_api_url)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--gpm-api", default=None)
    args = parser.parse_args()
    
    login_account(args.account_id, args.gpm_api)
