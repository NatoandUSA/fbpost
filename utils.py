import re
import random
import time
import os
import sys
import json
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

@dataclass
class ActionResult:
    success: bool
    code: str
    message: str = ""
    state: str = ""  # "published", "pending", "joined", "requested", "failed", "cancelled", etc.
    target_url: str = ""
    result_url: str = ""
    url_type: str = "unknown"  # "post", "group", "page", "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = None

    def __post_init__(self):
        if self.data is not None and not self.metadata:
            self.metadata = self.data
        elif self.metadata and self.data is None:
            self.data = self.metadata
        elif self.data is None and not self.metadata:
            self.data = {}
            self.metadata = self.data

    def __bool__(self) -> bool:
        return bool(self.success)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "code": self.code,
            "message": self.message,
            "state": self.state,
            "target_url": self.target_url,
            "result_url": self.result_url,
            "url_type": self.url_type,
            "metadata": self.metadata,
            "data": self.metadata,
        }

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

def _ensure_focus(locator):
    try:
        locator.focus(timeout=2000)
        return True
    except Exception:
        try:
            locator.click(force=True, timeout=2000)
            return True
        except Exception:
            return False

def human_type(page, locator, text, multiline_key="Enter"):
    """
    Types text character by character with random delays and occasional simulated typos.
    Nếu multiline_key='Shift+Enter': Xuống dòng bằng Shift+Enter để tránh bị gửi bình luận sớm trong khung comment Facebook.
    """
    print("Typing with human-like behavior (including possible typos)...")
    _ensure_focus(locator)
    time.sleep(random.uniform(0.5, 1.0))
    keyboard = page.keyboard
    
    for idx, char in enumerate(text):
        if idx > 0 and idx % 40 == 0:
            _ensure_focus(locator)

        if char == '\n':
            if multiline_key == "Shift+Enter":
                keyboard.press('Shift+Enter')
            else:
                keyboard.press('Enter')
            time.sleep(random.uniform(0.15, 0.35))
            continue

        # Non-BMP (emojis như 🌸, 🏡) hoặc zero-width spaces (\u200b) dùng insert_text trực tiếp để tránh lỗi gõ phím
        if ord(char) > 0xFFFF or char in ["\u200b", "\u200c", "\u200d"]:
            keyboard.insert_text(char)
            time.sleep(0.01)
            continue

        # 2% mô phỏng gõ nhầm với ký tự ASCII đơn giản
        if char.isalpha() and ord(char) < 128 and random.random() < 0.02:
            wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
            keyboard.type(wrong_char, delay=random.randint(20, 50))
            time.sleep(random.uniform(0.08, 0.2))
            keyboard.press("Backspace")
            time.sleep(random.uniform(0.08, 0.15))

        try:
            keyboard.type(char, delay=random.randint(20, 50))
        except Exception:
            keyboard.insert_text(char)

        if char in ['.', ',', '!', '?', ' '] and random.random() < 0.08:
            time.sleep(random.uniform(0.2, 0.6))

def safe_mouse_wheel(page, dx, dy):
    """
    Safely scroll using mouse wheel without crashing on TargetClosedError or disconnected CDP.
    """
    if not page:
        return False
    try:
        if hasattr(page, "is_closed") and page.is_closed():
            return False
        page.mouse.wheel(dx, dy)
        return True
    except Exception:
        return False

# ---- Multi-Account Handling ----

def load_accounts():
    try:
        from repositories.account_repo import AccountRepository
        accs = AccountRepository().list_accounts()
        if accs:
            return accs
    except Exception:
        pass
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_accounts(accounts):
    try:
        from repositories.account_repo import AccountRepository
        AccountRepository().save_accounts(accounts)
    except Exception:
        pass
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
                    msg = str(payload.get('message', ''))
                    if "ALREADY_OPEN" in msg.upper() or "ALREADY OPEN" in msg.upper():
                        print(f"⚠️ Profile GPM Local API đang mở (ALREADY_OPEN). Tự động đóng và khởi động lại...")
                        try:
                            requests.get(f"{api_url.rstrip('/')}/profiles/stop/{profile_id}", timeout=6)
                        except Exception:
                            pass
                        time.sleep(2.5)
                        print(f"Khởi động lại Profile GPM Local API: {url}")
                        try:
                            retry_payload = requests.get(url, timeout=25).json()
                            retry_data = retry_payload.get("data") if isinstance(retry_payload, dict) else None
                            ws_endpoint = retry_data.get("websocket_debugging_url") if isinstance(retry_data, dict) else None
                            if retry_payload.get("success") and ws_endpoint:
                                browser = connect_over_cdp_when_ready(p, ws_endpoint)
                            else:
                                gpm_error = f"GPM Local API retry: {retry_payload.get('message', 'no connection data returned')}"
                        except Exception as re_err:
                            gpm_error = f"GPM Local API retry failed: {re_err}"
                    else:
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
                    msg = str(payload.get('message', ''))
                    if "ALREADY_OPEN" in msg.upper() or "ALREADY OPEN" in msg.upper():
                        print(f"⚠️ Profile GPM đang mở (ALREADY_OPEN). Đang tự động đóng và khởi động lại...")
                        try:
                            requests.get(f"{api_base}/api/v3/profiles/close/{profile_id}", timeout=6)
                        except Exception:
                            pass
                        try:
                            requests.get(f"{api_base}/api/v2/close?profileId={profile_id}", timeout=6)
                        except Exception:
                            pass
                        time.sleep(2.5)
                        print(f"Khởi động lại Profile GPM: {url}")
                        try:
                            retry_payload = requests.get(url, params={"win_scale": 0.8}, timeout=25).json()
                            retry_data = retry_payload.get("data") if isinstance(retry_payload, dict) else None
                            retry_cdp = retry_data.get("remote_debugging_address") if isinstance(retry_data, dict) else None
                            if retry_cdp:
                                cdp_url = retry_cdp if retry_cdp.startswith("http") else f"http://{retry_cdp}"
                                browser = connect_over_cdp_when_ready(p, cdp_url)
                            else:
                                gpm_error = f"GPM Login v4 retry failed: {retry_payload.get('message', 'no CDP address returned')}"
                        except Exception as re_err:
                            gpm_error = f"GPM Login v4 retry connection failed: {re_err}"
                    else:
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
        page = None
        for p_item in context.pages:
            try:
                if not p_item.is_closed():
                    page = p_item
                    break
            except Exception:
                pass
        if not page:
            page = context.new_page()
        
        # Bỏ qua lỗi SSL / Certificate từ Proxy (ERR_CERT_COMMON_NAME_INVALID)
        try:
            cdp_client = context.new_cdp_session(page)
            cdp_client.send("Security.setIgnoreCertificateErrors", {"ignore": True})
        except Exception:
            pass

        def _auto_accept_dialog(d):
            try:
                print(f"🔔 Tự động xử lý dialog trình duyệt: [{d.type}] '{d.message}' -> Chấp nhận (Accept)")
                d.accept()
            except Exception:
                pass

        try:
            page.on("dialog", _auto_accept_dialog)
            context.on("page", lambda p_new: p_new.on("dialog", _auto_accept_dialog))
            context.add_init_script("""
                try {
                    window.onbeforeunload = null;
                    window.addEventListener('beforeunload', (e) => {
                        delete e['returnValue'];
                        e.stopImmediatePropagation();
                    }, true);
                    Object.defineProperty(window, 'onbeforeunload', {
                        get: () => null,
                        set: () => {}
                    });
                } catch(e) {}
            """)
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
        page = None
        for p_item in context.pages:
            try:
                if not p_item.is_closed():
                    page = p_item
                    break
            except Exception:
                pass
        if not page:
            page = context.new_page()

        def _auto_accept_local_dialog(d):
            try:
                print(f"🔔 Tự động xử lý dialog trình duyệt: [{d.type}] '{d.message}' -> Chấp nhận (Accept)")
                d.accept()
            except Exception:
                pass

        try:
            page.on("dialog", _auto_accept_local_dialog)
            context.on("page", lambda p_new: p_new.on("dialog", _auto_accept_local_dialog))
            context.add_init_script("""
                try {
                    window.onbeforeunload = null;
                    window.addEventListener('beforeunload', (e) => {
                        delete e['returnValue'];
                        e.stopImmediatePropagation();
                    }, true);
                    Object.defineProperty(window, 'onbeforeunload', {
                        get: () => null,
                        set: () => {}
                    });
                } catch(e) {}
            """)
        except Exception:
            pass

        return None, context, page

