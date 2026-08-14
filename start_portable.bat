@echo off
title FB Automation Portable Launcher
echo ===================================================
echo   KHOI CHAY COMPACT PORTABLE FB AUTOMATION TOOL
echo ===================================================
echo.

:: 1. Kiem tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] May cua ban chua cai dat Python!
    echo Vui long tai va cai dat Python tu: https://www.python.org/downloads/
    echo (Nho tick chon "Add Python to PATH" khi cai dat)
    echo.
    pause
    exit /b
)

:: 2. Kiem tra va tao Virtual Environment
if not exist "venv" (
    echo [INFO] Dang tao moi virtual environment (venv)...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Khong the tu dong tao venv.
        pause
        exit /b
    )
)

:: 3. Kiem tra & Cai dat thu vien
echo [INFO] Kiem tra va cai dat cac thu vien phu thuoc...
venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cai dat requirements.txt!
    pause
    exit /b
)

:: 4. Kiem tra & Cai dat Playwright Browsers
echo [INFO] Kiem tra va tai ve trinh duyet Playwright (Chromium)...
venv\Scripts\playwright.exe install chromium
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi tai trinh duyet Playwright!
    pause
    exit /b
)

:: 5. Tu dong mo trang chu tren trinh duyet mac dinh
echo [INFO] Dang mo Dashboard tai dia chi http://127.0.0.1:5000
start http://127.0.0.1:5000

:: 6. Chay Flask Server
echo [INFO] Dang khoi dong Flask Server...
echo Bam Ctrl+C neu ban muon dung cong cu.
echo ---------------------------------------------------
venv\Scripts\python.exe server.py

pause
