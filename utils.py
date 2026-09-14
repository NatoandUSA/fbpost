import re
import random
import time
import os
import sys
import json
import tempfile
import urllib.parse
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime
from paths import DATA_DIR
from services.profile_session_manager import (
    acquire_profile, attach_runtime, release_profile, runtime_snapshot,
    wait_endpoint_closed, ProfileLeaseError,
)

# GPM profiles with proxies/extensions can take longer than 15s to start.
GPM_START_TIMEOUT_SECONDS = 30
ENABLE_ADVANCED_HUMAN_ENGINE = os.getenv("ENABLE_ADVANCED_HUMAN_ENGINE", "false").lower() in ("true", "1", "yes")

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
ACCOUNTS_FILE = str(DATA_DIR / "accounts.json")
STATE_FILE = str(DATA_DIR / "state.json")

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
    """Enter exact text with conservative pacing; never simulate typos or character loss."""
    print("Typing content with conservative pacing...")
    _ensure_focus(locator)
    value = str(text or "")
    if ENABLE_ADVANCED_HUMAN_ENGINE:
        account_id = getattr(page, "_fb_automation_account_id", None)
        try:
            from modules.human_engine.adapter import human_type_advanced
            if human_type_advanced(page, locator, value, multiline_key=multiline_key, account_id=account_id, allow_typos=False):
                print(f"[Human Engine] op=type status=used account={account_id or 'default'}")
                return
            print(f"[Human Engine] op=type status=fallback account={account_id or 'default'} reason=advanced_returned_false")
        except Exception as exc:
            print(f"[Human Engine] op=type status=fallback account={account_id or 'default'} reason={type(exc).__name__}")
    try:
        locator.fill(value)
        time.sleep(0.45)
        return
    except Exception:
        pass
    keyboard = getattr(page, "keyboard", None)
    if not keyboard:
        return
    lines = value.split("\n")
    for idx, line in enumerate(lines):
        if line:
            for pos in range(0, len(line), 80):
                keyboard.insert_text(line[pos:pos + 80])
                time.sleep(0.06)
        if idx < len(lines) - 1:
            keyboard.press("Shift+Enter" if multiline_key == "Shift+Enter" else "Enter")
            time.sleep(0.12)


def human_type_with_page_mention(page, locator, text, brand_key=None):
    """Type one verified Facebook Page entity; fall back to unchanged plain text."""
    profiles = {
        "lacasa": ("Lacasa Homestay", "lacasahomestayinvietnam"),
        "umee": ("Umee Homestay", "umeehomestay"),
    }
    name, handle = profiles.get(str(brand_key or "").casefold(), ("", ""))
    value = str(text or "")
    match = re.search(re.escape(name), value, re.IGNORECASE) if name else None
    if not match:
        human_type(page, locator, value)
        return False
    try:
        locator.fill("")
        _ensure_focus(locator)
        prefix, suffix = value[:match.start()], value[match.end():]
        page.keyboard.insert_text(prefix)
        page.keyboard.insert_text("@")
        page.keyboard.type(name, delay=65)
        time.sleep(2.0)
        candidates = page.locator("[role='listbox'] [role='option'], [role='menu'] [role='menuitem'], div[role='dialog'] a")
        chosen = None
        for idx in range(min(candidates.count(), 30)):
            candidate = candidates.nth(idx)
            label = (candidate.inner_text(timeout=500) or "").strip().casefold()
            href = (candidate.get_attribute("href") or "").casefold()
            if name.casefold() in label and (handle in href or "homestay" in label):
                chosen = candidate
                break
        if chosen is None:
            raise RuntimeError("page autocomplete did not return the configured Page")
        chosen.click(force=True, timeout=3000)
        page.keyboard.insert_text(suffix)
        time.sleep(0.8)
        entity = locator.locator(f"a[href*='{handle}' i]")
        if entity.count() and entity.first.is_visible(timeout=1000):
            print(f"✅ [Page Mention] Đã xác minh entity Page: {name} (@{handle}).")
            return True
        raise RuntimeError("selected candidate was not retained as a Page entity")
    except Exception as exc:
        print(f"⚠️ [Page Mention] Không xác minh được entity {name}; dùng tên chữ thường ({type(exc).__name__}).")
        try:
            locator.fill("")
        except Exception:
            pass
        human_type(page, locator, value)
        return False


def verify_entered_content(locator, expected):
    try:
        actual = (locator.inner_text() or locator.text_content() or "").strip()
        if not actual and hasattr(locator, "input_value"):
            try:
                actual = (locator.input_value() or "").strip()
            except Exception:
                pass
    except Exception:
        return False
    expected=str(expected or "").strip()
    required=[t for t in ("#UMEEHomestay", "#LacasaHomestay") if t.casefold() in expected.casefold()]
    signature_part = ""
    for separator in ("━━━━━━━━━━━━━━━━━━━━", "-------------------"):
        if separator in expected:
            required.append(separator)
            # Canonical signatures are wrapped by the separator; validate every
            # non-empty line between the first and final separator.
            parts = expected.split(separator)
            if len(parts) >= 3:
                signature_part = separator.join(parts[1:-1])
            else:
                signature_part = parts[-1]
            break
    if signature_part:
        required.extend([line.strip() for line in signature_part.splitlines() if line.strip()])
    if not required:
        return True
    return all(t.casefold() in actual.casefold() for t in required) and len(actual) >= min(20,len(expected))