def close_browser(browser_or_context, account=None, api_url=None):
    # Support both close_browser(browser_obj, context, account) and close_browser(browser_or_context, account, api_url)
    if not isinstance(account, dict) and hasattr(account, "close") and isinstance(api_url, dict):
        browser_or_context = browser_or_context or account
        account = api_url
        api_url = None

    if browser_or_context:
        try:
            pages = []
            if hasattr(browser_or_context, "pages"):
                pages = browser_or_context.pages
            elif hasattr(browser_or_context, "contexts"):
                for ctx in browser_or_context.contexts:
                    pages.extend(getattr(ctx, "pages", []))
            for pg in pages:
                try:
                    if not pg.is_closed():
                        pg.evaluate("window.onbeforeunload = null;")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            browser_or_context.close()
        except Exception:
            pass

    account = account or {}
    acc_type = account.get("type", "local")
    profile_id = account.get("profile_path_or_id", "")
    
    if acc_type == "gpm" and profile_id:
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
        # Cho phép Chrome và GPM giải phóng port/file lock
        time.sleep(1.0)

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
            try:
                import paths
                output_dir = str(paths.DATA_DIR / "processed_media")
            except Exception:
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


def click_post_publish_button(page, dialog=None):
    """
    Tìm và bấm chính xác nút Đăng / Post ở dưới cùng của dialog Facebook:
    - Vô hiệu hóa beforeunload để ngăn chặn triệt để popup 'Rời khỏi trang web?'.
    - Kích hoạt cơ chế 3 tầng:
        1. Native JavaScript DOM Engine: Tìm phần tử có text 'Đăng'/'Post' hoặc aria-label 'Đăng'/'Post',
           loại bỏ 'Đăng ẩn danh', cuộn vào giữa màn hình, dispatch toàn bộ Pointer/Mouse events và click().
        2. Shortcut phím tắt Ctrl+Enter / Cmd+Enter trên ô soạn thảo.
        3. Playwright Locator fallback: Quét từ đáy lên trên, Accessible Name và Text regex.
    - Chờ đợi theo vòng lặp (polling up to 15s) cho đến khi ảnh tải xong và nút Đăng sẵn sàng.
    - Xác nhận dialog đóng hoặc bài viết được tiếp nhận.
    """
    FORBIDDEN_WORDS = [
        "ẩn danh", "anonym", "quy tắc", "rule", "chỉnh sửa", "cài đặt",
        "setting", "lên lịch", "schedule", "bản nháp", "draft", "hủy", "cancel", "đóng", "close",
        "chia sẻ lên", "chia sẻ vào", "share to", "thêm vào"
    ]
    PUBLISH_LABELS = ["đăng", "post", "chia sẻ ngay", "share now"]

    # 0. Vô hiệu hóa beforeunload ngay lập tức trên page
    try:
        page.evaluate("""
            try {
                window.onbeforeunload = null;
                window.addEventListener('beforeunload', (e) => {
                    delete e['returnValue'];
                    e.stopImmediatePropagation();
                }, true);
            } catch(e) {}
        """)
    except Exception:
        pass

    def is_composer_dialog(d):
        try:
            if not d.is_visible():
                return False
            # Dialog soạn bài phải chứa ô nhập bài viết (không phải ô bình luận)
            tb = d.locator("div[role='textbox']")
            if tb.count() > 0:
                for idx in range(tb.count()):
                    lbl = ((tb.nth(idx).get_attribute("aria-label") or "") + " " + (tb.nth(idx).get_attribute("aria-placeholder") or "")).lower()
                    if "bình luận" not in lbl and "comment" not in lbl:
                        return True
            # Hoặc chứa nút Đăng/Post
            has_post_btn = d.locator("div[role='button'], button").filter(has_text=re.compile(r"^\s*(Đăng|Post)\s*$", re.IGNORECASE)).count() > 0
            if has_post_btn:
                return True
        except Exception:
            pass
        return False

    def get_search_containers():
        containers = []
        if dialog:
            try:
                if dialog.is_visible():
                    containers.append(dialog)
            except Exception:
                pass
        try:
            dlgs = page.locator("div[role='dialog']").all()
            for d in dlgs:
                try:
                    if is_composer_dialog(d) and d not in containers:
                        containers.append(d)
                except Exception:
                    pass
            # Nếu chưa có container nào, thêm tất cả dialog visible
            if not containers:
                for d in dlgs:
                    try:
                        if d.is_visible() and d not in containers:
                            containers.append(d)
                    except Exception:
                        pass
        except Exception:
            pass
        containers.append(page)
        return containers

    JS_DISPATCH_PUBLISH = """
    (() => {
        try {
            const allDialogs = Array.from(document.querySelectorAll('div[role="dialog"]')).filter(d => {
                try {
                    const s = window.getComputedStyle(d);
                    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
                    const r = d.getBoundingClientRect();
                    return r.width > 50 && r.height > 50;
                } catch(e) { return false; }
            });

            let composerDialog = null;
            for (const d of allDialogs) {
                const tbs = Array.from(d.querySelectorAll('div[role="textbox"]'));
                const isPostTb = tbs.some(tb => {
                    const a = ((tb.getAttribute('aria-label') || '') + ' ' + (tb.getAttribute('aria-placeholder') || '')).toLowerCase();
                    return !a.includes('bình luận') && !a.includes('comment');
                });
                if (isPostTb) {
                    composerDialog = d;
                    break;
                }
            }

            const scopes = [];
            if (composerDialog) scopes.push(composerDialog);
            for (const d of allDialogs) {
                if (d !== composerDialog) scopes.push(d);
            }
            scopes.push(document.body);

            const FORBIDDEN = [
                'ẩn danh', 'anonym', 'quy tắc', 'rule', 'chỉnh sửa', 'cài đặt',
                'setting', 'lên lịch', 'schedule', 'bản nháp', 'draft', 'hủy',
                'cancel', 'đóng', 'close', 'chia sẻ lên', 'chia sẻ vào', 'thêm vào'
            ];

            for (const scope of scopes) {
                const candidates = Array.from(scope.querySelectorAll('div[role="button"], button, span[role="button"], div[aria-label], div[tabindex="0"]'));

                for (let i = candidates.length - 1; i >= 0; i--) {
                    const el = candidates[i];
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    if (el.closest('div[role="textbox"]')) continue;

                    const text = (el.innerText || el.textContent || '').trim();
                    const aria = (el.getAttribute('aria-label') || '').trim();
                    const combined = (text + ' ' + aria).toLowerCase();

                    if (FORBIDDEN.some(fw => combined.includes(fw))) continue;

                    const isMatch = 
                        /^(Đăng|Post|Chia sẻ ngay|Share now)$/i.test(text) ||
                        /^(Đăng|Post|Chia sẻ ngay|Share now)$/i.test(aria) ||
                        text === 'Đăng' || text === 'Post';

                    if (isMatch) {
                        const isDisabled = el.getAttribute('aria-disabled') === 'true' || el.disabled;
                        if (isDisabled) {
                            return { found: true, disabled: true, text: text || aria };
                        }

                        el.scrollIntoView({ behavior: 'instant', block: 'center' });
                        ['pointerdown', 'mousedown', 'pointerup', 'mouseup'].forEach(evt => {
                            el.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
                        });
                        if (typeof el.click === 'function') {
                            el.click();
                        }
                        return { found: true, clicked: true, text: text || aria };
                    }
                }
            }
        } catch (e) {
            return { error: e.toString() };
        }
        return { found: false };
    })()
    """

    def locate_publish_button():
        containers = get_search_containers()
        for c in containers:
            # Cách 1: Selector aria-label chuẩn xác
            for label in PUBLISH_LABELS:
                try:
                    btn = c.locator(f"div[role='button'][aria-label='{label}' i], div[aria-label='{label}' i], button[aria-label='{label}' i]").first
                    if btn.is_visible(timeout=300):
                        btn_text = (btn.inner_text() or "").lower()
                        aria = (btn.get_attribute("aria-label") or "").lower()
                        if not any(fw in btn_text or fw in aria for fw in FORBIDDEN_WORDS):
                            return btn
                except Exception:
                    continue

            # Cách 2: Playwright get_by_role (Accessible name W3C)
            try:
                for pat in [r"^\s*Đăng\s*$", r"^\s*Post\s*$", r"^(Đăng|Post|Chia sẻ ngay|Share now)$"]:
                    btns = c.get_by_role("button", name=re.compile(pat, re.IGNORECASE))
                    for idx in range(btns.count()):
                        role_btn = btns.nth(idx)
                        if role_btn.is_visible(timeout=300):
                            text_content = (role_btn.inner_text() or "").lower()
                            aria_content = (role_btn.get_attribute("aria-label") or "").lower()
                            if not any(fw in text_content or fw in aria_content for fw in FORBIDDEN_WORDS):
                                return role_btn
            except Exception:
                pass

            # Cách 3: Regex text trên div[role='button'] / button
            try:
                regex_post = re.compile(r"^\s*(Đăng|Post)\s*$", re.IGNORECASE)
                candidates = c.locator("div[role='button'], button").filter(has_text=regex_post)
                for idx in range(candidates.count() - 1, -1, -1):
                    cand = candidates.nth(idx)
                    if cand.is_visible(timeout=300):
                        cand_text = (cand.inner_text() or "").lower()
                        aria = (cand.get_attribute("aria-label") or "").lower()
                        if not any(fw in cand_text or fw in aria for fw in FORBIDDEN_WORDS):
                            return cand
            except Exception:
                pass

            # Cách 4: Quét ngược từ đáy dialog lên trên (nút Đăng luôn ở dưới cùng)
            try:
                buttons = c.locator("div[role='button'], button")
                count = buttons.count()
                for idx in range(count - 1, -1, -1):
                    b = buttons.nth(idx)
                    try:
                        if not b.is_visible():
                            continue
                        text = (b.inner_text() or "").strip()
                        aria = (b.get_attribute("aria-label") or "").strip()
                        full_str = (text + " " + aria).lower()

                        if any(fw in full_str for fw in FORBIDDEN_WORDS):
                            continue

                        first_line = text.split("\n")[0].strip().lower() if text else ""
                        if first_line in PUBLISH_LABELS or aria.lower() in PUBLISH_LABELS:
                            return b
                    except Exception:
                        continue
            except Exception:
                pass

        return None

    target_btn = None
    clicked_via_js = False

    # Polling chờ nút Đăng sẵn sàng trong tối đa 15 giây (mỗi lần 0.5s)
    for attempt in range(30):
        # 1. Thử qua Native DOM Engine trước
        try:
            js_res = page.evaluate(JS_DISPATCH_PUBLISH)
            if isinstance(js_res, dict):
                if js_res.get("clicked"):
                    print(f"🎯 Đã kích hoạt nút Đăng qua Native DOM Engine: '{js_res.get('text')}'!")
                    clicked_via_js = True
                    break
                elif js_res.get("disabled"):
                    print(f"⏳ Nút Đăng đang xử lý ảnh/phương tiện (aria-disabled=true), chờ 1s... ({attempt + 1}/30)")
                    time.sleep(1.0)
                    continue
        except Exception:
            pass

        # 2. Thử qua Playwright locator
        target_btn = locate_publish_button()
        if target_btn:
            break

        # Nếu sau 2s chưa thấy, kiểm tra xem có kẹt ở màn hình phụ không (Quay lại / Tiếp)
        if attempt in (4, 8):
            try:
                back_selectors = [
                    "div[role='dialog'] div[aria-label*='Quay lại' i]",
                    "div[role='dialog'] div[aria-label*='Back' i]",
                    "div[role='dialog'] div[role='button']:has-text('Quay lại')",
                ]
                for b_sel in back_selectors:
                    b_btn = page.locator(b_sel).first
                    if b_btn.is_visible(timeout=300):
                        print("👈 Phát hiện màn hình phụ trong dialog, bấm Quay lại...")
                        b_btn.click(force=True)
                        time.sleep(1.0)
                        break

                next_selectors = [
                    "div[role='dialog'] div[aria-label*='Tiếp' i]",
                    "div[role='dialog'] div[aria-label*='Next' i]",
                    "div[role='dialog'] div[role='button']:has-text('Tiếp')",
                ]
                for n_sel in next_selectors:
                    n_btn = page.locator(n_sel).first
                    if n_btn.is_visible(timeout=300) and n_btn.is_enabled():
                        print("👉 Phát hiện bước xác nhận 'Tiếp' (Next), bấm chuyển sang xuất bản...")
                        n_btn.click(force=True)
                        time.sleep(1.0)
                        break
            except Exception:
                pass

        time.sleep(0.5)

    # Nếu chưa click qua JS:
    if not clicked_via_js:
        if not target_btn:
            # Fallback cuối cùng: Thử gửi phím tắt Ctrl+Enter trên ô soạn bài
            try:
                tb = page.locator("div[role='dialog'] div[role='textbox']").first
                if tb.is_visible(timeout=500):
                    tb.focus()
                    page.keyboard.press("Control+Enter")
                    print("⌨️ Đã bấm tổ hợp phím Ctrl+Enter để xuất bản bài viết!")
                    clicked_via_js = True
            except Exception:
                pass

        if not clicked_via_js and not target_btn:
            raise Exception("Không tìm thấy nút 'Đăng' hợp lệ trên giao diện Facebook. Hãy đảm bảo tài khoản đã tham gia nhóm.")

        if target_btn:
            try:
                btn_name = target_btn.inner_text().strip() or target_btn.get_attribute('aria-label')
            except Exception:
                btn_name = "Đăng"
            print(f"🎯 Đã xác định chính xác nút Đăng: '{btn_name}'")

            # Đảm bảo nút được cuộn vào viewport
            try:
                target_btn.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass

            # Chờ ảnh/video upload xong nếu nút đang bị aria-disabled='true'
            for _ in range(25):
                try:
                    if target_btn.get_attribute("aria-disabled") == "true":
                        print("⏳ Nút Đăng đang chờ xử lý phương tiện/ảnh (aria-disabled=true), chờ 1s...")
                        time.sleep(1.0)
                    else:
                        break
                except Exception:
                    break

            # Click nút Đăng (kết hợp cả Playwright Click lẫn Native DOM Click)
            clicked = False
            try:
                target_btn.click(force=True, timeout=5000)
                print("✅ Đã click nút Đăng bài viết qua Playwright!")
                clicked = True
            except Exception as e:
                print(f"⚠️ Playwright click: {e}, chuyển sang Native DOM click...")
                try:
                    target_btn.evaluate("(el) => el.click()")
                    print("✅ Đã kích hoạt Native DOM click cho nút Đăng!")
                    clicked = True
                except Exception as e2:
                    print(f"❌ Lỗi click nút Đăng: {e2}")

            if not clicked:
                print("❌ Không thể click nút Đăng bài viết (cả Playwright lẫn Native DOM đều thất bại).")
                return False

    # Chờ Facebook xử lý và đóng khung bài viết
    print("⏳ Đang chờ Facebook xử lý và đóng khung bài viết...")
    dialog_closed = False
    for i in range(15):
        time.sleep(1.0)
        try:
            # Kiểm tra xem còn composer dialog nào hiển thị không
            open_composer = None
            dialogs = page.locator("div[role='dialog']").all()
            for d in dialogs:
                if is_composer_dialog(d):
                    open_composer = d
                    break

            if not open_composer or not open_composer.is_visible():
                dialog_closed = True
                print("🎉 Khung soạn thảo đã đóng — Bài đăng đã được Facebook tiếp nhận thành công!")
                break
            else:
                dlg_text = (open_composer.inner_text() or "").lower()
                # Phát hiện lỗi chặn bài hoặc vi phạm tiêu chuẩn
                if any(err_kw in dlg_text for err_kw in ["không thể đăng", "bị hạn chế", "bị chặn", "something went wrong", "tạm thời bị chặn", "vi phạm tiêu chuẩn"]):
                    print(f"❌ Facebook thông báo lỗi bài viết: {dlg_text[:150]}")
                    return False

                # Kiểm tra xem có thông báo chờ admin duyệt xuất hiện không
                if re.search(r"(bài viết.*chờ.*duyệt|post.*pending.*approval|submitted.*approval|đang chờ.*phê duyệt)", dlg_text, re.I):
                    print("📋 Phát hiện thông báo: Bài viết đã được gửi và đang chờ Quản trị viên duyệt!")
                    dialog_closed = True
                    break

                # v6: Sau khi submit đã được kích hoạt, chỉ quan sát trạng thái terminal.
                # Không tự gửi lại Ctrl+Enter/click vì Facebook có thể vẫn đang xử lý request đầu tiên.
                if i in (3, 6):
                    print("⏳ Facebook vẫn đang xử lý bài đăng; tiếp tục chờ xác nhận, không gửi lại thao tác.")
        except Exception as exc:
            print(f"⚠️ Đang chờ xử lý đóng khung soạn thảo: {exc}")
            continue

    if not dialog_closed:
        print("❌ Không xác minh được Facebook đã tiếp nhận bài viết (Khung soạn bài vẫn chưa đóng sau 15 giây).")
        return False

    return True


