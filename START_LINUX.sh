#!/bin/bash

# =====================================================
#   FB AUTOMATION - LINUX ONE-CLICK LAUNCHER
# =====================================================

cd "$(dirname "$0")"

echo "==================================================="
echo "   FB AUTOMATION TOOL - ĐANG KHỞI ĐỘNG..."
echo "==================================================="

# 1. Kiểm tra Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ Chưa cài Python3! Chạy: sudo apt install python3 python3-venv -y"
    exit 1
fi
echo "✅ Python3: $(python3 --version)"

# 2. Tạo venv nếu chưa có
if [ ! -d "venv" ]; then
    echo "🔧 Lần đầu chạy - Đang tạo venv..."
    python3 -m venv venv
fi

source venv/bin/activate

# 3. Cài thư viện
echo "📦 Đang cài thư viện..."
pip install -r requirements.txt -q

# 4. Cài Playwright Chromium
echo "🌐 Đang cài Playwright Chromium..."
playwright install chromium

# 5. Kill port cũ
fuser -k 5000/tcp 2>/dev/null
sleep 1

# 6. Mở browser
echo "🚀 Đang khởi động tại http://127.0.0.1:5000"
(sleep 2 && xdg-open http://127.0.0.1:5000 2>/dev/null || python3 -m webbrowser http://127.0.0.1:5000) &

python server.py
