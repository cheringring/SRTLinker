"""Build a self-contained SRTLinker installer package.

Steps:
1. Download Python embeddable (3.12)
2. Install pip into it
3. Install project dependencies
4. Copy project files
5. Create launcher bat
6. Run Inno Setup to build the installer exe
"""
import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
BUILD_DIR = ROOT / "installer_build"
DIST_DIR = BUILD_DIR / "SRTLinker"
PYTHON_DIR = DIST_DIR / "python"

PYTHON_VERSION = "3.12.8"
PYTHON_ZIP_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

PROJECT_FILES = [
    "gui_web.py",
    "main.py",
    "pipeline.py",
    "transcriber.py",
    "translator.py",
    "sentence_merger.py",
    "srt_chunker.py",
    "verify.py",
    "prompts.py",
    "glossary.json",
    "requirements.txt",
]


def download(url: str, dest: Path):
    print(f"  Downloading {url.split('/')[-1]}...")
    urllib.request.urlretrieve(url, dest)


def step1_download_python():
    print("[1/5] Downloading Python embeddable...")
    if PYTHON_DIR.exists():
        shutil.rmtree(PYTHON_DIR)
    PYTHON_DIR.mkdir(parents=True)

    zip_path = BUILD_DIR / "python_embed.zip"
    download(PYTHON_ZIP_URL, zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(PYTHON_DIR)
    zip_path.unlink()

    # Enable pip + add app root to path in python312._pth
    pth_files = list(PYTHON_DIR.glob("python*._pth"))
    for pth in pth_files:
        content = pth.read_text()
        content = content.replace("#import site", "import site")
        if "Lib\\site-packages" not in content:
            content += "\nLib\\site-packages\n"
        # Add parent dir (..) so project .py files are importable from python/ subfolder
        if ".." not in content:
            content += "\n..\n"
        pth.write_text(content)
    print("  Done.")


def step2_install_pip():
    print("[2/5] Installing pip...")
    get_pip = BUILD_DIR / "get-pip.py"
    download(GET_PIP_URL, get_pip)

    python_exe = PYTHON_DIR / "python.exe"
    subprocess.run([str(python_exe), str(get_pip), "--no-warn-script-location"], check=True)
    get_pip.unlink()
    print("  Done.")


def step3_install_deps():
    print("[3/5] Installing dependencies...")
    python_exe = PYTHON_DIR / "python.exe"
    pip_exe = PYTHON_DIR / "Scripts" / "pip.exe"
    
    # Install from requirements.txt
    req_file = ROOT / "requirements.txt"
    subprocess.run([
        str(python_exe), "-m", "pip", "install",
        "-r", str(req_file),
        "--no-warn-script-location",
        "-q",
    ], check=True)
    print("  Done.")


def step4_copy_project():
    print("[4/5] Copying project files...")
    for fname in PROJECT_FILES:
        src = ROOT / fname
        dst = DIST_DIR / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  {fname}")

    # Copy .env from project root (includes API key)
    env_src = ROOT / ".env"
    env_file = DIST_DIR / ".env"
    if env_src.exists():
        shutil.copy2(env_src, env_file)
        print("  .env (copied from project root - API key included)")
    else:
        env_file.write_text("OPENAI_API_KEY=your-api-key-here\nOPENAI_MODEL=gpt-4o\n")
        print("  .env (template - no API key found in project root)")

    # Create output directory
    (DIST_DIR / "output").mkdir(exist_ok=True)

    # Create launcher
    launcher = DIST_DIR / "SRTLinker.bat"
    launcher.write_text(
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'echo SRTLinker starting... Browser will open automatically.\r\n'
        'python\\python.exe gui_web.py\r\n'
        'if errorlevel 1 pause\r\n',
        encoding='ascii'
    )
    print("  Done.")


def step5_create_iss():
    print("[5/5] Creating Inno Setup script...")
    iss_content = r"""; SRTLinker Inno Setup Script
[Setup]
AppName=SRTLinker
AppVersion=1.0
AppPublisher=SRTLinker
DefaultDirName={autopf}\SRTLinker
DefaultGroupName=SRTLinker
OutputDir=OUTPUT_DIR
OutputBaseFilename=SRTLinker_Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=
UninstallDisplayIcon={app}\python\python.exe
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "DIST_PATH\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\SRTLinker"; Filename: "{app}\SRTLinker.bat"; IconFilename: "{app}\python\python.exe"; Comment: "SRTLinker - Auto Subtitle Translator"
Name: "{group}\SRTLinker"; Filename: "{app}\SRTLinker.bat"; IconFilename: "{app}\python\python.exe"

[Run]
Filename: "{app}\SRTLinker.bat"; Description: "Launch SRTLinker"; Flags: postinstall nowait skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Ensure output folder exists
    ForceDirectories(ExpandConstant('{app}\output'));
  end;
end;
""".replace("OUTPUT_DIR", str(BUILD_DIR).replace("\\", "\\\\")).replace("DIST_PATH", str(DIST_DIR).replace("\\", "\\\\"))

    iss_path = BUILD_DIR / "SRTLinker.iss"
    iss_path.write_text(iss_content, encoding='utf-8')
    print(f"  Created: {iss_path}")
    print()
    print("=" * 50)
    print("  Build package ready!")
    print(f"  Project folder: {DIST_DIR}")
    print(f"  Inno Setup script: {iss_path}")
    print()
    print("  To build the installer:")
    print("  1. Install Inno Setup: https://jrsoftware.org/isinfo.php")
    print('  2. Run: iscc "' + str(iss_path) + '"')
    print("  Or: Right-click .iss -> Compile")
    print("=" * 50)


def main():
    print("=" * 50)
    print("  SRTLinker Installer Builder")
    print("=" * 50)
    print()

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir()
    DIST_DIR.mkdir()

    step1_download_python()
    step2_install_pip()
    step3_install_deps()
    step4_copy_project()
    step5_create_iss()

    # 6) Inno Setup 컴파일
    iscc_paths = [
        Path(r"C:\Users\gksmf\AppData\Local\Programs\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    ]
    iscc = next((p for p in iscc_paths if p.exists()), None)
    iss_path = BUILD_DIR / "SRTLinker.iss"
    exe_path = BUILD_DIR / "SRTLinker_Setup.exe"

    if iscc:
        print()
        print("[6/7] Compiling installer...")
        subprocess.run([str(iscc), str(iss_path)], check=True)
        print("  Done.")
    else:
        print()
        print("[6/7] Inno Setup not found - skipping.")

    # 7) 네트워크 폴더에 자동 복사
    DEPLOY_DIR = Path(r"\\intranet.spss.co.kr\개인폴더\권체은\SRTLinker")
    if exe_path.exists():
        try:
            DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(exe_path, DEPLOY_DIR / "SRTLinker_Setup.exe")
            print()
            print(f"[7/7] Deployed: {DEPLOY_DIR}\\SRTLinker_Setup.exe")
        except Exception as e:
            print(f"[7/7] Deploy failed: {e}")
    print()
    print("=" * 50)
    print("  Build complete!")
    print("=" * 50)

    # 6) Inno Setup 컴파일 (설치되어 있으면 자동 실행)
    iscc_paths = [
        Path(r"C:\Users\gksmf\AppData\Local\Programs\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    ]
    iscc = next((p for p in iscc_paths if p.exists()), None)
    iss_path = BUILD_DIR / "SRTLinker.iss"
    exe_path = BUILD_DIR / "SRTLinker_Setup.exe"

    if iscc:
        print()
        print("[6/7] Compiling installer with Inno Setup...")
        subprocess.run([str(iscc), str(iss_path)], check=True)
        print("  Done.")
    else:
        print()
        print("[6/7] Inno Setup not found - skipping exe compile.")
        print(f'  Manually run: iscc "{iss_path}"')

    # 7) 네트워크 폴더에 자동 복사
    DEPLOY_DIR = Path(r"\\intranet.spss.co.kr\개인폴더\권체은\SRTLinker")
    if exe_path.exists():
        try:
            DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(exe_path, DEPLOY_DIR / "SRTLinker_Setup.exe")
            print()
            print(f"[7/7] Deployed to: {DEPLOY_DIR}\\SRTLinker_Setup.exe")
        except Exception as e:
            print()
            print(f"[7/7] Deploy failed (network unavailable?): {e}")
            print(f"  Manual copy: {exe_path}")
    else:
        print()
        print("[7/7] No exe to deploy - compile first.")

    print()
    print("=" * 50)
    print("  Build complete!")
    print("=" * 50)



if __name__ == "__main__":
    main()
