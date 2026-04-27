# SRTLinker

비디오 · 오디오 · 자막 파일을 자동으로 전사(Whisper) + 번역(GPT)하여 한국어 SRT를 생성하는 데스크톱 앱입니다.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20%2B%20GPT-green)
![PySide6](https://img.shields.io/badge/GUI-PySide6-orange)

## 주요 기능

- **자동 전사 (STT)**: Whisper API로 영상/오디오에서 자막 추출
- **문맥 보존 번역**: 슬라이딩 윈도우로 앞뒤 문맥을 함께 전달하여 자연스러운 한국어 번역
- **문장인식 분할 번역**: 문장 경계를 인식해 자연스러운 단위로 번역 후 원본 블록에 재배치
- **블록 1:1 정합성 보장**: 번역 후에도 원본과 동일한 블록 수·타임스탬프 유지
- **번역 검증**: 블록 수, 타임스탬프 일치, 미번역 잔존 등 자동 검증
- **Structured Outputs**: JSON Schema strict 모드로 출력 구조 붕괴 방지
- **id 매핑 검증 + 자동 재시도**: 누락된 번역 블록은 자동으로 재요청
- **용어집**: `glossary.json`으로 고유명사(Anzo, Ontology, RDF, SPARQL 등) 고정
- **GUI + CLI** 모두 지원

## 지원 입력 형식

| 비디오 | 오디오 | 자막 |
|--------|--------|------|
| `.mp4` `.mkv` `.mov` `.avi` `.webm` `.flv` `.wmv` `.m4v` | `.mp3` `.wav` `.m4a` `.aac` `.ogg` `.opus` `.flac` | `.srt` |

## 설치

### 1. 저장소 클론
```bash
git clone https://github.com/cheringring/SRTLinker.git
cd SRTLinker
```

### 2. 가상환경 생성 및 패키지 설치

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. API 키 설정
프로젝트 루트에 `.env` 파일을 생성하고 OpenAI API 키를 입력합니다:
```
OPENAI_API_KEY=sk-여기에-키-입력
```

> `imageio-ffmpeg`가 포터블 ffmpeg 바이너리를 자동 제공하므로 별도 ffmpeg 설치는 불필요합니다.

## 사용법

### GUI (추천)

```powershell
# Windows
python gui_qt.py

# macOS / Linux
python3 gui_qt.py
```

1. 창이 뜨면 영상/오디오/SRT 파일을 **드래그&드롭** 하거나 `파일 추가` 클릭
2. 번역 언어, 원본 언어 힌트(en 등), 모델, 전사 모델, 출력 폴더 설정
3. `번역 시작` 클릭
4. 진행률 + 로그가 실시간 표시되고 `output/` 폴더에 `<원본이름>.ko.srt` 저장

### CLI

```powershell
# 단일 파일 (영상/SRT 자동 판별)
python main.py path\to\video.mp4 -o output
python main.py path\to\subtitle.srt -o output

# 폴더 배치 처리
python main.py samples -o output
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

## 프로젝트 구조

```
SRTLinker/
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
├── requirements.txt
└── README.md
```

## 동작 흐름

```
입력 파일 (영상/오디오/SRT)
  → [영상/오디오] Whisper API 전사 → SRT 생성
  → pysrt 파싱 (id, timestamp, text)
  → 문장 경계 그룹핑 (sentence_merger)
  → chunk_blocks (translate=20, context=±5)
  → OpenAI GPT (system + JSON payload, strict JSON Schema)
  → id 집합 검증 → 불일치 시 해당 청크만 자동 재시도
  → 블록 1:1 재배치 (원본 타임스탬프 유지)
  → 정합성 검증 (블록 수, 타임스탬프, 미번역 등)
  → output/<name>.ko.srt
```

## 라이선스

MIT License
