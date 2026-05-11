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

def _split_long_blocks(srt_text: str, max_duration_sec: float = 8.0) -> str:
    """Whisper가 만든 블록을 문장/화자 전환 단위로 분할.

    - 8초 초과 블록: 문장 종결 부호(. ? !)로 분할 + 화자 전환 패턴 분할
    - 모든 블록: ? 뒤에 답변이 오는 패턴은 무조건 분할 (화자 전환)
    """
    import pysrt
    import re

    subs = pysrt.from_string(srt_text)
    if not subs:
        return srt_text

    # 문장 분할: .!? 뒤에 대문자로 시작하는 새 문장이 올 때만 분할
    # "Dr. Smith", "U.S. government" 등 약어 후 소문자는 분할 안 됨
    _SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
    
    # 화자 전환 패턴: 쉼표/마침표 뒤 + 명확한 전환어만 분할
    # 주의: "make sure", "I think that..." 같은 일반 문장 중간 패턴은 절대 포함하지 않음
    _SPEAKER_SPLIT = re.compile(
        r'(?<=[.!?,])\s+(?=(?:Yeah|Yes|No|Okay so|Thanks|Thank you|That\'s great|Absolutely|Exactly|Right so|All right))',
        re.I,
    )
    # ? 뒤에 답변이 오는 패턴 (화자 전환 거의 확실)
    _QA_SPLIT = re.compile(
        r'(\?)\s+(That\'s|Yes|Yeah|No|So|Sure|I |We |It |The |My |OK|Okay|Absolutely|Exactly|Right)',
    )

    out = pysrt.SubRipFile()

    for sub in subs:
        duration_ms = sub.end.ordinal - sub.start.ordinal
        duration_sec = duration_ms / 1000.0
        text = sub.text.strip()

        if not text:
            out.append(pysrt.SubRipItem(
                index=len(out) + 1, start=sub.start, end=sub.end, text=text,
            ))
            continue

        # 모든 블록: ? 뒤 답변 패턴 분할 (화자 전환)
        qa_parts = _QA_SPLIT.split(text)
        if len(qa_parts) > 1:
            # 재조합: split이 캡처 그룹 때문에 [질문부분, '?', '답변시작', 나머지...] 형태
            reassembled = []
            i = 0
            while i < len(qa_parts):
                part = qa_parts[i].strip()
                if part == '?' and reassembled:
                    reassembled[-1] = reassembled[-1] + '?'
                    i += 1
                    continue
                if part and i > 0 and reassembled and not reassembled[-1].endswith('?'):
                    reassembled[-1] = reassembled[-1] + ' ' + part
                elif part:
                    reassembled.append(part)
                i += 1
            if len(reassembled) > 1:
                total_chars = sum(len(p) for p in reassembled) or 1
                cursor_ms = sub.start.ordinal
                for si, part in enumerate(reassembled):
                    ratio = len(part) / total_chars
                    seg_dur = int(duration_ms * ratio)
                    seg_start = cursor_ms
                    seg_end = cursor_ms + seg_dur if si < len(reassembled) - 1 else sub.end.ordinal
                    cursor_ms = seg_end
                    out.append(pysrt.SubRipItem(
                        index=len(out) + 1,
                        start=pysrt.SubRipTime.from_ordinal(seg_start),
                        end=pysrt.SubRipTime.from_ordinal(seg_end),
                        text=part,
                    ))
                continue

        # 짧은 블록도 여러 문장이 있으면 분할
        sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
        
        if len(sentences) > 1:
            # 여러 문장이 있으면 분할
            total_chars = sum(len(s) for s in sentences) or 1
            cursor_ms = sub.start.ordinal
            
            for si, sent in enumerate(sentences):
                ratio = len(sent) / total_chars
                seg_duration = int(duration_ms * ratio)
                seg_start = cursor_ms
                seg_end = cursor_ms + seg_duration if si < len(sentences) - 1 else sub.end.ordinal
                cursor_ms = seg_end
                
                out.append(pysrt.SubRipItem(
                    index=len(out) + 1,
                    start=pysrt.SubRipTime.from_ordinal(seg_start),
                    end=pysrt.SubRipTime.from_ordinal(seg_end),
                    text=sent,
                ))
            continue
        
        # 한 문장이면 그대로
        if duration_sec <= max_duration_sec:
            out.append(pysrt.SubRipItem(
                index=len(out) + 1, start=sub.start, end=sub.end, text=text,
            ))
            continue

        # 8초 초과: 문장 종결 부호로 분할
        sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]

        # 긴 조각은 화자 전환 패턴으로 추가 분할
        final_parts = []
        for sent in sentences:
            if len(sent) > 60:
                sub_parts = [p.strip() for p in _SPEAKER_SPLIT.split(sent) if p.strip()]
                final_parts.extend(sub_parts)
            else:
                final_parts.append(sent)

        if len(final_parts) <= 1:
            out.append(pysrt.SubRipItem(
                index=len(out) + 1, start=sub.start, end=sub.end, text=text,
            ))
            continue

        total_chars = sum(len(s) for s in final_parts) or 1
        cursor_ms = sub.start.ordinal

        for si, part in enumerate(final_parts):
            ratio = len(part) / total_chars
            seg_duration = int(duration_ms * ratio)
            seg_start = cursor_ms
            seg_end = cursor_ms + seg_duration if si < len(final_parts) - 1 else sub.end.ordinal
            cursor_ms = seg_end

            out.append(pysrt.SubRipItem(
                index=len(out) + 1,
                start=pysrt.SubRipTime.from_ordinal(seg_start),
                end=pysrt.SubRipTime.from_ordinal(seg_end),
                text=part,
            ))

    out.clean_indexes()
    return "\n".join(str(s) for s in out)

