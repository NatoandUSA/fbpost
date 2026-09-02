import re
import random
import time
import os
import json
import tempfile

ACCOUNTS_FILE = "accounts.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1600, "height": 900},
    {"width": 1920, "height": 1080}
]

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
    
    # Facebook composer inputs often need an initial click
    locator.click()
    time.sleep(random.uniform(0.5, 1.0))
    
    for char in text:
        if char == '\n':
            keyboard.press('Enter')
            time.sleep(random.uniform(0.2, 0.5))
            continue
            
        # 3% chance to make a typo (if it's a common char)
        if char.isalpha() and random.random() < 0.03:
            wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
            keyboard.type(wrong_char, delay=random.randint(30, 80))
            time.sleep(random.uniform(0.1, 0.4))
            keyboard.press("Backspace")
            time.sleep(random.uniform(0.1, 0.3))
            
        try:
            keyboard.type(char, delay=random.randint(30, 80))
        except:
            keyboard.insert_text(char)
            
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
    temporary_path = None
    try:
        fd, temporary_path = tempfile.mkstemp(prefix="accounts-", suffix=".json", dir=".")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        os.replace(temporary_path, ACCOUNTS_FILE)
        return True
    except OSError:
        return False
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)

def launch_browser(account, p, api_url=None):
    """
    Launches browser for a given account. Unifies local profile and GPM profile methods.
    Enhanced with anti-detection fingerprint features.
    """
    acc_type = account.get("type", "local")
    profile_id = account.get("profile_path_or_id", "")
    proxy_str = account.get("proxy", "").strip()
    
    if acc_type == "gpm":
        if not api_url:
            api_url = "http://127.0.0.1:13926"
            
        import requests
        browser = None
        
        # Try GPM V2 API
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
            
        # Try GPM V3 API
        if not browser:
            try:
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
        # Launch persistent local profile with random UA & Viewport for anti-detection
        os.makedirs("profiles", exist_ok=True)
        safe_dir_name = re.sub(r'[^a-zA-Z0-9_-]', '_', profile_id)
        if not safe_dir_name:
            safe_dir_name = "default_profile"
        profile_dir = os.path.abspath(os.path.join("profiles", safe_dir_name))
        
        ua = random.choice(USER_AGENTS)
        viewport = random.choice(VIEWPORTS)
        
        print(f"Khởi chạy Local Profile tại: {profile_dir}")
        print(f"Sử dụng User-Agent: {ua}")
        print(f"Sử dụng Viewport: {viewport['width']}x{viewport['height']}")
        
        proxy = None
        if proxy_str:
            proxy = {"server": proxy_str}
            print(f"Sử dụng Proxy: {proxy_str}")
            
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            proxy=proxy,
            user_agent=ua,
            viewport=viewport,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications",
                "--start-maximized"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()
        return None, context, page

def close_browser(browser_or_context, account, api_url=None):
    acc_type = account.get("type", "local")
    profile_id = account.get("profile_path_or_id", "")
    
    if acc_type == "gpm":
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
            
        if browser_or_context:
            try:
                browser_or_context.close()
            except Exception:
                pass
    else:
        if browser_or_context:
            try:
                browser_or_context.close()
            except Exception:
                pass

# ---- Advanced Composer Features (Feeling, Checkin, Link Scraping) ----

def add_feeling(page):
    """
    Selects a random feeling inside the Facebook post composer.
    """
    print("Đang thêm cảm xúc ngẫu nhiên cho bài viết...")
    try:
        # Find feeling/activity button
        feeling_btn = page.locator("div[role='button'], div[aria-label]").filter(
            has_text=re.compile("Feeling/activity|Cảm xúc/hoạt động", re.IGNORECASE)
        ).first
        
        if feeling_btn.is_visible():
            feeling_btn.click()
            time.sleep(random.uniform(1.5, 2.5))
            
            feelings_list = ["Vui vẻ", "Hạnh phúc", "Tuyệt vời", "Hào hứng", "Biết ơn", "Năng động", "Hài lòng"]
            selected_feeling = random.choice(feelings_list)
            
            # Locate search textbox inside the feelings popover
            search_input = page.locator("input[placeholder*='Search'], input[placeholder*='Tìm kiếm']").first
            if search_input.is_visible():
                search_input.fill(selected_feeling)
                time.sleep(random.uniform(1.5, 2.5))
                
                # Choose the first matching feeling
                first_option = page.locator("div[role='button']").filter(
                    has_text=re.compile(selected_feeling, re.IGNORECASE)
                ).first
                if first_option.is_visible():
                    first_option.click()
                    print(f"✅ Đã gắn cảm xúc: {selected_feeling}")
                    time.sleep(random.uniform(1.0, 2.0))
    except Exception as e:
        print(f"⚠️ Cảnh báo: Không thể thêm cảm xúc. Lỗi: {e}")

