"""\uc804\uccb4 \ud30c\uc774\ud504\ub77c\uc778: \ube44\ub514\uc624/\uc624\ub514\uc624/SRT \u2192 \ubc88\uc5ed\ub41c SRT (1:1 \uad6c\uc870 \uc720\uc9c0)."""
from __future__ import annotations
import pysrt
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from srt_chunker import load_srt, chunk_blocks, write_srt, Block
from translator import Translator, TranslatorConfig
from transcriber import video_to_srt, VIDEO_EXTS, AUDIO_EXTS, _split_long_blocks, _clean_whisper_artifacts
from sentence_merger import group_sentences, build_merged_srt


ProgressCb = Callable[[str, float], None]  # (message, progress 0~1)


@dataclass
class PipelineConfig:
    model_translate: str = "gpt-4o"
    model_transcribe: str = "whisper-1"
    target_lang: str = "Korean"
    source_lang: str | None = None
    chunk_size: int = 30
    context_size: int = 5
    parallel_workers: int = 1
    glossary_path: Path | None = None
    output_dir: Path = Path("output")
    suffix: str = ".ko"


def _next_available_path(base: Path) -> Path:
    """\ud30c\uc77c\uc774 \uc874\uc7ac\ud558\uba74 _2, _3 ... \uc811\ubbf8\uc0ac \ubd80\uc5ec\ud574 \ub300\uccb4 \uacbd\ub85c \ubc18\ud658."""
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix  # e.g. "video.ko", ".srt"
    n = 2
    while True:
        cand = base.with_name(f"{stem}_{n}{suffix}")
        if not cand.exists():
            return cand
        n += 1


def _transcribe_if_needed(src: Path, cfg: PipelineConfig, progress: ProgressCb | None) -> Path:
    """Whisper 전사 결과(raw)를 output/en/raw/ 에 저장. 이미 있으면 재사용."""
    ext = src.suffix.lower()
    if ext == ".srt":
        return src
    raw_dir = cfg.output_dir / "en" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
        srt_path = raw_dir / f"{src.stem}.raw.srt"
        if srt_path.exists():
            if progress:
                progress(f"기존 전사 재사용: {srt_path.name}", 0.4)
            return srt_path
        if progress:
            progress("미디어 → SRT 변환 시작", 0.05)
        video_to_srt(
            src, srt_path,
            model=cfg.model_transcribe,
            language=cfg.source_lang,
            progress_cb=lambda m: progress(m, 0.15) if progress else None,
        )
        if progress:
            progress("SRT 생성 완료", 0.4)
        return srt_path
    raise ValueError(f"지원하지 않는 파일 형식: {ext}")


def _translate_blocks(translator: Translator, blocks: list[Block], cfg: PipelineConfig, progress: ProgressCb | None, base: float = 0.45) -> dict[int, str]:
    chunks = list(chunk_blocks(blocks, chunk_size=cfg.chunk_size, context_size=cfg.context_size))
    if progress:
        progress(f"\ubc88\uc5ed \uc2dc\uc791 ({len(blocks)}\ube14\ub85d / {len(chunks)}\uccad\ud06c, {cfg.parallel_workers}\ubcd1\ub82c)", base)
    merged: dict[int, str] = {}
    total = max(1, len(chunks))
    done_count = 0

    def do_chunk(idx_ch):
        idx, ch = idx_ch
        return idx, translator.translate_chunk(ch)

    with ThreadPoolExecutor(max_workers=cfg.parallel_workers) as pool:
        futures = {pool.submit(do_chunk, (i, ch)): i for i, ch in enumerate(chunks, 1)}
        for future in as_completed(futures):
            idx, result = future.result()
            merged.update(result)
            done_count += 1
            if progress:
                progress(f"\ubc88\uc5ed \uc9c4\ud589 {done_count}/{total}", base + (1.0 - base - 0.05) * (done_count / total))
    return merged


def process_file(src: Path, cfg: PipelineConfig, progress: ProgressCb | None = None) -> Path:
    src = Path(src)

    en_dir = cfg.output_dir / "en"
    ko_dir = cfg.output_dir / "ko"
    en_dir.mkdir(parents=True, exist_ok=True)
    ko_dir.mkdir(parents=True, exist_ok=True)

    en_path = en_dir / f"{src.stem}.en.srt"

    # 1) 기존 en.srt가 있으면 전사+후처리 건너뜀 (수동 편집본 보존)
    if en_path.exists() and en_path.stat().st_size > 0:
        if progress:
            progress(f"기존 영어 SRT 재사용: {en_path.name}", 0.43)
    else:
        # 전사 원본(raw) 확보
        raw_srt_path = _transcribe_if_needed(src, cfg, progress)

        # raw → 긴 블록 분할 + 필러 제거 + 화자 분리
        raw_text = raw_srt_path.read_text(encoding="utf-8")
        clean_text = _split_long_blocks(raw_text)
        clean_text = _clean_whisper_artifacts(clean_text)

        # 정리된 영어 SRT 저장
        clean_subs = pysrt.from_string(clean_text)
        clean_subs.save(str(en_path), encoding="utf-8")
        if progress:
            progress(f"영어 SRT: {len(clean_subs)}블록 정리 완료", 0.43)

    # 2) 정리된 영어 SRT를 1:1 번역 → ko/
    translator = Translator(TranslatorConfig(
        model=cfg.model_translate,
        target_lang=cfg.target_lang,
        glossary_path=cfg.glossary_path,
    ))

    original, blocks = load_srt(en_path)
    translations = _translate_blocks(translator, blocks, cfg, progress)

    out_path = _next_available_path(ko_dir / f"{src.stem}{cfg.suffix}.srt")
    write_srt(original, translations, out_path)

    if progress:
        progress(f"완료: ko/{out_path.name}", 1.0)
    return out_path
