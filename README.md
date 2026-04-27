# SRTLinker

비디오 · 오디오 · 자막 파일을 자동으로 전사(Whisper) + 번역(GPT)하여 한국어 SRT를 생성하는 데스크톱 앱입니다.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20%2B%20GPT-green)
![PySide6](https://img.shields.io/badge/GUI-PySide6-orange)

---

## 주요 기능

- **자동 전사 (STT)** — Whisper API로 영상/오디오에서 자막 자동 추출
- **문맥 보존 번역** — 슬라이딩 윈도우로 앞뒤 문맥을 함께 전달하여 자연스러운 한국어 번역
- **문장인식 분할 번역** — 문장 경계를 인식해 자연스러운 단위로 번역 후 원본 블록에 재배치
- **블록 1:1 정합성** — 번역 후에도 원본과 동일한 블록 수·타임스탬프 유지
- **자동 검증** — 블록 수, 타임스탬프, 미번역 잔존 등 자동 확인
- **용어집** — `glossary.json`으로 고유명사 고정 번역
- **GUI + CLI** 모두 지원

### 지원 입력 형식

| 비디오 | 오디오 | 자막 |
|--------|--------|------|
| `.mp4` `.mkv` `.mov` `.avi` `.webm` `.flv` `.wmv` `.m4v` | `.mp3` `.wav` `.m4a` `.aac` `.ogg` `.opus` `.flac` | `.srt` |

---

## 빠른 시작 (Windows)

> **사전 준비**: [Python 3.10 이상](https://www.python.org/downloads/) 설치 필요  
> 설치 시 **"Add Python to PATH"** 를 반드시 체크하세요.

### 방법 1. 자동 설치 (추천)

1. 이 저장소를 다운로드하거나 클론합니다:
   ```
   git clone https://github.com/cheringring/SRTLinker.git
   ```
2. `SRTLinker` 폴더 안의 **`install.bat`** 을 더블클릭합니다.
   - 가상환경 생성, 패키지 설치가 자동으로 진행됩니다 (1~2분 소요).
   - `.env` 파일이 자동 생성됩니다.
3. `.env` 파일을 메모장으로 열어 OpenAI API 키를 입력합니다:
   ```
   OPENAI_API_KEY=sk-proj-여기에-실제-키-입력
   ```
4. **`SRTLinker.bat`** 을 더블클릭하면 프로그램이 실행됩니다.

### 방법 2. 수동 설치

```powershell
git clone https://github.com/cheringring/SRTLinker.git
cd SRTLinker

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`.env` 파일을 만들고 API 키를 입력합니다:
```
OPENAI_API_KEY=sk-proj-여기에-실제-키-입력
```

실행:
```powershell
python gui_qt.py
```

### macOS / Linux

```bash
git clone https://github.com/cheringring/SRTLinker.git
cd SRTLinker

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "OPENAI_API_KEY=sk-proj-여기에-실제-키-입력" > .env
python3 gui_qt.py
```

> `imageio-ffmpeg`가 포터블 ffmpeg 바이너리를 자동 제공하므로 별도 ffmpeg 설치는 불필요합니다.

---

## 사용법

### GUI (추천)

`SRTLinker.bat`을 더블클릭하거나 `python gui_qt.py`로 실행합니다.

1. 영상/오디오/SRT 파일을 창에 **드래그&드롭** 하거나 `파일 추가` 버튼 클릭
2. 설정 확인:
   - **번역 언어**: 번역할 대상 언어 (기본: Korean)
   - **원본 언어**: 원본 자막 언어 힌트 (기본: en)
   - **번역 모델**: GPT 모델 (기본: gpt-4o)
   - **전사 모델**: Whisper 모델 (기본: whisper-1)
   - **출력 폴더**: 번역된 SRT 저장 위치
   - **문장인식 분할 번역**: 체크하면 문장 단위로 자연스럽게 번역 (추천)
3. **`번역 시작`** 클릭
4. 진행률과 로그가 실시간으로 표시됩니다
5. 완료 후 `출력 폴더` 버튼으로 결과 확인 — `<원본이름>.ko.srt` 파일 생성

### CLI

```powershell
# 영상 파일 → 전사 + 번역
python main.py video.mp4 -o output

# SRT 파일 → 번역만
python main.py subtitle.srt -o output

# 폴더 내 모든 파일 배치 처리
python main.py my_folder -o output
```

**주요 옵션:**

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `-t, --target-lang` | 번역 대상 언어 | `Korean` |
| `-m, --model` | OpenAI 번역 모델 | `gpt-4o` |
| `--stt-model` | Whisper 전사 모델 | `whisper-1` |
| `--chunk-size` | 한 번에 번역할 블록 수 | `20` |
| `--context-size` | 앞뒤 참고 블록 수 | `5` |
| `--glossary` | 용어집 JSON 경로 | `glossary.json` |
| `--suffix` | 출력 파일 접미사 | `.ko` |
| `--no-merge` | 문장인식 분할 번역 비활성화 | - |

---

## 자주 묻는 질문

**Q. OpenAI API 키는 어디서 발급하나요?**  
[OpenAI Platform](https://platform.openai.com/api-keys)에서 발급받을 수 있습니다. 유료 크레딧이 필요합니다.

**Q. 번역 비용은 얼마나 드나요?**  
파일 크기와 자막 수에 따라 다르지만, 일반적인 1시간 영상 기준 약 $0.5~$2 정도입니다 (gpt-4o 기준).

**Q. 영상 파일이 아주 큰데 괜찮나요?**  
영상은 로컬에서 오디오만 추출한 뒤 Whisper API로 전송합니다. 대용량 파일은 자동으로 분할 처리됩니다.

**Q. 인터넷 없이 사용할 수 있나요?**  
OpenAI API를 사용하므로 인터넷 연결이 필요합니다.

---

## 프로젝트 구조

```
SRTLinker/
├── install.bat        # 자동 설치 스크립트 (Windows)
├── SRTLinker.bat      # 실행 스크립트 (Windows)
├── gui_qt.py          # PySide6 GUI
├── main.py            # CLI 엔트리포인트
├── pipeline.py        # 전사 → 번역 → 검증 파이프라인
├── transcriber.py     # Whisper API 전사
├── translator.py      # OpenAI 번역 + Structured Outputs + 재시도
├── sentence_merger.py # 문장 경계 인식 + 블록 재배치
├── srt_chunker.py     # SRT 파싱 / 청킹 / 재조립
├── verify.py          # 번역 결과 정합성 검증
├── prompts.py         # 시스템/유저 프롬프트 빌더
├── glossary.json      # 고유명사 & 고정 번역
├── requirements.txt   # 패키지 목록
└── README.md
```

## 동작 흐름

```
입력 파일 (영상/오디오/SRT)
  → [영상/오디오] Whisper API 전사 → SRT 생성
  → pysrt 파싱 (id, timestamp, text)
  → 문장 경계 그룹핑 (sentence_merger)
  → chunk_blocks (translate=20, context=±5)
  → OpenAI GPT (JSON Schema strict 모드)
  → id 집합 검증 → 불일치 시 해당 청크만 자동 재시도
  → 블록 1:1 재배치 (원본 타임스탬프 유지)
  → 정합성 검증 (블록 수, 타임스탬프, 미번역 등)
  → output/<name>.ko.srt
```

---

## 라이선스

MIT License