def add_feeling(page):
    """
    Chọn cảm xúc ngẫu nhiên trong khung soạn thảo Facebook:
    - Tìm icon Cảm xúc qua aria-label (hỗ trợ cả khi bị ẩn trong nút 'Xem thêm').
    - Chọn cảm xúc từ danh sách hoặc gõ tìm kiếm.
    - Luôn đảm bảo thoát màn hình phụ và trở về khung soạn bài chính.
    """
    print("😊 Đang thêm cảm xúc ngẫu nhiên cho bài viết...")
    try:
        # 1. Tìm nút Cảm xúc/hoạt động trong dialog
        feeling_selectors = [
            "div[role='dialog'] div[aria-label*='Cảm xúc/hoạt động' i]",
            "div[role='dialog'] div[aria-label*='Feeling/activity' i]",
            "div[role='dialog'] div[aria-label*='Cảm xúc' i]",
            "div[role='dialog'] div[aria-label*='Feeling' i]",
            "div[role='dialog'] [role='button'][aria-label*='Cảm xúc' i]",
            "div[role='dialog'] div[role='button']:has-text('Cảm xúc')",
            "div[role='dialog'] div[role='button']:has-text('Feeling')"
        ]
        feeling_btn = None
        for sel in feeling_selectors:
            cand = page.locator(sel).first
            if cand.is_visible(timeout=1000):
                feeling_btn = cand
                break

        # Nếu không thấy trực tiếp, thử mở menu "Xem thêm" (...) ở thanh công cụ dưới cùng
        if not feeling_btn:
            more_selectors = [
                "div[role='dialog'] div[aria-label*='Xem thêm' i]",
                "div[role='dialog'] div[aria-label*='More' i]",
                "div[role='dialog'] div[role='button'][aria-label*='Thêm vào' i]"
            ]
            for m_sel in more_selectors:
                m_btn = page.locator(m_sel).first
                if m_btn.is_visible(timeout=1000):
                    m_btn.click(force=True)
                    time.sleep(1.0)
                    for sel in feeling_selectors:
                        cand = page.locator(sel).first
                        if cand.is_visible(timeout=1000):
                            feeling_btn = cand
                            break
                    break

        if feeling_btn and feeling_btn.is_visible():
            feeling_btn.click(force=True, timeout=5000)
            time.sleep(random.uniform(1.5, 2.5))
            
            feelings_list = ["Vui vẻ", "Hạnh phúc", "Tuyệt vời", "Hào hứng", "Biết ơn", "Năng động", "Hài lòng"]
            selected_feeling = random.choice(feelings_list)
            
            search_input = page.locator("div[role='dialog'] input[placeholder*='Search' i], div[role='dialog'] input[placeholder*='Tìm kiếm' i], div[role='dialog'] input[type='search'], div[role='dialog'] input[type='text']").first
            if search_input.is_visible(timeout=2500):
                search_input.fill(selected_feeling)
                time.sleep(random.uniform(1.5, 2.5))
                
                # Tìm option tương ứng với cảm xúc đã chọn
                first_option = page.locator("div[role='dialog'] div[role='button']").filter(
                    has_text=re.compile(selected_feeling, re.IGNORECASE)
                ).first
                if not first_option.is_visible(timeout=1500):
                    # Fallback tìm bất kỳ cảm xúc thông dụng nào xuất hiện
                    first_option = page.locator("div[role='dialog'] div[role='button']").filter(
                        has_text=re.compile(r"Vui vẻ|Hạnh phúc|Tuyệt vời|Hào hứng|Biết ơn|Happy|Loved|Excited", re.IGNORECASE)
                    ).first

                if first_option.is_visible(timeout=2000):
                    first_option.click(force=True, timeout=5000)
                    print(f"✅ Đã gắn cảm xúc: {selected_feeling}")
                    time.sleep(1.5)

        # Đảm bảo nếu màn hình phụ vẫn còn (chưa tự thoát), bấm nút Quay lại về khung soạn thảo chính
        back_btn = page.locator("div[role='dialog'] div[aria-label*='Quay lại' i], div[role='dialog'] div[aria-label*='Back' i]").first
        if back_btn.is_visible(timeout=1000):
            back_btn.click(force=True)
            time.sleep(1.0)
    except Exception as e:
        print(f"⚠️ Cảnh báo: Bỏ qua thêm cảm xúc ({e}).")
        try:
            back_btn = page.locator("div[role='dialog'] div[aria-label*='Quay lại' i], div[role='dialog'] div[aria-label*='Back' i]").first
            if back_btn.is_visible(timeout=1000):
                back_btn.click(force=True)
        except Exception:
            pass

