# SRTLinker

비디오 · 오디오 · 자막 파일을 자동으로 전사(Whisper) + 번역(GPT)하여 한국어 SRT를 생성하는 데스크톱 앱입니다.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20%2B%20GPT-green)
![Flask](https://img.shields.io/badge/GUI-Flask%20Web-orange)

---

## 주요 기능

- **자동 전사 (STT)** — Whisper API로 영상/오디오에서 자막 자동 추출
- **영어 SRT 자동 정리** — 긴 블록 분할, 필러 제거, 화자 전환 분리, 문장 병합
- **문맥 보존 번역** — 슬라이딩 윈도우로 앞뒤 문맥을 함께 전달하여 자연스러운 한국어 번역
- **원문 부호 구조 유지** — 원문이 쉼표로 이어지면 번역도 쉼표로 유지 (마침표 임의 추가 금지)
- **화자 전환 감지** — 질문(`?`) 뒤 답변 패턴, 시간 갭, 응답 시작 패턴으로 화자 분리
- **블록 1:1 정합성** — 영어/한국어 SRT가 동일한 블록 수·타임스탬프 유지
- **용어집** — `glossary.json`으로 고유명사 고정 번역
- **웹 GUI** — 로컬 Flask 서버, 브라우저에서 드래그앤드롭으로 사용

### 지원 입력 형식

| 비디오 | 오디오 | 자막 |
|--------|--------|------|
| `.mp4` `.mkv` `.mov` `.avi` `.webm` `.flv` `.wmv` `.m4v` | `.mp3` `.wav` `.m4a` `.aac` `.ogg` `.opus` `.flac` | `.srt` |

---

## 빠른 시작 (Windows)

> **Python 별도 설치 불필요** — 설치 스크립트가 자동으로 처리합니다.

### 방법 1. 자동 설치 (추천)

1. 이 저장소를 클론합니다:
   ```
   git clone https://github.com/cheringring/SRTLinker.git
   ```
2. `SRTLinker` 폴더 안의 **`설치_및_실행.bat`** 을 더블클릭합니다.
   - Python 자동 다운로드 + 패키지 설치가 진행됩니다 (인터넷 필요, 1~2분).
   - `.env` 파일이 자동 생성됩니다.
3. `.env` 파일을 메모장으로 열어 OpenAI API 키를 입력합니다:
   ```
   OPENAI_API_KEY=sk-proj-여기에-실제-키-입력
   OPENAI_MODEL=gpt-4o
   ```
4. 다음부터는 **`SRTLinker.bat`** 더블클릭으로 실행합니다.

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
OPENAI_MODEL=gpt-4o
```

실행:
```powershell
python gui_web.py
```
브라우저에서 `http://localhost:8456` 으로 접속됩니다.

### macOS / Linux

```bash
git clone https://github.com/cheringring/SRTLinker.git
cd SRTLinker

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

echo "OPENAI_API_KEY=sk-proj-여기에-실제-키-입력" > .env
python3 gui_web.py
```

> `imageio-ffmpeg`가 포터블 ffmpeg 바이너리를 자동 제공하므로 별도 ffmpeg 설치는 불필요합니다.

---

## 사용법

### 웹 GUI (추천)

`SRTLinker.bat`을 더블클릭하거나 `python gui_web.py`로 실행합니다.
브라우저에서 `http://localhost:8456` 이 자동으로 열립니다.

1. 파일을 **드래그앤드롭** 하거나, 경로를 직접 입력하거나, **파일 찾기** 버튼 클릭
2. 설정 확인:
   - **번역 언어**: 번역할 대상 언어 (기본: Korean)
   - **원본 언어**: 원본 자막 언어 힌트 (기본: en)
   - **번역 모델**: GPT 모델 (기본: gpt-4o)
   - **전사 모델**: Whisper 모델 (기본: whisper-1)
3. **`번역 시작`** 클릭
4. 진행률과 로그가 실시간으로 표시됩니다
5. 완료 후 `출력 폴더` 버튼으로 결과 확인

### 출력 구조

```
output/
  en/
    raw/영상.raw.srt    ← Whisper 전사 원본 (한번 만들면 재사용)
    영상.en.srt          ← 정리된 영어 SRT (문장 병합 + 화자 분리)
  ko/
    영상.ko.srt          ← 한국어 번역 SRT
```

- `en/raw/` — Whisper 전사 원본. 한번 생성되면 재사용되어 전사 비용이 다시 들지 않음
- `en/` — 정리된 영어 SRT. 코드 수정 시 매번 새로 생성됨
- `ko/` — 한국어 번역 결과

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
| `--chunk-size` | 한 번에 번역할 블록 수 | `30` |
| `--context-size` | 앞뒤 참고 블록 수 | `5` |
| `--glossary` | 용어집 JSON 경로 | `glossary.json` |
| `--suffix` | 출력 파일 접미사 | `.ko` |

### 번역 테스트 (빠른 확인용)

전체 파이프라인을 돌리지 않고 특정 구간만 빠르게 번역 테스트할 수 있습니다:

```powershell
# 기본: 블록 1~30 구간 번역
python test_translate.py output/en/영상.en.srt

# 특정 구간
python test_translate.py output/en/영상.en.srt --start 50 --count 10

# 자동 난이도 테스트 (긴문장, 복잡문장, 구어체 등 자동 선별)
python test_translate.py output/en/영상.en.srt --auto --pick 3
```

---

## 동작 흐름 (파이프라인)

```
입력 파일 (영상/오디오/SRT)
  │
  ├─ [영상/오디오] Whisper API 전사 → raw SRT 생성
  │   └─ output/en/raw/영상.raw.srt (한번만, 이후 재사용)
  │
  ├─ 영어 SRT 후처리
  │   ├─ 긴 블록 분할 (8초 초과 → 문장 단위로 분할)
  │   ├─ 필러 제거 ("Uh.", "Um." 등 필러 전용 블록 삭제)
  │   ├─ 불완전 문장 병합 (전치사/접속사로 끝나는 블록 → 다음 블록에 합침)
  │   ├─ 화자 전환 분리 (? 뒤 답변 패턴, 시간 갭, 응답 시작 패턴)
  │   └─ 문장 병합 (한 블록 = 한 문장으로 정리)
  │       └─ output/en/영상.en.srt
  │
  ├─ 번역 (GPT)
  │   ├─ chunk 단위로 묶어서 문맥(context_before/after) 제공
  │   ├─ JSON Schema strict 모드로 id 매핑 보장
  │   ├─ 원문 부호 구조 유지 (쉼표→마침표 변환 금지)
  │   └─ id 누락 시 해당 청크만 자동 재시도
  │       └─ output/ko/영상.ko.srt
  │
  └─ 영어/한국어 SRT 동일한 블록 수·타임스탬프 유지
```

---

## 번역 프롬프팅 설계

GPT에게 번역을 요청할 때 단순히 "번역해줘"가 아니라, 영상 자막 번역에 특화된 규칙들을 시스템 프롬프트로 전달합니다. 이 규칙들은 실제 번역 결과를 보면서 문제가 발견될 때마다 하나씩 추가/수정한 것입니다.

### 시스템 프롬프트 구조

GPT에게 "너는 전문 영상 자막 번역가이다"라는 역할을 부여하고, 아래 규칙들을 반드시 지키도록 지시합니다:

**입출력 구조 규칙**
- translate 배열의 각 블록만 번역하고, context_before/context_after는 문맥 참고용 (번역 대상 아님)
- 출력의 id 집합과 순서는 입력과 정확히 일치해야 함 (id 추가/삭제/변경 금지)
- 한 블록 = 하나의 번역 (블록 경계 바꾸기 안 됨)
- 출력은 반드시 `{items:[{id, text}]}` JSON 스키마를 따름

**번역 품질 규칙**
- 의역 허용, 직역보다 의미 기반 자연스러운 표현 우선. 정보를 임의 추가/생략하지 않음
- 회의/교육 톤에 맞는 경어 반말(~합니다 / ~입니다) 사용
- 구어체(uh, um, you know, like 등 필러)는 자연스러운 범위 내에서 제거 가능

**용어 처리 규칙**
- 기술 용어(Anzo, Ontology, Dataset, Knowledge Graph, RDF, SPARQL, API, SDK, JSON 등)는 영문 그대로 유지
- 고유명사/제품명/버전명은 원문 표기 유지
- `glossary.json`에 정의된 고정 번역 반드시 적용

**부호 구조 유지 규칙 (핵심)**
- 원문이 쉼표(,)로 이어지는 문장이면 번역문도 쉼표로 이어야 함
- 원문에 마침표(./!/?/)가 없는데 번역문에 마침표를 추가하지 않음
- 원문의 문장 부호 구조를 그대로 따름

이 규칙이 중요한 이유: Whisper가 만든 SRT에서 한 문장이 여러 블록으로 쪼개져 있을 때, 각 블록을 독립적으로 번역하면 GPT가 쉼표로 이어지는 문장을 마침표로 끊어버리는 문제가 있었음. 이 규칙을 추가해서 원문의 부호 구조를 유지하도록 강제함.

### 유저 페이로드 구조

번역 요청 시 GPT에게 보내는 데이터:

```json
{
  "target_language": "Korean",
  "context_before": [{"id": 8, "text": "이전 블록 텍스트"}],
  "translate": [
    {"id": 9, "text": "번역할 블록 1"},
    {"id": 10, "text": "번역할 블록 2"}
  ],
  "context_after": [{"id": 11, "text": "다음 블록 텍스트"}],
  "instruction": "translate 배열의 각 블록을 target_language로 번역하고, {items:[{id,text}]} 형태의 JSON으로만 응답하라."
}
```

- `context_before/after`: 앞뒤 5개 블록을 문맥으로 제공 (번역 대상 아님)
- `translate`: 실제 번역할 블록들 (30개씩 chunk)
- GPT는 JSON Schema strict 모드로 응답하므로 id 매핑이 보장됨

### 용어집 (glossary.json)

```json
{
  "keep_as_is": ["Anzo", "Ontology", "SPARQL", "RDF", "Graph", "Cambridge Semantics"],
  "fixed_translations": {
    "knowledge graph": "지식 그래프",
    "data fabric": "데이터 패브릭"
  }
}
```

- `keep_as_is`: 번역하지 않고 원문 그대로 유지할 단어 목록
- `fixed_translations`: 항상 지정된 번역을 사용할 단어 매핑
- 시스템 프롬프트에 자동으로 주입되어 GPT가 번역 시 참고

### 번역 안정성 보장

- OpenAI Structured Outputs (JSON Schema strict 모드)로 응답 형식 강제
- id 누락 시 해당 블록만 자동 재요청 (최대 1회)
- 최종적으로도 누락되면 원문 텍스트 유지 (빈 번역 방지)
- API 일시 장애 시 exponential backoff 재시도 (tenacity 라이브러리)

---

## 트러블슈팅

### 화자 전환이 분리되지 않는 경우

Whisper가 여러 화자의 발화를 하나의 블록에 넣는 경우가 있습니다.

**현재 적용된 해결책:**
- `?` 뒤에 답변이 오는 패턴 자동 감지 ("That's", "Yes", "I think" 등)
- 시간 갭 1초 이상 + 문장 끝이면 화자 전환으로 판단
- "Yeah", "Sure", "Thanks" 등 응답 시작 패턴 감지

**추가 조치가 필요한 경우:**
- `transcriber.py`의 `_QA_SPLIT` 패턴에 새로운 답변 시작 단어 추가
- `sentence_merger.py`의 `_RESPONSE_START` 패턴에 새로운 응답 패턴 추가

### 번역에서 쉼표가 마침표로 바뀌는 경우

원문이 쉼표(`,`)로 이어지는 한 문장인데 번역에서 마침표(`.`)로 끊기는 문제.

**현재 적용된 해결책:**
- `prompts.py`에 "원문이 쉼표로 이어지면 번역도 쉼표로 유지" 규칙 추가
- 문장 병합으로 영어 SRT를 한 문장 단위로 정리하여 문장 중간 끊김 방지

### 긴 블록에 여러 문장이 섞이는 경우

Whisper가 30초 이상의 긴 블록을 생성하는 경우.

**현재 적용된 해결책:**
- `_split_long_blocks`: 8초 초과 블록을 문장 종결 부호(`. ? !`)로 자동 분할
- 화자 전환 패턴으로 추가 분할 ("but just", "yeah", "thanks" 등)
- `_clean_whisper_artifacts` 후 재분할로 병합 과정에서 다시 길어진 블록 처리

### "그래서 팔." 같은 의미 없는 번역

Whisper 오인식으로 원문 자체가 이상한 경우 ("So in the arm." ← "So in the, um").

**현재 적용된 해결책:**
- `_clean_whisper_artifacts`에서 전치사/접속사로 끝나는 불완전 문장을 다음 블록에 병합
- 필러 전용 블록("Uh.", "Um.", "Okay." 등) 자동 제거

### 전사를 다시 하지 않고 영어 SRT만 재생성하고 싶은 경우

`output/en/raw/` 폴더에 Whisper 전사 원본이 보존됩니다. 코드를 수정한 후 다시 번역을 실행하면:
1. 전사는 건너뜀 (raw 재사용)
2. 영어 SRT 후처리가 최신 코드로 새로 적용됨
3. 번역도 새로 실행됨

전사부터 다시 하고 싶으면 `output/en/raw/` 폴더의 `.raw.srt` 파일을 삭제하면 됩니다.

### Failed to fetch 오류 (웹 GUI)

대용량 영상 파일을 드래그앤드롭할 때 발생할 수 있습니다.

**해결:**
- 경로 직접 입력란에 파일 경로를 붙여넣기 (업로드 없이 로컬 경로로 처리)
- 또는 `파일 찾기` 버튼으로 OS 파일 다이얼로그 사용

---

## 용어집 설정

`glossary.json` 파일로 고유명사와 고정 번역을 관리합니다:

```json
{
  "keep_as_is": ["Anzo", "SPARQL", "RDF", "Elasticsearch", "GDI", "PDI"],
  "fixed_translations": {
    "Knowledge Graph": "Knowledge Graph",
    "graph mark": "그래프 마크"
  }
}
```

- `keep_as_is`: 번역하지 않고 원문 그대로 유지할 단어
- `fixed_translations`: 항상 지정된 번역을 사용할 단어

---

## 프로젝트 구조

```
SRTLinker/
├── install.bat          # 자동 설치 스크립트 (Windows)
├── SRTLinker.bat        # 실행 스크립트 (Windows)
├── gui_web.py           # Flask 웹 GUI (localhost:8456)
├── main.py              # CLI 엔트리포인트
├── pipeline.py          # 전사 → 정리 → 번역 파이프라인
├── transcriber.py       # Whisper API 전사 + 후처리 (분할/필러제거/화자분리)
├── translator.py        # OpenAI 번역 + Structured Outputs + 재시도
├── sentence_merger.py   # 문장 경계 인식 + 화자 전환 감지 + 블록 병합
├── srt_chunker.py       # SRT 파싱 / 청킹 / 재조립
├── prompts.py           # 번역 프롬프트 (규칙 + 용어집)
├── verify.py            # 번역 결과 정합성 검증
├── glossary.json        # 고유명사 & 고정 번역
├── test_translate.py    # 번역 퀵 테스트 (특정 구간/자동 난이도)
├── build_installer.py   # exe 인스톨러 빌드 (Inno Setup)
├── requirements.txt     # 패키지 목록
└── output/
    ├── en/
    │   ├── raw/         # Whisper 전사 원본 (재사용)
    │   └── *.en.srt     # 정리된 영어 SRT
    └── ko/
        └── *.ko.srt     # 한국어 번역 SRT
```

---

## exe 인스톨러 빌드

개발이 완료된 후 배포용 exe를 만들려면:

```powershell
python build_installer.py
```

1. Python embeddable 다운로드
2. 의존성 설치
3. 프로젝트 파일 복사
4. Inno Setup 스크립트 생성

생성된 `.iss` 파일을 [Inno Setup](https://jrsoftware.org/isinfo.php)으로 컴파일하면 설치 exe가 만들어집니다.

---

## 자주 묻는 질문

**Q. OpenAI API 키는 어디서 발급하나요?**
[OpenAI Platform](https://platform.openai.com/api-keys)에서 발급받을 수 있습니다. 유료 크레딧이 필요합니다.

**Q. 번역 비용은 얼마나 드나요?**
파일 크기와 자막 수에 따라 다르지만, 일반적인 1시간 영상 기준 약 $0.5~$2 정도입니다 (gpt-4o 기준).

**Q. 영상 파일이 아주 큰데 괜찮나요?**
영상은 로컬에서 오디오만 추출한 뒤 Whisper API로 전송합니다. 25MB 초과 시 자동으로 10분 단위로 분할 처리됩니다.

**Q. 인터넷 없이 사용할 수 있나요?**
OpenAI API를 사용하므로 인터넷 연결이 필요합니다.

**Q. 서버 비용이 드나요?**
아닙니다. 로컬 Flask 서버(localhost)로 동작하므로 서버 비용은 없습니다. OpenAI API 사용료만 발생합니다.

**Q. 전사를 다시 하고 싶으면?**
`output/en/raw/` 폴더의 `.raw.srt` 파일을 삭제하고 다시 실행하면 됩니다.

---

## 라이선스

MIT License
-----


#### 코드 수정 후 exe 다시 만들기


```powershell
python build_installer.py

```