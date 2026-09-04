import re
import random
import time
import os
import json
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.json")
STATE_FILE = os.path.join(BASE_DIR, "state.json")

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

def process_spintax(text, anti_hash=False):
    """
    Parses Spintax like {Hello|Hi|Hey} there!
    Supports simple, non-nested spintax.
    Nếu anti_hash=True: Tự động chèn Zero-Width Space ngẫu nhiên để chống Meta trùng mã băm.
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

    if anti_hash:
        try:
            from ai_spinner import inject_zero_width_chars
            text = inject_zero_width_chars(text)
        except Exception:
            pass

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


def fetch_gpm_profiles(gpm_api_url=None, page=1, page_size=100):
    """
    Kéo danh sách Profile trực tiếp từ GPMLogin REST API v3 (mặc định port 19995).
    Tham khảo từ kiến trúc Autoupload Zalopro (automation_tools).
    """
    api_base = (gpm_api_url or os.getenv("GPM_API_URL", "http://127.0.0.1:19995")).rstrip("/")
    if "/api" in api_base:
        url = f"{api_base}/profiles"
    else:
        url = f"{api_base}/api/v3/profiles"

    try:
        import requests
        res = requests.get(url, params={"page": page, "page_size": page_size}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            profiles_data = data.get("data", [])
            pagination = data.get("pagination", {})
            total = pagination.get("total", len(profiles_data)) if isinstance(pagination, dict) else len(profiles_data)
            return {"connected": True, "profiles": profiles_data, "total": total, "base_url": api_base}
    except Exception:
        pass
    return {"connected": False, "profiles": [], "total": 0, "base_url": api_base}


def resolve_account(account_id, gpm_api_url=None):
    """
    Tìm hoặc tự động phân giải cấu hình tài khoản:
    1. Kiểm tra trong accounts.json (nếu đã nạp).
    2. Nếu không có (người dùng chọn trực tiếp từ GPM mà không nạp), tự động tra cứu từ GPM API v3.
    3. Trả về cấu hình dict hoàn chỉnh cho launch_browser() khởi chạy trực tiếp qua CDP.
    """
    if not account_id:
        return None

    # 1. Tìm trong accounts.json
    accounts = load_accounts()
    acc = next((a for a in accounts if a.get("id") == account_id or a.get("name") == account_id or a.get("profile_path_or_id") == account_id), None)
    if acc:
        return acc

    # 2. Tra cứu trực tiếp từ GPM API v3 (Zero-Config)
    gpm_res = fetch_gpm_profiles(gpm_api_url=gpm_api_url, page_size=200)
    if gpm_res.get("connected"):
        for p in gpm_res.get("profiles", []):
            if p.get("id") == account_id or p.get("name") == account_id:
                return {
                    "id": p.get("id"),
                    "name": p.get("name", account_id),
                    "type": "gpm",
                    "profile_path_or_id": p.get("id"),
                    "proxy": p.get("raw_proxy", ""),
                    "browser_type": p.get("browser_type", "Chrome"),
                    "status": "GPM Trực tiếp"
                }

    # 3. Fallback: Nếu không kết nối được GPM API nhưng có ID, tạo cấu hình GPM tạm thời để chạy
    is_uuid = bool(re.search(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", account_id))
    return {
        "id": account_id,
        "name": account_id if not is_uuid else f"GPM ({account_id[:8]})",
        "type": "gpm",
        "profile_path_or_id": account_id,
        "proxy": "",
        "status": "GPM Trực tiếp"
    }


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
                print(f"Calling GPM Login v4/v3 API: {url}")
                payload = requests.get(url, params={"win_scale": 0.8}, timeout=15).json()
                data = payload.get("data") if isinstance(payload, dict) else None
                cdp_address = data.get("remote_debugging_address") if isinstance(data, dict) else None
                if cdp_address and (payload.get("success") or payload.get("status") or True):
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

# =========================================================================
# MEDIA ANTI-HASH PIPELINE (EXIF STRIPPER & PHASH RANDOMIZER)
# =========================================================================

def clean_and_randomize_image(image_path: str, output_dir: str = None) -> str:
    """
    Xóa sạch EXIF metadata và vi chỉnh nhẹ hình ảnh để thay đổi mã băm (pHash/MD5) của ảnh:
    - Bóc tách toàn bộ metadata EXIF (GPS, thông số camera, timestamp chụp).
    - Vi chỉnh kích thước ngẫu nhiên (cắt xén hoặc co giãn cực nhẹ ±1 đến ±2 pixel).
    - Lưu file vào thư mục runtime/processed_media/ (giữ nguyên file gốc của người dùng).
    - Nếu Pillow chưa có hoặc gặp lỗi, trả về image_path gốc an toàn.
    """
    if not image_path or not os.path.exists(image_path):
        return image_path

    if "processed_media" in os.path.abspath(image_path):
        return image_path

    try:
        from PIL import Image, ImageOps
        import uuid
        
        if not output_dir:
            output_dir = os.path.join("runtime", "processed_media")
        os.makedirs(output_dir, exist_ok=True)
        
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            return image_path
            
        unique_name = f"clean_{uuid.uuid4().hex[:10]}{ext if ext != '.webp' else '.jpg'}"
        out_path = os.path.abspath(os.path.join(output_dir, unique_name))

        with Image.open(image_path) as img:
            # 1. Tự động xoay ảnh theo hướng chuẩn trước khi xóa EXIF
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
                
            # 2. Tạo bản sao ảnh RGB mới hoàn toàn không chứa EXIF
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            else:
                img = img.copy()

            # 3. Vi chỉnh kích thước ngẫu nhiên ±1 đến ±2 pixel để đổi Perceptual Hash
            w, h = img.size
            if w > 100 and h > 100:
                delta_w = random.choice([-2, -1, 1, 2])
                delta_h = random.choice([-2, -1, 1, 2])
                new_w = max(100, w + delta_w)
                new_h = max(100, h + delta_h)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # 4. Lưu lại với EXIF rỗng và chất lượng nén ngẫu nhiên (92 - 96)
            save_quality = random.randint(92, 96)
            img.save(out_path, format="JPEG" if ext in {".jpg", ".jpeg", ".webp"} else "PNG", quality=save_quality)

        return out_path
    except Exception as e:
        try:
            print(f"⚠️ [Media Anti-Hash] Không thể xử lý ảnh ({e}), dùng ảnh gốc: {image_path}")
        except Exception:
            pass
        return image_path


def process_images_anti_hash(image_paths: list) -> list:
    """
    Xử lý danh sách ảnh qua Media Anti-Hash Pipeline trước khi đính kèm vào bài đăng.
    """
    if not image_paths:
        return []
    cleaned_paths = []
    for path in image_paths:
        cleaned = clean_and_randomize_image(path)
        cleaned_paths.append(cleaned)
    return cleaned_paths


def pick_random_photos(folder_path, count_mode="2-4", clean_exif=True):
    """
    Quét thư mục ảnh và bốc ngẫu nhiên số lượng ảnh theo cấu hình:
    count_mode: '2-4' (ngẫu nhiên 2 đến 4 ảnh), '1', '2', '3', '4', hoặc 'all'.
    Nếu clean_exif=True: Tự động xóa sạch EXIF và vi chỉnh kích thước để chống Meta quét trùng ảnh.
    Trả về danh sách đường dẫn tuyệt đối của các ảnh được chọn.
    """
    if not folder_path or not os.path.exists(folder_path):
        return []
        
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    photos = []
    try:
        for entry in os.listdir(folder_path):
            full_path = os.path.join(folder_path, entry)
            if os.path.isfile(full_path):
                ext = os.path.splitext(entry)[1].lower()
                if ext in valid_exts:
                    photos.append(os.path.abspath(full_path))
    except Exception as e:
        print(f"⚠️ Lỗi khi quét thư mục ảnh {folder_path}: {e}")
        return []

    if not photos:
        return []

    # Xáo trộn ngẫu nhiên
    random.shuffle(photos)

    # Xác định số lượng ảnh cần lấy
    total = len(photos)
    if count_mode == "2-4":
        count = random.randint(min(2, total), min(4, total))
    elif count_mode == "all":
        count = total
    else:
        try:
            count = min(int(count_mode), total)
        except Exception:
            count = min(2, total)

    selected = photos[:count]
    
    # Áp dụng Media Anti-Hash Pipeline nếu được bật
    if clean_exif:
        try:
            selected = process_images_anti_hash(selected)
            try:
                print("🛡️ [Media Anti-Hash] Đã xóa EXIF và đổi mã băm thành công cho ảnh trước khi đăng.")
            except Exception:
                pass
        except Exception as e:
            try:
                print(f"⚠️ [Media Anti-Hash] Bỏ qua ({e})")
            except Exception:
                pass

    try:
        print(f"[Bốc ảnh ngẫu nhiên] Đã chọn {len(selected)}/{total} ảnh từ thư mục '{folder_path}'")
    except UnicodeEncodeError:
        print(f"[Boc anh ngau nhien] Da chon {len(selected)}/{total} anh tu '{folder_path}'")
    return selected



def attach_image_to_composer(page, dialog, image_path, clean_exif=True):
    """
    Đính kèm hình ảnh chuẩn xác vào khung soạn thảo Facebook (Group & Page).
    Hỗ trợ cả 1 file ảnh (str) hoặc danh sách nhiều ảnh (list[str]).
    Tự động bấm nút Ảnh/video để mở vùng chọn file, sau đó gán file ảnh vào đúng input file.
    Nếu clean_exif=True: Tự động xóa EXIF và đổi mã băm trước khi upload.
    """
    if not image_path:
        return False

    # Chuẩn hóa về danh sách file tồn tại
    if isinstance(image_path, str):
        files_to_attach = [image_path] if os.path.exists(image_path) else []
    elif isinstance(image_path, (list, tuple)):
        files_to_attach = [f for f in image_path if f and os.path.exists(f)]
    else:
        files_to_attach = []

    if not files_to_attach:
        return False

    if clean_exif:
        try:
            files_to_attach = process_images_anti_hash(files_to_attach)
            try:
                print("🛡️ [Media Anti-Hash] Đã xóa EXIF và đổi mã băm cho ảnh đính kèm.")
            except Exception:
                pass
        except Exception as e:
            try:
                print(f"⚠️ [Media Anti-Hash] Bỏ qua ({e})")
            except Exception:
                pass

    print(f"📸 Đang đính kèm {len(files_to_attach)} hình ảnh vào bài viết...")
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
            fc.set_files(files_to_attach)
            attached = True
            print(f"✅ Đã chọn {len(files_to_attach)} ảnh thành công qua File Chooser.")
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
                    fc.set_files(files_to_attach)
                    attached = True
                    print(f"✅ Đã chọn {len(files_to_attach)} ảnh thành công qua Dropzone File Chooser.")
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
                    inp.set_input_files(files_to_attach)
                    attached = True
                    print(f"✅ Đã gán {len(files_to_attach)} ảnh thành công vào thẻ input file của Facebook.")
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

POSTED_LINKS_FILE = "posted_links.json"

def record_posted_link(target, post_url, content=""):
    """
    Lưu link bài viết đã đăng thành công vào posted_links.json để phục vụ comment seeding.
    """
    if not post_url or not post_url.startswith("http"):
        return
    try:
        items = []
        if os.path.exists(POSTED_LINKS_FILE):
            try:
                with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    if not isinstance(items, list):
                        items = []
            except Exception:
                items = []
        
        # Tránh trùng lặp
        if not any(item.get("url") == post_url for item in items):
            now_ts = time.time()
            item = {
                "id": str(int(now_ts * 1000)),
                "timestamp": now_ts,
                "target": target,
                "url": post_url,
                "content_preview": (content[:120] + "...") if len(content) > 120 else content,
                "posted_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            items.insert(0, item)
            # Giữ tối đa 200 link gần nhất
            items = items[:200]
            with open(POSTED_LINKS_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            print(f"💾 Đã lưu bài viết vào Lịch sử đăng: {post_url}")
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu link bài đăng: {e}")

def normalize_target_url(url: str) -> str:
    """
    Chuẩn hóa URL nhóm/trang để so sánh trùng lặp chính xác (bỏ query parameters, trailing slashes, lowercase).
    """
    if not url:
        return ""
    clean = url.strip().lower().split("?")[0].rstrip("/")
    return clean

def is_recently_posted(target_url: str, hours: float = 24.0):
    """
    Kiểm tra xem target_url (Group hoặc Page) đã từng đăng bài thành công trong vòng `hours` giờ qua chưa.
    Trả về (True, hours_ago, posted_at_str) nếu trùng lặp gần đây, ngược lại trả về (False, 0, None).
    """
    if not target_url or not os.path.exists(POSTED_LINKS_FILE):
        return False, 0, None

    norm_target = normalize_target_url(target_url)
    try:
        with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
            items = json.load(f)
            if not isinstance(items, list):
                return False, 0, None
                
        now = time.time()
        max_age_seconds = hours * 3600.0

        for item in items:
            recorded_target = normalize_target_url(item.get("target", ""))
            # So sánh target hoặc kiểm tra target có nằm trong url bài đăng
            if recorded_target and (recorded_target == norm_target or norm_target in recorded_target or recorded_target in norm_target):
                ts = item.get("timestamp")
                if ts:
                    diff = now - float(ts)
                    if diff < max_age_seconds:
                        hours_ago = round(diff / 3600.0, 1)
                        return True, hours_ago, item.get("posted_at", "gần đây")
                else:
                    # Fallback parse posted_at nếu bản ghi cũ chưa có trường timestamp
                    posted_at = item.get("posted_at")
                    if posted_at:
                        try:
                            t_struct = time.strptime(posted_at, "%Y-%m-%d %H:%M:%S")
                            diff = now - time.mktime(t_struct)
                            if diff < max_age_seconds:
                                hours_ago = round(diff / 3600.0, 1)
                                return True, hours_ago, posted_at
                        except Exception:
                            pass
    except Exception as e:
        print(f"⚠️ Lỗi kiểm tra trùng lặp target: {e}")

    return False, 0, None

def scrape_post_link(page, target="", content=""):
    """
    Trích xuất permalink của bài viết vừa đăng từ thông báo toast hoặc đầu Newsfeed.
    """
    print("Đang quét tìm liên kết của bài đăng vừa tạo...")
    clean_href = None
    try:
        # Chờ modal soạn thảo đóng hoàn toàn
        page.wait_for_selector("div[role='dialog']", state="hidden", timeout=15000)
        time.sleep(3.0)
        
        # Cách 1: Tìm thông báo Toast nổi lên của Facebook ("Xem bài viết", "View post", "Xem bài đăng")
        try:
            toast_links = page.locator("a[href*='/posts/'], a[href*='/permalink/'], a[href*='permalink.php']").all()
            for link in toast_links:
                href = link.get_attribute("href")
                if href and ("view" in (link.inner_text() or "").lower() or "xem" in (link.inner_text() or "").lower()):
                    clean = href.split("?")[0]
                    if not clean.startswith("http"):
                        clean = f"https://www.facebook.com{clean}"
                    clean_href = clean
                    break
        except Exception:
            pass

        # Cách 2: Quét thẻ bài viết đầu tiên trên tường (Top feed article)
        if not clean_href:
            try:
                first_article = page.locator("div[role='article'], div[role='feed'] > div").first
                if first_article.is_visible(timeout=3000):
                    # Tìm link thời gian đăng (timestamp link) hoặc link permalink
                    article_links = first_article.locator("a[href*='/posts/'], a[href*='/permalink/'], a[href*='permalink.php'], a[href*='/videos/']").all()
                    for link in article_links:
                        href = link.get_attribute("href")
                        if href and not any(x in href for x in ["/groups/user/", "/comment/", "reaction"]):
                            clean = href.split("?")[0]
                            if not clean.startswith("http"):
                                clean = f"https://www.facebook.com{clean}"
                            clean_href = clean
                            break
            except Exception:
                pass

        if clean_href:
            print(f"POSTED_LINK:{clean_href}")
            record_posted_link(target, clean_href, content)
            return clean_href
            
        print("⚠️ Không thể trích xuất liên kết bài viết tự động (sẽ lưu link mục tiêu).")
        return None
    except Exception as e:
        print(f"⚠️ Cảnh báo: Lỗi khi quét liên kết bài đăng: {e}")
        return None
