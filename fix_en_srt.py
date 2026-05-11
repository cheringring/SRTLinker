"""en.srt에서 쪼개진 문장과 짧은 파편을 병합하는 일회용 스크립트."""
import re
import pysrt
import copy

INPUT = r"output\en\Accenture Anzo Training Workshop-20240709_090646-Meeting Recording.en.srt"
OUTPUT = INPUT  # 덮어쓰기 (백업은 .bak으로 저장)

subs = pysrt.open(INPUT, encoding='utf-8')

# ── 병합 대상 정의 ──
# 각 튜플: (병합할 블록 번호 리스트) → 텍스트를 공백으로 합치고, 첫 시작~마지막 종료 시간 사용
MERGE_GROUPS = [
    # Category 1: 문장 쪼개짐 (연속 문장)
    (245, 246),     # "I'm going to need to." + "to confirm that with engineering."
    (247, 248, 249),# "But I believe that at the time at this time." + "That's um." + "that's what I would say."
    (415, 416),     # "...slightly different numbers." + "they have slightly different IRIs..."
    (539, 540, 541),# "because I'm querying..." + "this line 11..." + "Isn't doing anything..."
    (547, 548),     # "Or I could just say." + "Comment that line out..."
    (641, 642),     # ontology/model continuation
    (723, 724),     # "...we need more info..." + "whether that conclusion is true..."
    (836, 837),     # "...those links..." + "meeting."
    (970, 971),     # SQL/SPARQL comparison long sentence
    (992, 993),     # "disambiguating." + "we already talked about this slide..."
    (1080, 1081),   # "...either of these." + "the subject, the predicate..."
    (1346, 1347),   # "inner join and outer join..." + "whereas that's not quite..."

    # Category 2: 짧은 파편 (불완전 블록 → 인접 블록에 합침)
    (148, 149),     # "...as a side note." + "get a bit of context."
    (300, 301),     # "So in the." + next sentence
    (336, 337, 338, 339),  # "And it's referring to." + "Whatever this is." + "This is just." + "Uh, saying that..."
    (549, 550),     # "So just to." + "So suppose that optionally..."
    (553, 554, 555),# "And I could end that..." + "I can have in Sparkle." + "It's called an optional."
    (557, 558, 559, 560),  # "And I can say sometimes." + "An actor." + "Will have." + "An actor ID."
    (611, 612, 613),# "Encode for URI." + "And then." + "Title as."
    (749, 750),     # "So suppose." + "Here."
    (757, 758),     # "And so." + next
    (1359, 1360),   # "They." + next
    (1368, 1369),   # "It seems like." + next
    (1383, 1384),   # "The movie." + next
    (1389, 1390),   # "Even though." + next
    (1392, 1393),   # "Because." + next
    (1394, 1395),   # "But it is." + next
    (1410, 1411),   # "I'm." + next
    (1413, 1414),   # "You have to." + next
]

# 블록 번호 → 인덱스 매핑 (1-based → 0-based)
idx_map = {sub.index: i for i, sub in enumerate(subs)}

# 어떤 블록이 병합 그룹에 속하는지 기록
block_to_group = {}
for gid, group in enumerate(MERGE_GROUPS):
    for block_num in group:
        if block_num in idx_map:
            block_to_group[block_num] = gid

# 병합 실행
merged_subs = []
processed = set()

for sub in subs:
    bnum = sub.index
    if bnum in processed:
        continue

    if bnum in block_to_group:
        gid = block_to_group[bnum]
        group = MERGE_GROUPS[gid]

        # 그룹의 모든 블록 수집
        group_subs = []
        for bn in group:
            if bn in idx_map:
                group_subs.append(subs[idx_map[bn]])
                processed.add(bn)

        if group_subs:
            # 텍스트 합치기 (필러 정리)
            texts = []
            for s in group_subs:
                t = s.text.strip()
                # "Uh, " / "Um, " 로 시작하면 제거
                t = re.sub(r'^(Uh,?\s*|Um,?\s*)', '', t, flags=re.I)
                texts.append(t)

            # 합칠 때 소문자 시작이면 이어붙이기 (마침표 제거)
            joined_parts = []
            for idx_t, t in enumerate(texts):
                if idx_t == 0:
                    joined_parts.append(t)
                else:
                    prev = joined_parts[-1]
                    # 이전 텍스트 끝의 불필요한 마침표 제거 후 이어붙이기
                    if t and t[0].islower():
                        prev = prev.rstrip('.')
                        joined_parts[-1] = prev + ' ' + t
                    else:
                        joined_parts.append(t)

            merged_text = ' '.join(joined_parts)
            # 연속 공백 정리
            merged_text = re.sub(r'\s+', ' ', merged_text).strip()

            new_sub = copy.copy(group_subs[0])
            new_sub.text = merged_text
            new_sub.end = group_subs[-1].end
            merged_subs.append(new_sub)
    else:
        processed.add(bnum)
        merged_subs.append(sub)

# 재번호
for i, sub in enumerate(merged_subs, 1):
    sub.index = i

# 백업 저장
import shutil
shutil.copy2(INPUT, INPUT + '.bak')
print(f"Backup saved: {INPUT}.bak")

# 저장
out_file = pysrt.SubRipFile(items=merged_subs)
out_file.save(OUTPUT, encoding='utf-8')
print(f"Fixed: {len(subs)} blocks -> {len(merged_subs)} blocks ({len(subs) - len(merged_subs)} merged)")

# 변경 내역 출력
for gid, group in enumerate(MERGE_GROUPS):
    texts = []
    for bn in group:
        if bn in idx_map:
            texts.append(f"  #{bn}: {subs[idx_map[bn]].text.strip()[:60]}")
    if texts:
        print(f"\nMerge group {gid+1} (blocks {group}):")
        for t in texts:
            print(t)