def _clean_whisper_artifacts(srt_text: str) -> str:
    """Whisper 전사 후처리: 필러 블록 제거 + 불완전 문장을 다음 블록에 병합.

    - "Uh.", "Um.", "Hmm." 등 필러만 있는 블록 제거
    - 불완전 문장을 다음 블록에 병합 (불완전 문장은 30초, 완결 문장은 15초 제한)
    - 온점이 있으면 완결된 문장으로 간주하여 절대 병합하지 않음
    - 온점이 없으면 불완전 문장으로 간주하여 다음 블록과 병합
    """
    import pysrt
    import re

    subs = pysrt.from_string(srt_text)
    if not subs:
        return srt_text

    _FILLER_ONLY = re.compile(
        r'^(uh+|um+|hmm+|ah+|oh+|er+|huh|mhm|mm+|okay|so|and|but|right|yeah|yes|well|you know|I mean)[.!?,\s]*$',
        re.I,
    )
    cleaned = [s for s in subs if not _FILLER_ONLY.match(s.text.strip())]

    _SENT_END = re.compile(r'[.!?\u2026][\"\'\)\]\u201d\u2019]?\s*$')

    MAX_MERGE_MS = 15000  # 완결 문장 병합 soft 제한
    MAX_MERGE_HARD_MS = 30000  # 불완전 문장은 여기까지 허용 (문장이 끊기는 것보다 나음)

    merged = []
    pending_text = ""
    pending_start = None
    pending_end = None

    for idx, sub in enumerate(cleaned):
        text = sub.text.strip()
        if not text:
            continue

        # pending이 있으면 현재 블록과 병합
        if pending_text:
            merged_duration = sub.end.ordinal - pending_start.ordinal
            # 불완전 문장(pending)은 hard 제한까지 병합 허용
            limit = MAX_MERGE_HARD_MS if not _SENT_END.search(pending_text) else MAX_MERGE_MS
            if merged_duration <= limit:
                # 병합
                text = pending_text + " " + text
                start = pending_start
            else:
                # 너무 길면 pending을 별도 블록으로 저장
                merged.append(pysrt.SubRipItem(
                    index=len(merged) + 1,
                    start=pending_start,
                    end=pending_end,
                    text=pending_text,
                ))
                start = sub.start
            pending_text = ""
            pending_start = None
            pending_end = None
        else:
            start = sub.start

        # 온점이 있으면 완결된 문장, 없으면 불완전 문장
        has_period = bool(_SENT_END.search(text))
        
        if has_period:
            # 완결된 문장 → 바로 저장
            merged.append(pysrt.SubRipItem(
                index=len(merged) + 1,
                start=start,
                end=sub.end,
                text=text,
            ))
        else:
            # 불완전 문장 → pending에 저장하고 다음 블록과 병합 대기
            pending_text = text
            pending_start = start
            pending_end = sub.end

    # 마지막 pending 처리
    if pending_text:
        if merged:
            # 마지막 블록에 붙이기
            merged[-1].text = merged[-1].text + " " + pending_text
            merged[-1].end = pending_end
        else:
            # merged가 비어있으면 그냥 추가
            merged.append(pysrt.SubRipItem(
                index=1,
                start=pending_start,
                end=pending_end,
                text=pending_text,
            ))

    out = pysrt.SubRipFile(items=merged)
    out.clean_indexes()
    return "\n".join(str(s) for s in out)


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
                try:
                    text = transcribe_audio(chunk_path, model, language, client)
                except Exception as e:
                    # 중간 실패: 지금까지 전사된 부분이라도 저장
                    if parts:
                        partial = _renumber_srt("\n\n".join(p for p in parts if p.strip()))
                        out_srt.parent.mkdir(parents=True, exist_ok=True)
                        out_srt.write_text(partial, encoding="utf-8")
                        if progress_cb:
                            progress_cb(f"\uc804\uc0ac \uc911\ub2e8: {i-1}/{total} \uccad\ud06c\uae4c\uc9c0 \uc800\uc7a5\ub428 → {out_srt.name}")
                    raise RuntimeError(
                        f"\uc804\uc0ac \uc2e4\ud328 (청크 {i}/{total}): {e}\n"
                        f"{'→ ' + str(i-1) + '개 청크는 ' + str(out_srt) + ' 에 부분 저장됨' if parts else '→ 저장된 부분 없음'}"
                    ) from e
                parts.append(_shift_srt(text, offset))
            srt_text = _renumber_srt("\n\n".join(p for p in parts if p.strip()))

        out_srt.parent.mkdir(parents=True, exist_ok=True)
        # raw 그대로 저장 (후처리는 pipeline.process_file에서 1회만 수행)
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
