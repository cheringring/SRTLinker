@echo off
pushd "%~dp0"

echo ============================================
echo   SRTLinker Install
echo ============================================
echo.

set "PYTHON_VER=3.11.9"
set "PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%"
set "PYTHON_DIR=python"
set "PYTHON_EXE=python\python.exe"
set "PIP_EXE=python\Scripts\pip.exe"

echo [1/5] Setting up Python (no install needed)...
if exist "%PYTHON_EXE%" (
    echo       Python already exists. Skipping.
    goto :pip_check
)

echo       Downloading Python %PYTHON_VER% embedded...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%' -UseBasicParsing; Write-Host 'Download complete.'"
if not exist "%PYTHON_ZIP%" (
    echo [ERROR] Download failed. Check internet connection.
    pause
    exit /b 1
)

echo       Extracting...
if exist "%PYTHON_DIR%" rmdir /s /q "%PYTHON_DIR%"
mkdir "%PYTHON_DIR%"
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force; Write-Host 'Extract complete.'"
del "%PYTHON_ZIP%" 2>nul

:: Enable site-packages by uncommenting "import site" in ._pth file
powershell -NoProfile -Command "(Get-ChildItem 'python\*._pth') | ForEach-Object { (Get-Content $_) -replace '#import site','import site' | Set-Content $_ }"
echo       Done.
echo.

:pip_check
:: Always ensure ._pth allows site-packages
powershell -NoProfile -Command "(Get-ChildItem 'python\*._pth') | ForEach-Object { (Get-Content $_) -replace '#import site','import site' | Set-Content $_ }"

echo [2/5] Setting up pip...
if exist "%PIP_EXE%" (
    echo       pip already exists. Skipping.
    goto :packages
)

echo       Downloading get-pip.py...
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'python\get-pip.py' -UseBasicParsing; Write-Host 'Download complete.'"
echo       Installing pip...
python\python.exe python\get-pip.py --no-warn-script-location
del python\get-pip.py 2>nul
echo       Done.
echo.

:packages
echo [3/5] Installing packages...
if exist wheels (
    python\python.exe -m pip install -r requirements.txt --no-index --find-links wheels --no-warn-script-location
) else (
    python\python.exe -m pip install -r requirements.txt --no-warn-script-location
)
echo       Done.
echo.

echo [4/5] Checking .env file...
if not exist .env (
    echo OPENAI_API_KEY=your-api-key-here> .env
    echo       Created .env file.
    echo       ** Open .env and enter your OpenAI API key **
) else (
    echo       .env already exists.
)
echo.

echo [5/5] Creating output folders...
mkdir output\en\raw 2>nul
mkdir output\ko 2>nul
echo       output/en/raw/  - Whisper raw transcription
echo       output/en/      - English post-processed
echo       output/ko/      - Korean translation
echo       Done.
echo.

echo ============================================
echo   Install complete!
echo.
echo   Pipeline: Video -^> Whisper(raw) -^> English(en) -^> Korean(ko)
echo.
echo   Next: Double-click SRTLinker.bat to run.
echo ============================================
echo.
pause
