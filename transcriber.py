"""\ube44\ub514\uc624 \u2192 \uc624\ub514\uc624 \ucd94\ucd9c \ubc0f OpenAI Whisper \uc804\uc0ac (\uae34 \ud30c\uc77c \uc790\ub3d9 \ubd84\ud560)."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path
from openai import OpenAI

try:
    import imageio_ffmpeg
    _FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FFMPEG = "ffmpeg"


VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"}

# Whisper API \ud30c\uc77c \uc81c\ud55c 25MB. \uc5ec\uc720 \uac12 \ub450\uace0 24MB \uc774\ud558\uc5d0\uc11c \uccad\ud06c \ubd84\ud560.
_MAX_BYTES = 24 * 1024 * 1024
_CHUNK_SECONDS = 600  # 10\ubd84\uc529 \ubd84\ud560


def is_media(path: Path) -> bool:
    ext = path.suffix.lower()
    return ext in VIDEO_EXTS or ext in AUDIO_EXTS


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run([_FFMPEG, "-y", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg \uc2e4\ud328: {proc.stderr[-800:]}")


def _ffprobe_duration(path: Path) -> float:
    """ffmpeg\ub85c \uc9c0\uc18d\uc2dc\uac04 \uc5bb\uae30 (\ucd08). ffprobe \uc5c6\uc774 ffmpeg stderr \ud30c\uc2f1."""
    proc = subprocess.run(
        [_FFMPEG, "-i", str(path)],
        capture_output=True, text=True,
    )
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", proc.stderr)
    if not m:
        return 0.0
    h, mm, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mm * 60 + s


def extract_audio(src: Path, out_path: Path | None = None, bitrate: str = "32k") -> Path:
    """\uc800\uc6a9\ub7c9 opus(ogg) \uc2f1\uae00 \ud30c\uc77c\ub85c \ucd94\ucd9c."""
    if out_path is None:
        out_path = Path(tempfile.gettempdir()) / f"{src.stem}.srtlinker.ogg"
    _run_ffmpeg([
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "libopus", "-b:a", bitrate,
        str(out_path),
    ])
    return out_path


def split_audio(audio: Path, chunk_seconds: int = _CHUNK_SECONDS) -> list[tuple[Path, float]]:
    """\uc624\ub514\uc624\ub97c N\ucd08 \ub2e8\uc704\ub85c \ubd84\ud560. \ubc18\ud658: [(chunk_path, start_offset_seconds), ...]"""
    duration = _ffprobe_duration(audio)
    if duration <= 0:
        return [(audio, 0.0)]
    if duration <= chunk_seconds and audio.stat().st_size <= _MAX_BYTES:
        return [(audio, 0.0)]

    tmpdir = Path(tempfile.mkdtemp(prefix="srtlinker_chunks_"))
    out_pattern = tmpdir / f"{audio.stem}_%03d.ogg"
    # libopus \uc2a4\ud2b8\ub9bc \ubcf5\uc0ac\ub294 \ubd88\uac00\ub2a5\ud55c \uacbd\uc6b0\uac00 \uc788\uc5b4 \uc7ac\uc778\ucf54\ub529.
    _run_ffmpeg([
        "-i", str(audio),
        "-f", "segment", "-segment_time", str(chunk_seconds),
        "-ac", "1", "-ar", "16000",
        "-c:a", "libopus", "-b:a", "32k",
        "-reset_timestamps", "1",
        str(out_pattern),
    ])
    chunks = sorted(tmpdir.glob(f"{audio.stem}_*.ogg"))
    return [(c, i * chunk_seconds) for i, c in enumerate(chunks)]


def _shift_srt(srt_text: str, offset_seconds: float) -> str:
    """SRT \ud14d\uc2a4\ud2b8\uc758 \ubaa8\ub4e0 \ud0c0\uc784\uc2a4\ud0ec\ud504\uc5d0 offset \uc801\uc6a9."""
    if offset_seconds <= 0 or not srt_text:
        return srt_text
    import pysrt
    subs = pysrt.from_string(srt_text)
    subs.shift(seconds=offset_seconds)
    return "\n".join(str(s) for s in subs)


def _renumber_srt(srt_text: str) -> str:
    import pysrt
    subs = pysrt.from_string(srt_text)
    subs.clean_indexes()
    return "\n".join(str(s) for s in subs)


def transcribe_audio(audio: Path, model: str, language: str | None, client: OpenAI) -> str:
    with audio.open("rb") as f:
        kwargs = {"model": model, "file": f, "response_format": "srt"}
        if language:
            kwargs["language"] = language
        result = client.audio.transcriptions.create(**kwargs)
    return result if isinstance(result, str) else getattr(result, "text", str(result))


def video_to_srt(src: Path, out_srt: Path, model: str = "whisper-1", language: str | None = None, client: OpenAI | None = None, progress_cb=None) -> Path:
    """\ube44\ub514\uc624/\uc624\ub514\uc624 \u2192 SRT. 25MB \ucd08\uacfc \uc2dc \uc790\ub3d9 \uccad\ud06c \ubd84\ud560."""
    client = client or OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    if progress_cb:
        progress_cb("\uc624\ub514\uc624 \ucd94\ucd9c \uc911...")
    audio = extract_audio(src)
    tmp_dirs: list[Path] = []
    try:
        size_mb = audio.stat().st_size / (1024 * 1024)
        duration = _ffprobe_duration(audio)
        need_split = audio.stat().st_size > _MAX_BYTES or duration > _CHUNK_SECONDS * 1.5

        if not need_split:
            if progress_cb:
                progress_cb(f"\uc804\uc0ac \uc694\uccad \uc911 ({size_mb:.1f}MB, \ub2e8\uc77c)...")
            srt_text = transcribe_audio(audio, model, language, client)
        else:
            if progress_cb:
                progress_cb(f"\uae34 \uc624\ub514\uc624 \uac10\uc9c0({size_mb:.1f}MB, {duration/60:.1f}\ubd84) \u2192 \ubd84\ud560 \uc804\uc0ac...")
            chunks = split_audio(audio)
            if chunks and chunks[0][0].parent != audio.parent:
                tmp_dirs.append(chunks[0][0].parent)
            parts = []
            total = len(chunks)
            for i, (chunk_path, offset) in enumerate(chunks, 1):
                if progress_cb:
                    cs = chunk_path.stat().st_size / (1024 * 1024)
                    progress_cb(f"\uccad\ud06c \uc804\uc0ac {i}/{total} ({cs:.1f}MB)...")
                text = transcribe_audio(chunk_path, model, language, client)
                parts.append(_shift_srt(text, offset))
            srt_text = _renumber_srt("\n\n".join(p for p in parts if p.strip()))

        out_srt.parent.mkdir(parents=True, exist_ok=True)
        out_srt.write_text(srt_text, encoding="utf-8")
        return out_srt
    finally:
        try:
            audio.unlink(missing_ok=True)
        except Exception:
            pass
        for d in tmp_dirs:
            try:
                for f in d.iterdir():
                    f.unlink(missing_ok=True)
                d.rmdir()
            except Exception:
                pass


# \ud558\uc704 \ud638\ud658\uc131
def transcribe_to_srt(audio_path: Path, out_srt: Path, model: str = "whisper-1", language: str | None = None, client: OpenAI | None = None) -> Path:
    client = client or OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    text = transcribe_audio(audio_path, model, language, client)
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    out_srt.write_text(text, encoding="utf-8")
    return out_srt