def navigate_facebook_surface(page, target_url, *, prewarm=True, rounds=3, timeout=45000, label="Facebook"):
    """Read-only navigation with cold-session hydration recovery.

    Returns True only when Facebook exposes a meaningful body or interactive controls.
    No write action is performed here.
    """
    if prewarm:
        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=min(timeout, 35000))
            page.wait_for_timeout(2500)
        except Exception as warm_err:
            print(f"[{label} Surface] prewarm warning: {warm_err}")
    last_err = None
    for attempt in range(1, max(1, int(rounds)) + 1):
        try:
            if attempt == 1:
                page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)
            else:
                page.reload(wait_until="domcontentloaded", timeout=min(timeout, 35000))
        except Exception as nav_err:
            last_err = nav_err
        try:
            page.wait_for_timeout(1800 if attempt == 1 else 2500)
        except Exception:
            pass
        try:
            body_text = (page.locator("body").inner_text(timeout=3000) or "").strip()
        except Exception:
            body_text = ""
        try:
            controls = page.locator("a, div[role='button'], button").count()
        except Exception:
            controls = 0
        current = (getattr(page, "url", "") or "").lower()
        if "facebook.com" in current and (len(body_text) >= 20 or controls >= 8):
            print(f"[{label} Surface] hydrated round={attempt} chars={len(body_text)} controls={controls}")
            return True
        print(f"[{label} Surface] not hydrated round={attempt} chars={len(body_text)} controls={controls}")
    if last_err:
        print(f"[{label} Surface] navigation failed after recovery: {last_err}")
    return False


def safe_mouse_wheel(page, dx, dy):
    """
    Safely scroll using mouse wheel without crashing on TargetClosedError or disconnected CDP.
    """
    if not page:
        return False
    if ENABLE_ADVANCED_HUMAN_ENGINE:
        account_id = getattr(page, "_fb_automation_account_id", None)
        try:
            from modules.human_engine.adapter import kinetic_mouse_wheel
            if kinetic_mouse_wheel(page, dx, dy, account_id=account_id):
                print(f"[Human Engine] op=scroll status=used account={account_id or 'default'}")
                return True
            print(f"[Human Engine] op=scroll status=fallback account={account_id or 'default'} reason=advanced_returned_false")
        except Exception as exc:
            print(f"[Human Engine] op=scroll status=fallback account={account_id or 'default'} reason={type(exc).__name__}")
    try:
        if hasattr(page, "is_closed") and page.is_closed():
            return False
        page.mouse.wheel(dx, dy)
        return True
    except Exception:
        return False



