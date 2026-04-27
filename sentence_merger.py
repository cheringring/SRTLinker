"""\ud30c\ud3b8\ud654\ub41c SRT \ube14\ub85d\uc744 \ubb38\uc7a5 \ub2e8\uc704\ub85c \ubcd1\ud569."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
import pysrt


# \ubb38\uc7a5 \uc885\uacb0 \ubd80\ud638 (\ub4a4\uc5d0 \ub530\uc634\ud45c/\uad04\ud638 \ud5c8\uc6a9)
_SENT_END = re.compile(r'[.!?\u2026\uff01\uff1f\u3002][\"\'\)\]\u201d\u2019]?\s*$')


@dataclass
class SentenceGroup:
    """\uc5f0\uc18d\ub41c SRT \ube14\ub85d\uc744 \ud558\ub098\uc758 \ubb38\uc7a5\uc73c\ub85c \ubb36\uc740 \ub2e8\uc704."""
    indices: list[int] = field(default_factory=list)  # 1-based \uc6d0\ubcf8 SRT \uc778\ub371\uc2a4
    fragments: list[str] = field(default_factory=list)  # \uac01 \uc6d0\ubcf8 \ube14\ub85d\uc758 \ud14d\uc2a4\ud2b8
    starts_ms: list[int] = field(default_factory=list)  # fragment\ubcc4 \uc2dc\uc791 (ms)
    ends_ms: list[int] = field(default_factory=list)    # fragment\ubcc4 \uc885\ub8cc (ms)
    start: object = None  # pysrt.SubRipTime (\uadf8\ub8f9 \uc804\uccb4 \uc2dc\uc791)
    end: object = None    # pysrt.SubRipTime (\uadf8\ub8f9 \uc804\uccb4 \uc885\ub8cc)
    text: str = ""        # fragments\ub97c \uacf5\ubc31\uc73c\ub85c \uc774\uc740 \uc644\uc804\uccb4


def _normalize(text: str) -> str:
    # \uc904\ubc14\uafc8 \u2192 \uacf5\ubc31, \uc5f0\uc18d \uacf5\ubc31 \uc815\ub9ac
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def group_sentences(subs: pysrt.SubRipFile, max_blocks: int = 8) -> list[SentenceGroup]:
    """\uc5f0\uc18d \ube14\ub85d\uc744 \ubb38\uc7a5 \ub2e8\uc704\ub85c \ubcd1\ud569.

    - \ubd80\ud638\ub85c \ubb38\uc7a5 \ub05d\uc774 \ub098\ud0c0\ub098\uba74 \uadf8\ub8f9 \uc885\ub8cc.
    - \ubd80\ud638\uac00 \uc5c6\uc5b4\ub3c4 max_blocks \uac1c \uc30c\uc774\uba74 \uac15\uc81c \uc885\ub8cc (\ubb34\ud55c \ub204\uc801 \ubc29\uc9c0).
    """
    groups: list[SentenceGroup] = []
    cur_idx: list[int] = []
    cur_texts: list[str] = []

    def flush():
        if not cur_idx:
            return
        joined = _normalize(" ".join(cur_texts))
        starts_ms = [int(subs[i - 1].start.ordinal) for i in cur_idx]
        ends_ms = [int(subs[i - 1].end.ordinal) for i in cur_idx]
        groups.append(SentenceGroup(
            indices=list(cur_idx),
            fragments=list(cur_texts),
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            start=subs[cur_idx[0] - 1].start,
            end=subs[cur_idx[-1] - 1].end,
            text=joined,
        ))
        cur_idx.clear()
        cur_texts.clear()

    for i, sub in enumerate(subs, 1):
        text = _normalize(sub.text)
        if not text:
            continue
        cur_idx.append(i)
        cur_texts.append(text)
        ends = bool(_SENT_END.search(text))
        if ends or len(cur_idx) >= max_blocks:
            flush()

    flush()
    return groups


def build_merged_srt(groups: list[SentenceGroup], translations: dict[int, str]) -> pysrt.SubRipFile:
    """\uadf8\ub8f9\ubcc4\ub85c \ubcd1\ud569\ub41c \ud0c0\uc784\uc2a4\ud0ec\ud504 + \ubc88\uc5ed\ubb38\uc73c\ub85c \uc0c8 SRT \uc0dd\uc131."""
    out = pysrt.SubRipFile()
    for i, g in enumerate(groups, 1):
        translated = translations.get(i, g.text)
        out.append(pysrt.SubRipItem(
            index=i,
            start=g.start,
            end=g.end,
            text=translated,
        ))
    return out


# \ubcc8\uc5ed\ubb38\uc744 \ubb38\uc7a5 \ub05d \ubd80\ud638\ub85c \uc790\ub974\ub294 \ud328\ud134
# (\ub9c8\uce68\ud45c/\ubb3c\uc74c\ud45c/\ub290\ub08c\ud45c \ub4a4\uc5d0 \uacf5\ubc31\uc774 \uc788\uc73c\uba74 \ubd84\ud560)
_SPLIT_KO = re.compile(r'(?<=[.!?\u2026\uff01\uff1f\u3002])\s+')


def _split_translation_into_sentences(text: str) -> list[str]:
    """\ubc88\uc5ed\ubb38\uc744 \ubb38\uc7a5 \ub05d \ubd80\ud638(. ? !) \uae30\uc900\uc73c\ub85c \uc7ac\ubd84\ud560.

    , (\uc27c\ud45c) / \uacf5\ubc31\uc740 \ubd84\ud560 \uacbd\uacc4\uac00 \uc544\ub2c8\ubbc0\ub85c \uc774\uc5b4\uc9c4\ub2e4.
    """
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _SPLIT_KO.split(text)]
    return [p for p in parts if p]


def _merge_to_n(pieces: list[str], n: int) -> list[str]:
    """pieces 개수가 n보다 많으면 인접한 짧은 쌍부터 병합해 정확히 n개로 축소."""
    items = list(pieces)
    while len(items) > n and len(items) >= 2:
        # 인접한 두 요소의 합이 최소인 위치를 찾아 병합
        best = 0
        best_sum = len(items[0]) + len(items[1])
        for i in range(1, len(items) - 1):
            s = len(items[i]) + len(items[i + 1])
            if s < best_sum:
                best_sum = s
                best = i
        items[best] = (items[best] + " " + items[best + 1]).strip()
        del items[best + 1]
    return items


def _split_to_n(text: str, n: int, weights: list[int]) -> list[str]:
    """text를 n개로 쪼갠다. weights(양수) 비율로 분배하되 가능하면 공백에서 자른다."""
    text = text.strip()
    if n <= 0:
        return []
    if n == 1:
        return [text]
    total_w = sum(max(1, w) for w in weights) or 1
    total_chars = len(text)
    pieces: list[str] = []
    cur = 0
    for i in range(n):
        if i == n - 1:
            pieces.append(text[cur:].strip())
            break
        w = max(1, weights[i] if i < len(weights) else 1)
        target = cur + int(total_chars * w / total_w)
        # 근처 공백에서 자르기 (±8자 창)
        cut = target
        if 0 < cut < len(text):
            left = text.rfind(" ", cur, cut)
            right = text.find(" ", cut)
            if left != -1 and cut - left <= 8:
                cut = left
            elif right != -1 and right - cut <= 8:
                cut = right
        cut = max(cur, min(cut, len(text)))
        pieces.append(text[cur:cut].strip())
        cur = cut
    # 빈 조각 방어: 뒤 조각에서 한 글자씩 당겨옴
    for i, p in enumerate(pieces):
        if not p and i + 1 < len(pieces) and pieces[i + 1]:
            pieces[i] = pieces[i + 1][:1]
            pieces[i + 1] = pieces[i + 1][1:].strip()
    return pieces


def _distribute(sentences: list[str], n_orig: int, weights: list[int]) -> list[str]:
    """번역 문장을 원본 블록 수 n_orig 개로 정확히 맞춘다."""
    if n_orig <= 0:
        return []
    sentences = [s for s in sentences if s]
    if not sentences:
        return [""] * n_orig
    if len(sentences) == n_orig:
        return sentences
    if len(sentences) > n_orig:
        return _merge_to_n(sentences, n_orig)
    # 부족: 전체를 붙여서 가중치 비율로 분할
    combined = " ".join(sentences)
    return _split_to_n(combined, n_orig, weights)


def build_split_srt(original: pysrt.SubRipFile, groups: list[SentenceGroup], translations: dict[int, str]) -> pysrt.SubRipFile:
    """원본 SRT와 동일한 블록 수/타임스탬프를 유지하면서 각 블록에 번역 텍스트를 배치.

    정합성 불변식:
    - 출력 블록 수 == len(original)
    - 출력 블록 i의 start/end == 원본 블록 i의 start/end (단조성 자동 보존)
    - 빈 원본 블록도 그대로 유지 (빈 텍스트로 출력)
    """
    # 원본 1-based index -> (group_id, position_in_group)
    idx_map: dict[int, tuple[int, int]] = {}
    for gi, g in enumerate(groups, 1):
        for pos, orig_idx in enumerate(g.indices):
            idx_map[orig_idx] = (gi, pos)

    # 그룹별로 한 번만 분배 계산해서 캐시
    group_pieces: dict[int, list[str]] = {}
    for gi, g in enumerate(groups, 1):
        translated = translations.get(gi, g.text)
        sentences = _split_translation_into_sentences(translated) or [translated.strip() or g.text]
        weights = [max(1, len(f)) for f in g.fragments] or [1]
        group_pieces[gi] = _distribute(sentences, len(g.indices), weights)

    out = pysrt.SubRipFile()
    for i, sub in enumerate(original, 1):
        if i in idx_map:
            gi, pos = idx_map[i]
            pieces = group_pieces[gi]
            text = pieces[pos] if pos < len(pieces) else ""
        else:
            # 그룹에 포함되지 않은 블록 (빈 텍스트 등) — 원본 텍스트 보존
            text = sub.text
        out.append(pysrt.SubRipItem(
            index=i,
            start=sub.start,
            end=sub.end,
            text=text or "",
        ))
    return out
