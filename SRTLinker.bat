@echo off
pushd "%~dp0"

echo ============================================
echo   SRTLinker
echo ============================================
echo.
echo   Pipeline: Video -^> Whisper(raw) -^> English(en) -^> Korean(ko)
echo.
echo   Output:
echo     output/en/raw/  - Whisper raw transcription
echo     output/en/      - English post-processed
echo     output/ko/      - Korean translation
echo.

:: Ensure output folders exist (ignore errors on read-only shares)
mkdir "output\en\raw" 2>nul
mkdir "output\ko" 2>nul

:: Check .env
if not exist .env (
    echo [WARNING] .env not found. Create .env with your OpenAI API key.
    echo           Example: OPENAI_API_KEY=sk-...
    echo.
)

echo Starting web server...
echo.

if exist python\python.exe (
    python\python.exe gui_web.py
) else if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe gui_web.py
) else (
    echo [ERROR] Python not found. Run install.bat first.
)
if errorlevel 1 pause
popd
