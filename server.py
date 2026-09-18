import sys
import os
import json
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import re
import hmac
import hashlib
import base64
import struct
import random
import time
import traceback
import requests
from flask import Flask, request, jsonify, Response, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from utils import (
    load_accounts,
    save_accounts,
    resolve_account,
    fetch_gpm_profiles,
    pick_random_photos,
    normalize_target_url,
)
from paths import (
    BASE_DIR,
    DATA_DIR,
    UPLOAD_DIR,
    LOG_DIR,
    BACKUP_DIR,
    DB_FILE,
    get_version,
)
from repositories.account_repo import AccountRepository
from repositories.settings_repo import SettingsRepository
from repositories.group_repo import GroupRepository
from repositories.campaign_repo import CampaignRepository
from repositories.activity_repo import ActivityRepository
from repositories.vault_repo import VaultRepository
from services.migration_service import run_migration_if_needed
from db import backup_db

# Auto-migrate legacy state to SQLite if needed
try:
    run_migration_if_needed()
except Exception as _mig_err:
    print(f"Warning: Database migration initialization error: {_mig_err}")

app = Flask(__name__, static_folder='static')
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

from api.jobs import jobs_bp
app.register_blueprint(jobs_bp)

try:
    from services.job_manager import JobManager
    _reconciled = JobManager().reconcile_on_startup()
    if _reconciled:
        print(f"[JobManager] Đã khôi phục {_reconciled} tiến trình dở dang.")
except Exception as _jm_err:
    print(f"Warning: JobManager init error: {_jm_err}")

try:
    _queue_recovered = CampaignRepository().reconcile_processing_queue()
    if _queue_recovered:
        print(f"[PublicationQueue] Đã chuyển {_queue_recovered} mục processing bị gián đoạn sang chưa xác minh để đối soát; không tự retry.")
except Exception as _queue_err:
    print(f"Warning: Publication queue reconciliation error: {_queue_err}")

CONFIG_FILE = str(DATA_DIR / "config.json")
QUEUE_FILE = str(DATA_DIR / "publication_queue.json")
CAMPAIGNS_FILE = str(DATA_DIR / "campaigns.json")
ACTIVITY_LOG_FILE = str(DATA_DIR / "profile_activity.json")
GROUPS_FILE = str(DATA_DIR / "group_registry.json")
MANUAL_GROUP_QUEUE_FILE = str(DATA_DIR / "manual_group_queue.json")
VAULT_FILE = str(DATA_DIR / "account_vault.json")
ACCOUNTS_FILE = str(DATA_DIR / "accounts.json")
STATE_FILE = str(DATA_DIR / "state.json")
AUTH_STATUS_FILE = str(DATA_DIR / "auth_status.json")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_COMMANDS = {"auth", "group", "page", "thread", "interact", "scrape", "comment", "join-group", "create-page", "reconcile-post"}
APP_VERSION = get_version()
BUILD_TIME = "2026-09-18 v6.1.28"


def app_build_info():
    """Return a local build identity so the UI can detect a mismatched server."""
    source_mtime = datetime.fromtimestamp(Path(__file__).stat().st_mtime, timezone.utc)
    return {
        "version": APP_VERSION,
        "built_at": BUILD_TIME,
        "source_updated_at": source_mtime.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "runtime_root": str(BASE_DIR.resolve()),
        "main_path": str((BASE_DIR / "main.py").resolve()),
        "process_id": os.getpid(),
        "group_manager_available": True,
        "entrypoint": str(Path(__file__).resolve()),
    }

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    try:
        cfg = SettingsRepository().get_config()
        if cfg:
            return cfg
    except Exception:
        pass
    return {}

