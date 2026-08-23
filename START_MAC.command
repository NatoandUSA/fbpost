#!/bin/bash

# =====================================================
#   FB AUTOMATION - MAC ONE-CLICK LAUNCHER
#   Double-click file này để khởi động Tool
# =====================================================

# Di chuyển vào thư mục chứa script này
cd "$(dirname "$0")"

echo "==================================================="
echo "   FB AUTOMATION TOOL - ĐANG KHỞI ĐỘNG..."
echo "==================================================="
echo ""

# 1. Kiểm tra Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ [LỖI] Máy chưa cài Python3!"
    echo ""
    echo "Vui lòng tải và cài đặt Python tại:"
    echo "👉 https://www.python.org/downloads/"
    echo ""
    read -p "Nhấn Enter để thoát..."
    exit 1
fi

echo "✅ Python3 đã được cài đặt: $(python3 --version)"

# 2. Tạo Virtual Environment nếu chưa có
if [ ! -d "venv" ]; then
    echo ""
    echo "🔧 [INFO] Lần đầu chạy - Đang tạo môi trường ảo (venv)..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ [LỖI] Không thể tạo venv!"
        read -p "Nhấn Enter để thoát..."
        exit 1
    fi
    echo "✅ Tạo venv thành công!"
fi

# 3. Kích hoạt venv
source venv/bin/activate

# 4. Cài đặt/cập nhật thư viện
echo ""
echo "📦 [INFO] Đang kiểm tra và cài đặt thư viện..."
pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "❌ [LỖI] Lỗi khi cài requirements.txt!"
    read -p "Nhấn Enter để thoát..."
    exit 1
fi
echo "✅ Thư viện đã sẵn sàng!"

# 5. Cài đặt trình duyệt Playwright Chromium
echo ""
echo "🌐 [INFO] Đang kiểm tra trình duyệt Playwright (Chromium)..."
playwright install chromium -q
if [ $? -ne 0 ]; then
    echo "❌ [LỖI] Lỗi khi cài Playwright!"
    read -p "Nhấn Enter để thoát..."
    exit 1
fi
echo "✅ Trình duyệt Chromium đã sẵn sàng!"

# 6. Kill process cũ trên port 5000 nếu có
echo ""
echo "🔄 [INFO] Kiểm tra port 5000..."
lsof -ti:5000 | xargs kill -9 2>/dev/null
sleep 1

# 7. Mở Dashboard trên trình duyệt
echo ""
echo "🚀 [INFO] Đang khởi động Dashboard..."
echo "---------------------------------------------------"
echo "   Truy cập tại: http://127.0.0.1:5000"
echo "---------------------------------------------------"

# Delay 2 giây rồi mở trình duyệt trong background
(sleep 2 && open http://127.0.0.1:5000) &

# 8. Chạy Flask Server
python server.py
