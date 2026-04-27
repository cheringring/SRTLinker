"""번역 결과 SRT의 정합성 검증.

불변식:
1) 블록 개수가 원본과 동일해야 함
2) 각 블록의 타임스탬프가 원본과 동일해야 함 (start/end)
3) 각 블록의 start < end (동일 시간 금지)
4) 블록 간 순차 증가 (앞 블록 end <= 뒤 블록 start)
5) 번역 누락으로 영어 원문이 그대로 남아있지 않아야 함 (휴리스틱 경고)
"""
from __future__ import annotations
from pathlib import Path

import pysrt


def _ascii_alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    ascii_count = sum(1 for c in alpha if c.isascii())
    return ascii_count / len(alpha)


def verify_srt_pair(original_path: Path | str, output_path: Path | str) -> list[str]:
    """원본과 출력 SRT를 비교해 정합성 이슈 목록 반환. 빈 리스트면 정상."""
    issues: list[str] = []
    a = pysrt.open(str(original_path), encoding="utf-8")
    b = pysrt.open(str(output_path), encoding="utf-8")

    if len(a) != len(b):
        issues.append(f"블록 수 불일치: 원본 {len(a)} vs 출력 {len(b)}")

    n = min(len(a), len(b))
    english_count = 0
    for i in range(n):
        oi, ot = a[i], b[i]
        # 타임스탬프 일치
        if oi.start != ot.start or oi.end != ot.end:
            issues.append(f"#{i+1} 타임스탬프 불일치")
        # 시간 역전/동일
        if ot.start >= ot.end:
            issues.append(f"#{i+1} start>=end ({ot.start} >= {ot.end})")
        # 순차 증가
        if i > 0 and b[i - 1].end > ot.start:
            issues.append(f"#{i+1} 앞 블록과 겹침")
        # 영어 잔존 휴리스틱 (원본이 ASCII였을 가능성이 높은데 출력도 ASCII면 미번역 의심)
        if ot.text.strip() and _ascii_alpha_ratio(ot.text) > 0.7 and _ascii_alpha_ratio(oi.text) > 0.7:
            english_count += 1

    if english_count:
        issues.append(f"미번역 의심 블록 {english_count}개 (영어 잔존)")

    return issues


def format_issues(issues: list[str], max_items: int = 5) -> str:
    if not issues:
        return "OK"
    head = issues[:max_items]
    tail = f" 외 {len(issues) - max_items}건" if len(issues) > max_items else ""
    return "; ".join(head) + tail
