"""SRT \ud30c\uc2f1 \ubc0f \uccad\ud0b9 \uc720\ud2f8\ub9ac\ud2f0."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import pysrt


@dataclass
class Block:
    id: int  # 1-based, \uc6d0\ubcf8 SRT index
    text: str


@dataclass
class Chunk:
    translate: list[Block]
    context_before: list[Block]
    context_after: list[Block]


def load_srt(path: Path) -> tuple[pysrt.SubRipFile, list[Block]]:
    """SRT \ud30c\uc77c\uc744 \uc77d\uace0 (\uc6d0\ubcf8 \uac1d\uccb4, \ube14\ub85d \ub9ac\uc2a4\ud2b8) \ubc18\ud658."""
    subs = pysrt.open(str(path), encoding="utf-8")
    blocks = [Block(id=i + 1, text=s.text) for i, s in enumerate(subs)]
    return subs, blocks


def chunk_blocks(blocks: list[Block], chunk_size: int = 20, context_size: int = 5) -> Iterator[Chunk]:
    n = len(blocks)
    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        translate = blocks[start:end]
        before = blocks[max(0, start - context_size):start]
        after = blocks[end:min(n, end + context_size)]
        yield Chunk(translate=translate, context_before=before, context_after=after)


def blocks_to_dicts(bs: list[Block]) -> list[dict]:
    return [{"id": b.id, "text": b.text} for b in bs]


def write_srt(original: pysrt.SubRipFile, translated: dict[int, str], out_path: Path) -> None:
    """\ubc88\uc5ed\ubb38\uc744 \uc6d0\ubcf8 \ud0c0\uc784\uc2a4\ud0ec\ud504\uc5d0 \ub9e4\ud551\ud574 \uc0c8 SRT\ub85c \uc800\uc7a5."""
    for i, sub in enumerate(original):
        new_text = translated.get(i + 1)
        if new_text is not None:
            sub.text = new_text
    out_path.parent.mkdir(parents=True, exist_ok=True)
    original.save(str(out_path), encoding="utf-8")
