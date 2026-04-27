"""SRTLinker CLI \uc5d4\ud2b8\ub9ac\ud3ec\uc778\ud2b8 (video/audio/srt \u2192 \ubc88\uc5ed\ub41c srt)."""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from pipeline import process_file, PipelineConfig
from transcriber import VIDEO_EXTS, AUDIO_EXTS

SUPPORTED = {".srt"} | VIDEO_EXTS | AUDIO_EXTS


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SRTLinker - \ube44\ub514\uc624/\uc790\ub9c9 \ubb38\ub9e5 \ubcf4\uc874 \ubc88\uc5ed")
    p.add_argument("input", type=Path, help="\uc785\ub825 \ud30c\uc77c \ub610\ub294 \ud3f4\ub354")
    p.add_argument("-o", "--output", type=Path, default=Path("output"))
    p.add_argument("-t", "--target-lang", default="Korean")
    p.add_argument("-s", "--source-lang", default=None, help="Whisper \uc5b8\uc5b4 \ud78c\ud2b8 (\uc608: en)")
    p.add_argument("-m", "--model", default=None, help="\ubc88\uc5ed \ubaa8\ub378 (\uae30\ubcf8: env OPENAI_MODEL \ub610\ub294 gpt-4o)")
    p.add_argument("--stt-model", default="whisper-1")
    p.add_argument("--chunk-size", type=int, default=20)
    p.add_argument("--context-size", type=int, default=5)
    p.add_argument("--glossary", type=Path, default=Path("glossary.json"))
    p.add_argument("--suffix", default=".ko")
    return p.parse_args()


def collect(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted([p for p in path.iterdir() if p.suffix.lower() in SUPPORTED])
    if path.is_file():
        return [path]
    raise FileNotFoundError(path)


def main() -> int:
    load_dotenv()
    args = parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        print("[!] OPENAI_API_KEY \ubbf8\uc124\uc815", file=sys.stderr)
        return 2

    model = args.model or os.environ.get("OPENAI_MODEL") or "gpt-4o"
    cfg = PipelineConfig(
        model_translate=model,
        model_transcribe=args.stt_model,
        target_lang=args.target_lang,
        source_lang=args.source_lang,
        chunk_size=args.chunk_size,
        context_size=args.context_size,
        glossary_path=args.glossary if args.glossary.exists() else None,
        output_dir=args.output,
        suffix=args.suffix,
    )

    try:
        inputs = collect(args.input)
    except FileNotFoundError as e:
        print(f"[!] \uacbd\ub85c \uc5c6\uc74c: {e}", file=sys.stderr)
        return 2
    if not inputs:
        print("[!] \ucc98\ub9ac\ud560 \ud30c\uc77c \uc5c6\uc74c", file=sys.stderr)
        return 1

    print(f"[=] model={model} stt={args.stt_model} lang={args.target_lang} files={len(inputs)}")

    def prog(msg: str, p: float):
        bar = "#" * int(p * 20)
        print(f"\r  [{bar:<20}] {p*100:5.1f}% {msg}", end="", flush=True)

    rc = 0
    for src in inputs:
        print(f"\n[+] {src.name}")
        try:
            out = process_file(src, cfg, progress=prog)
            print(f"\n  \u2713 \uc800\uc7a5: {out}")
        except Exception as e:
            print(f"\n  \u2717 \uc2e4\ud328: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
