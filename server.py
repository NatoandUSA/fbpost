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
UPLOAD_DIR = Path("uploads").resolve()
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_COMMANDS = {"auth", "group", "page", "thread", "interact", "scrape"}

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
    fd, temp_path = tempfile.mkstemp(prefix="config-", suffix=".json", dir=".")
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

STATE_FILE = "state.json"

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/status', methods=['GET'])
def get_status():
    is_authenticated = os.path.exists(STATE_FILE)
    return jsonify({"authenticated": is_authenticated})

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
        if account_id:
            base_cmd.extend(["--account-id", account_id])
        if gpm_api:
            base_cmd.extend(["--gpm-api", gpm_api])

        if cmd == 'auth':
            full_cmd = base_cmd + ["auth"]
            process = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield line
            process.wait()
            return

        if cmd == 'interact':
            limit = max(1, min(int(data.get('limit', 5)), 50))
            comments = data.get('comments', '')
            full_cmd = base_cmd + ["interact", "--limit", str(limit)]
            if comments:
                full_cmd.extend(["--comments", comments])
                
            process = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield line
            process.wait()
            return

        if cmd == 'scrape':
            target_url = data.get('target', '').strip()
            limit = max(1, min(int(data.get('limit', 50)), 200))
            if not target_url:
                yield "Error: No target URL provided for scraping.\n"
                return
            full_cmd = base_cmd + ["scrape", target_url, "--limit", str(limit)]
            process = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield line
            process.wait()
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
                
            process = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield line
            process.wait()
            
            if i < total - 1:
                delay = random.randint(30, 60)
                yield f"\n[Anti-Spam] Waiting {delay} seconds before next post...\n"
                for sec in range(delay, 0, -1):
                    if sec % 10 == 0 or sec <= 5:
                        yield f"... {sec}s remaining\n"
                    time.sleep(1)
                    
        yield "\n[Batch processing completed successfully!]\n"
        
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
    except (TypeError, ValueError):
        return jsonify({"error": "Chu kỳ không hợp lệ."}), 400
    if not is_valid_http_url(url):
        return jsonify({"error": "Sheets URL phải là HTTPS hợp lệ."}), 400
    if interval not in {5, 10, 15, 30, 60}:
        return jsonify({"error": "Chu kỳ chỉ có thể là 5, 10, 15, 30 hoặc 60 phút."}), 400
    config = load_config()
    config["sheets_csv_url"] = url
    config["scheduler_interval_minutes"] = interval
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
