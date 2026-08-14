import re
import random
import time
import os
import json

ACCOUNTS_FILE = "accounts.json"

def process_spintax(text):
    """
    Parses Spintax like {Hello|Hi|Hey} there!
    Supports simple, non-nested spintax.
    """
    if not text:
        return ""
    pattern = re.compile(r'\{([^{}]*)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        options = match.group(1).split('|')
        choice = random.choice(options)
        text = text[:match.start()] + choice + text[match.end():]
    return text

def human_type(page, locator, text):
    """
    Types text character by character with random delays and occasional simulated typos.
    """
    print("Typing with human-like behavior (including possible typos)...")
    locator.focus()
    keyboard = page.keyboard
    
    # Facebook inputs often need an initial click or it might miss the first char
    locator.click()
    time.sleep(random.uniform(0.5, 1.0))
    
    for char in text:
        # Special handling for newlines
        if char == '\n':
            keyboard.press('Enter')
            time.sleep(random.uniform(0.2, 0.5))
            continue
            
        # 3% chance to make a typo (if it's a common char)
        if char.isalpha() and random.random() < 0.03:
            # Type a random wrong character
            wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
            keyboard.type(wrong_char, delay=random.randint(30, 80))
            time.sleep(random.uniform(0.1, 0.4))
            # Delete it
            keyboard.press("Backspace")
            time.sleep(random.uniform(0.1, 0.3))
            
        # Type the correct character
        try:
            keyboard.type(char, delay=random.randint(30, 80))
        except:
            # Fallback for weird characters
            keyboard.insert_text(char)
            
        # Occasional longer pause (thinking pause)
        if char in ['.', ',', '!', '?', ' '] and random.random() < 0.1:
            time.sleep(random.uniform(0.4, 1.2))

# ---- Multi-Account Handling ----

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_accounts(accounts):
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def launch_browser(account, p, api_url=None):
    """
    Launches browser for a given account. Unifies local profile and GPM profile methods.
    Returns (browser_or_none, context, page)
    """
    acc_type = account.get("type", "local")
    profile_id = account.get("profile_path_or_id", "")
    proxy_str = account.get("proxy", "").strip()
    
    if acc_type == "gpm":
        # Connect to GPM Login profile via API
        if not api_url:
            api_url = "http://127.0.0.1:13926" # default V2 API port
            
        import requests
        browser = None
        
        # Try V2 API (Start Profile)
        try:
            url = f"{api_url}/api/v2/start?profileId={profile_id}"
            print(f"Gọi GPM V2 API: {url}")
            res = requests.get(url, timeout=10).json()
            if res.get("success") or "data" in res:
                browser_url = res["data"].get("browser_url")
                if browser_url:
                    if not browser_url.startswith("http"):
                        browser_url = f"http://{browser_url}"
                    print(f"Đang kết nối Playwright tới địa chỉ CDP: {browser_url}")
                    browser = p.chromium.connect_over_cdp(browser_url)
        except Exception as e:
            print(f"Thử gọi GPM V2 API thất bại: {e}")
            
        # Try V3 API (Start Profile) if V2 failed or wsEndpoint needed
        if not browser:
            try:
                # GPM V3 default port is 19995
                v3_api = api_url if "19995" in api_url else "http://127.0.0.1:19995"
                url = f"{v3_api}/api/v3/profiles/start?id={profile_id}"
                print(f"Gọi GPM V3 API: {url}")
                res = requests.get(url, timeout=10).json()
                if res.get("success") or "data" in res:
                    ws_endpoint = res["data"].get("wsEndpoint")
                    if ws_endpoint:
                        print(f"Đang kết nối Playwright tới wsEndpoint: {ws_endpoint}")
                        browser = p.chromium.connect_over_cdp(ws_endpoint)
            except Exception as e:
                print(f"Thử gọi GPM V3 API thất bại: {e}")
                
        if not browser:
            raise Exception("Không thể khởi chạy profile GPM qua API. Hãy kiểm tra xem app GPM Login có đang chạy hay không.")
            
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        return browser, context, page
        
    else:
        # Launch persistent local profile
        os.makedirs("profiles", exist_ok=True)
        # Tên thư mục an toàn
        safe_dir_name = re.sub(r'[^a-zA-Z0-9_-]', '_', profile_id)
        if not safe_dir_name:
            safe_dir_name = "default_profile"
        profile_dir = os.path.abspath(os.path.join("profiles", safe_dir_name))
        print(f"Khởi chạy Local Profile tại: {profile_dir}")
        
        proxy = None
        if proxy_str:
            proxy = {"server": proxy_str}
            print(f"Sử dụng Proxy: {proxy_str}")
            
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            proxy=proxy,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        # For local persistent profiles, the browser instance is implicit in context.
        # We return (None, context, page).
        return None, context, page

def close_browser(browser_or_context, account, api_url=None):
    """
    Closes the connection. Unifies local profile and GPM profile methods.
    """
    acc_type = account.get("type", "local")
    profile_id = account.get("profile_path_or_id", "")
    
    if acc_type == "gpm":
        # Try to close GPM profile via GPM API
        if not api_url:
            api_url = "http://127.0.0.1:13926"
        import requests
        try:
            requests.get(f"{api_url}/api/v2/close?profileId={profile_id}", timeout=5)
        except Exception:
            pass
        try:
            v3_api = api_url if "19995" in api_url else "http://127.0.0.1:19995"
            requests.get(f"{v3_api}/api/v3/profiles/close?id={profile_id}", timeout=5)
        except Exception:
            pass
            
        # Close the local Playwright connection handle
        if browser_or_context:
            try:
                browser_or_context.close()
            except Exception:
                pass
    else:
        # Local persistent context close
        if browser_or_context:
            try:
                browser_or_context.close()
            except Exception:
                pass