def add_checkin(page):
    """
    Chọn vị trí check-in ngẫu nhiên tại Huế trong khung soạn thảo Facebook:
    - Tìm icon Check-in qua aria-label (hỗ trợ cả khi bị ẩn trong nút 'Xem thêm').
    - Nhập tìm kiếm địa danh Huế và chọn kết quả gợi ý.
    - Luôn đảm bảo thoát màn hình phụ và trở về khung soạn bài chính.
    """
    print("📍 Đang check-in địa điểm ngẫu nhiên cho bài viết...")
    try:
        # 1. Tìm nút Check-in trong dialog
        checkin_selectors = [
            "div[role='dialog'] div[aria-label*='Check in' i]",
            "div[role='dialog'] div[aria-label*='Check-in' i]",
            "div[role='dialog'] div[aria-label*='Vị trí' i]",
            "div[role='dialog'] div[aria-label*='Location' i]",
            "div[role='dialog'] [role='button'][aria-label*='Check in' i]",
            "div[role='dialog'] div[role='button']:has-text('Check in')",
            "div[role='dialog'] div[role='button']:has-text('Check-in')",
            "div[role='dialog'] div[role='button']:has-text('Vị trí')"
        ]
        checkin_btn = None
        for sel in checkin_selectors:
            cand = page.locator(sel).first
            if cand.is_visible(timeout=1000):
                checkin_btn = cand
                break

        # Nếu không thấy trực tiếp, thử mở menu "Xem thêm" (...)
        if not checkin_btn:
            more_selectors = [
                "div[role='dialog'] div[aria-label*='Xem thêm' i]",
                "div[role='dialog'] div[aria-label*='More' i]",
                "div[role='dialog'] div[role='button'][aria-label*='Thêm vào' i]"
            ]
            for m_sel in more_selectors:
                m_btn = page.locator(m_sel).first
                if m_btn.is_visible(timeout=1000):
                    m_btn.click(force=True)
                    time.sleep(1.0)
                    for sel in checkin_selectors:
                        cand = page.locator(sel).first
                        if cand.is_visible(timeout=1000):
                            checkin_btn = cand
                            break
                    break

        if checkin_btn and checkin_btn.is_visible():
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
            
            search_input = page.locator("div[role='dialog'] input[placeholder*='Where' i], div[role='dialog'] input[placeholder*='ở đâu' i], div[role='dialog'] input[placeholder*='Tìm kiếm' i], div[role='dialog'] input[type='text'], div[role='dialog'] input[type='search']").first
            if search_input.is_visible(timeout=2500):
                search_input.fill(selected_location)
                time.sleep(random.uniform(2.5, 4.0))
                
                # Tìm kết quả địa điểm xuất hiện trong danh sách
                first_option = page.locator("div[role='dialog'] div[role='button']").filter(
                    has_text=re.compile(re.escape(selected_location) + r"|Huế|Hue", re.IGNORECASE)
                ).first
                
                # Fallback: lấy kết quả đầu tiên bên dưới ô tìm kiếm (bỏ qua nút quay lại)
                if not first_option.is_visible(timeout=1500):
                    candidates = page.locator("div[role='dialog'] div[role='button']")
                    for i in range(candidates.count()):
                        c = candidates.nth(i)
                        c_text = (c.inner_text() or "").strip()
                        if "Quay lại" not in c_text and "Back" not in c_text and len(c_text) > 3:
                            first_option = c
                            break

                if first_option and first_option.is_visible(timeout=2000):
                    first_option.click(force=True, timeout=5000)
                    print(f"✅ Đã check-in địa điểm: {selected_location}")
                    time.sleep(1.5)

        # Đảm bảo nếu màn hình phụ vẫn còn, bấm nút Quay lại về khung soạn thảo chính
        back_btn = page.locator("div[role='dialog'] div[aria-label*='Quay lại' i], div[role='dialog'] div[aria-label*='Back' i]").first
        if back_btn.is_visible(timeout=1000):
            back_btn.click(force=True)
            time.sleep(1.0)
    except Exception as e:
        print(f"⚠️ Cảnh báo: Bỏ qua check-in ({e}).")
        try:
            back_btn = page.locator("div[role='dialog'] div[aria-label*='Quay lại' i], div[role='dialog'] div[aria-label*='Back' i]").first
            if back_btn.is_visible(timeout=1000):
                back_btn.click(force=True)
        except Exception:
            pass

