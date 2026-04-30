"""빠른 번역 테스트 스크립트 (문장 병합 → 번역, 실제 파이프라인과 동일).

SRT 파일에서 일부 구간만 뽑아 문장 병합 후 번역 결과를 콘솔에 출력합니다.

사용법:
  # 기본: 블록 1~30 구간을 병합 후 번역
  python test_translate.py output/영상.en.srt

  # 특정 구간
  python test_translate.py output/영상.en.srt --start 50 --count 30

  # 자동 난이도 테스트 (긴문장, 복잡문장, 문맥의존 구간 자동 선별)
  python test_translate.py output/영상.en.srt --auto --pick 3
"""
from __future__ import annotations
import argparse
import os
import re
import sys
import time
from pathlib import Path

import pysrt
from dotenv import load_dotenv

from srt_chunker import load_srt, chunk_blocks, Block, Chunk
from sentence_merger import group_sentences, SentenceGroup
from translator import Translator, TranslatorConfig


# ── 난이도 자동 선별 ──────────────────────────────────────────

def _complexity(text: str) -> int:
    conj = len(re.findall(
        r"\b(and|but|or|so|because|however|although|though|which|that|where|when|while|if)\b",
        text, re.I,
    ))
    return text.count(",") + conj


def pick_hard_groups(groups: list[SentenceGroup], pick: int = 3) -> list[tuple[str, list[int]]]:
    """카테고리별로 까다로운 문장그룹 인덱스(0-based)를 선별."""
    categories: list[tuple[str, list[int]]] = []
    already: set[int] = set()

    # 1) 긴 문장 (병합 후 글자수 상위)
    by_len = sorted(range(len(groups)), key=lambda i: len(groups[i].text), reverse=True)
    top = [i for i in by_len if i not in already][:pick]
    categories.append(("🔤 긴 문장 (병합 후)", top))
    already.update(top)

    # 2) 많은 블록이 합쳐진 문장 (fragment 수 상위)
    by_frag = sorted(range(len(groups)), key=lambda i: len(groups[i].indices), reverse=True)
    top = [i for i in by_frag if i not in already][:pick]
    categories.append(("🧩 많은 블록 병합 (fragment 수 상위)", top))
    already.update(top)

    # 3) 구문 복잡도 높은 문장
    by_cx = sorted(range(len(groups)), key=lambda i: _complexity(groups[i].text), reverse=True)
    top = [i for i in by_cx if i not in already][:pick]
    categories.append(("🔗 복잡한 구문 (접속사/쉼표 다수)", top))
    already.update(top)

    # 4) 필러/구어체 많은 문장
    filler_pat = re.compile(r"\b(you know|like|basically|I mean|actually|right|okay|so)\b", re.I)
    by_filler = sorted(range(len(groups)), key=lambda i: len(filler_pat.findall(groups[i].text)), reverse=True)
    top = [i for i in by_filler if i not in already and len(filler_pat.findall(groups[i].text)) >= 2][:pick]
    categories.append(("💬 구어체/필러 많은 문장", top))

    return categories


# ── 병합 그룹 → 번역 & 출력 ──────────────────────────────────

def translate_groups(
    groups: list[SentenceGroup],
    group_indices: list[int],
    all_groups: list[SentenceGroup],
    translator: Translator,
    context_size: int,
) -> tuple[dict[int, str], float]:
    """선택된 그룹들을 번역. 그룹 id(1-based) → 번역문 dict와 소요시간 반환."""
    results: dict[int, str] = {}
    total_g = len(all_groups)

    t0 = time.time()
    for gi in group_indices:
        g = all_groups[gi]
        gid = gi + 1  # 번역기에 넘길 1-based id
        blk = Block(id=gid, text=g.text)

        # 문맥: 인접 그룹의 텍스트
        ctx_b = [Block(id=j + 1, text=all_groups[j].text)
                 for j in range(max(0, gi - context_size), gi)]
        ctx_a = [Block(id=j + 1, text=all_groups[j].text)
                 for j in range(gi + 1, min(total_g, gi + 1 + context_size))]

        chunk = Chunk(translate=[blk], context_before=ctx_b, context_after=ctx_a)
        r = translator.translate_chunk(chunk)
        results.update(r)
    elapsed = time.time() - t0
    return results, elapsed


