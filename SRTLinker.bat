@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe gui_qt.py
) else (
    echo [오류] .venv 가상환경이 없습니다.
    echo 먼저 설치를 진행하세요:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip.exe install -r requirements.txt
    pause
)
