import sys
import os
import json
import subprocess
from flask import Flask, request, jsonify, Response, send_from_directory

app = Flask(__name__, static_folder='static')

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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

# ---- Image Upload Endpoint for Manual Posting ----

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return jsonify({"error": "Không tìm thấy tệp gửi lên!"}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "Chưa chọn tệp ảnh!"}), 400
    if file:
        import uuid
        upload_dir = os.path.abspath("uploads")
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        return jsonify({"filepath": filepath})

# ---- REST APIs for Account Management ----

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    from utils import load_accounts
    return jsonify(load_accounts())

@app.route('/api/accounts', methods=['POST'])
def add_account():
    from utils import load_accounts, save_accounts
    import uuid
    
    data = request.json or {}
    name = data.get('name', '').strip()
    acc_type = data.get('type', 'local').strip()
    profile_id = data.get('profile_path_or_id', '').strip()
    proxy = data.get('proxy', '').strip()
    
    if not name:
        return jsonify({"error": "Vui lòng nhập tên tài khoản!"}), 400
        
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
    data = request.json or {}
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
    
    data = request.json or {}
    cmd = data.get('command')
    account_id = data.get('accountId')
    gpm_api = data.get('gpmApiUrl')
    
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
            limit = data.get('limit', 5)
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
            limit = data.get('limit', 50)
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
            
        total = len(tasks)
        for i, task in enumerate(tasks):
            target = task.get('target', '').strip()
            content = task.get('content', '').strip()
            image = task.get('image', None)
            
            # Extract task-specific parameters, falling back to global ones
            task_feeling = task.get('feeling', feeling)
            task_checkin = task.get('checkin', checkin)
            
            if not target:
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

if __name__ == '__main__':
    # Auto-start scheduler if it was running before
    config = load_config()
    if config.get("scheduler_running", False):
        from scheduler import start_scheduler
        interval = config.get("scheduler_interval_minutes", 5)
        start_scheduler(interval)

    print("Starting Facebook Automation Dashboard...")
    print("Access the dashboard at: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000)

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
    data = request.json or {}
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
    data = request.json or {}
    url = data.get("url", "").strip()
    interval = int(data.get("interval", 5))
    if not url:
        return jsonify({"error": "URL không được để trống"}), 400
    config = load_config()
    config["sheets_csv_url"] = url
    config["scheduler_interval_minutes"] = interval
    save_config(config)
    return jsonify({"success": True})

@app.route('/api/page/preview', methods=['POST'])
def preview_sheets():
    from scheduler import preview_sheets as _preview
    data = request.json or {}
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
    lines = request.args.get("lines", 80, type=int)
    return jsonify({"logs": get_log_tail(lines)})

@app.route('/api/page/post-now', methods=['POST'])
def post_now_api():
    """Manually post a single post to a page via API (not scheduled)."""
    from fb_page_api import post_to_page
    data = request.json or {}
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

    ok, result = post_to_page(page_id, token, content, image_url or None)
    if ok:
        return jsonify({"success": True, "post_id": result.get("post_id")})
    else:
        return jsonify({"error": result}), 400
