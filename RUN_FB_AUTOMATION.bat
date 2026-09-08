@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
cd /d "%~dp0"

set "PYTHON_EXE="
set "VENV_DIR=%CD%\runtime\venv"
set "PYTHON_INSTALLER=%CD%\runtime\python-3.12.10-amd64.exe"

REM === 1. Venv da co san ? dung luon (fast path) ===
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
    goto :check_libs
)

REM === 2. Tim Python 3.12 cai tren may ===
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "BASE_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :create_venv
)

REM === 3. Thu bundled installer ===
if exist "%PYTHON_INSTALLER%" (
    echo Dang cai Python. Qua trinh nay chi xay ra mot lan...
    "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_test=0
    set "BASE_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :create_venv
)

REM === 4. Thu py launcher ===
where py >nul 2>&1 && for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "BASE_PYTHON=%%P"
if defined BASE_PYTHON goto :create_venv

echo [LOI] Khong tim thay Python 3.12.
echo Hay tai Python tai https://www.python.org/downloads/ hoac ket noi Internet.
pause
exit /b 1

:create_venv
echo Dang tao moi truong chay rieng (chi xay ra mot lan)...
"%BASE_PYTHON%" -m venv "%VENV_DIR%"
if errorlevel 1 goto :error
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

echo Dang cai thu vien (chi xay ra mot lan, can ket noi Internet)...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :error

echo Dang tai Chromium (chi xay ra mot lan)...
"%VENV_DIR%\Scripts\playwright.exe" install chromium
if errorlevel 1 goto :error
goto :run

:check_libs
REM Kiem tra nhanh flask da co chua (tranh pip install lai moi lan)
if not exist "%VENV_DIR%\Lib\site-packages\flask" (
    echo Dang kiem tra va cap nhat thu vien...
    "%PYTHON_EXE%" -m pip install --disable-pip-version-check -q -r requirements.txt
    if errorlevel 1 goto :error
)

:run
set "LAUNCH_MODE="
set "APP_PORT="
for /f "tokens=1,2" %%A in ('"%PYTHON_EXE%" launcher_preflight.py') do (
    set "LAUNCH_MODE=%%A"
    set "APP_PORT=%%B"
)
if not defined APP_PORT goto :port_error
if /I "%LAUNCH_MODE%"=="REUSE" (
    echo [OK] Dung server cung version/root dang chay tai port %APP_PORT%.
    start "" http://127.0.0.1:%APP_PORT%
    exit /b 0
)
set "FB_AUTOMATION_PORT=%APP_PORT%"
for /f "usebackq delims=" %%V in ("VERSION") do set "APP_VERSION=%%V"
start "" http://127.0.0.1:%APP_PORT%
echo.
echo =====================================================
echo  FB Automation Panel v%APP_VERSION% - port %APP_PORT%
echo  Runtime root: %CD%
echo  Bam Ctrl+C de dung server
echo =====================================================
echo.
"%PYTHON_EXE%" server.py
exit /b %errorlevel%

:port_error
echo [LOI] Khong tim duoc port 5000-5010 de khoi dong.
pause
exit /b 1

:error
echo.
echo [LOI] Khoi dong that bai. Kiem tra ket noi Internet va thu lai.
pause
exit /b 1
