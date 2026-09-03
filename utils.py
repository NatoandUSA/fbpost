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
    try:
        locator.focus()
    except Exception:
        pass
    
    keyboard = page.keyboard
    
    # Facebook composer inputs often need an initial click - dùng force=True để tránh bị backdrop che
    try:
        locator.click(force=True, timeout=5000)
    except Exception:
        try:
            locator.focus()
        except Exception:
            pass
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


def connect_over_cdp_when_ready(playwright, cdp_url, timeout_seconds=20):
    """Wait for a GPM-launched browser to expose its local CDP endpoint."""
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            return playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as error:
            last_error = error
            if attempt == 1:
                print("GPM has started the profile; waiting for its debugging port to become ready...")
            time.sleep(0.75)
    raise RuntimeError(f"GPM debugging port was not ready after {timeout_seconds} seconds: {last_error}")


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
            # GPM Login v4 (Legacy) exposes its local API on this address.
            api_url = "http://127.0.0.1:19995"

        import requests
        browser = None
        gpm_error = None
        api_base = api_url.rstrip("/").split("/api/")[0]
        profile_id_match = re.search(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", profile_id)
        if profile_id_match:
            profile_id = profile_id_match.group(0)

        api_is_v1 = api_url.rstrip("/").endswith("/api/v1")
        if api_is_v1:
            try:
                url = f"{api_url.rstrip('/')}/profiles/start/{profile_id}"
                print(f"Calling GPM Local API: {url}")
                payload = requests.get(url, timeout=10).json()
                data = payload.get("data") if isinstance(payload, dict) else None
                ws_endpoint = data.get("websocket_debugging_url") if isinstance(data, dict) else None
                if payload.get("success") and ws_endpoint:
                    browser = connect_over_cdp_when_ready(p, ws_endpoint)
                elif isinstance(payload, dict):
                    gpm_error = f"GPM Local API: {payload.get('message', 'no connection data returned')}"
                    print(f"GPM Local API did not start the profile: {payload.get('message', 'no connection data returned')}")
            except Exception as e:
                gpm_error = f"GPM Local API connection failed: {e}"
                print(f"GPM Local API attempt failed: {e}")

        # GPM Login v4 (Legacy): GET /api/v3/profiles/start/{id}.
        # It returns a CDP address rather than a websocket endpoint.
        if not browser and not api_is_v1:
            try:
                url = f"{api_base}/api/v3/profiles/start/{profile_id}"
                print(f"Calling GPM Login v4 API: {url}")
                payload = requests.get(url, timeout=10).json()
                data = payload.get("data") if isinstance(payload, dict) else None
                cdp_address = data.get("remote_debugging_address") if isinstance(data, dict) else None
                if payload.get("success") and cdp_address:
                    cdp_url = cdp_address if cdp_address.startswith("http") else f"http://{cdp_address}"
                    browser = connect_over_cdp_when_ready(p, cdp_url)
                elif isinstance(payload, dict):
                    gpm_error = f"GPM Login v4: {payload.get('message', 'no CDP address returned')}"
                    print(f"GPM Login v4 did not start the profile: {payload.get('message', 'no CDP address returned')}")
            except Exception as e:
                gpm_error = f"GPM Login v4 CDP connection failed: {e}"
                print(f"GPM Login v4 API attempt failed: {e}")

        # Backward-compatible GPM v2 fallback.
        if not browser and not api_is_v1:
            try:
                url = f"{api_base}/api/v2/start?profileId={profile_id}"
                payload = requests.get(url, timeout=10).json()
                data = payload.get("data") if isinstance(payload, dict) else None
                browser_url = data.get("browser_url") if isinstance(data, dict) else None
                if browser_url:
                    cdp_url = browser_url if browser_url.startswith("http") else f"http://{browser_url}"
                    browser = connect_over_cdp_when_ready(p, cdp_url)
            except Exception as e:
                if not gpm_error:
                    gpm_error = f"GPM v2 fallback connection failed: {e}"
                
        if not browser:
            raise Exception(gpm_error or "Không thể khởi chạy profile GPM. Dùng URL http://127.0.0.1:19995 và API v3 trong GPM Login v4.")
            
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        
        # Bỏ qua lỗi SSL / Certificate từ Proxy (ERR_CERT_COMMON_NAME_INVALID)
        try:
            cdp_client = context.new_cdp_session(page)
            cdp_client.send("Security.setIgnoreCertificateErrors", {"ignore": True})
        except Exception:
            pass
            
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
            ignore_https_errors=True,
            proxy=proxy,
            user_agent=ua,
            viewport=viewport,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-notifications",
                "--ignore-certificate-errors",
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
            api_url = "http://127.0.0.1:19995"
        import requests
        api_base = api_url.rstrip("/").split("/api/")[0]
        profile_id_match = re.search(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", profile_id)
        if profile_id_match:
            profile_id = profile_id_match.group(0)
        if api_url.rstrip("/").endswith("/api/v1"):
            try:
                requests.get(f"{api_url.rstrip('/')}/profiles/stop/{profile_id}", timeout=5)
            except Exception:
                pass
        else:
            try:
                requests.get(f"{api_base}/api/v3/profiles/close/{profile_id}", timeout=5)
            except Exception:
                pass
        try:
            requests.get(f"{api_base}/api/v2/close?profileId={profile_id}", timeout=5)
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

# ---- Advanced Composer Features (Image, Feeling, Checkin, Link Scraping) ----

def attach_image_to_composer(page, dialog, image_path):
    """
    Đính kèm hình ảnh chuẩn xác vào khung soạn thảo Facebook (Group & Page).
    Tự động bấm nút Ảnh/video để mở vùng chọn file, sau đó gán file ảnh vào đúng input file.
    """
    if not image_path or not os.path.exists(image_path):
        return False

    print(f"📸 Đang đính kèm hình ảnh: {image_path}")
    attached = False

    # 1. Tìm nút "Ảnh/video" trong Dialog
    photo_btn = None
    photo_selectors = [
        "div[role='dialog'] div[aria-label*='Ảnh/video' i]",
        "div[role='dialog'] div[aria-label*='Photo/video' i]",
        "div[role='dialog'] div[aria-label*='Ảnh' i]",
        "div[role='dialog'] div[role='button']:has-text('Ảnh/video')",
        "div[role='dialog'] div[role='button']:has-text('Photo/video')"
    ]
    for sel in photo_selectors:
        btn = page.locator(sel).first
        if btn.is_visible(timeout=1500):
            photo_btn = btn
            break

    # 2. Thử kích hoạt file chooser bằng cách bấm nút Ảnh/video
    if photo_btn:
        try:
            with page.expect_file_chooser(timeout=3500) as fc_info:
                photo_btn.click(force=True)
            fc = fc_info.value
            fc.set_files(image_path)
            attached = True
            print("✅ Đã chọn ảnh thành công qua File Chooser.")
        except Exception:
            pass

    # 3. Nếu chưa attach được: bấm vào vùng "Thêm ảnh/video" hoặc gán thẳng vào input file trong dialog
    if not attached:
        try:
            dropzone = page.locator("div[role='dialog'] div:has-text('Thêm ảnh/video'), div[role='dialog'] div:has-text('Add photos/videos')").first
            if dropzone.is_visible(timeout=1500):
                try:
                    with page.expect_file_chooser(timeout=3500) as fc_info:
                        dropzone.click(force=True)
                    fc = fc_info.value
                    fc.set_files(image_path)
                    attached = True
                    print("✅ Đã chọn ảnh thành công qua Dropzone File Chooser.")
                except Exception:
                    pass
        except Exception:
            pass

    # 4. Fallback gán trực tiếp vào input[type='file'] của dialog
    if not attached:
        try:
            inputs = page.locator("div[role='dialog'] input[type='file'], input[type='file'][accept*='image']")
            for idx in range(inputs.count()):
                inp = inputs.nth(idx)
                try:
                    inp.set_input_files(image_path)
                    attached = True
                    print("✅ Đã gán ảnh thành công vào thẻ input file của Facebook.")
                    break
                except Exception:
                    continue
        except Exception as err:
            print(f"⚠️ Không thể gán file ảnh: {err}")

    # 5. Chờ xem preview ảnh có xuất hiện trong dialog không
    if attached:
        print("⏳ Đang chờ ảnh tải lên hoàn tất...")
        try:
            page.wait_for_selector("div[role='dialog'] img[src*='blob:'], div[role='dialog'] img[src*='data:'], div[role='dialog'] img", timeout=7000)
            print("✅ Đã xác nhận hình ảnh hiển thị trong khung bài viết!")
        except Exception:
            time.sleep(4.0)
    return attached

def add_feeling(page):
    """
    Selects a random feeling inside the Facebook post composer.
    """
    print("Đang thêm cảm xúc ngẫu nhiên cho bài viết...")
    try:
        feeling_btn = page.locator("div[role='dialog'] div[role='button'], div[role='dialog'] div[aria-label]").filter(
            has_text=re.compile("Feeling/activity|Cảm xúc/hoạt động|Cảm xúc", re.IGNORECASE)
        ).first
        
        if feeling_btn.is_visible(timeout=3000):
            feeling_btn.click(force=True, timeout=5000)
            time.sleep(random.uniform(1.5, 2.5))
            
            feelings_list = ["Vui vẻ", "Hạnh phúc", "Tuyệt vời", "Hào hứng", "Biết ơn", "Năng động", "Hài lòng"]
            selected_feeling = random.choice(feelings_list)
            
            search_input = page.locator("input[placeholder*='Search'], input[placeholder*='Tìm kiếm']").first
            if search_input.is_visible(timeout=3000):
                search_input.fill(selected_feeling)
                time.sleep(random.uniform(1.5, 2.5))
                
                first_option = page.locator("div[role='button']").filter(
                    has_text=re.compile(selected_feeling, re.IGNORECASE)
                ).first
                if first_option.is_visible(timeout=3000):
                    first_option.click(force=True, timeout=5000)
                    print(f"✅ Đã gắn cảm xúc: {selected_feeling}")
                    time.sleep(random.uniform(1.0, 2.0))
    except Exception as e:
        print(f"⚠️ Cảnh báo: Bỏ qua thêm cảm xúc ({e}).")

def add_checkin(page):
    """
    Selects a random checkin location inside the Facebook post composer.
    """
    print("Đang check-in địa điểm ngẫu nhiên cho bài viết...")
    try:
        checkin_btn = page.locator("div[role='dialog'] div[role='button'], div[role='dialog'] div[aria-label]").filter(
            has_text=re.compile("Check in|Check-in|Địa điểm", re.IGNORECASE)
        ).first
        
        if checkin_btn.is_visible(timeout=3000):
            checkin_btn.click(force=True, timeout=5000)
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
            if search_input.is_visible(timeout=3000):
                search_input.fill(selected_location)
                time.sleep(random.uniform(2.5, 4.0))
                
                first_option = page.locator("div[role='button']").filter(
                    has_text=re.compile(selected_location, re.IGNORECASE)
                ).first
                if first_option.is_visible(timeout=3000):
                    first_option.click(force=True, timeout=5000)
                    print(f"✅ Đã check-in địa điểm: {selected_location}")
                    time.sleep(random.uniform(1.0, 2.0))
    except Exception as e:
        print(f"⚠️ Cảnh báo: Bỏ qua check-in ({e}).")

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
