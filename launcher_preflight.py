import json
import socket
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8-sig').strip()

def listener(port):
    with socket.socket() as s:
        s.settimeout(0.25)
        return s.connect_ex(('127.0.0.1', port)) == 0

def app_info(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/app-info', timeout=1.0) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return {}
for port in range(5000, 5011):
    if not listener(port):
        print(f'START {port}')
        raise SystemExit(0)
    info = app_info(port)
    same_version = str(info.get('version') or '') == VERSION
    runtime_root = str(info.get('runtime_root') or '').strip()
    same_root = bool(runtime_root) and Path(runtime_root).resolve() == ROOT
    if same_version and same_root:
        print(f'REUSE {port}')
        raise SystemExit(0)

print('ERROR 0')
raise SystemExit(2)