POSTED_LINKS_FILE = "posted_links.json"

def _resolve_posted_links_file():
    global POSTED_LINKS_FILE
    if POSTED_LINKS_FILE and POSTED_LINKS_FILE != "posted_links.json" and os.path.isabs(POSTED_LINKS_FILE):
        return POSTED_LINKS_FILE
    try:
        import paths
        p = str(paths.DATA_DIR / "posted_links.json")
        if os.path.exists(p) or not os.path.exists(POSTED_LINKS_FILE):
            POSTED_LINKS_FILE = p
            return p
    except Exception:
        pass
    return POSTED_LINKS_FILE or "posted_links.json"

def record_posted_link(target, post_url, content="", note="", account_id="", status="", url_type=None, publish_state=None):
    """
    Lưu link bài viết đã đăng thành công vào SQLite và posted_links.json để phục vụ quản lý và comment seeding.
    """
    if not post_url or not post_url.startswith("http"):
        return

    is_post = any(kw in post_url for kw in ["/posts/", "/permalink/", "permalink.php", "/videos/"])
    derived_url_type = url_type or ("post" if is_post else ("group" if "/groups/" in post_url else "page"))
    derived_state = publish_state or ("published" if is_post else "pending")
    final_status = status or note or ("Đã xuất bản" if is_post else "Chờ duyệt")

    # 1. Ghi nhận vào SQLite qua ActivityRepository
    try:
        from repositories.activity_repo import ActivityRepository
        ActivityRepository().record_posted_link(
            target=target,
            post_url=post_url,
            content=content,
            note=final_status,
            account_id=account_id or "default",
            status=final_status,
            url_type=derived_url_type,
            publish_state=derived_state,
        )
    except Exception:
        pass

    # 2. Ghi nhận vào JSON file (đồng bộ kép)
    try:
        target_file = _resolve_posted_links_file()
        items = []
        if os.path.exists(target_file):
            try:
                with open(target_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    if not isinstance(items, list):
                        items = []
            except Exception:
                items = []
        
        now_ts = time.time()
        # Tránh ghi đúp cùng 1 bài trong vòng 60 giây
        is_recent_dup = False
        for item in items:
            item_ts = float(item.get("timestamp", 0))
            if item.get("target") == target and item.get("url") == post_url and (now_ts - item_ts) < 60.0:
                is_recent_dup = True
                break

        if not is_recent_dup:
            item = {
                "id": str(int(now_ts * 1000)),
                "timestamp": now_ts,
                "target": target,
                "url": post_url,
                "url_type": derived_url_type,
                "publish_state": derived_state,
                "account_id": account_id or "default",
                "status": final_status,
                "content_preview": (content[:120] + "...") if len(content) > 120 else content,
                "posted_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            items.insert(0, item)
            # Giữ tối đa 200 link gần nhất
            items = items[:200]
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            print(f"💾 Đã lưu bài viết vào Lịch sử đăng: {post_url} [{item['status']}] (Loại: {derived_url_type})")
    except Exception as e:
        print(f"⚠️ Lỗi khi lưu link bài đăng: {e}")

def normalize_target_url(url: str) -> str:
    """
    Chuẩn hóa URL nhóm/trang để so sánh trùng lặp chính xác (bỏ query parameters, trailing slashes, scheme đồng nhất, www/m subdomain đồng nhất).
    """
    if not url:
        return ""
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u.lstrip("/")
    try:
        parsed = urllib.parse.urlparse(u)
        netloc = (parsed.netloc or "").lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        elif netloc.startswith("m."):
            netloc = netloc[2:]
        path = (parsed.path or "").rstrip("/")
        return f"https://{netloc}{path}"
    except Exception:
        return u.lower().split("?")[0].rstrip("/")

def is_recently_posted(target_url: str, hours: float = 24.0):
    """
    Kiểm tra xem target_url (Group hoặc Page) đã từng đăng bài thành công trong vòng `hours` giờ qua chưa.
    Chỉ chặn nếu bài trước đó ở trạng thái 'published' hoặc 'pending'.
    KHÔNG chặn retry nếu lần trước thất bại hoặc unverified.
    Trả về (True, hours_ago, posted_at_str) nếu trùng lặp gần đây, ngược lại trả về (False, 0, None).
    """
    if not target_url:
        return False, 0, None

    norm_target = normalize_target_url(target_url)
    cutoff_ts = time.time() - (hours * 3600.0)

    # 1. Thử kiểm tra từ ActivityRepository SQLite
    try:
        from repositories.activity_repo import ActivityRepository
        db_links = ActivityRepository().list_posted_links(limit=300)
        for row in db_links:
            pub_state = (row.get("publish_state") or "").lower()
            # Nếu có publish_state, chỉ chặn published hoặc pending
            if pub_state and pub_state not in ("published", "pending"):
                continue
            item_target = normalize_target_url(row.get("target") or "")
            # So sánh chính xác tuyệt đối (exact match)
            if item_target and item_target == norm_target:
                posted_at_str = row.get("created_at") or ""
                try:
                    dt = datetime.strptime(posted_at_str, "%Y-%m-%d %H:%M:%S")
                    item_ts = dt.timestamp()
                    if item_ts >= cutoff_ts:
                        hours_ago = round((time.time() - item_ts) / 3600.0, 1)
                        return True, hours_ago, posted_at_str
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Kiểm tra từ JSON file (fallback)
    target_file = _resolve_posted_links_file()
    if not os.path.exists(target_file):
        return False, 0, None

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            items = json.load(f)
            if not isinstance(items, list):
                return False, 0, None
                
        now = time.time()
        max_age_seconds = hours * 3600.0

        for item in items:
            pub_state = (item.get("publish_state") or "").lower()
            if pub_state and pub_state not in ("published", "pending"):
                continue
            recorded_target = normalize_target_url(item.get("target", ""))
            # So sánh chính xác tuyệt đối (exact match)
            if recorded_target and recorded_target == norm_target:
                ts = item.get("timestamp")
                if ts:
                    diff = now - float(ts)
                    if diff < max_age_seconds:
                        hours_ago = round(diff / 3600.0, 1)
                        return True, hours_ago, item.get("posted_at", "gần đây")
                else:
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

def clean_facebook_post_url(href: str) -> str:
    """
    Chuẩn hóa và làm sạch liên kết bài viết Facebook.
    - Giữ nguyên query params thiết yếu cho permalink.php / story.php (story_fbid, id, fbid, post_id).
    - Loại bỏ tracking params (__cft__, __tn__, ref, notif_id, etc.).
    - Đảm bảo đầy đủ scheme và domain https://www.facebook.com.
    """
    if not href:
        return ""
    href = href.strip()
    if not href.startswith("http"):
        href = f"https://www.facebook.com{href if href.startswith('/') else '/' + href}"

    parsed = urllib.parse.urlparse(href)
    # Nếu là permalink.php hoặc link dạng query params
    if "permalink.php" in parsed.path or "story.php" in parsed.path:
        qs = urllib.parse.parse_qs(parsed.query)
        keep_keys = {"story_fbid", "id", "fbid", "post_id"}
        filtered_qs = {k: v for k, v in qs.items() if k in keep_keys}
        new_query = urllib.parse.urlencode(filtered_qs, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", new_query, ""))

    # Đối với các URL dạng /posts/123, /permalink/123, /videos/123, /groups/xyz/permalink/123
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

def text_similarity_match(needle: str, haystack: str) -> bool:
    """
    Kiểm tra xem một đoạn văn bản needle có xuất hiện trong haystack hay không
    sử dụng cơ chế multi-checkpoint (prefix, middle, suffix) để tránh false-positives
    từ các câu mở đầu phổ biến.
    """
    def norm(s):
        return re.sub(r"[\s\u200b\u200c\u200d]+", " ", s or "").strip().lower()

    a = norm(needle)
    b = norm(haystack)

    if not a or not b:
        return False

    if len(a) <= 40:
        return a in b

    checkpoints = [
        a[:60],
        a[len(a)//2:len(a)//2 + 60],
        a[-60:],
    ]

    matches = sum(1 for part in checkpoints if len(part) >= 15 and part in b)
    return matches >= 2

TOAST_CONFIRM_RE = re.compile(r"(đã đăng|đã chia sẻ|bài viết của bạn đã|bài viết đã được chia sẻ|posted|published|shared|your post has been)", re.I)

def scrape_post_link(page, target="", content="", account_id="") -> ActionResult:
    """
    Trích xuất permalink của bài viết vừa đăng:
    - Ưu tiên 1: Chỉ quét link từ Toast/Alert/Notification container xác nhận xuất bản.
    - Ưu tiên 2: Quét feed article nhưng chỉ chọn article khớp nội dung bài viết vừa đăng (multi-checkpoint).
    - Fallback: Nếu không tìm thấy link trực tiếp, kiểm tra modal duyệt pending (scoped vào dialog/alert container).
      Nếu unverified -> success=False. Chỉ POST_PENDING với dialog xác nhận mới success=True.
    """
    print("Đang quét tìm liên kết của bài đăng vừa tạo...")
    clean_href = None
    try:
        time.sleep(2.0)
        
        # Cách 1: Tìm thông báo Toast/Alert nổi lên của Facebook xác nhận xuất bản
        try:
            toast_containers = page.locator("div[role='alert'], div[role='status']").all()
            for container in toast_containers:
                try:
                    c_text = container.inner_text(timeout=500) or ""
                    if TOAST_CONFIRM_RE.search(c_text):
                        toast_links = container.locator("a[href*='/posts/'], a[href*='/permalink/'], a[href*='permalink.php']").all()
                        for link in toast_links:
                            href = link.get_attribute("href")
                            if href:
                                clean = clean_facebook_post_url(href)
                                if clean:
                                    clean_href = clean
                                    break
                        if clean_href:
                            break
                except Exception:
                    continue
        except Exception:
            pass

        # Cách 2: Quét các article trên feed nhưng BẮT BUỘC phải khớp nội dung vừa đăng (multi-checkpoint)
        if not clean_href:
            try:
                articles = page.locator("div[role='article']").all()[:5]
                for art in articles:
                    try:
                        if not art.is_visible(timeout=1000):
                            continue
                        art_text = art.inner_text() or ""
                        # Nếu có content truyền vào, chỉ nhận article khớp nội dung
                        if content and not text_similarity_match(content, art_text):
                            continue
                        article_links = art.locator("a[href*='/posts/'], a[href*='/permalink/'], a[href*='permalink.php'], a[href*='/videos/']").all()
                        for link in article_links:
                            href = link.get_attribute("href")
                            if href and not any(x in href for x in ["/groups/user/", "/comment/", "reaction"]):
                                clean = clean_facebook_post_url(href)
                                if clean:
                                    clean_href = clean
                                    break
                        if clean_href:
                            break
                    except Exception:
                        continue
            except Exception:
                pass

        if clean_href:
            print(f"POSTED_LINK:{clean_href}")
            record_posted_link(target, clean_href, content, note="Đã xuất bản", account_id=account_id, url_type="post", publish_state="published")
            return ActionResult(
                success=True,
                code="POST_PUBLISHED",
                state="published",
                target_url=target,
                result_url=clean_href,
                url_type="post",
                message="Đã đăng bài và trích xuất thành công liên kết bài viết."
            )
            
        # Fallback: Kiểm tra xem có dialog/alert thông báo chờ admin duyệt hay không (chỉ scope vào dialog/alert)
        fallback_url = target or (page.url if hasattr(page, 'url') else "")
        target_type = "group" if "/groups/" in fallback_url else ("page" if "/pages/" in fallback_url else "unknown")
        is_pending = False
        try:
            pending_notice = page.locator(
                "div[role='alert'], div[role='status'], div[role='dialog']"
            ).filter(
                has_text=re.compile(
                    r"(bài viết.*chờ.*duyệt|post.*pending.*approval|submitted.*approval)",
                    re.I,
                )
            )
            is_pending = pending_notice.count() > 0
        except Exception:
            pass

        if is_pending:
            note_status = "Đang chờ admin duyệt"
            publish_state = "pending"
            record_posted_link(target, fallback_url, content, note=note_status, account_id=account_id, url_type=target_type, publish_state=publish_state)
            print(f"💾 Đã ghi nhận bài đăng vào Lịch sử: {fallback_url} [{note_status}]")
            return ActionResult(
                success=True,
                code="POST_PENDING",
                state=publish_state,
                target_url=target,
                result_url="",
                url_type=target_type,
                message=f"Bài đăng đã được tiếp nhận [{note_status}]"
            )

        # Nếu không có permalink và cũng không có thông báo pending xác nhận -> unverified (success=False)
        note_status = "Đã gửi đăng (Chưa trích xuất được link bài)"
        publish_state = "submitted_unverified"
        record_posted_link(target, fallback_url, content, note=note_status, account_id=account_id, url_type=target_type, publish_state=publish_state)
        print(f"⚠️ Bài đăng chưa được xác thực permalink: {fallback_url} [{note_status}]")
        return ActionResult(
            success=False,
            code="POST_SUBMITTED_UNVERIFIED",
            state=publish_state,
            target_url=target,
            result_url="",
            url_type=target_type,
            message="Bài đăng đã gửi nhưng chưa trích xuất được permalink xác thực."
        )
    except Exception as e:
        print(f"⚠️ Cảnh báo: Lỗi khi quét liên kết bài đăng: {e}")
        fallback_url = target or (page.url if hasattr(page, 'url') else "")
        target_type = "group" if "/groups/" in fallback_url else "page"
        record_posted_link(target, fallback_url, content, note="Đã gửi đăng (lỗi quét)", account_id=account_id, url_type=target_type, publish_state="submitted_unverified")
        return ActionResult(
            success=False,
            code="POST_SUBMITTED_UNVERIFIED",
            state="submitted_unverified",
            target_url=target,
            result_url="",
            url_type=target_type,
            message=f"Đã gửi đăng (gặp lỗi khi quét link: {e})"
        )
