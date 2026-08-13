import sys
import os
import subprocess
from flask import Flask, request, jsonify, Response, send_from_directory

app = Flask(__name__, static_folder='static')

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

@app.route('/api/run', methods=['POST'])
def run_script():
    import random
    import time
    
    data = request.json
    cmd = data.get('command')
    
    def generate():
        if cmd == 'auth':
            full_cmd = [sys.executable, "main.py", "auth"]
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
            
            if not target:
                continue
                
            yield f"\n========== [Target {i+1}/{total}] ==========\n"
            yield f"Posting to: {target}\n"
            
            full_cmd = [sys.executable, "main.py", cmd, target, content]
            if image:
                full_cmd.extend(["--image", image])
                
            process = subprocess.Popen(
                full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                yield line
            process.wait()
            
            # If there are more tasks, wait to avoid spam detection
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
    print("Starting Facebook Automation Dashboard...")
    print("Access the dashboard at: http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000)
