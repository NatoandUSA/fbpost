@echo off
setlocal
cd /d "%~dp0"
call RUN_FB_AUTOMATION.bat
exit /b %errorlevel%
