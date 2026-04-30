@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe gui_web.py
) else (
    echo [ERROR] .venv not found.
    echo Run install.bat first.
    pause
)