def print_group_result(g: SentenceGroup, gid: int, translation: str):
    """한 그룹의 원문(fragment별) + 병합문 + 번역 출력."""
    frag_count = len(g.indices)
    print(f"  [그룹 {gid:4d}] ({frag_count}블록 병합)  {g.start} → {g.end}")
    for idx, frag in zip(g.indices, g.fragments):
        print(f"    블록{idx:4d}: {frag}")
    print(f"    ─ 병합EN: {g.text}")
    print(f"    ─ 번역KO: {translation}")
    print()


# ── CLI ───────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="SRT 번역 퀵 테스트 (문장 병합 → 번역)")
    p.add_argument("srt", type=Path, help="원본 영어 SRT 파일 경로")
    p.add_argument("--start", type=int, default=1, help="시작 블록 번호 (1-based, default=1)")
    p.add_argument("--count", type=int, default=30, help="테스트할 원본 블록 수 (default=30)")
    p.add_argument("--context", type=int, default=3, help="앞뒤 문맥 그룹 수 (default=3)")
    p.add_argument("--max-merge", type=int, default=6, help="병합 최대 블록 수 (default=6)")
    p.add_argument("--model", type=str, default=None, help="번역 모델 (default=OPENAI_MODEL 또는 gpt-4o)")
    p.add_argument("--lang", type=str, default="Korean", help="번역 대상 언어 (default=Korean)")
    p.add_argument("--glossary", type=Path, default=Path("glossary.json"), help="용어집 경로")
    p.add_argument("--temp", type=float, default=0.2, help="temperature (default=0.2)")
    p.add_argument("--auto", action="store_true", help="자동으로 까다로운 문장 선별 테스트")
    p.add_argument("--pick", type=int, default=3, help="--auto 시 카테고리별 선별 개수 (default=3)")
    return p.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("[!] OPENAI_API_KEY 미설정", file=sys.stderr)
        return 1
    if not args.srt.exists():
        print(f"[!] 파일 없음: {args.srt}", file=sys.stderr)
        return 1

    model = args.model or os.environ.get("OPENAI_MODEL") or "gpt-4o"

    # SRT 로드 & 문장 병합
    subs = pysrt.open(str(args.srt), encoding="utf-8")
    groups = group_sentences(subs, max_blocks=args.max_merge)
    print(f"[=] SRT 로드: {len(subs)}블록 → 문장 병합: {len(groups)}그룹  |  모델: {model}")

    glossary = args.glossary if args.glossary.exists() else None
    translator = Translator(TranslatorConfig(
        model=model, target_lang=args.lang,
        glossary_path=glossary, temperature=args.temp,
    ))

    # ── AUTO 모드 ──
    if args.auto:
        categories = pick_hard_groups(groups, pick=args.pick)
        all_idxs = [i for _, idxs in categories for i in idxs]
        print(f"[=] AUTO 모드: {len(categories)}카테고리, 총 {len(all_idxs)}그룹 테스트")
        print("=" * 70)

        results, elapsed = translate_groups(all_idxs, all_idxs, groups, translator, args.context)

        for cat_name, idxs in categories:
            print(f"\n  ── {cat_name} ──")
            if not idxs:
                print("    (해당 없음)")
                continue
            for gi in idxs:
                gid = gi + 1
                tr = results.get(gid, "(번역 없음)")
                print_group_result(groups[gi], gid, tr)

        print("=" * 70)
        print(f"[✓] AUTO 테스트 완료: {len(all_idxs)}그룹  ({elapsed:.1f}s)")
        return 0

    # ── 기본 모드: 연속 구간 ──
    # 원본 블록 범위 → 해당 그룹 찾기
    s = max(0, args.start - 1)
    e = min(len(subs), s + args.count)
    target_orig_ids = set(range(s + 1, e + 1))  # 1-based

    target_group_idxs = []
    for gi, g in enumerate(groups):
        if any(idx in target_orig_ids for idx in g.indices):
            target_group_idxs.append(gi)

    print(f"[=] 원본 블록 {s+1}~{e} → {len(target_group_idxs)}그룹 해당")
    print("-" * 70)

    results, elapsed = translate_groups(
        target_group_idxs, target_group_idxs, groups, translator, args.context,
    )

    for gi in target_group_idxs:
        gid = gi + 1
        tr = results.get(gid, "(번역 없음)")
        print_group_result(groups[gi], gid, tr)

    print("-" * 70)
    print(f"[✓] {len(target_group_idxs)}그룹 번역 완료  ({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