def find_post_composer_textbox(page, dialog=None, wait_seconds=8.0):
    """Return the editor inside a visible Create Post surface, never global chat/search/comment boxes."""
    rejects = ("bình luận", "comment", "tìm kiếm", "search", "tin nhắn", "message", "chat")
    accepts = ("bạn đang nghĩ gì", "bạn viết gì", "write something", "what's on your mind", "tạo bài", "create post")
    deadline = time.monotonic() + max(0.5, float(wait_seconds))
    while time.monotonic() < deadline:
        scopes = []
        if dialog is not None:
            try:
                if dialog.is_visible(timeout=250): scopes.append((dialog, True))
            except Exception:
                pass
        # Facebook can expose a nested title-only role=dialog as `.last`; search every
        # visible dialog and keep only surfaces whose text/aria identifies Create Post.
        try:
            dialogs = page.locator("div[role='dialog']")
            for di in range(min(dialogs.count(), 12)):
                d = dialogs.nth(di)
                try:
                    if not d.is_visible(timeout=200):
                        continue
                    title = ((d.get_attribute("aria-label") or "") + " " + (d.inner_text() or "")[:180]).lower()
                    if any(x in title for x in ("tạo bài viết", "create post")):
                        scopes.append((d, True))
                except Exception:
                    continue
        except Exception:
            pass
        # Main is only a fallback for inline Page composers; unlike dialogs, it requires
        # an explicit composer label and never accepts an unlabeled textbox.
        try:
            scopes.append((page.locator("div[role='main']"), False))
        except Exception:
            pass

        seen = set()
        for scope, is_dialog in scopes:
            try:
                key = str(scope)
                if key in seen:
                    continue
                seen.add(key)
                candidates = scope.locator("div[role='textbox'][contenteditable='true'], div[contenteditable='true'][data-lexical-editor='true']")
                dialog_fallback = None
                for idx in range(min(candidates.count(), 16)):
                    c = candidates.nth(idx)
                    if not c.is_visible(timeout=250):
                        continue
                    label = ((c.get_attribute("aria-label") or "") + " " + (c.get_attribute("aria-placeholder") or "")).strip().lower()
                    if any(x in label for x in rejects):
                        continue
                    if any(x in label for x in accepts):
                        return c
                    if is_dialog and dialog_fallback is None:
                        dialog_fallback = c
                if dialog_fallback is not None:
                    return dialog_fallback
            except Exception:
                continue
        time.sleep(0.35)
    return None

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
        fd, temporary_path = tempfile.mkstemp(prefix="accounts-", suffix=".json", dir=str(DATA_DIR))
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

    # 2. Tra cứu trực tiếp từ GPM API v3 (Zero-Config), phân trang để tên profile
    # ngoài 200 bản ghi đầu vẫn resolve đúng.
    page_no = 1
    gpm_connected = False
    while page_no <= 20:
        gpm_res = fetch_gpm_profiles(gpm_api_url=gpm_api_url, page=page_no, page_size=200)
        if not gpm_res.get("connected"):
            break
        gpm_connected = True
        profiles = gpm_res.get("profiles", []) or []
        for p in profiles:
            if p.get("id") == account_id or p.get("name") == account_id:
                return {
                    "id": p.get("id"), "name": p.get("name", account_id), "type": "gpm",
                    "profile_path_or_id": p.get("id"), "proxy": p.get("raw_proxy", ""),
                    "browser_type": p.get("browser_type", "Chrome"), "status": "GPM Trực tiếp"
                }
        total = int(gpm_res.get("total") or len(profiles))
        if not profiles or page_no * 200 >= total:
            break
        page_no += 1

    # 3. Chỉ UUID hợp lệ mới được dùng như direct GPM id khi list API tạm thời lỗi.
    # Tên/chuỗi gõ sai phải fail closed thành ACCOUNT_NOT_FOUND.
    is_uuid = bool(re.fullmatch(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", str(account_id)))
    if is_uuid and not gpm_connected:
        return {"id": account_id, "name": f"GPM ({account_id[:8]})", "type": "gpm",
                "profile_path_or_id": account_id, "proxy": "", "status": "GPM Trực tiếp"}
    return None


def connect_over_cdp_when_ready(playwright, cdp_url, timeout_seconds=30):
    """Wait for a GPM-launched browser to expose its local CDP endpoint."""
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            # Sử dụng timeout 8s cho mỗi lần thử để không block quá lâu và có thể retry
            return playwright.chromium.connect_over_cdp(cdp_url, timeout=8000)
        except Exception as error:
            last_error = error
            if attempt == 1:
                print("GPM has started the profile; waiting for its debugging port to become ready...")
            else:
                print(f"⏳ Đang thử kết nối lại CDP lần {attempt}...")
            time.sleep(1.0)
    raise RuntimeError(f"GPM debugging port was not ready after {timeout_seconds} seconds: {last_error}")


def _normalize_single_interactive_page(context, settle_seconds=10.0):
    """Enforce one page after asynchronous GPM session restore settles."""
    deadline = time.time() + max(1.0, float(settle_seconds))
    keep = None
    stable_since = None
    while time.time() < deadline:
        pages = []
        for pg in list(getattr(context, "pages", []) or []):
            try:
                if not pg.is_closed():
                    pages.append(pg)
            except Exception:
                pass
        if keep is None or keep.is_closed():
            keep = pages[0] if pages else context.new_page()
        for pg in pages:
            if pg is keep:
                continue
            try:
                pg.close(run_before_unload=False)
            except Exception:
                try: pg.evaluate("window.close()")
                except Exception: pass
        try:
            live = [pg for pg in list(context.pages) if not pg.is_closed()]
        except Exception:
            live = [keep] if keep else []
        if len(live) == 1 and live[0] is keep:
            stable_since = stable_since or time.time()
        else:
            stable_since = None
        try:
            keep.wait_for_timeout(250)
        except Exception:
            time.sleep(0.25)
    try:
        remaining = len([pg for pg in list(context.pages) if not pg.is_closed()])
    except Exception:
        remaining = -1
    if remaining != 1:
        raise RuntimeError(f"GPM_PAGE_SINGLETON_FAILED: expected 1 live page, found {remaining}")
    return keep


def _gpm_root_processes(profile_id):
    """Return root GPM Chrome processes that own this profile on Windows."""
    if sys.platform != "win32" or not profile_id:
        return []
    escaped = str(profile_id).replace("'", "''")
    script = (
        "$p=Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' "
        f"-and $_.CommandLine -like '*{escaped}*' -and $_.CommandLine -notlike '*--type=*' }} | "
        "Select-Object ProcessId,CommandLine; if($p){$p|ConvertTo-Json -Compress}"
    )
    try:
        raw = subprocess.check_output(
            ["powershell.exe", "-NoProfile", "-Command", script],
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", timeout=8,
        ).strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        return [x for x in data if isinstance(x, dict) and x.get("ProcessId")]
    except Exception:
        return []


def _kill_gpm_root_processes(profile_id):
    killed = []
    for proc in _gpm_root_processes(profile_id):
        pid = int(proc.get("ProcessId") or 0)
        if not pid:
            continue
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
            killed.append(pid)
        except Exception:
            pass
    return killed


def _wait_gpm_roots_closed(profile_id, timeout=12.0):
    deadline = time.time() + max(0.5, float(timeout))
    while time.time() < deadline:
        if not _gpm_root_processes(profile_id):
            return True
        time.sleep(0.5)
    return not _gpm_root_processes(profile_id)


def _ensure_clean_gpm_process_state(profile_id, api_base):
    """Before a new Start, guarantee no previous root browser for the profile survives."""
    roots = _gpm_root_processes(profile_id)
    if not roots:
        return
    print(f"[Profile Process] Phát hiện {len(roots)} GPM root process cũ; đóng sạch trước khi Start.")
    import requests
    for url in (
        f"{api_base}/api/v3/profiles/close/{profile_id}",
        f"{api_base}/api/v3/profiles/stop/{profile_id}",
        f"{api_base}/api/v2/close?profileId={profile_id}",
    ):
        try:
            requests.get(url, timeout=5)
        except Exception:
            pass
    if not _wait_gpm_roots_closed(profile_id, timeout=8.0):
        killed = _kill_gpm_root_processes(profile_id)
        if killed:
            print(f"[Profile Process] Force-closed stale GPM process PID(s): {killed}")
        _wait_gpm_roots_closed(profile_id, timeout=5.0)
    remaining = _gpm_root_processes(profile_id)
    if remaining:
        raise RuntimeError(f"GPM_STALE_PROCESS: profile {profile_id} còn {len(remaining)} root process sau cleanup")


def _ensure_gpm_service_reachable(api_url, timeout=3.0):
    import socket
    parsed = urllib.parse.urlparse(api_url or "http://127.0.0.1:19995")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError as exc:
        raise RuntimeError(f"GPM_API_UNREACHABLE: {host}:{port} ({exc})") from exc


def launch_browser(account, p, api_url=None):
    """
    Launches browser for a given account. Unifies local profile and GPM profile methods.
    Preserves the existing browser/session configuration and exposes account identity for optional interaction pacing.
    """
    acc_type = account.get("type", "local")
    profile_id = account.get("profile_path_or_id", "")
    proxy_str = account.get("proxy", "").strip()
    
    if acc_type == "gpm":
        if not api_url:
            # GPM Login v4 (Legacy) exposes its local API on this address.
            api_url = "http://127.0.0.1:19995"

        import requests
        _ensure_gpm_service_reachable(api_url, timeout=3.0)
        browser = None
        gpm_error = None
        api_base = api_url.rstrip("/").split("/api/")[0]
        profile_id_match = re.search(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", profile_id)
        if profile_id_match:
            profile_id = profile_id_match.group(0)

        try:
            acquire_profile(profile_id, timeout=20.0)
            attach_runtime(profile_id, api_url=api_base)
            print(f"🔒 [Profile Lease] Đã khóa độc quyền profile {account.get('name', profile_id)}.")
            _ensure_clean_gpm_process_state(profile_id, api_base)
        except ProfileLeaseError as lease_err:
            raise Exception(f"PROFILE_BUSY: {lease_err}")
        except Exception:
            release_profile(profile_id)
            raise

        api_is_v1 = api_url.rstrip("/").endswith("/api/v1")
        if api_is_v1:
            try:
                url = f"{api_url.rstrip('/')}/profiles/start/{profile_id}"
                print(f"Calling GPM Local API: {url}")
                payload = requests.get(url, timeout=10).json()
                data = payload.get("data") if isinstance(payload, dict) else None
                ws_endpoint = data.get("websocket_debugging_url") if isinstance(data, dict) else None
                if payload.get("success") and ws_endpoint:
                    attach_runtime(profile_id, cdp_endpoint=ws_endpoint)
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
                                attach_runtime(profile_id, cdp_endpoint=ws_endpoint)
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
                payload = requests.get(url, params={"win_scale": 0.8}, timeout=GPM_START_TIMEOUT_SECONDS).json()
                data = payload.get("data") if isinstance(payload, dict) else None
                cdp_address = data.get("remote_debugging_address") if isinstance(data, dict) else None
                if cdp_address and (payload.get("success") or payload.get("status") or True):
                    cdp_url = cdp_address if cdp_address.startswith("http") else f"http://{cdp_address}"
                    attach_runtime(profile_id, cdp_endpoint=cdp_url)
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
                                attach_runtime(profile_id, cdp_endpoint=cdp_url)
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
                try:
                    requests.get(f"{api_base}/api/v3/profiles/close/{profile_id}", timeout=4)
                    requests.get(f"{api_base}/api/v3/profiles/stop/{profile_id}", timeout=4)
                except Exception:
                    pass

        # Backward-compatible GPM v2 fallback.
        if not browser and not api_is_v1:
            try:
                url = f"{api_base}/api/v2/start?profileId={profile_id}"
                payload = requests.get(url, timeout=10).json()
                data = payload.get("data") if isinstance(payload, dict) else None
                browser_url = data.get("browser_url") if isinstance(data, dict) else None
                if browser_url:
                    cdp_url = browser_url if browser_url.startswith("http") else f"http://{browser_url}"
                    attach_runtime(profile_id, cdp_endpoint=cdp_url)
                    browser = connect_over_cdp_when_ready(p, cdp_url)
            except Exception as e:
                if not gpm_error:
                    gpm_error = f"GPM v2 fallback connection failed: {e}"
                try:
                    requests.get(f"{api_base}/api/v2/close?profileId={profile_id}", timeout=4)
                except Exception:
                    pass
                
        if not browser:
            release_profile(profile_id)
            raise Exception(gpm_error or "Không thể khởi chạy profile GPM. Dùng URL http://127.0.0.1:19995 và API v3 trong GPM Login v4.")

        if sys.platform == "win32":
            roots = []
            for _ in range(6):
                roots = _gpm_root_processes(profile_id)
                if len(roots) == 1:
                    break
                time.sleep(0.5)
            if len(roots) != 1:
                print(f"[Profile Process] INVALID root process count for {account.get('name', profile_id)}: {len(roots)}")
                try:
                    requests.get(f"{api_base}/api/v3/profiles/close/{profile_id}", timeout=5)
                    requests.get(f"{api_base}/api/v3/profiles/stop/{profile_id}", timeout=5)
                except Exception:
                    pass
                _kill_gpm_root_processes(profile_id)
                release_profile(profile_id)
                raise RuntimeError(f"GPM_PROCESS_SINGLETON_FAILED: expected 1 root Chrome, found {len(roots)}")
            print(f"[Profile Process] Singleton verified: {account.get('name', profile_id)} · root_pid={roots[0].get('ProcessId')}")

        context = browser.contexts[0]
        page = _normalize_single_interactive_page(context)
        try:
            print(f"[Profile Session] Single-page invariant active: {account.get('name', profile_id)} · pages={len(context.pages)}")
        except Exception:
            pass
        
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
            def _guard_new_page(p_new):
                try:
                    p_new.on("dialog", _auto_accept_dialog)
                    if p_new is not page and not p_new.is_closed():
                        print("[Profile Session] Closing unexpected restored/new page to preserve singleton.")
                        p_new.close(run_before_unload=False)
                except Exception:
                    pass
            context.on("page", _guard_new_page)
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

        try:
            setattr(page, "_fb_automation_account_id", str(account.get("id") or profile_id or "default"))
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
            print(f"Sử dụng Proxy: {proxy_str.rsplit(chr(64), 1)[-1] if chr(64) in proxy_str else proxy_str}")
            
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

        try:
            setattr(page, "_fb_automation_account_id", str(account.get("id") or profile_id or "default"))
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
        lease_meta = runtime_snapshot(profile_id)
        cdp_endpoint = str(lease_meta.get("cdp_endpoint") or "")
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
                requests.get(f"{api_base}/api/v3/profiles/stop/{profile_id}", timeout=5)
            except Exception:
                pass
        try:
            requests.get(f"{api_base}/api/v2/close?profileId={profile_id}", timeout=5)
        except Exception:
            pass
        # Chờ cả CDP endpoint và root GPM Chrome thực sự chết trước khi release lease.
        time.sleep(1.0)
        cdp_closed = wait_endpoint_closed(cdp_endpoint, timeout=15.0)
        roots_closed = _wait_gpm_roots_closed(profile_id, timeout=8.0)
        if not roots_closed:
            killed = _kill_gpm_root_processes(profile_id)
            if killed:
                print(f"[Profile Process] Force-closed leftover root PID(s) during teardown: {killed}")
            roots_closed = _wait_gpm_roots_closed(profile_id, timeout=5.0)
        if cdp_closed and roots_closed:
            print(f"[Profile Lease] GPM/CDP/process teardown verified: {account.get('name', profile_id)}")
            release_profile(profile_id)
        else:
            remaining = len(_gpm_root_processes(profile_id))
            print(f"[Profile Lease] Teardown incomplete: cdp_closed={cdp_closed}, root_processes={remaining}. Keeping lease to block profile reuse.")

# ---- Advanced Composer Features (Image, Feeling, Checkin, Link Scraping) ----

# =========================================================================
# MEDIA ANTI-HASH PIPELINE (EXIF STRIPPER & PHASH RANDOMIZER)
# =========================================================================

def clean_and_randomize_image(image_path: str, output_dir: str = None) -> str:
    """Compatibility name: create a metadata-sanitized copy without pixel randomization."""
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
        out_ext = ".jpg" if ext == ".webp" else ext
        out_path = os.path.abspath(os.path.join(output_dir, f"clean_{uuid.uuid4().hex[:10]}{out_ext}"))
        with Image.open(image_path) as img:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            if img.mode in ("RGBA", "P") and out_ext in {".jpg", ".jpeg"}:
                img = img.convert("RGB")
            else:
                img = img.copy()
            save_kwargs = {}
            if out_ext in {".jpg", ".jpeg"}:
                save_kwargs["quality"] = 95
            img.save(out_path, format="JPEG" if out_ext in {".jpg", ".jpeg"} else "PNG", **save_kwargs)
        return out_path
    except Exception as e:
        print(f"⚠️ [Media Sanitizer] Không thể xóa metadata ảnh ({e}), dùng ảnh gốc: {image_path}")
        return image_path

def process_images_anti_hash(image_paths: list) -> list:
    """
    Tạo bản sao ảnh đã xóa metadata trước khi đính kèm vào bài đăng.
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
    Nếu clean_exif=True: tạo bản sao đã xóa metadata EXIF, không ngẫu nhiên hóa pixel/kích thước.
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
                print("🧹 [Media Sanitizer] Đã tạo bản sao ảnh không chứa EXIF trước khi đăng.")
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
                print("🧹 [Media Sanitizer] Đã xóa metadata EXIF cho ảnh đính kèm.")
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

    # 5. Chờ xem preview ảnh có xuất hiện trong dialog không (tránh match nhầm avatar cá nhân)
    if attached:
        print("⏳ Đang chờ ảnh tải lên hoàn tất...")
        try:
            page.wait_for_selector(
                "div[role='dialog'] img[src*='blob:'], div[role='dialog'] img[src*='data:'], "
                "div[role='dialog'] div[aria-label*='Xóa ảnh' i], div[role='dialog'] div[aria-label*='Remove' i]",
                timeout=7000
            )
            print("✅ Đã xác nhận hình ảnh hiển thị trong khung bài viết!")
        except Exception:
            time.sleep(3.5)
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
                print("ℹ️ Khung soạn thảo đã đóng — chuyển sang bước xác minh permalink/pending; chưa coi là published.")
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
        print("⚠️ Đã trigger submit nhưng chưa xác minh được terminal state sau 15 giây; chuyển sang submitted_unverified để đối soát, không tự retry.")
        return ActionResult(
            success=False,
            code="SUBMIT_TRIGGERED_UNVERIFIED",
            state="submitted_unverified",
            message="Đã trigger submit nhưng chưa xác minh được Facebook hoàn tất xử lý.",
        )

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

def add_checkin(page, brand_key=None):
    """
    Chọn vị trí check-in tại Huế trong khung soạn thảo Facebook:
    - Ưu tiên check-in ngay tại Homestay (Lacasa Homestay hoặc UMEE Homestay) theo brand_key.
    - Đa dạng xoay tua các danh lam thắng cảnh nổi tiếng tại Huế.
    - Tìm icon Check-in qua aria-label (hỗ trợ cả khi bị ẩn trong nút 'Xem thêm').
    - Luôn đảm bảo thoát màn hình phụ và trở về khung soạn bài chính.
    """
    print("📍 Đang check-in địa điểm cho bài viết...")
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
            
            homestay_map = {
                "lacasa": ["Lacasa Homestay", "Lacasa Homestay Huế"],
                "umee": ["UMEE Homestay", "UMEE Homestay Huế"]
            }
            norm_key = str(brand_key or "").strip().lower()
            priority_locs = homestay_map.get(norm_key, ["Lacasa Homestay", "UMEE Homestay"])
            famous_hue_locs = [
                "Thành phố Huế",
                "Đại Nội Huế", 
                "Chùa Thiên Mụ", 
                "Cầu Trường Tiền", 
                "Lăng Khải Định", 
                "Lăng Tự Đức", 
                "Lăng Minh Mạng", 
                "Trường Quốc Học Huế", 
                "Làng hương Thủy Xuân", 
                "Đồi Vọng Cảnh", 
                "Cung An Định",
                "Chợ Đông Ba",
                "Phố Tây Huế",
                "Sông Hương"
            ]
            # 70% ưu tiên check-in ngay tại Homestay, 30% xoay tua danh lam Huế
            if random.random() < 0.70:
                selected_location = random.choice(priority_locs)
            else:
                selected_location = random.choice(famous_hue_locs)
            
            search_input = page.locator("div[role='dialog'] input[placeholder*='Where' i], div[role='dialog'] input[placeholder*='ở đâu' i], div[role='dialog'] input[placeholder*='Tìm kiếm' i], div[role='dialog'] input[type='text'], div[role='dialog'] input[type='search']").first
            if search_input.is_visible(timeout=2500):
                try:
                    search_input.click(force=True)
                    search_input.fill("")
                    time.sleep(0.3)
                    search_input.press_sequentially(selected_location, delay=45)
                except Exception:
                    page.keyboard.type(selected_location, delay=45)
                time.sleep(random.uniform(2.5, 3.5))
                
                # 1. Thử bấm kết quả địa điểm xuất hiện trong danh sách
                checked_in = False
                def norm_place(value):
                    import unicodedata
                    value = unicodedata.normalize("NFD", str(value or "").casefold())
                    return re.sub(r"[^a-z0-9]+", " ", "".join(ch for ch in value if unicodedata.category(ch) != "Mn")).strip()

                first_option = page.locator("div[role='dialog'] [role='option'], div[role='dialog'] [role='menuitem'], div[role='dialog'] div[role='button']").filter(
                    has_text=re.compile(re.escape(selected_location), re.IGNORECASE)
                ).first
                
                if first_option.is_visible(timeout=1500):
                    try:
                        first_option.click(force=True, timeout=3000)
                        checked_in = True
                    except Exception:
                        pass

                # 2. Fallback: chỉ chọn candidate có chữ khớp; không click mù kết quả đầu.
                if not checked_in:
                    candidates = page.locator("div[role='dialog'] [role='option'], div[role='dialog'] [role='menuitem'], div[role='dialog'] div[role='button']")
                    expected = norm_place(selected_location)
                    for i in range(min(candidates.count(), 30)):
                        c = candidates.nth(i)
                        c_text = (c.inner_text() or "").strip()
                        candidate_name = norm_place(c_text.split("\n", 1)[0])
                        if expected and (candidate_name == expected or candidate_name.startswith(expected + " ")):
                            try:
                                c.click(force=True, timeout=2500)
                                checked_in = True
                                break
                            except Exception:
                                pass

                if checked_in:
                    time.sleep(1.5)
                    # A click is not success: require the search surface to close and
                    # the chosen place to be retained in the composer dialog.
                    search_closed = not search_input.is_visible(timeout=800)
                    composer_text = (page.locator("div[role='dialog']").last.inner_text(timeout=1500) or "")
                    retained = norm_place(selected_location) in norm_place(composer_text)
                    if search_closed and retained:
                        print(f"✅ [Check-in Verified] Đã gắn địa điểm: {selected_location}")
                    else:
                        checked_in = False
                        print(f"⚠️ [Check-in Unverified] Facebook chưa giữ địa điểm {selected_location}; không báo thành công.")
                else:
                    print(f"⚠️ Không tìm thấy kết quả check-in khớp: {selected_location}; bỏ qua để tránh chọn sai địa điểm.")

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
    Ghi nhận lifecycle của lần submit (published/pending/submitted_unverified) vào SQLite và JSON compatibility mirror.
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
    except Exception as db_err:
        print(f"⚠️ [History DB] Không thể ghi posted_links vào SQLite: {db_err}")

    # 2. JSON compatibility mirror; SQLite remains authoritative.
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
        # Reconcile the same lifecycle in JSON instead of appending a second row.
        lifecycle_item = None
        for item in items:
            same_attempt = (
                item.get("target") == target
                and (item.get("account_id") or "default") == (account_id or "default")
                and (item.get("content_preview") or "") == ((content[:120] + "...") if len(content) > 120 else content)
            )
            if same_attempt and item.get("publish_state") in ("submitted_unverified", "pending"):
                lifecycle_item = item
                break
        lifecycle_updated = False
        if lifecycle_item and derived_state in ("published", "pending"):
            lifecycle_item.update({"timestamp": now_ts, "url": post_url, "url_type": derived_url_type, "publish_state": derived_state, "status": final_status, "posted_at": time.strftime("%Y-%m-%d %H:%M:%S")})
            lifecycle_updated = True
            is_recent_dup = True
        else:
            is_recent_dup = any(item.get("target") == target and item.get("url") == post_url and (now_ts - float(item.get("timestamp", 0))) < 60.0 for item in items)

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
        elif lifecycle_updated:
            items = items[:200]
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            print(f"🔄 Đã cập nhật lifecycle History: {post_url} [{final_status}]")
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
    Chặn nếu target gần đây đã published, pending, hoặc submitted_unverified.
    submitted_unverified có thể đã được Facebook nhận nên phải đối soát trước khi đăng lại.
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
            # Fail-closed: uncertain submission also blocks automatic retry.
            if pub_state and pub_state not in ("published", "pending", "submitted_unverified"):
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
            if pub_state and pub_state not in ("published", "pending", "submitted_unverified"):
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
    """Match post content with word checkpoints resilient to FB truncation/DOM wrapping."""
    def norm(s):
        s = re.sub(r"[\s\u200b\u200c\u200d]+", " ", s or "").strip().casefold()
        return re.sub(r"[^\wÀ-ỹ]+", " ", s, flags=re.UNICODE).strip()

    a = norm(needle)
    b = norm(haystack)
    if not a or not b:
        return False
    if len(a) <= 40:
        return a in b

    words = a.split()
    if len(words) < 8:
        return a in b
    width = 6 if len(words) >= 18 else 4
    starts = [0, max(0, len(words) // 2 - width // 2), max(0, len(words) - width)]
    checkpoints = [" ".join(words[s:s + width]) for s in starts]
    matches = sum(1 for part in checkpoints if len(part) >= 12 and part in b)
    return matches >= 2

TOAST_CONFIRM_RE = re.compile(r"(đã đăng|đã chia sẻ|bài viết của bạn đã|bài viết đã được chia sẻ|posted|published|shared|your post has been)", re.I)

def _group_key_from_url(url: str) -> str:
    try:
        path = urllib.parse.urlparse(url or "").path
        m = re.search(r"/groups/([^/]+)", path, re.I)
        return (m.group(1) if m else "").lower()
    except Exception:
        return ""


def _scan_post_permalink_once(page, target="", content="", max_articles=10) -> str:
    target_group = _group_key_from_url(target)
    selectors = (
        "a[href*='/posts/'], a[href*='/permalink/'], a[href*='permalink.php'], "
        "a[href*='story.php'], a[href*='/videos/'], a[href*='/share/p/'], "
        "a[href*='/share/v/'], a[href*='/reel/']"
    )
    try:
        for container in page.locator("div[role='alert'], div[role='status']").all():
            try:
                c_text = container.inner_text(timeout=500) or ""
                if not TOAST_CONFIRM_RE.search(c_text):
                    continue
                for link in container.locator(selectors).all():
                    href = link.get_attribute("href") or ""
                    clean = clean_facebook_post_url(href)
                    if clean and (not target_group or _group_key_from_url(clean) in ("", target_group)):
                        return clean
            except Exception:
                continue
    except Exception:
        pass

    try:
        articles = page.locator("div[role='article']").all()[:max_articles]
        for art in articles:
            try:
                if not art.is_visible(timeout=800):
                    continue
                art_text = art.inner_text() or ""
                if content and not text_similarity_match(content, art_text):
                    continue
                for link in art.locator(selectors).all():
                    href = link.get_attribute("href") or ""
                    if not href or any(x in href for x in ["/groups/user/", "/comment/", "reaction"]):
                        continue
                    clean = clean_facebook_post_url(href)
                    if not clean:
                        continue
                    candidate_group = _group_key_from_url(clean)
                    if target_group and candidate_group and candidate_group != target_group:
                        continue
                    return clean
            except Exception:
                continue
    except Exception:
        pass
    return ""



def _copy_post_permalink_via_share_sheet(page, target="", content="") -> str:
    """Resolve a post permalink using Facebook's native Share -> Copy link action."""
    if not content:
        return ""
    share_button = None
    dialog = None
    try:
        print("[Permalink Resolver] native_share:start")
        normalized = re.sub(r"\s+", " ", content).strip()
        words = normalized.split()
        fragments = []
        if len(words) >= 4:
            fragments.append(" ".join(words[:8])[:70])
            mid = max(0, len(words) // 2 - 3)
            fragments.append(" ".join(words[mid:mid + 7])[:70])
        node = None
        for fragment in fragments:
            if len(fragment) < 12:
                continue
            candidates = page.get_by_text(fragment, exact=False)
            for idx in range(min(candidates.count(), 8)):
                candidate = candidates.nth(idx)
                try:
                    if candidate.is_visible(timeout=700):
                        node = candidate
                        break
                except Exception:
                    pass
            if node is not None:
                break
        if node is None:
            print("[Permalink Resolver] native_share:text_match=0")
            return ""
        print("[Permalink Resolver] native_share:text_match=1")
        try:
            node.scroll_into_view_if_needed(timeout=2500)
        except Exception:
            pass
        current = node
        for _ in range(16):
            current = current.locator("xpath=..")
            try:
                current_text = current.inner_text(timeout=800) or ""
                current_norm = re.sub(r"\s+", " ", current_text).strip().casefold()
                if not any(fragment.casefold() in current_norm for fragment in fragments if fragment):
                    continue
                buttons = current.locator("[role='button'], button")
                for idx in range(min(buttons.count(), 50)):
                    candidate = buttons.nth(idx)
                    label = (candidate.get_attribute("aria-label") or "").lower()
                    if ("g\u1eedi n\u1ed9i dung n\u00e0y cho b\u1ea1n b\u00e8" in label or
                            "send this to friends" in label or
                            "share this content" in label or
                            "chia s\u1ebb" in label or label.strip() == "share"):
                        share_button = candidate
                        break
                if share_button:
                    break
            except Exception:
                continue
        if not share_button:
            print("[Permalink Resolver] native_share:share_button=0")
            return ""
        print("[Permalink Resolver] native_share:share_button=1")
        try:
            page.context.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://www.facebook.com")
        except Exception:
            pass
        try:
            share_button.evaluate("el => el.click()")
        except Exception:
            share_button.click(force=True, timeout=1800)
        time.sleep(0.8)
        dialog = page.locator("[role='dialog']").last
        copy_button = dialog.get_by_text(re.compile("^(Sao ch\u00e9p li\u00ean k\u1ebft|Copy link)$", re.I), exact=True).first
        if not copy_button.count() or not copy_button.is_visible(timeout=1800):
            print("[Permalink Resolver] native_share:copy_link=0")
            return ""
        print("[Permalink Resolver] native_share:copy_link=1")
        try:
            copy_button.evaluate("el => el.click()")
        except Exception:
            copy_button.click(force=True, timeout=1800)
        time.sleep(0.4)
        copied = page.evaluate("async () => await navigator.clipboard.readText()") or ""
        print(f"[Permalink Resolver] native_share:clipboard={'1' if copied.strip() else '0'}")
        clean = clean_facebook_post_url(copied.strip())
        if not clean:
            print("[Permalink Resolver] native_share:canonical=0")
            return ""
        print(f"[Permalink Resolver] native_share:canonical=1 url={clean}")
        target_group = _group_key_from_url(target)
        copied_group = _group_key_from_url(clean)
        if target_group and copied_group and target_group != copied_group:
            return ""
        parsed = urllib.parse.urlparse(clean)
        is_post_route = bool(re.search(
            r"(?:/groups/[^/]+/(?:posts|permalink)/[^/]+|/[^/]+/(?:posts|videos)/[^/]+|/share/[pv]/[^/]+|/reel/[^/]+)",
            parsed.path, re.I
        ))
        qs = urllib.parse.parse_qs(parsed.query)
        is_query_post = parsed.path.lower().endswith(("/permalink.php", "/story.php")) and any(
            key in qs for key in ("story_fbid", "fbid", "post_id")
        )
        if not is_post_route and not is_query_post and "multi_permalinks" not in qs:
            return ""
        return clean
    except Exception:
        return ""
    finally:
        if dialog is not None:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

def _has_pending_post_notice(page) -> bool:
    try:
        pending_notice = page.locator(
            "div[role='alert'], div[role='status'], div[role='dialog']"
        ).filter(
            has_text=re.compile(
                r"(bài viết.*(chờ|quản trị|phê duyệt|xét duyệt)|post.*(pending|approval|admin)|submitted.*approval|đang chờ.*(phê duyệt|duyệt|xét)|awaiting.*approval|sẽ hiển thị sau khi|quản trị viên.*duyệt)",
                re.I,
            )
        )
        return pending_notice.count() > 0
    except Exception:
        return False


def _has_published_toast(page) -> bool:
    try:
        for container in page.locator("div[role='alert'], div[role='status']").all():
            c_text = container.inner_text(timeout=400) or ""
            if TOAST_CONFIRM_RE.search(c_text):
                return True
    except Exception:
        pass
    return False


def scrape_post_link(page, target="", content="", account_id="") -> ActionResult:
    """Resolve a submitted post with native permalink fallback before and after refresh."""
    print("Đang quét tìm liên kết của bài đăng vừa tạo...")
    fallback_url = target or (page.url if hasattr(page, "url") else "")
    target_type = "group" if "/groups/" in fallback_url else ("page" if fallback_url else "unknown")

    def _published(clean_href, message):
        print(f"POSTED_LINK:{clean_href}")
        record_posted_link(target, clean_href, content, note="Đã xuất bản", account_id=account_id,
                           url_type="post", publish_state="published")
        return ActionResult(True, "POST_PUBLISHED", message, state="published", target_url=target,
                            result_url=clean_href, url_type="post")

    try:
        time.sleep(1.5)
        for attempt in range(3):
            clean_href = _scan_post_permalink_once(page, target=target, content=content, max_articles=12)
            if not clean_href and target_type in ("group", "page") and attempt >= 1:
                clean_href = _copy_post_permalink_via_share_sheet(page, target=target, content=content)
            if clean_href:
                return _published(clean_href, "Đã đăng bài và trích xuất thành công permalink.")
            if _has_pending_post_notice(page):
                record_posted_link(target, fallback_url, content, note="Đang chờ admin duyệt", account_id=account_id,
                                   url_type=target_type, publish_state="pending")
                return ActionResult(True, "POST_PENDING", "Bài đăng đang chờ admin duyệt.", state="pending",
                                    target_url=target, url_type=target_type)
            if _has_published_toast(page):
                # Toast confirms submission but not identity; continue trying for a permalink.
                print("✅ Facebook đã xác nhận submit; tiếp tục lấy permalink canonical...")
            if attempt < 2:
                time.sleep(2.0)

        if target_type in ("group", "page"):
            print(f"🔄 Chưa thấy permalink; refresh {target_type.title()} một lần rồi tiếp tục native resolver...")
            try:
                page.reload(wait_until="domcontentloaded", timeout=20000)
            except Exception as reload_err:
                current = (page.url or "").lower()
                try:
                    body_chars = len(page.locator("body").inner_text(timeout=3000).strip())
                except Exception:
                    body_chars = 0
                if "facebook.com" not in current or body_chars < 20:
                    raise
                print(f"⚠️ Reload timeout nhưng DOM Facebook vẫn còn ({body_chars} chars); tiếp tục: {reload_err}")
            time.sleep(3.0)
            for attempt in range(3):
                clean_href = _scan_post_permalink_once(page, target=target, content=content, max_articles=18)
                if not clean_href:
                    clean_href = _copy_post_permalink_via_share_sheet(page, target=target, content=content)
                if clean_href:
                    return _published(clean_href, "Đã đối soát và trích xuất permalink canonical.")
                if _has_pending_post_notice(page):
                    record_posted_link(target, fallback_url, content, note="Đang chờ admin duyệt", account_id=account_id,
                                       url_type=target_type, publish_state="pending")
                    return ActionResult(True, "POST_PENDING", "Bài đăng đang chờ admin duyệt.", state="pending",
                                        target_url=target, url_type=target_type)
                if attempt < 2:
                    time.sleep(2.0)

        note_status = "Đã gửi đăng (Chưa trích xuất được link bài)"
        record_posted_link(target, fallback_url, content, note=note_status, account_id=account_id,
                           url_type=target_type, publish_state="submitted_unverified")
        print(f"⚠️ Bài đăng chưa được xác thực permalink: {fallback_url} [{note_status}]")
        return ActionResult(False, "POST_SUBMITTED_UNVERIFIED",
                            "Bài đăng đã gửi nhưng chưa trích xuất được permalink xác thực.",
                            state="submitted_unverified", target_url=target, result_url="", url_type=target_type)
    except Exception as e:
        print(f"⚠️ Cảnh báo: Lỗi khi quét liên kết bài đăng: {e}")
        record_posted_link(target, fallback_url, content, note="Đã gửi đăng (lỗi quét)", account_id=account_id,
                           url_type=target_type, publish_state="submitted_unverified")
        return ActionResult(False, "POST_SUBMITTED_UNVERIFIED", f"Đã gửi đăng (gặp lỗi khi quét link: {e})",
                            state="submitted_unverified", target_url=target, result_url="", url_type=target_type)
