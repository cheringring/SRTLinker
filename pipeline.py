"""\uc804\uccb4 \ud30c\uc774\ud504\ub77c\uc778: \ube44\ub514\uc624/\uc624\ub514\uc624/SRT \u2192 \ubc88\uc5ed\ub41c SRT (1:1 \uad6c\uc870 \uc720\uc9c0)."""
from __future__ import annotations
import pysrt
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from srt_chunker import load_srt, chunk_blocks, write_srt, Block
from translator import Translator, TranslatorConfig
from transcriber import video_to_srt, VIDEO_EXTS, AUDIO_EXTS
from sentence_merger import group_sentences, SentenceGroup, build_split_srt
from verify import verify_srt_pair, format_issues


ProgressCb = Callable[[str, float], None]  # (message, progress 0~1)


@dataclass
class PipelineConfig:
    model_translate: str = "gpt-4o"
    model_transcribe: str = "whisper-1"
    target_lang: str = "Korean"
    source_lang: str | None = None
    chunk_size: int = 20
    context_size: int = 5
    glossary_path: Path | None = None
    output_dir: Path = Path("output")
    suffix: str = ".ko"
    sentence_aware: bool = True   # \ubb38\uc7a5\uc778\uc2dd \ubd84\ud560 \ubc88\uc5ed (1:1 \uad6c\uc870 \uc720\uc9c0 + \uc790\uc5f0\uc2a4\ub7ec\uc6b4 \ubc88\uc5ed)
    max_merge_blocks: int = 8     # \ubd80\ud638 \uc5c6\uc774 \ub204\uc801\ub420 \uc218 \uc788\ub294 \ucd5c\ub300 \ube14\ub85d (\ubb38\uc7a5 \uadf8\ub8f9 \uc548\uc804\uc7a5\uce58)
    sentence_chunk_size: int = 8  # \ud55c \uccad\ud06c\uc5d0 \ubaa8\uc744 \ubb38\uc7a5 \uadf8\ub8f9 \uc218
    sentence_context_size: int = 2  # \uc55e\ub4a4 \ubb38\ub9e5 \uadf8\ub8f9 \uc218

    # \ud558\uc704 \ud638\ud658\uc131
    @property
    def merge_sentences(self) -> bool:
        return self.sentence_aware


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
    ext = src.suffix.lower()
    if ext == ".srt":
        return src
    if ext in VIDEO_EXTS or ext in AUDIO_EXTS:
        srt_path = cfg.output_dir / f"{src.stem}.srt"
        if srt_path.exists():
            if progress:
                progress(f"\uae30\uc874 SRT \uc7ac\uc0ac\uc6a9: {srt_path.name}", 0.4)
            return srt_path
        if progress:
            progress("\ubbf8\ub514\uc5b4 \u2192 SRT \ubcc0\ud658 \uc2dc\uc791", 0.05)
        video_to_srt(
            src, srt_path,
            model=cfg.model_transcribe,
            language=cfg.source_lang,
            progress_cb=lambda m: progress(m, 0.15) if progress else None,
        )
        if progress:
            progress("SRT \uc0dd\uc131 \uc644\ub8cc", 0.4)
        return srt_path
    raise ValueError(f"\uc9c0\uc6d0\ud558\uc9c0 \uc54a\ub294 \ud30c\uc77c \ud615\uc2dd: {ext}")


def _translate_blocks(translator: Translator, blocks: list[Block], cfg: PipelineConfig, progress: ProgressCb | None, base: float = 0.45) -> dict[int, str]:
    chunks = list(chunk_blocks(blocks, chunk_size=cfg.chunk_size, context_size=cfg.context_size))
    if progress:
        progress(f"\ubc88\uc5ed \uc2dc\uc791 ({len(blocks)}\ube14\ub85d / {len(chunks)}\uccad\ud06c)", base)
    merged: dict[int, str] = {}
    total = max(1, len(chunks))
    for idx, ch in enumerate(chunks, 1):
        merged.update(translator.translate_chunk(ch))
        if progress:
            progress(f"\ubc88\uc5ed \uc9c4\ud589 {idx}/{total}", base + (1.0 - base - 0.05) * (idx / total))
    return merged


def process_file(src: Path, cfg: PipelineConfig, progress: ProgressCb | None = None) -> Path:
    src = Path(src)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    # 1) SRT \ud655\ubcf4 (\uc601\uc0c1\uc774\uba74 \uc804\uc0ac)
    srt_path = _transcribe_if_needed(src, cfg, progress)

    translator = Translator(TranslatorConfig(
        model=cfg.model_translate,
        target_lang=cfg.target_lang,
        glossary_path=cfg.glossary_path,
    ))

    out_path = _next_available_path(cfg.output_dir / f"{src.stem}{cfg.suffix}.srt")

    if cfg.sentence_aware:
        # \ubb38\uc7a5 \ub2e8\uc704 \ubcd1\ud569 \ucd9c\ub825: \ud55c \ubb38\uc7a5 = \ud55c \uc790\uba89 \ube14\ub85d (\ud0c0\uc784\uc2a4\ud0ec\ud504\ub3c4 \ubcd1\ud569)
        original = pysrt.open(str(srt_path), encoding="utf-8")
        groups = group_sentences(original, max_blocks=cfg.max_merge_blocks)
        if progress:
            progress(f"\ubb38\uc7a5 \uadf8\ub8f9\ud551: {len(original)}\ube14\ub85d \u2192 {len(groups)}\ubb38\uc7a5", 0.42)

        # \uac01 \ubb38\uc7a5\uc744 \ud558\ub098\uc758 Block\uc73c\ub85c \ubc88\uc5ed (id = \ubb38\uc7a5 \uc21c\uc11c)
        sent_blocks = [Block(id=i + 1, text=g.text) for i, g in enumerate(groups)]
        translations = _translate_blocks(translator, sent_blocks, cfg, progress)

        merged_srt = build_split_srt(original, groups, translations)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        merged_srt.save(str(out_path), encoding="utf-8")
    else:
        # \uc21c\uc218 1:1 \ube14\ub85d \ubcc4 \ubc88\uc5ed (\uc774\uc804 \uae30\ubcf8 \ub3d9\uc791)
        original, blocks = load_srt(srt_path)
        translations = _translate_blocks(translator, blocks, cfg, progress)
        write_srt(original, translations, out_path)

    # \uc815\ud569\uc131 \uac80\uc99d
    try:
        issues = verify_srt_pair(srt_path, out_path)
        if issues and progress:
            progress(f"\u26a0 \uc815\ud569\uc131 \uacbd\uace0: {format_issues(issues)}", 0.98)
    except Exception as e:
        if progress:
            progress(f"\uac80\uc99d \uc2e4\ud328(\ubb34\uc2dc): {e}", 0.98)

    if progress:
        progress(f"\uc644\ub8cc: {out_path.name}", 1.0)
    return out_path
