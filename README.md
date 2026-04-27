# SRTLinker

OpenAI API 기반 SRT 자막 문맥 보존 번역기.

## 핵심 설계

- **슬라이딩 윈도우 문맥 주입**: 번역 대상 N블록 + 앞뒤 M블록을 context로 함께 전달 (LLM은 context는 참고만, 번역은 translate 블록만).
- **Structured Outputs (JSON Schema, strict)**: 출력 구조 붕괴 원천 차단.
- **id 매핑 검증**: 응답의 id 집합이 요청과 100% 일치하지 않으면 해당 청크만 자동 재시도.
- **타임스탬프 무결성**: 번역은 텍스트만 교체, 원본 `SubRipFile` 객체의 시간값을 그대로 재직렬화.
- **용어집**: `glossary.json`으로 고유명사(Anzo, Ontology 등) 고정.

## 설치

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 입력
```

**macOS / Linux (bash / zsh)**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env 파일을 열어 OPENAI_API_KEY 입력
```

> `imageio-ffmpeg`가 포터블 ffmpeg 바이너리를 자동 제공하므로 별도 ffmpeg 설치 불필요.

## 사용법 1. GUI (추천)

**Windows (PowerShell)**
```powershell
python gui.py
```

**macOS / Linux (bash)**
```bash
python3 gui.py
```

- 창이 뜨면 영상/오디오/SRT 파일을 **드래그&드롭** 하거나 `파일 추가`.
- 번역 언어, 원본 언어 힌트(en 등), 모델, 출력 폴더 설정 후 `번역 시작`.
- 진행률 + 로그가 실시간 표시되고 `output/` 폴더에 `<원본이름>.ko.srt` 저장.

지원 입력: `.mp4 .mkv .mov .avi .webm .flv .wmv .m4v .mp3 .wav .m4a .aac .ogg .opus .flac .srt`

## 사용법 2. CLI

단일 파일 (영상이든 SRT든 자동 판별):

**Windows (PowerShell)**
```powershell
python main.py path\to\video.mp4 -o output
python main.py path\to\video.srt -o output
```

**macOS / Linux (bash)**
```bash
python3 main.py path/to/video.mp4 -o output
python3 main.py path/to/video.srt -o output
```

폴더 배치:

**Windows (PowerShell)**
```powershell
python main.py samples -o output
```

**macOS / Linux (bash)**
```bash
python3 main.py samples -o output
```

주요 옵션:
```
-t, --target-lang     번역 대상 언어 (기본 Korean)
-m, --model           OpenAI 모델 (기본 gpt-4o)
--chunk-size          한 번에 번역할 블록 수 (기본 20)
--context-size        앞뒤 참고 블록 수 (기본 5)
--glossary            용어집 JSON 경로 (기본 glossary.json)
--suffix              출력 파일 접미사 (기본 .ko → video.ko.srt)
```

## 프로젝트 구조

```
SRTLinker/
├── main.py            # CLI 엔트리포인트
├── srt_chunker.py     # SRT 파싱 / 청킹 / 재조립
├── translator.py      # OpenAI 호출 + Structured Outputs + 재시도
├── prompts.py         # 시스템/유저 프롬프트 빌더
├── glossary.json      # 고유명사 & 고정 번역
├── requirements.txt
├── .env.example
└── README.md
```

## 동작 흐름

```
input.srt
  → pysrt 파싱 (id, timestamp, text)
  → chunk_blocks (translate=20, context=±5)
  → OpenAI (system + JSON payload, response_format=json_schema strict)
  → id 집합 검증 → 불일치 시 tenacity로 해당 청크만 재시도
  → 원본 timestamp에 매핑
  → output/<name>.ko.srt
```

## 확장 아이디어

- `faster-whisper`를 앞단에 붙여 `mp4 → SRT → ko.srt` 완성 파이프라인화
- Tkinter/PySimpleGUI로 드래그&드롭 GUI 래핑 후 PyInstaller로 exe 배포
- 번역 캐시(해시 기반) 도입해 재실행 시 API 비용 절감
