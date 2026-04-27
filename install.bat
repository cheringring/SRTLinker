@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================
echo   SRTLinker 설치 스크립트
echo ============================================
echo.

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요.
    echo 설치 시 "Add Python to PATH" 를 반드시 체크하세요.
    echo.
    pause
    exit /b 1
)

echo [1/3] 가상환경 생성 중...
if not exist .venv (
    python -m venv .venv
    echo       완료!
) else (
    echo       이미 존재합니다. 건너뜁니다.
)
echo.

echo [2/3] 패키지 설치 중... (1~2분 소요)
.venv\Scripts\pip.exe install -r requirements.txt -q
echo       완료!
echo.

echo [3/3] API 키 설정 확인...
if not exist .env (
    echo OPENAI_API_KEY=여기에-API-키-입력 > .env
    echo       .env 파일을 생성했습니다.
    echo       .env 파일을 열어 OPENAI_API_KEY 값을 입력하세요.
) else (
    echo       .env 파일이 이미 존재합니다.
)
echo.

echo ============================================
echo   설치 완료!
echo   SRTLinker.bat 을 더블클릭하여 실행하세요.
echo ============================================
echo.
pause
