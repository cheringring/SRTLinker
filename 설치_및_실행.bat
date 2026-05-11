@echo off
pushd "%~dp0"

echo ============================================
echo   SRTLinker - Install ^& Launch
echo ============================================
echo.
echo   Pipeline: Video -^> Whisper(raw) -^> English(en) -^> Korean(ko)
echo.
echo   Files:
echo     pipeline.py      - Main processing flow
echo     transcriber.py   - Whisper STT + English post-processing
echo     translator.py    - GPT-4o translation + retry
echo     prompts.py       - Translation prompt (12 rules)
echo     glossary.json    - Term dictionary
echo.

echo [1/2] Installing...
call install.bat
echo.

echo [2/2] Launching SRTLinker...
start "" "%~dp0SRTLinker.bat"

echo ============================================
echo   Done! Next time, run SRTLinker.bat directly.
echo ============================================
popd
pause