def save_config(data):
    try:
        SettingsRepository().save_config(data)
    except Exception:
        pass
    config_directory = str(Path(CONFIG_FILE).resolve().parent)
    fd, temp_path = tempfile.mkstemp(prefix="config-", suffix=".json", dir=config_directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, CONFIG_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def _is_canonical_runtime_file(path_value, filename):
    try:
        return Path(path_value).resolve() == (DATA_DIR / filename).resolve()
    except Exception:
        return False

def load_queue():
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        try:
            return CampaignRepository().list_queue()
        except Exception as db_err:
            print(f"⚠️ Không thể đọc publication queue từ SQLite: {db_err}")
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                queue = json.load(f)
            if isinstance(queue, list):
                return queue
        except (OSError, json.JSONDecodeError):
            pass
    return []

def _write_queue_json(queue):
    queue_directory = str(Path(QUEUE_FILE).resolve().parent)
    fd, temp_path = tempfile.mkstemp(prefix="publication-queue-", suffix=".json", dir=queue_directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, QUEUE_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def save_queue(queue):
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        CampaignRepository().save_queue(queue)
    _write_queue_json(queue)

def load_campaigns():
    if _is_canonical_runtime_file(CAMPAIGNS_FILE, "campaigns.json"):
        try:
            return CampaignRepository().list_campaigns()
        except Exception as db_err:
            print(f"⚠️ Không thể đọc campaigns từ SQLite: {db_err}")
    if os.path.exists(CAMPAIGNS_FILE):
        try:
            with open(CAMPAIGNS_FILE, "r", encoding="utf-8") as f:
                campaigns = json.load(f)
            if isinstance(campaigns, list):
                return campaigns
        except (OSError, json.JSONDecodeError):
            pass
    return []

def save_campaigns(campaigns):
    if _is_canonical_runtime_file(CAMPAIGNS_FILE, "campaigns.json"):
        CampaignRepository().save_campaigns(campaigns)
    campaign_directory = str(Path(CAMPAIGNS_FILE).resolve().parent)
    fd, temp_path = tempfile.mkstemp(prefix="campaigns-", suffix=".json", dir=campaign_directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(campaigns, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, CAMPAIGNS_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def load_json_list(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_json_list(filename, value, prefix):
    directory = str(Path(filename).resolve().parent)
    fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, filename)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def record_profile_activity(profile_id, action, target="", content="", outcome="finished"):
    """Persist an operational audit trail; it never asserts Facebook publication."""
    try:
        ActivityRepository().record_activity(profile_id, action, target, content, outcome)
    except Exception:
        pass
    activities = load_json_list(ACTIVITY_LOG_FILE)
    activities.insert(0, {
        "id": uuid.uuid4().hex[:12],
        "at": now_iso(),
        "profile_id": profile_id or "default-session",
        "action": action,
        "target": target[:2_000],
        "content_preview": content[:180],
        "outcome": outcome,
    })
    save_json_list(ACTIVITY_LOG_FILE, activities[:1_000], "profile-activity-")

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def parse_queue_date(value, field_name="date"):
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} phải có định dạng YYYY-MM-DD.") from exc

def campaign_summary(campaign, queue):
    items = [item for item in queue if item.get("campaign_id") == campaign.get("id")]
    by_state = {state: sum(item.get("state") == state for item in items) for state in ("draft", "approved", "published", "failed", "cancelled")}
    return {**campaign, "summary": {"total": len(items), **by_state}}

def json_body():
    return request.get_json(silent=True) or {}

def is_valid_http_url(value):
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)

def is_uploaded_image(value):
    try:
        return Path(value).resolve().is_relative_to(UPLOAD_DIR)
    except (OSError, ValueError):
        return False


def json_list_count(filename):
    """Return a safe count for an optional JSON list without exposing its contents."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            value = json.load(f)
        return len(value) if isinstance(value, list) else 0
    except (OSError, json.JSONDecodeError):
        return 0


def valid_vault_date(value):
    """Accept an optional calendar date without silently changing its meaning."""
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def scheduler_posted_count():
    try:
        with open(DATA_DIR / "scheduler_state.json", "r", encoding="utf-8") as f:
            value = json.load(f)
        posted = value.get("posted", {}) if isinstance(value, dict) else {}
        return len(posted) if isinstance(posted, dict) else 0
    except (OSError, json.JSONDecodeError):
        return 0


STATE_FILE = str(DATA_DIR / "state.json")
AUTH_STATUS_FILE = str(DATA_DIR / "auth_status.json")

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/status', methods=['GET'])
@app.route('/api/auth-status', methods=['GET'])
def get_status():
    is_authenticated = os.path.exists(STATE_FILE) or os.path.exists(AUTH_STATUS_FILE)
    return jsonify({"authenticated": is_authenticated})


@app.route('/api/groups/moderation', methods=['GET'])
def api_groups_moderation():
    from repositories.moderation_repo import ModerationRepository
    rows = ModerationRepository().list_moderated_groups()
    for row in rows:
        pending = int(row.get("pending_count") or 0)
        threshold = int(row.get("skip_threshold") or 2)
        row["decision"] = "skip" if pending >= threshold else ("low_priority" if row.get("requires_approval") else "normal")
    return jsonify({"groups": rows, "count": len(rows)})


@app.route('/api/app-info', methods=['GET'])
def get_app_info():
    return jsonify(app_build_info())


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    config = load_config()
    if request.method == 'POST':
        data = json_body()
        if "gpm_api_url" in data:
            config["gpm_api_url"] = str(data["gpm_api_url"]).strip()
        if "gemini_api_key" in data:
            new_key = str(data["gemini_api_key"]).strip()
            if new_key:  # only update if non-empty
                config["gemini_api_key"] = new_key
        if "gemini_api_keys" in data:
            from ai_spinner import parse_gemini_keys
            keys = parse_gemini_keys(data.get("gemini_api_keys"))
            if keys:
                config["gemini_api_keys"] = keys
                config["gemini_api_key"] = keys[0]
        if "delay_preset" in data:
            config["delay_preset"] = str(data["delay_preset"]).strip()
        if "delay_min" in data:
            config["delay_min"] = max(5, int(data["delay_min"]))
        if "delay_max" in data:
            config["delay_max"] = max(int(data.get("delay_min", 5)), int(data["delay_max"]))
        if "auto_join_groups" in data:
            config["auto_join_groups"] = bool(data["auto_join_groups"])
        if "group_keywords" in data:
            config["group_keywords"] = str(data["group_keywords"]).strip()
        save_config(config)
        return jsonify({
            "success": True,
            "message": "Đã lưu cấu hình thành công!",
            "settings": {
                "gpm_api_url": config.get("gpm_api_url", "http://127.0.0.1:19995"),
                "delay_preset": config.get("delay_preset", "safe"),
                "delay_min": config.get("delay_min", 300),
                "delay_max": config.get("delay_max", 600),
                "auto_join_groups": config.get("auto_join_groups", False),
                "group_keywords": config.get("group_keywords", "Homestay Huế, Du lịch Huế"),
            }
        })

    from ai_spinner import parse_gemini_keys
    keys = parse_gemini_keys(config.get("gemini_api_keys") or config.get("gemini_api_key", ""))
    key = keys[0] if keys else ""
    masked_key = f"...{key[-6:]}" if len(key) > 6 else ("" if not key else key)
    return jsonify({
        "gpm_api_url": config.get("gpm_api_url", "http://127.0.0.1:19995"),
        "gemini_api_key_masked": masked_key,
        "has_gemini_key": bool(key),
        "gemini_api_key_configured": bool(key),
        "gemini_api_key_count": len(keys),
        "delay_preset": config.get("delay_preset", "safe"),
        "delay_min": config.get("delay_min", 300),
        "delay_max": config.get("delay_max", 600),
        "auto_join_groups": config.get("auto_join_groups", False),
        "group_keywords": config.get("group_keywords", "Homestay Huế, Du lịch Huế"),
    })


@app.route('/api/security/overview', methods=['GET'])
def security_overview():
    """Expose configuration health only; never return tokens, sessions, or file contents."""
    config = load_config()
    return jsonify({
        "local_only": True,
        "page_token_configured": bool(config.get("page_access_token")),
        "page_name": config.get("page_name", ""),
        "sheets_configured": bool(config.get("sheets_csv_url")),
        "browser_session_saved": os.path.exists(STATE_FILE) or os.path.exists(AUTH_STATUS_FILE),
        "profiles_configured": json_list_count("accounts.json"),
        "scheduler_history_count": scheduler_posted_count(),
    })


@app.route('/api/profile-activity', methods=['GET'])
def profile_activity():
    profile_id = request.args.get("profile_id", "").strip()
    limit = max(1, min(request.args.get("limit", 100, type=int) or 100, 500))
    activities = load_json_list(ACTIVITY_LOG_FILE)
    if profile_id:
        activities = [entry for entry in activities if entry.get("profile_id") == profile_id]
    return jsonify(activities[:limit])


@app.route('/api/created-pages', methods=['GET'])
def api_created_pages():
    try:
        import fb_create_page
        pages = fb_create_page.load_created_pages()
        allowed, count, reason = fb_create_page.can_create_page(max_per_day=2)
        return jsonify({
            "pages": pages,
            "allowed": allowed,
            "count_24h": count,
            "max_per_day": 2,
            "reason": reason
        })
    except Exception as e:
        return jsonify({
            "pages": [],
            "allowed": True,
            "count_24h": 0,
            "max_per_day": 2,
            "reason": str(e)
        })


GROUP_STATUSES = {"not_requested", "requested_manually", "pending", "approved", "declined", "paused"}
GROUP_TYPES = {"public", "private", "unknown"}


def valid_group_url(value):
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in {"facebook.com", "www.facebook.com", "m.facebook.com"}


def normalize_member_count(value):
    if value in (None, ""):
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if 0 <= count <= 2_000_000_000 else None


@app.route('/api/groups', methods=['GET'])
def get_groups():
    return jsonify(load_json_list(GROUPS_FILE))


@app.route('/api/groups', methods=['POST'])
def create_group():
    data = json_body()
    url = data.get("url", "").strip()
    name = data.get("name", "").strip()
    group_type = data.get("group_type", "unknown")
    member_count = normalize_member_count(data.get("member_count"))
    if not valid_group_url(url):
        return jsonify({"error": "Group link phải là URL HTTPS facebook.com hợp lệ."}), 400
    if len(name) > 120 or group_type not in GROUP_TYPES:
        return jsonify({"error": "Tên hoặc loại Group không hợp lệ."}), 400
    if data.get("member_count") not in (None, "") and member_count is None:
        return jsonify({"error": "Số thành viên phải là số từ 0 đến 2 tỷ."}), 400
    groups = load_json_list(GROUPS_FILE)
    if any(entry.get("url") == url for entry in groups):
        return jsonify({"error": "Group link này đã có trong danh sách."}), 409
    group = {
        "id": uuid.uuid4().hex[:12],
        "url": url,
        "name": name or url,
        "group_type": group_type,
        "member_count": member_count,
        "status": "not_requested",
        "rating": 0,
        "notes": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    groups.insert(0, group)
    save_json_list(GROUPS_FILE, groups, "group-registry-")
    return jsonify(group), 201


@app.route('/api/groups/<group_id>', methods=['PATCH'])
def update_group(group_id):
    data = json_body()
    groups = load_json_list(GROUPS_FILE)
    group = next((entry for entry in groups if entry.get("id") == group_id), None)
    if not group:
        return jsonify({"error": "Không tìm thấy Group."}), 404
    status = data.get("status", group.get("status", "not_requested"))
    rating = data.get("rating", group.get("rating", 0))
    notes = data.get("notes", group.get("notes", ""))
    group_type = data.get("group_type", group.get("group_type", "unknown"))
    member_count = normalize_member_count(data.get("member_count", group.get("member_count")))
    if status not in GROUP_STATUSES or group_type not in GROUP_TYPES:
        return jsonify({"error": "Trạng thái Group không hợp lệ."}), 400
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"error": "Điểm đánh giá không hợp lệ."}), 400
    if not 0 <= rating <= 5 or not isinstance(notes, str) or len(notes) > 2_000:
        return jsonify({"error": "Điểm phải từ 0 đến 5 và ghi chú tối đa 2.000 ký tự."}), 400
    if data.get("member_count", group.get("member_count")) not in (None, "") and member_count is None:
        return jsonify({"error": "Số thành viên phải là số từ 0 đến 2 tỷ."}), 400
    group.update({"status": status, "rating": rating, "notes": notes.strip(), "group_type": group_type, "member_count": member_count, "updated_at": now_iso()})
    save_json_list(GROUPS_FILE, groups, "group-registry-")
    return jsonify(group)


@app.route('/api/groups/<group_id>', methods=['DELETE'])
def delete_group(group_id):
    groups = load_json_list(GROUPS_FILE)
    remaining = [entry for entry in groups if entry.get("id") != group_id]
    if len(remaining) == len(groups):
        return jsonify({"error": "Không tìm thấy Group."}), 404
    save_json_list(GROUPS_FILE, remaining, "group-registry-")
    return jsonify({"success": True})


@app.route('/api/groups/sync-sheet', methods=['POST'])
def api_sync_groups_from_sheet():
    from services.sheet_sync import (
        to_csv_export_url,
        fetch_sheet_csv,
        parse_group_sheet,
        sync_to_group_registry,
        DEFAULT_SHEET_URL,
    )
    data = json_body()
    raw_sheet_url = data.get("sheet_url", "").strip() or DEFAULT_SHEET_URL
    filter_active = bool(data.get("filter_active_only", False))
    save_registry = bool(data.get("save_registry", True))

    try:
        csv_url = to_csv_export_url(raw_sheet_url)
        csv_text = fetch_sheet_csv(csv_url)
    except Exception as e:
        return jsonify({"success": False, "error": f"Lỗi tải Google Sheet: {str(e)}"}), 400

    parsed = parse_group_sheet(csv_text, filter_active_only=filter_active)
    if not parsed.get("success"):
        return jsonify(parsed), 400

    if save_registry and parsed.get("groups"):
        try:
            parsed["registry"] = sync_to_group_registry(parsed["groups"])
        except Exception as se:
            app.logger.exception("Google Sheet parsed but registry synchronization failed")
            return jsonify({
                "success": False,
                "error": f"Đã đọc Google Sheet nhưng không thể lưu kho Group: {str(se)}",
                "sheet": {
                    "total_rows": parsed.get("total_rows", 0),
                    "unique_count": parsed.get("unique_count", 0),
                    "duplicates_count": parsed.get("duplicates_count", 0),
                    "selected_count": parsed.get("selected_count", 0),
                },
            }), 500

    return jsonify(parsed)


@app.route('/api/groups/sheet-config', methods=['GET'])
def api_get_sheet_config():
    from services.sheet_sync import DEFAULT_SHEET_URL
    return jsonify({
        "default_sheet_url": DEFAULT_SHEET_URL,
        "sample_columns": ["STT", "Group Link", "Group Name", "Nhóm Public/Private", "Số thành viên làm tròn lên", "Đăng bài tự động (Y/N)"]
    })


# ---- Manual Group workflow: preparation and audit only, never browser posting ----
MANUAL_GROUP_QUEUE_STATES = {"planned", "ready", "completed", "skipped"}


def get_manual_group_queue_item(item_id):
    items = load_json_list(MANUAL_GROUP_QUEUE_FILE)
    return items, next((entry for entry in items if entry.get("id") == item_id), None)


@app.route('/api/manual-group-queue', methods=['GET'])
def get_manual_group_queue():
    return jsonify(load_json_list(MANUAL_GROUP_QUEUE_FILE))


@app.route('/api/manual-group-queue', methods=['POST'])
def create_manual_group_queue_item():
    data = json_body()
    group_id = data.get("group_id", "").strip()
    profile_id = data.get("profile_id", "").strip()
    content = data.get("content", "").strip()
    planned_at = data.get("planned_at", "").strip()
    group = next((entry for entry in load_json_list(GROUPS_FILE) if entry.get("id") == group_id), None)
    if not group:
        return jsonify({"error": "Hãy chọn Group trong registry."}), 400
    if not profile_id or len(profile_id) > 100:
        return jsonify({"error": "Hãy chọn profile phụ trách."}), 400
    if not 15 <= len(content) <= 60_000:
        return jsonify({"error": "Nội dung cần từ 15 đến 60.000 ký tự."}), 400
    if len(planned_at) > 40:
        return jsonify({"error": "Thời điểm dự kiến không hợp lệ."}), 400
    item = {
        "id": uuid.uuid4().hex[:12],
        "group_id": group["id"],
        "group_name": group.get("name", group["url"]),
        "group_url": group["url"],
        "profile_id": profile_id,
        "content": content,
        "planned_at": planned_at,
        "state": "planned",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "audit": [{"at": now_iso(), "event": "created"}],
    }
    items = load_json_list(MANUAL_GROUP_QUEUE_FILE)
    items.insert(0, item)
    save_json_list(MANUAL_GROUP_QUEUE_FILE, items, "manual-group-queue-")
    return jsonify(item), 201


@app.route('/api/manual-group-queue/<item_id>/<action>', methods=['POST'])
def update_manual_group_queue_item(item_id, action):
    transitions = {
        "mark-ready": ("planned", "ready"),
        "mark-completed": ("ready", "completed"),
        "skip": ({"planned", "ready"}, "skipped"),
    }
    if action not in transitions:
        return jsonify({"error": "Thao tác không hợp lệ."}), 400
    items, item = get_manual_group_queue_item(item_id)
    if not item:
        return jsonify({"error": "Không tìm thấy mục trong hàng đợi."}), 404
    expected, next_state = transitions[action]
    if (isinstance(expected, set) and item.get("state") not in expected) or (not isinstance(expected, set) and item.get("state") != expected):
        return jsonify({"error": "Trạng thái hiện tại không cho phép thao tác này."}), 409
    item["state"] = next_state
    item["updated_at"] = now_iso()
    item.setdefault("audit", []).append({"at": now_iso(), "event": action})
    save_json_list(MANUAL_GROUP_QUEUE_FILE, items, "manual-group-queue-")
    if action == "mark-completed":
        record_profile_activity(item["profile_id"], "manual_group_confirmation", target=item["group_url"], content=item["content"], outcome="completed")
    return jsonify(item)

# ---- Compliance workflow: preflight -> human approval -> tracked queue ----

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    queue = load_queue()
    return jsonify([campaign_summary(campaign, queue) for campaign in load_campaigns()])

@app.route('/api/campaigns', methods=['POST'])
def create_campaign():
    data = json_body()
    name = data.get("name", "").strip()
    brand = data.get("brand", "").strip()
    target = data.get("target", "").strip()
    if not name or len(name) > 120:
        return jsonify({"error": "Tên chiến dịch là bắt buộc và tối đa 120 ký tự."}), 400
    if len(brand) > 80 or len(target) > 2_000:
        return jsonify({"error": "Thông tin chiến dịch vượt giới hạn cho phép."}), 400
    campaign = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "brand": brand,
        "target": target,
        "state": "active",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "audit": [{"at": now_iso(), "event": "created"}],
    }
    campaigns = load_campaigns()
    campaigns.insert(0, campaign)
    save_campaigns(campaigns)
    return jsonify(campaign_summary(campaign, load_queue())), 201

@app.route('/api/campaigns/<campaign_id>/toggle', methods=['POST'])
def toggle_campaign(campaign_id):
    campaigns = load_campaigns()
    campaign = next((entry for entry in campaigns if entry.get("id") == campaign_id), None)
    if not campaign:
        return jsonify({"error": "Không tìm thấy chiến dịch."}), 404
    campaign["state"] = "paused" if campaign.get("state") == "active" else "active"
    campaign["updated_at"] = now_iso()
    campaign.setdefault("audit", []).append({"at": now_iso(), "event": campaign["state"]})
    save_campaigns(campaigns)
    return jsonify(campaign_summary(campaign, load_queue()))

@app.route('/api/campaigns/<campaign_id>/approve-drafts', methods=['POST'])
def approve_campaign_drafts(campaign_id):
    campaign = next((entry for entry in load_campaigns() if entry.get("id") == campaign_id), None)
    if not campaign:
        return jsonify({"error": "Không tìm thấy chiến dịch."}), 404
    if campaign.get("state") != "active":
        return jsonify({"error": "Chỉ có thể duyệt mục thuộc chiến dịch đang hoạt động."}), 409
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        approved = CampaignRepository().approve_campaign_drafts_atomic(campaign_id)
        queue = CampaignRepository().list_queue()
        _write_queue_json(queue)
    else:
        queue = load_queue()
        approved = 0
        for item in queue:
            if item.get("campaign_id") == campaign_id and item.get("state") == "draft":
                item["state"] = "approved"
                item["updated_at"] = now_iso()
                item.setdefault("audit", []).append({"at": now_iso(), "event": "approved_batch"})
                approved += 1
        save_queue(queue)
    return jsonify({"approved": approved, "campaign": campaign_summary(campaign, queue)})

@app.route('/api/preflight', methods=['POST'])
def preflight_post():
    data = json_body()
    target = data.get("target", "").strip()
    content = data.get("content", "").strip()
    issues = []
    if not target:
        issues.append("Chưa chọn target.")
    if not content:
        issues.append("Nội dung đang trống.")
    if len(content) > 60_000:
        issues.append("Nội dung vượt giới hạn 60.000 ký tự.")
    if content and len(content) < 15:
        issues.append("Nội dung quá ngắn; nên kiểm tra lại trước khi đăng.")
    duplicate = any(item.get("target") == target and item.get("content") == content and item.get("state") != "cancelled" for item in load_queue())
    if duplicate:
        issues.append("Nội dung tương tự đã tồn tại trong hàng đợi.")
    return jsonify({"ready": not issues, "issues": issues})

@app.route('/api/queue', methods=['GET'])
def get_queue():
    items = load_queue()
    active = request.args.get("active", "0") == "1"
    state = (request.args.get("state") or "").strip().lower()
    try:
        date_filter = parse_queue_date(request.args.get("date"), "date")
        date_from = parse_queue_date(request.args.get("date_from"), "date_from")
        date_to = parse_queue_date(request.args.get("date_to"), "date_to")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if date_filter:
        if not date_from: date_from = date_filter
        if not date_to: date_to = date_filter
    try:
        limit = max(1, min(int(request.args.get("limit", 500)), 1000))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return jsonify({"error": "limit/offset không hợp lệ"}), 400
    if active:
        items = [i for i in items if i.get("state") in ("draft", "approved", "processing", "reconciling")]
    elif state == "reconcile":
        items = [i for i in items if str(i.get("state", "")).lower() in ("unverified", "manual_review")]
    elif state:
        items = [i for i in items if str(i.get("state", "")).lower() == state]
    if date_from:
        items = [i for i in items if str(i.get("created_at") or "")[:10] >= date_from]
    if date_to:
        items = [i for i in items if str(i.get("created_at") or "")[:10] <= date_to]
    items = sorted(items, key=lambda i: i.get("updated_at") or i.get("created_at") or "", reverse=True)
    return jsonify(items[offset:offset + limit])

@app.route('/api/queue-summary', methods=['GET'])
def queue_summary():
    items = load_queue()
    try:
        date_filter = parse_queue_date(request.args.get("date"), "date")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if date_filter:
        items = [i for i in items if str(i.get("created_at") or "")[:10] == date_filter]
    counts = {"total": len(items), "draft": 0, "approved": 0, "processing": 0, "reconciling": 0, "pending": 0, "unverified": 0, "manual_review": 0, "failed": 0, "cancelled": 0, "published": 0}
    for item in items:
        st = str(item.get("state") or "")
        if st in counts:
            counts[st] += 1
    counts["active"] = counts["draft"] + counts["approved"] + counts["processing"] + counts["reconciling"]
    counts["needs_reconcile"] = counts["unverified"] + counts["manual_review"]
    return jsonify(counts)

@app.route('/api/queue/dates', methods=['GET'])
def get_queue_dates():
    items = load_queue()
    dates_set = set()
    for item in items:
        dt = (item.get("created_at") or "")[:10]
        if len(dt) == 10:
            dates_set.add(dt)
    return jsonify(sorted(list(dates_set), reverse=True))

@app.route('/api/queue', methods=['POST'])
def create_queue_item():
    data = json_body()
    target = data.get("target", "").strip()
    content = data.get("content", "").strip()
    image_url = data.get("image_url", "").strip()
    campaign_id = data.get("campaign_id", "").strip()
    allow_duplicate = bool(data.get("allow_duplicate", False))
    if not target or not content:
        return jsonify({"error": "Target và nội dung là bắt buộc."}), 400
    if len(target) > 2_000 or len(content) > 60_000:
        return jsonify({"error": "Dữ liệu vượt giới hạn cho phép."}), 400
    if image_url and not is_valid_http_url(image_url):
        return jsonify({"error": "Link ảnh phải là HTTPS hợp lệ."}), 400
    if campaign_id:
        campaign = next((entry for entry in load_campaigns() if entry.get("id") == campaign_id), None)
        if not campaign:
            return jsonify({"error": "Chiến dịch không tồn tại."}), 400
        if campaign.get("state") != "active":
            return jsonify({"error": "Chiến dịch đang tạm dừng."}), 409
    queue = load_queue()
    if not allow_duplicate:
        canonical_target = normalize_target_url(target)
        existing = next((
            i for i in queue
            if normalize_target_url(i.get("target") or "") == canonical_target
            and str(i.get("content") or "").strip() == content
            and i.get("state") in ("draft", "approved", "pending")
        ), None)
        if existing:
            return jsonify({"error": f"Bài viết với mục tiêu này đã có trong hàng đợi ({existing.get('state')}).", "duplicate": True, "existing_id": existing.get("id")}), 409
    item = {
        "id": uuid.uuid4().hex[:12],
        "target": target,
        "content": content,
        "image_url": image_url,
        "campaign_id": campaign_id or None,
        "state": "draft",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "audit": [{"at": now_iso(), "event": "created"}],
    }
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        if not CampaignRepository().insert_queue_item(item):
            return jsonify({"error": "Không thể tạo mục hàng đợi."}), 409
        # Compatibility mirror only after authoritative DB commit.
        _write_queue_json(CampaignRepository().list_queue())
    else:
        queue.insert(0, item)
        save_queue(queue)
    return jsonify(item), 201

@app.route('/api/queue/<item_id>/approve', methods=['POST'])
def approve_queue_item(item_id):
    queue = load_queue()
    item = next((entry for entry in queue if entry.get("id") == item_id), None)
    if not item:
        return jsonify({"error": "Không tìm thấy mục trong hàng đợi."}), 404
    if item.get("state") != "draft":
        return jsonify({"error": "Chỉ mục nháp mới có thể được duyệt."}), 409
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        updated = CampaignRepository().transition_queue_item(item_id, ("draft",), "approved", {"approved_at": now_iso(), "error": None}, "approved")
        if not updated:
            return jsonify({"error": "Trạng thái mục đã thay đổi; hãy làm mới hàng đợi."}), 409
        _write_queue_json(CampaignRepository().list_queue())
        return jsonify(updated)
    item["state"] = "approved"
    item["updated_at"] = now_iso()
    item.setdefault("audit", []).append({"at": now_iso(), "event": "approved"})
    save_queue(queue)
    return jsonify(item)

@app.route('/api/queue/<item_id>/retry', methods=['POST'])
def retry_queue_item(item_id):
    updated=CampaignRepository().transition_queue_item(item_id,("failed",),"approved",{"error":None,"approved_at":now_iso()},"manual_retry_approved")
    if not updated: return jsonify({"error":"Chỉ bài lỗi xác định trước submit mới được thử lại."}),409
    _write_queue_json(CampaignRepository().list_queue()); return jsonify(updated)

@app.route('/api/queue/<item_id>/cancel', methods=['POST'])
def cancel_queue_item(item_id):
    queue = load_queue()
    item = next((entry for entry in queue if entry.get("id") == item_id), None)
    if not item:
        return jsonify({"error": "Không tìm thấy mục trong hàng đợi."}), 404
    if item.get("state") == "published":
        return jsonify({"error": "Không thể hủy mục đã đăng."}), 409
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        updated = CampaignRepository().transition_queue_item(item_id, ("draft", "approved", "pending", "unverified"), "cancelled", {}, "cancelled")
        if not updated:
            return jsonify({"error": "Không thể hủy mục ở trạng thái hiện tại."}), 409
        _write_queue_json(CampaignRepository().list_queue())
        return jsonify(updated)
    item["state"] = "cancelled"
    item["updated_at"] = now_iso()
    item.setdefault("audit", []).append({"at": now_iso(), "event": "cancelled"})
    save_queue(queue)
    return jsonify(item)

@app.route('/api/queue/approve-all', methods=['POST'])
def approve_all_queue():
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        approved = CampaignRepository().approve_all_drafts()
        _write_queue_json(CampaignRepository().list_queue())
    else:
        queue = load_queue()
        now = now_iso()
        approved = 0
        for item in queue:
            if item.get("state") == "draft":
                item["state"] = "approved"
                item["approved_at"] = now
                item["updated_at"] = now
                item.setdefault("audit", []).append({"at": now, "event": "approved_all_drafts"})
                approved += 1
        save_queue(queue)
    return jsonify({"success": True, "approved": approved})

@app.route('/api/queue/cancel-all', methods=['POST'])
def cancel_all_queue():
    data = json_body()
    states = data.get("states") or ["approved", "draft"]
    if not isinstance(states, list) or not states or any(state not in ("approved", "draft") for state in states):
        return jsonify({"error": "Chỉ được hủy hàng loạt bài ở trạng thái approved hoặc draft."}), 400
    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        cancelled = CampaignRepository().cancel_all_queue(states=tuple(states))
        _write_queue_json(CampaignRepository().list_queue())
    else:
        queue = load_queue()
        now = now_iso()
        cancelled = 0
        for item in queue:
            if item.get("state") in states:
                item["state"] = "cancelled"
                item["updated_at"] = now
                item.setdefault("audit", []).append({"at": now, "event": "cancelled_batch"})
                cancelled += 1
        save_queue(queue)
    return jsonify({"success": True, "cancelled": cancelled})

@app.route('/api/queue/clear', methods=['POST'])
def clear_queue_items():
    data = json_body()
    scope = (data.get("scope") or "").strip().lower()
    if scope not in ("all", "cancelled_or_failed", "date", "approved", "draft"):
        return jsonify({"error": "Tham số scope không hợp lệ. Cần một trong: all, cancelled_or_failed, date, approved, draft."}), 400
    target_date = data.get("date")
    try:
        date_from = parse_queue_date(data.get("date_from") or target_date, "date_from")
        date_to = parse_queue_date(data.get("date_to") or target_date, "date_to")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if scope == "date" and not date_from:
        return jsonify({"error": "Scope date yêu cầu date hoặc date_from hợp lệ."}), 400
    if date_from and date_to and date_from > date_to:
        return jsonify({"error": "date_from không được sau date_to."}), 400

    if _is_canonical_runtime_file(QUEUE_FILE, "publication_queue.json"):
        repo = CampaignRepository()
        if scope == "all":
            deleted = repo.delete_queue_items(clear_all=True)
        elif scope == "cancelled_or_failed":
            deleted = repo.delete_queue_items(states=["cancelled", "failed"])
        elif scope == "approved":
            deleted = repo.delete_queue_items(states=["approved"])
        elif scope == "draft":
            deleted = repo.delete_queue_items(states=["draft"])
        elif scope == "date":
            states_filter = data.get("states")
            deleted = repo.delete_queue_items(states=states_filter, date_from=date_from, date_to=date_to)
        else:
            deleted = 0
        _write_queue_json(repo.list_queue())
    else:
        queue = load_queue()
        initial_len = len(queue)
        if scope == "all":
            queue = []
        elif scope == "cancelled_or_failed":
            queue = [i for i in queue if i.get("state") not in ("cancelled", "failed")]
        elif scope == "approved":
            queue = [i for i in queue if i.get("state") != "approved"]
        elif scope == "draft":
            queue = [i for i in queue if i.get("state") != "draft"]
        elif scope == "date" and date_from:
            states_filter = set(data.get("states") or [])
            def keep(item):
                d = str(item.get("created_at") or "")[:10]
                if date_from and date_to and (date_from <= d <= date_to):
                    if not states_filter or item.get("state") in states_filter:
                        return False
                return True
            queue = [i for i in queue if keep(i)]
        deleted = initial_len - len(queue)
        save_queue(queue)

    return jsonify({"success": True, "deleted": deleted})

@app.route('/api/content-studio/topics', methods=['GET'])
def content_studio_topics():
    from content_studio import topic_catalog, writing_option_catalog
    return jsonify({"success": True, "topics": topic_catalog(), "writing_options": writing_option_catalog()})


@app.route('/api/content-studio/generate', methods=['POST'])
def content_studio_generate():
    from content_studio import generate_with_quality
    data = json_body()
    cfg = load_config()
    brand = str(data.get("brand") or "").strip().lower()
    topic = str(data.get("topic") or "room_sale").strip()
    keyword = str(data.get("keyword") or "").strip()
    supplied = data.get("apiKeys") or data.get("api_keys") or ""
    keys = supplied or cfg.get("gemini_api_keys") or cfg.get("gemini_api_key") or ""
    history = []
    try:
        history = [row.get("content") or "" for row in ActivityRepository().list_posted_links(limit=200)]
    except Exception:
        history = []
    try:
        result = generate_with_quality(brand, topic, keyword, keys, history=history,
            audience=str(data.get("audience") or ""), angle=str(data.get("angle") or ""),
            user_facts=str(data.get("verifiedFacts") or ""), attempts=data.get("attempts", 4),
            tone=str(data.get("tone") or "natural"), length=str(data.get("length") or "medium"), cta=str(data.get("cta") or "message"))
        return jsonify({"success": True, **result})
    except (ValueError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 422


@app.route('/api/content/generate', methods=['POST'])
def generate_content():
    """Proxy Content Hub AI requests without exposing the application key to the browser."""
    proxy_url = os.getenv("CONTENT_AI_PROXY_URL", "").strip()
    app_key = os.getenv("CONTENT_AI_APP_KEY", "").strip()
    data = json_body()
    prompt = data.get("prompt", "")
    if not proxy_url or not app_key:
        return jsonify({"error": "AI chưa được cấu hình. Hãy đặt CONTENT_AI_PROXY_URL và CONTENT_AI_APP_KEY."}), 503
    if not is_valid_http_url(proxy_url) or not isinstance(prompt, str) or not prompt or len(prompt) > 30_000:
        return jsonify({"error": "Yêu cầu tạo nội dung không hợp lệ."}), 400
    try:
        response = requests.post(
            proxy_url,
            headers={"Content-Type": "text/plain;charset=UTF-8"},
            data=json.dumps({"prompt": prompt, "key": app_key}),
            timeout=60,
        )
        response.raise_for_status()
        return jsonify(response.json())
    except (requests.RequestException, ValueError):
        return jsonify({"error": "Không thể kết nối dịch vụ AI. Hãy thử lại sau."}), 502

@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_error):
    return jsonify({"error": "Ảnh tối đa 10 MB."}), 413

# ---- Image Upload Endpoint for Manual Posting ----

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return jsonify({"error": "Không tìm thấy tệp gửi lên!"}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "Chưa chọn tệp ảnh!"}), 400
    extension = Path(secure_filename(file.filename)).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS or not file.mimetype.startswith("image/"):
        return jsonify({"error": "Chỉ nhận ảnh JPG, PNG, GIF hoặc WEBP."}), 400

    import uuid
    UPLOAD_DIR.mkdir(exist_ok=True)
    filepath = UPLOAD_DIR / f"{uuid.uuid4()}{extension}"
    file.save(filepath)
    return jsonify({"filepath": str(filepath)})

# ---- REST APIs for Account Management ----

# ---- Offline account vault.  This is deliberately separate from automation profiles. ----
VAULT_PLATFORM_LIMIT = 80
VAULT_TEXT_LIMIT = 2_000


def vault_payload(data, existing=None):
    """Validate the user-facing vault fields and retain no unexpected values."""
    platform = data.get("platform", existing.get("platform", "") if existing else "")
    account_name = data.get("account_name", existing.get("account_name", "") if existing else "")
    email = data.get("email", existing.get("email", "") if existing else "")
    password = data.get("password", existing.get("password", "") if existing else "")
    notes = data.get("notes", existing.get("notes", "") if existing else "")
    date_added = valid_vault_date(data.get("date_added", existing.get("date_added", "") if existing else ""))
    password_changed_at = valid_vault_date(data.get("password_changed_at", existing.get("password_changed_at", "") if existing else ""))
    if not all(isinstance(value, str) for value in (platform, account_name, email, password, notes)):
        return None, "Dữ liệu tài khoản không hợp lệ."
    values = [platform.strip(), account_name.strip(), email.strip(), password, notes.strip()]
    if not values[0] or not values[1] or not values[2]:
        return None, "Nền tảng, tên gợi nhớ và email/tên đăng nhập là bắt buộc."
    if len(values[0]) > VAULT_PLATFORM_LIMIT or any(len(value) > VAULT_TEXT_LIMIT for value in values[1:]):
        return None, "Một hoặc nhiều trường vượt giới hạn cho phép."
    if date_added is None or password_changed_at is None:
        return None, "Ngày cần theo định dạng YYYY-MM-DD."
    return {
        "platform": values[0], "account_name": values[1], "email": values[2],
        "password": password, "notes": values[4], "date_added": date_added,
        "password_changed_at": password_changed_at,
    }, None


def sanitize_vault_entry(entry: dict) -> dict:
    safe = dict(entry)
    safe["has_password"] = bool(entry.get("password"))
    safe.pop("password", None)
    return safe

@app.route('/api/vault', methods=['GET'])
def get_vault_accounts():
    query = request.args.get("q", "").strip().casefold()
    platform = request.args.get("platform", "").strip().casefold()
    entries = load_json_list(VAULT_FILE)
    if platform:
        entries = [entry for entry in entries if entry.get("platform", "").casefold() == platform]
    if query:
        entries = [entry for entry in entries if query in " ".join(str(entry.get(key, "")) for key in ("platform", "account_name", "email", "notes")).casefold()]
    return jsonify([sanitize_vault_entry(e) for e in entries])


@app.route('/api/vault', methods=['POST'])
def create_vault_account():
    fields, error = vault_payload(json_body())
    if error:
        return jsonify({"error": error}), 400
    entry = {
        "id": uuid.uuid4().hex[:12], **fields, "created_at": now_iso(), "updated_at": now_iso(),
        "password_history": ([{"at": now_iso(), "event": "Đã nhập mật khẩu"}] if fields["password"] else []),
    }
    entries = load_json_list(VAULT_FILE)
    entries.insert(0, entry)
    save_json_list(VAULT_FILE, entries, "account-vault-")
    return jsonify(sanitize_vault_entry(entry)), 201


@app.route('/api/vault/<entry_id>', methods=['PATCH'])
def update_vault_account(entry_id):
    entries = load_json_list(VAULT_FILE)
    entry = next((item for item in entries if item.get("id") == entry_id), None)
    if not entry:
        return jsonify({"error": "Không tìm thấy tài khoản."}), 404
    fields, error = vault_payload(json_body(), entry)
    if error:
        return jsonify({"error": error}), 400
    password_changed = fields["password"] != entry.get("password", "")
    entry.update(fields)
    entry["updated_at"] = now_iso()
    if password_changed:
        entry["password_changed_at"] = fields["password_changed_at"] or datetime.now().date().isoformat()
        entry.setdefault("password_history", []).insert(0, {"at": now_iso(), "event": "Đã cập nhật mật khẩu"})
    save_json_list(VAULT_FILE, entries, "account-vault-")
    return jsonify(sanitize_vault_entry(entry))


@app.route('/api/vault/<entry_id>', methods=['DELETE'])
def delete_vault_account(entry_id):
    entries = load_json_list(VAULT_FILE)
    remaining = [item for item in entries if item.get("id") != entry_id]
    if len(remaining) == len(entries):
        return jsonify({"error": "Không tìm thấy tài khoản."}), 404
    save_json_list(VAULT_FILE, remaining, "account-vault-")
    return jsonify({"success": True})

def _mask_proxy_value(value):
    raw = str(value or '').strip()
    if not raw:
        return ''
    return raw.rsplit('@', 1)[-1] if '@' in raw else raw


def _public_account(account):
    item = dict(account or {})
    item['proxy'] = _mask_proxy_value(item.get('proxy'))
    return item


@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    from utils import load_accounts
    return jsonify([_public_account(a) for a in load_accounts()])

@app.route('/api/accounts', methods=['POST'])
def add_account():
    from utils import load_accounts, save_accounts
    import uuid
    
    data = json_body()
    name = data.get('name', '').strip()
    acc_type = data.get('type', 'local').strip()
    profile_id = data.get('profile_path_or_id', '').strip()
    proxy = data.get('proxy', '').strip()
    
    if not name or len(name) > 100:
        return jsonify({"error": "Vui lòng nhập tên tài khoản!"}), 400
    if acc_type not in {"local", "gpm"}:
        return jsonify({"error": "Loại tài khoản không hợp lệ."}), 400
    if acc_type == "gpm" and not profile_id:
        return jsonify({"error": "Profile GPM cần Copy ID từ ứng dụng GPM."}), 400
    if len(profile_id) > 200 or len(proxy) > 300:
        return jsonify({"error": "Thông tin profile hoặc proxy quá dài."}), 400
        
    accounts = load_accounts()
    
    # Generate unique ID
    acc_id = str(uuid.uuid4())[:8]
    
    if acc_type == 'local' and not profile_id:
        profile_id = f"local_profile_{acc_id}"
        
    new_acc = {
        "id": acc_id,
        "name": name,
        "type": acc_type,
        "profile_path_or_id": profile_id,
        "proxy": proxy,
        "status": "Chưa xác thực",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    
    accounts.append(new_acc)
    if save_accounts(accounts):
        return jsonify(_public_account(new_acc))
    else:
        return jsonify({"error": "Không thể lưu tệp accounts.json!"}), 500

@app.route('/api/accounts/<id>', methods=['DELETE'])
def delete_account(id):
    from utils import load_accounts, save_accounts
    accounts = load_accounts()
    
    filtered_accounts = [a for a in accounts if a["id"] != id]
    if len(filtered_accounts) == len(accounts):
        return jsonify({"error": "Không tìm thấy tài khoản để xóa!"}), 404
        
    if save_accounts(filtered_accounts):
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Không thể lưu tệp accounts.json!"}), 500


@app.route('/api/accounts/batch-import', methods=['POST'])
def batch_import_accounts():
    """Nhập danh sách Profile Facebook đã chọn từ GPM vào danh sách Tài khoản đã lưu (accounts.json)."""
    from utils import load_accounts, save_accounts
    data = json_body()
    profiles = data.get('profiles', [])
    if not isinstance(profiles, list) or not profiles:
        return jsonify({"error": "Danh sách profile không hợp lệ."}), 400

    accounts = load_accounts()
    existing_ids = {str(a.get("profile_path_or_id")).strip() for a in accounts if a.get("profile_path_or_id")}
    existing_ids.update({str(a.get("id")).strip() for a in accounts if a.get("id")})

    added_profiles = []
    for p in profiles:
        pid = str(p.get('id', '')).strip()
        pname = str(p.get('name', '')).strip() or pid
        raw_proxy = ''  # GPM owns proxy configuration; never trust/store client-supplied proxy credentials.
        browser_type = str(p.get('browser_type', 'Chrome')).strip()

        if not pid or pid in existing_ids:
            continue

        new_acc = {
            "id": pid,
            "name": pname,
            "type": "gpm",
            "profile_path_or_id": pid,
            "proxy": raw_proxy,
            "browser_type": browser_type,
            "status": "Sẵn sàng (Facebook GPM)",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        accounts.append(new_acc)
        existing_ids.add(pid)
        added_profiles.append(new_acc)

    if added_profiles:
        if save_accounts(accounts):
            return jsonify({
                "success": True,
                "added_count": len(added_profiles),
                "total_accounts": len(accounts),
                "message": f"Đã thêm {len(added_profiles)} Profile Facebook vào danh sách lưu thành công!"
            })
        else:
            return jsonify({"error": "Không thể ghi tệp accounts.json"}), 500

    return jsonify({
        "success": True,
        "added_count": 0,
        "total_accounts": len(accounts),
        "message": "Các profile đã chọn đều đã tồn tại trong danh sách tài khoản đã lưu."
    })


@app.route('/api/gpm/profiles', methods=['GET'])
def api_gpm_profiles():
    """Kéo danh sách Profile trực tiếp từ GPMLogin REST API v3 (mặc định port 19995)."""
    from utils import fetch_gpm_profiles
    gpm_url = request.args.get('gpm_api_url', '').strip() or None
    page = max(1, request.args.get('page', 1, type=int))
    page_size = max(1, min(request.args.get('page_size', 100, type=int), 500))
    result = fetch_gpm_profiles(gpm_api_url=gpm_url, page=page, page_size=page_size)
    safe_profiles = []
    for profile in result.get("profiles", []):
        item = dict(profile)
        raw_proxy = item.pop("raw_proxy", "")
        item.pop("proxy", None)
        item["proxy_hint"] = _mask_proxy_value(raw_proxy)
        safe_profiles.append(item)
    result = dict(result)
    result["profiles"] = safe_profiles
    return jsonify(result)


@app.route('/api/gpm/status', methods=['GET'])
def api_gpm_status():
    """Kiểm tra kết nối và số lượng Profile trực tiếp trong GPMLogin."""
    from utils import fetch_gpm_profiles
    gpm_url = request.args.get('gpm_api_url', '').strip() or None
    result = fetch_gpm_profiles(gpm_api_url=gpm_url, page=1, page_size=1)
    return jsonify({
        "connected": result.get("connected", False),
        "total_profiles": result.get("total", 0),
        "base_url": result.get("base_url", "http://127.0.0.1:19995")
    })


@app.route('/api/profiles/open-browser', methods=['POST'])
def open_profile_browser():
    """Khởi chạy Profile GPM hoặc Local Profile được chỉ định và mở trực tiếp link (Group/Page)."""
    from utils import resolve_account, load_accounts
    data = json_body()
    account_id = data.get('accountId', '').strip()
    target_url = data.get('url', 'https://www.facebook.com/').strip()
    gpm_api_url = data.get('gpmApiUrl', 'http://127.0.0.1:19995').strip()

    account = resolve_account(account_id, gpm_api_url)
    if not account:
        accounts = load_accounts()
        account = accounts[0] if accounts else None

    if not account:
        return jsonify({"error": "Chưa có tài khoản nào được cấu hình hoặc không thể kết nối GPM."}), 400

    def start_browser_background(acc, url, gpm_url):
        try:
            import time
            from playwright.sync_api import sync_playwright
            from utils import launch_browser
            with sync_playwright() as p:
                browser_obj, context, page = launch_browser(acc, p, gpm_url)
                if page:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                while True:
                    try:
                        time.sleep(1)
                        if not context.pages:
                            break
                    except Exception:
                        break
        except Exception as e:
            print(f"Error opening profile browser: {e}")

    threading.Thread(target=start_browser_background, args=(account, target_url, gpm_api_url), daemon=True).start()
    return jsonify({
        "success": True,
        "message": f"Đang khởi chạy Profile '{account.get('name')}' và mở liên kết: {target_url}",
        "profile": account.get("name")
    })


@app.route('/api/2fa', methods=['POST'])
def generate_2fa():
    data = json_body()
    secret = data.get('secret', '').strip()
    if not secret:
        return jsonify({"error": "Vui lòng nhập khóa bảo mật 2FA!"}), 400
    try:
        secret = secret.replace(" ", "").upper()
        import hmac
        import hashlib
        import time
        import base64
        import struct
        
        missing_padding = len(secret) % 8
        if missing_padding:
            secret += '=' * (8 - missing_padding)
            
        key = base64.b32decode(secret)
        counter = struct.pack(">Q", int(time.time() / 30))
        mac = hmac.new(key, counter, hashlib.sha1).digest()
        offset = mac[-1] & 0x0f
        binary = struct.unpack(">I", mac[offset:offset+4])[0] & 0x7fffffff
        token = str(binary % 1000000).zfill(6)
        return jsonify({"token": token})
    except Exception as e:
        return jsonify({"error": f"Lỗi tính toán mã 2FA: {str(e)}"}), 400

POSTED_LINKS_FILE = str(DATA_DIR / "posted_links.json")

@app.route('/api/posted-links', methods=['GET', 'DELETE'])
def api_posted_links():
    if request.method == 'DELETE':
        try:
            try:
                from repositories.activity_repo import ActivityRepository
                ActivityRepository().clear_posted_links()
            except Exception:
                pass
            with open(POSTED_LINKS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
            return jsonify({"status": "cleared", "count": 0})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Ưu tiên 1: Đọc từ SQLite ActivityRepository (nguồn chuẩn của hệ thống)
    try:
        from repositories.activity_repo import ActivityRepository
        try:
            limit = max(1, min(int(request.args.get("limit", 30)), 200))
        except ValueError:
            return jsonify({"error": "limit không hợp lệ"}), 400
        state_filter = (request.args.get("state") or "").strip().lower()
        fetch_limit = 200 if state_filter else limit
        db_items = ActivityRepository().list_posted_links(limit=fetch_limit)
        if state_filter:
            db_items = [r for r in db_items if str(r.get("publish_state") or "").lower() == state_filter][:limit]
        formatted = []
        for r in db_items:
            content_str = r.get("content") or ""
            preview = (content_str[:120] + "...") if len(content_str) > 120 else content_str
            formatted.append({
                "id": str(r.get("id", "")),
                "url": r.get("url", ""),
                "target": r.get("target", ""),
                "content": content_str,
                "content_preview": preview,
                "note": r.get("note", ""),
                "status": r.get("status") or r.get("note") or "Đã xuất bản",
                "account_id": r.get("account_id", ""),
                "url_type": r.get("url_type", "unknown"),
                "publish_state": r.get("publish_state", "unknown"),
                "posted_at": r.get("created_at", ""),
            })
        return jsonify(formatted)
    except Exception as dbe:
        print(f"⚠️ Không thể đọc posted_links từ DB: {dbe}")

    # Fallback 2: Đọc từ JSON file nếu DB chưa có
    if not os.path.exists(POSTED_LINKS_FILE):
        return jsonify([])
    try:
        with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return jsonify(data if isinstance(data, list) else [])
    except Exception:
        return jsonify([])

JOINED_GROUPS_FILE = str(DATA_DIR / "joined_groups.json")

@app.route('/api/joined-groups', methods=['GET', 'DELETE'])
def api_joined_groups():
    canonical_file = str(DATA_DIR / "joined_groups.json")
    if request.method == 'DELETE':
        try:
            if os.path.abspath(JOINED_GROUPS_FILE) == os.path.abspath(canonical_file):
                GroupRepository().clear_joined_groups()
            with open(JOINED_GROUPS_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
            return jsonify({"status": "cleared", "count": 0})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if os.path.abspath(JOINED_GROUPS_FILE) != os.path.abspath(canonical_file):
        try:
            with open(JOINED_GROUPS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data if isinstance(data, list) else [])
        except Exception:
            return jsonify([])
    try:
        return jsonify(GroupRepository().list_joined_groups())
    except Exception as ge:
        print(f"⚠️ Không thể đọc joined_groups từ SQLite: {ge}")
        try:
            with open(JOINED_GROUPS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify(data if isinstance(data, list) else [])
        except Exception:
            return jsonify([])

@app.route('/api/ai/spin', methods=['POST'])
def api_ai_spin():
    from ai_spinner import generate_unique_variant_with_evidence, spin_comment, generate_interact_comments
    data = json_body()
    content = (data.get("content") or data.get("text") or "").strip()
    supplied_keys = data.get("apiKeys") or data.get("api_keys") or data.get("apiKey") or data.get("api_key") or ""
    cfg = load_config()
    api_key = supplied_keys or cfg.get("gemini_api_keys") or cfg.get("gemini_api_key", "")
    mode = data.get("mode", "post")
    brand_key = data.get("brandKey") or data.get("brand") or ""
    # Manual rewrite returns clean copy for review/editing. The executor adds the
    # mandatory project signature once, immediately before the Facebook composer.
    include_signature = bool(data.get("includeSignature", False))
    if not content and mode != "interact":
        return jsonify({"error": "Vui lòng nhập nội dung cần xào."}), 400
    try:
        if mode == "comment":
            spun = spin_comment(content, api_key)
        elif mode == "interact":
            spun = generate_interact_comments(content, api_key)
        else:
            result = generate_unique_variant_with_evidence(
                content, api_key, brand_key=brand_key, include_signature=include_signature,
                signature_mode="linkless"
            )
            return jsonify({
                "success": True,
                "spun_content": result["content"],
                "spinned": result["content"],
                **{key: value for key, value in result.items() if key != "content"}
            })
        return jsonify({
            "success": True,
            "spun_content": spun,
            "spinned": spun,
            "changed": spun.strip() != content.strip()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/brands', methods=['GET'])
def api_brands():
    from brand_profiles import BRAND_LINKLESS_SIGNATURES
    return jsonify({"success": True, "brands": BRAND_LINKLESS_SIGNATURES})

@app.route('/api/photos/list', methods=['GET'])
def api_photos_list():
    import tempfile
    folder = request.args.get("folder", "uploads").strip()
    target_dir = Path(folder).resolve()

    # Kiểm tra allowlist chống path traversal
    cfg = load_config()
    allowed_dirs = [
        UPLOAD_DIR.resolve(),
        (BASE_DIR / "photos").resolve(),
        (BASE_DIR / "uploads").resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    cfg_photo = cfg.get("photo_folder", "").strip()
    if cfg_photo:
        try:
            allowed_dirs.append(Path(cfg_photo).resolve())
        except Exception:
            pass

    is_allowed = any(
        target_dir == allowed or target_dir.is_relative_to(allowed)
        for allowed in allowed_dirs
    )
    if not is_allowed:
        return jsonify({"exists": False, "count": 0, "photos": [], "error": "Thư mục không được phép truy cập."}), 403

    if not target_dir.exists() or not target_dir.is_dir():
        return jsonify({"exists": False, "count": 0, "photos": []})
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    photos = []
    for p in target_dir.iterdir():
        if p.is_file() and p.suffix.lower() in valid_exts:
            photos.append(p.name)
    return jsonify({
        "exists": True,
        "folder": str(target_dir),
        "count": len(photos),
        "photos": photos[:50]
    })

# /api/run and /api/jobs routes are handled by api.jobs.jobs_bp

# ===================== PAGE SCHEDULER API =====================

@app.route('/api/page/config', methods=['GET'])
def get_page_config():
    config = load_config()
    # Mask token safely (never leak short token)
    token = config.get("page_access_token", "")
    if token:
        masked = f"...{token[-4:]}" if len(token) >= 4 else "(đã cấu hình)"
    else:
        masked = "(chưa cấu hình)"
    return jsonify({
        "page_id": config.get("page_id", ""),
        "page_name": config.get("page_name", ""),
        "token_masked": masked,
        "has_token": bool(token),
        "sheets_csv_url": config.get("sheets_csv_url", ""),
        "scheduler_interval_minutes": config.get("scheduler_interval_minutes", 5),
        "post_delay_min_minutes": config.get("post_delay_min_minutes", 0),
        "post_delay_max_minutes": config.get("post_delay_max_minutes", 0),
    })

@app.route('/api/page/token', methods=['POST'])
def save_page_token():
    from fb_page_api import validate_token
    data = json_body()
    token = data.get("token", "").strip()
    if not token:
        return jsonify({"error": "Token không được để trống"}), 400

    ok, info = validate_token(token)
    if not ok:
        return jsonify({"error": f"Token không hợp lệ: {info}"}), 400

    config = load_config()
    config["page_access_token"] = token
    config["page_id"] = info.get("id", "")
    config["page_name"] = info.get("name", "")
    save_config(config)
    return jsonify({"success": True, "page_name": info.get("name"), "page_id": info.get("id")})

@app.route('/api/page/sheets', methods=['POST'])
def save_sheets_url():
    data = json_body()
    url = data.get("url", "").strip()
    try:
        interval = int(data.get("interval", 5))
        post_delay_min = int(data.get("post_delay_min", 0))
        post_delay_max = int(data.get("post_delay_max", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Chu kỳ hoặc giãn cách không hợp lệ."}), 400
    if not is_valid_http_url(url):
        return jsonify({"error": "Sheets URL phải là HTTPS hợp lệ."}), 400
    if interval not in {5, 10, 15, 30, 60}:
        return jsonify({"error": "Chu kỳ chỉ có thể là 5, 10, 15, 30 hoặc 60 phút."}), 400
    delay_is_disabled = post_delay_min == 0 and post_delay_max == 0
    if not delay_is_disabled and (post_delay_min < 5 or post_delay_max < post_delay_min or post_delay_max > 180):
        return jsonify({"error": "Giãn cách ngẫu nhiên phải tối thiểu 5 phút, tối đa 180 phút và có giá trị lớn hơn hoặc bằng mức tối thiểu."}), 400
    config = load_config()
    config["sheets_csv_url"] = url
    config["scheduler_interval_minutes"] = interval
    config["post_delay_min_minutes"] = post_delay_min
    config["post_delay_max_minutes"] = post_delay_max
    save_config(config)
    return jsonify({"success": True})

@app.route('/api/page/preview', methods=['POST'])
def preview_sheets():
    from scheduler import preview_sheets as _preview
    data = json_body()
    url = data.get("url", "").strip()
    if not url:
        config = load_config()
        url = config.get("sheets_csv_url", "")
    if not url:
        return jsonify({"error": "Chưa có Sheets URL"}), 400
    rows = _preview(url)
    return jsonify({"rows": rows})

@app.route('/api/scheduler/status', methods=['GET'])
def scheduler_status():
    from scheduler import get_scheduler_status
    return jsonify(get_scheduler_status())

@app.route('/api/scheduler/start', methods=['POST'])
def start_sched():
    from scheduler import start_scheduler
    config = load_config()
    interval = config.get("scheduler_interval_minutes", 5)
    ok = start_scheduler(interval)
    if ok:
        config["scheduler_running"] = True
        save_config(config)
    return jsonify({"success": ok})

@app.route('/api/scheduler/stop', methods=['POST'])
def stop_sched():
    from scheduler import stop_scheduler
    ok = stop_scheduler()
    config = load_config()
    config["scheduler_running"] = False
    save_config(config)
    return jsonify({"success": ok})

@app.route('/api/scheduler/run-now', methods=['POST'])
def run_now():
    """Manually trigger one scheduler job run immediately."""
    from scheduler import run_scheduler_job
    try:
        run_scheduler_job()
        return jsonify({"success": True, "message": "Đã chạy thủ công xong!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scheduler/logs', methods=['GET'])
def get_logs():
    from scheduler import get_log_tail
    lines = max(1, min(request.args.get("lines", 80, type=int) or 80, 500))
    return jsonify({"logs": get_log_tail(lines)})

@app.route('/api/page/post-now', methods=['POST'])
def post_now_api():
    """Manually post a single post to a page via API (not scheduled)."""
    from fb_page_api import post_to_page
    data = json_body()
    config = load_config()
    token = config.get("page_access_token", "")
    page_id = data.get("page_id") or config.get("page_id", "")
    content = data.get("content", "").strip()
    image_url = data.get("image_url", "").strip()

    if not token:
        return jsonify({"error": "Chưa có Page Access Token. Hãy cấu hình ở tab Page Scheduler!"}), 400
    if not page_id:
        return jsonify({"error": "Chưa có Page ID"}), 400
    if not content:
        return jsonify({"error": "Nội dung không được để trống"}), 400
    if len(content) > 60_000:
        return jsonify({"error": "Nội dung quá dài."}), 400
    if image_url and not is_valid_http_url(image_url):
        return jsonify({"error": "Link ảnh phải là HTTPS hợp lệ."}), 400

    ok, result = post_to_page(page_id, token, content, image_url or None)
    if ok:
        return jsonify({"success": True, "post_id": result.get("post_id")})
    else:
        return jsonify({"error": result}), 400

@app.route('/api/backup', methods=['POST'])
def api_backup_database():
    try:
        backup_file = backup_db()
        return jsonify({"success": True, "backup_file": str(backup_file), "message": "Sao lưu cơ sở dữ liệu SQLite thành công!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/group-catalog/defaults', methods=['GET'])
def api_default_group_catalog():
    from services.default_catalog import load_default_group_rows
    rows = load_default_group_rows()
    return jsonify({'count': len(rows), 'groups': rows})

@app.route('/api/profile-presets/default', methods=['GET'])
def api_default_profile_preset():
    from services.default_catalog import DEFAULT_PROFILE_NAMES
    accounts = {str(a.get('name') or ''): _public_account(a) for a in load_accounts()}
    profiles = [accounts[name] for name in DEFAULT_PROFILE_NAMES if name in accounts]
    missing = [name for name in DEFAULT_PROFILE_NAMES if name not in accounts]
    return jsonify({'name': '8 Profile Test Hue', 'profiles': profiles, 'missing': missing})

@app.route('/api/workflows/tasks', methods=['GET'])
def api_workflow_tasks():
    from repositories.workflow_repo import WorkflowRepository
    states = [x for x in request.args.get('states', '').split(',') if x]
    rows = WorkflowRepository().list_tasks(job_id=request.args.get('job_id') or None, states=states or None, limit=500)
    accounts = load_accounts()
    names = {}
    for account in accounts:
        display = str(account.get('name') or '').strip()
        for key in (account.get('id'), account.get('profile_path_or_id')):
            if key and display:
                names[str(key)] = display
    for row in rows:
        row['profile_name'] = names.get(str(row.get('profile_id') or ''), str(row.get('profile_id') or ''))
    return jsonify({'count': len(rows), 'tasks': rows})

@app.route('/api/workflows/profile-performance', methods=['GET'])
def api_workflow_profile_performance():
    from repositories.workflow_repo import WorkflowRepository
    rows = WorkflowRepository().profile_posting_performance(limit=200)
    names = {}
    for account in load_accounts():
        display = str(account.get('name') or '').strip()
        for key in (account.get('id'), account.get('profile_path_or_id')):
            if key and display:
                names[str(key)] = display
    name_counts = {}
    for account in load_accounts():
        display = str(account.get('name') or '').strip()
        if display:
            name_counts[display] = name_counts.get(display, 0) + 1
    for row in rows:
        row['profile_name'] = names.get(str(row.get('profile_id') or ''), str(row.get('profile_id') or ''))
        row['duplicate_profile_name'] = name_counts.get(row['profile_name'], 0) > 1
    summary = WorkflowRepository().system_posting_summary()
    summary['duplicate_profile_names'] = sorted([name for name, count in name_counts.items() if count > 1])
    return jsonify({'count': len(rows), 'profiles': rows, 'summary': summary})

@app.route('/api/workflows/tasks/<task_id>/events', methods=['GET'])
def api_workflow_events(task_id):
    from repositories.workflow_repo import WorkflowRepository
    return jsonify({'task_id': task_id, 'events': WorkflowRepository().list_events(task_id)})

if __name__ == '__main__':
    # All routes are registered before the development server starts.
    config = load_config()
    if config.get("scheduler_running", False):
        from scheduler import start_scheduler
        start_scheduler(config.get("scheduler_interval_minutes", 5))

    port = int(os.getenv("FB_AUTOMATION_PORT", "5000"))
    print(f"Starting Facebook Automation Dashboard v{APP_VERSION} from {BASE_DIR.resolve()}...")
    print(f"Access the dashboard at: http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port)
