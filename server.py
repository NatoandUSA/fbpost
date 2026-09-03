import sys
import os
import json
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, request, jsonify, Response, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static')
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

CONFIG_FILE = "config.json"
QUEUE_FILE = "publication_queue.json"
CAMPAIGNS_FILE = "campaigns.json"
ACTIVITY_LOG_FILE = "profile_activity.json"
GROUPS_FILE = "group_registry.json"
MANUAL_GROUP_QUEUE_FILE = "manual_group_queue.json"
VAULT_FILE = "account_vault.json"
UPLOAD_DIR = Path("uploads").resolve()
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_COMMANDS = {"auth", "group", "page", "thread", "interact", "scrape", "comment"}
APP_VERSION = "5.5.1"
BUILD_TIME = "2026-09-04 00:07"


def app_build_info():
    """Return a local build identity so the UI can detect a mismatched server."""
    source_mtime = datetime.fromtimestamp(Path(__file__).stat().st_mtime, timezone.utc)
    return {
        "version": APP_VERSION,
        "built_at": BUILD_TIME,
        "source_updated_at": source_mtime.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "group_manager_available": True,
    }

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def save_config(data):
    config_directory = str(Path(CONFIG_FILE).resolve().parent)
    fd, temp_path = tempfile.mkstemp(prefix="config-", suffix=".json", dir=config_directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, CONFIG_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def load_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            queue = json.load(f)
        return queue if isinstance(queue, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def save_queue(queue):
    queue_directory = str(Path(QUEUE_FILE).resolve().parent)
    fd, temp_path = tempfile.mkstemp(prefix="publication-queue-", suffix=".json", dir=queue_directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, QUEUE_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def load_campaigns():
    if not os.path.exists(CAMPAIGNS_FILE):
        return []
    try:
        with open(CAMPAIGNS_FILE, "r", encoding="utf-8") as f:
            campaigns = json.load(f)
        return campaigns if isinstance(campaigns, list) else []
    except (OSError, json.JSONDecodeError):
        return []

def save_campaigns(campaigns):
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
        with open("scheduler_state.json", "r", encoding="utf-8") as f:
            value = json.load(f)
        posted = value.get("posted", {}) if isinstance(value, dict) else {}
        return len(posted) if isinstance(posted, dict) else 0
    except (OSError, json.JSONDecodeError):
        return 0


STATE_FILE = "state.json"
AUTH_STATUS_FILE = "auth_status.json"

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/status', methods=['GET'])
def get_status():
    is_authenticated = os.path.exists(STATE_FILE) or os.path.exists(AUTH_STATUS_FILE)
    return jsonify({"authenticated": is_authenticated})


@app.route('/api/app-info', methods=['GET'])
def get_app_info():
    return jsonify(app_build_info())


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
    return jsonify(load_queue())

@app.route('/api/queue', methods=['POST'])
def create_queue_item():
    data = json_body()
    target = data.get("target", "").strip()
    content = data.get("content", "").strip()
    image_url = data.get("image_url", "").strip()
    campaign_id = data.get("campaign_id", "").strip()
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
    item["state"] = "approved"
    item["updated_at"] = now_iso()
    item.setdefault("audit", []).append({"at": now_iso(), "event": "approved"})
    save_queue(queue)
    return jsonify(item)

@app.route('/api/queue/<item_id>/cancel', methods=['POST'])
def cancel_queue_item(item_id):
    queue = load_queue()
    item = next((entry for entry in queue if entry.get("id") == item_id), None)
    if not item:
        return jsonify({"error": "Không tìm thấy mục trong hàng đợi."}), 404
    if item.get("state") == "published":
        return jsonify({"error": "Không thể hủy mục đã đăng."}), 409
    item["state"] = "cancelled"
    item["updated_at"] = now_iso()
    item.setdefault("audit", []).append({"at": now_iso(), "event": "cancelled"})
    save_queue(queue)
    return jsonify(item)

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


@app.route('/api/vault', methods=['GET'])
def get_vault_accounts():
    query = request.args.get("q", "").strip().casefold()
    platform = request.args.get("platform", "").strip().casefold()
    entries = load_json_list(VAULT_FILE)
    if platform:
        entries = [entry for entry in entries if entry.get("platform", "").casefold() == platform]
    if query:
        entries = [entry for entry in entries if query in " ".join(str(entry.get(key, "")) for key in ("platform", "account_name", "email", "notes")).casefold()]
    return jsonify(entries)


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
    return jsonify(entry), 201


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
    return jsonify(entry)


@app.route('/api/vault/<entry_id>', methods=['DELETE'])
def delete_vault_account(entry_id):
    entries = load_json_list(VAULT_FILE)
    remaining = [item for item in entries if item.get("id") != entry_id]
    if len(remaining) == len(entries):
        return jsonify({"error": "Không tìm thấy tài khoản."}), 404
    save_json_list(VAULT_FILE, remaining, "account-vault-")
    return jsonify({"success": True})

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    from utils import load_accounts
    return jsonify(load_accounts())

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
        "status": "Chưa xác thực"
    }
    
    accounts.append(new_acc)
    if save_accounts(accounts):
        return jsonify(new_acc)
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


@app.route('/api/profiles/open-browser', methods=['POST'])
def open_profile_browser():
    """Khởi chạy Profile GPM hoặc Local Profile được chỉ định và mở trực tiếp link (Group/Page)."""
    from utils import load_accounts
    data = json_body()
    account_id = data.get('accountId', '').strip()
    target_url = data.get('url', 'https://www.facebook.com/').strip()
    gpm_api_url = data.get('gpmApiUrl', 'http://127.0.0.1:19995').strip()

    accounts = load_accounts()
    account = None
    if account_id:
        account = next((a for a in accounts if a.get("id") == account_id or a.get("name") == account_id or a.get("profile_path_or_id") == account_id), None)

    if not account and accounts:
        account = accounts[0]

    if not account:
        return jsonify({"error": "Chưa có tài khoản nào được cấu hình trong kho tài khoản."}), 400

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

@app.route('/api/run', methods=['POST'])
def run_script():
    import random
    import time
    
    data = json_body()
    cmd = data.get('command')
    account_id = data.get('accountId')
    gpm_api = data.get('gpmApiUrl')
    
    if cmd not in ALLOWED_COMMANDS:
        return jsonify({"error": "Tác vụ không hợp lệ."}), 400
    if account_id and not isinstance(account_id, str):
        return jsonify({"error": "Account ID không hợp lệ."}), 400
    if gpm_api and (not isinstance(gpm_api, str) or urlparse(gpm_api).hostname not in {"127.0.0.1", "localhost"}):
        return jsonify({"error": "GPM API chỉ được phép chạy trên máy cục bộ."}), 400

    # Feeling and checkin settings
    feeling = data.get('feeling', False)
    checkin = data.get('checkin', False)
    
    def generate():
        base_cmd = [sys.executable, "main.py"]
        process_environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

        def start_cli_process(command):
            return subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=process_environment,
            )

        if account_id:
            base_cmd.extend(["--account-id", account_id])
        if gpm_api:
            base_cmd.extend(["--gpm-api", gpm_api])

        if cmd == 'auth':
            full_cmd = base_cmd + ["auth"]
            process = start_cli_process(full_cmd)
            for line in iter(process.stdout.readline, ''):
                yield line
            outcome = "finished" if process.wait() == 0 else "failed"
            if outcome == "failed":
                # Avoid presenting an old successful login as a live GPM connection.
                try:
                    os.unlink(AUTH_STATUS_FILE)
                except FileNotFoundError:
                    pass
            yield f"RUN_RESULT:{outcome}\n"
            record_profile_activity(account_id, "auth", outcome=outcome)
            return

        if cmd == 'interact':
            limit = max(1, min(int(data.get('limit', 5)), 50))
            comments = data.get('comments', '')
            full_cmd = base_cmd + ["interact", "--limit", str(limit)]
            if comments:
                full_cmd.extend(["--comments", comments])
                
            process = start_cli_process(full_cmd)
            for line in iter(process.stdout.readline, ''):
                yield line
            outcome = "finished" if process.wait() == 0 else "failed"
            yield f"RUN_RESULT:{outcome}\n"
            record_profile_activity(account_id, "interact", target="newsfeed", content=comments, outcome=outcome)
            return

        if cmd == 'scrape':
            target_url = data.get('target', '').strip()
            limit = max(1, min(int(data.get('limit', 50)), 200))
            if not target_url:
                yield "Error: No target URL provided for scraping.\n"
                return
            full_cmd = base_cmd + ["scrape", target_url, "--limit", str(limit)]
            process = start_cli_process(full_cmd)
            for line in iter(process.stdout.readline, ''):
                yield line
            outcome = "finished" if process.wait() == 0 else "failed"
            yield f"RUN_RESULT:{outcome}\n"
            record_profile_activity(account_id, "scrape", target=target_url, outcome=outcome)
            return

        if cmd == 'comment':
            like_post = data.get('likePost', True)
            comment_tasks = data.get('tasks', [])
            if not comment_tasks:
                targets = data.get('targets', [])
                content = data.get('content', '')
                comment_tasks = [{'target': t, 'content': content} for t in targets]

            if not comment_tasks:
                yield "Error: Chưa có danh sách link bài viết hoặc nội dung comment.\n"
                return

            total = len(comment_tasks)
            batch_failed = False
            for i, task in enumerate(comment_tasks):
                target_url = task.get('target', '').strip()
                comment_text = task.get('content', '').strip()
                if not target_url or not comment_text:
                    continue

                yield f"\n========== [Bài viết {i+1}/{total}] ==========\n"
                yield f"Đang mở bài viết: {target_url}\n"

                full_cmd = base_cmd + ["comment", target_url, comment_text]
                if like_post:
                    full_cmd.append("--like")

                process = start_cli_process(full_cmd)
                for line in iter(process.stdout.readline, ''):
                    yield line
                outcome = "finished" if process.wait() == 0 else "failed"
                if outcome == "failed":
                    batch_failed = True
                record_profile_activity(account_id, "comment", target=target_url, content=comment_text, outcome=outcome)

                if i < total - 1:
                    delay = random.randint(25, 45)
                    yield f"\n[Anti-Spam] Nghỉ {delay} giây trước khi chuyển bài viết tiếp theo...\n"
                    for sec in range(delay, 0, -1):
                        if sec % 10 == 0 or sec <= 5:
                            yield f"... còn {sec}s\n"
                        time.sleep(1)

            yield f"RUN_RESULT:{'failed' if batch_failed else 'finished'}\n"
            yield "\n[Hoàn thành bình luận danh sách bài viết!]\n" if not batch_failed else "\n[Hoàn thành với một số lỗi!]\n"
            return

        # Support both old format (targets array + single content) and new format (tasks array of dicts)
        tasks = data.get('tasks', [])
        if not tasks:
            targets = data.get('targets', [])
            content = data.get('content', '')
            tasks = [{'target': t, 'content': content, 'image': None} for t in targets]
            
        if not tasks:
            yield "Error: No tasks or targets provided.\n"
            return
            
        if not isinstance(tasks, list) or len(tasks) > 100:
            yield "Error: Batch must contain between 1 and 100 tasks.\n"
            return
        total = len(tasks)
        batch_failed = False
        for i, task in enumerate(tasks):
            if not isinstance(task, dict):
                continue
            target = task.get('target', '').strip()
            content = task.get('content', '').strip()
            image = task.get('image', None)
            
            # Extract task-specific parameters, falling back to global ones
            task_feeling = task.get('feeling', feeling)
            task_checkin = task.get('checkin', checkin)
            
            if not target:
                continue
            if len(target) > 2_000 or len(content) > 60_000:
                yield f"Error: Target {i+1} exceeds the allowed size.\n"
                continue
            if image and not is_uploaded_image(image):
                yield f"Error: Target {i+1} has an invalid image path.\n"
                continue
                
            yield f"\n========== [Target {i+1}/{total}] ==========\n"
            yield f"Posting to: {target}\n"
            
            full_cmd = base_cmd + [cmd, target, content]
            if image:
                full_cmd.extend(["--image", image])
            if task_feeling:
                full_cmd.append("--feeling")
            if task_checkin:
                full_cmd.append("--checkin")
                
            process = start_cli_process(full_cmd)
            for line in iter(process.stdout.readline, ''):
                yield line
            outcome = "finished" if process.wait() == 0 else "failed"
            if outcome == "failed":
                batch_failed = True
            record_profile_activity(account_id, cmd, target=target, content=content, outcome=outcome)
            
            if i < total - 1:
                delay = random.randint(30, 60)
                yield f"\n[Anti-Spam] Waiting {delay} seconds before next post...\n"
                for sec in range(delay, 0, -1):
                    if sec % 10 == 0 or sec <= 5:
                        yield f"... {sec}s remaining\n"
                    time.sleep(1)
                    
        yield f"RUN_RESULT:{'failed' if batch_failed else 'finished'}\n"
        yield "\n[Batch processing completed successfully!]\n" if not batch_failed else "\n[Batch processing completed with errors.]\n"
        
    return Response(generate(), mimetype='text/plain')

# ===================== PAGE SCHEDULER API =====================

@app.route('/api/page/config', methods=['GET'])
def get_page_config():
    config = load_config()
    # Never expose full token to frontend — mask it
    token = config.get("page_access_token", "")
    masked = f"...{token[-8:]}" if len(token) > 8 else ("(chưa cấu hình)" if not token else token)
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

if __name__ == '__main__':
    # All routes are registered before the development server starts.
    config = load_config()
    if config.get("scheduler_running", False):
        from scheduler import start_scheduler
        start_scheduler(config.get("scheduler_interval_minutes", 5))

    print("Starting Facebook Automation Dashboard...")
    print("Access the dashboard at: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000)
