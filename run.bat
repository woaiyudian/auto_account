@echo off
REM 启动全自动记账本（桌面调试用）
setlocal
cd /d "%~dp0"
set KIVY_NO_ARGS=1
python main.py
pause