def add_checkin(page):
    """
    Selects a random checkin location inside the Facebook post composer.
    """
    print("Đang check-in địa điểm ngẫu nhiên cho bài viết...")
    try:
        checkin_btn = page.locator("div[role='button'], div[aria-label]").filter(
            has_text=re.compile("Check in|Check-in|Địa điểm", re.IGNORECASE)
        ).first
        
        if checkin_btn.is_visible():
            checkin_btn.click()
            time.sleep(random.uniform(1.5, 2.5))
            
            locations_list = [
                "Đại Nội Huế", 
                "Chùa Thiên Mụ", 
                "Cầu Trường Tiền", 
                "Lăng Khải Định", 
                "Lăng Tự Đức", 
                "Lăng Minh Mạng", 
                "Trường Quốc Học Huế", 
                "Làng hương Thủy Xuân", 
                "Đồi Vọng Cảnh", 
                "Cung An Định"
            ]
            selected_location = random.choice(locations_list)
            
            search_input = page.locator("input[placeholder*='Where are you'], input[placeholder*='Bạn đang ở đâu'], input[placeholder*='Tìm kiếm']").first
            if search_input.is_visible():
                search_input.fill(selected_location)
                time.sleep(random.uniform(2.5, 4.0)) # Wait for suggestions to load
                
                # Select the first option
                first_option = page.locator("div[role='button']").filter(
                    has_text=re.compile(selected_location, re.IGNORECASE)
                ).first
                if first_option.is_visible():
                    first_option.click()
                    print(f"✅ Đã check-in địa điểm: {selected_location}")
                    time.sleep(random.uniform(1.0, 2.0))
    except Exception as e:
        print(f"⚠️ Cảnh báo: Không thể check-in. Lỗi: {e}")

def scrape_post_link(page):
    """
    Scrapes the URL of the newly created post from the feed or the popup notification.
    """
    print("Đang quét tìm liên kết của bài đăng vừa tạo...")
    try:
        # Wait for the composer modal/dialog to close
        page.wait_for_selector("div[role='dialog']", state="hidden", timeout=20000)
        time.sleep(4.0) # Wait for page to render the new post
        
        # Method 1: Search for Toast notification popup link ("View post" / "Xem bài viết")
        links = page.locator("a").all()
        for link in links:
            try:
                href = link.get_attribute("href")
                text = link.inner_text()
                if href and re.search(r"View|Xem", text, re.IGNORECASE) and ("/posts/" in href or "/permalink/" in href or "permalink.php" in href):
                    clean_href = href.split("?")[0]
                    if not clean_href.startswith("http"):
                        clean_href = f"https://www.facebook.com{clean_href}"
                    print(f"POSTED_LINK:{clean_href}")
                    return clean_href
            except Exception:
                continue
                
        # Method 2: Look at the top article on the feed
        first_article = page.locator("div[role='article']").first
        if first_article.is_visible():
            article_links = first_article.locator("a[role='link'], a").all()
            for link in article_links:
                href = link.get_attribute("href")
                if href and ("/posts/" in href or "/permalink/" in href or "permalink.php" in href):
                    clean_href = href.split("?")[0]
                    if not clean_href.startswith("http"):
                        clean_href = f"https://www.facebook.com{clean_href}"
                    print(f"POSTED_LINK:{clean_href}")
                    return clean_href
                    
        print("⚠️ Không thể trích xuất liên kết bài viết tự động.")
        return None
    except Exception as e:
        print(f"⚠️ Cảnh báo: Lỗi khi quét liên kết bài đăng: {e}")
        return None
