@echo off
cd /d "%~dp0"

echo ============================================
echo   SRTLinker Install
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed.
    echo Download Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
if not exist .venv (
    python -m venv .venv
    echo       Done.
) else (
    echo       Already exists. Skipping.
)
echo.

echo [2/3] Installing packages... (1-2 min)
.venv\Scripts\pip.exe install -r requirements.txt -q
echo       Done.
echo.

echo [3/3] Checking .env file...
if not exist .env (
    echo OPENAI_API_KEY=your-api-key-here> .env
    echo       Created .env file.
    echo       Open .env and enter your OpenAI API key.
) else (
    echo       .env already exists.
)
echo.

echo ============================================
echo   Install complete!
echo   Double-click SRTLinker.bat to run.
echo ============================================
echo.
pause
