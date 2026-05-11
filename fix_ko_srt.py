"""ko.srt에서 en.srt와 동일한 블록 병합을 적용하는 스크립트."""
import re
import pysrt
import copy

INPUT = r"output\ko\Accenture Anzo Training Workshop-20240709_090646-Meeting Recording.ko.srt"
OUTPUT = INPUT

subs = pysrt.open(INPUT, encoding='utf-8')

# en.srt와 동일한 병합 그룹 (블록 번호 기준)
MERGE_GROUPS = [
    (245, 246),
    (247, 248, 249),
    (415, 416),
    (539, 540, 541),
    (547, 548),
    (641, 642),
    (723, 724),
    (836, 837),
    (970, 971),
    (992, 993),
    (1080, 1081),
    (1346, 1347),
    (148, 149),
    (300, 301),
    (336, 337, 338, 339),
    (549, 550),
    (553, 554, 555),
    (557, 558, 559, 560),
    (611, 612, 613),
    (749, 750),
    (757, 758),
    (1359, 1360),
    (1368, 1369),
    (1383, 1384),
    (1389, 1390),
    (1392, 1393),
    (1394, 1395),
    (1410, 1411),
    (1413, 1414),
]

idx_map = {sub.index: i for i, sub in enumerate(subs)}

block_to_group = {}
for gid, group in enumerate(MERGE_GROUPS):
    for block_num in group:
        if block_num in idx_map:
            block_to_group[block_num] = gid

merged_subs = []
processed = set()

for sub in subs:
    bnum = sub.index
    if bnum in processed:
        continue

    if bnum in block_to_group:
        gid = block_to_group[bnum]
        group = MERGE_GROUPS[gid]

        group_subs = []
        for bn in group:
            if bn in idx_map:
                group_subs.append(subs[idx_map[bn]])
                processed.add(bn)

        if group_subs:
            # 한국어는 단순히 공백으로 합침
            merged_text = ' '.join(s.text.strip() for s in group_subs)
            merged_text = re.sub(r'\s+', ' ', merged_text).strip()

            new_sub = copy.copy(group_subs[0])
            new_sub.text = merged_text
            new_sub.end = group_subs[-1].end
            merged_subs.append(new_sub)
    else:
        processed.add(bnum)
        merged_subs.append(sub)

for i, sub in enumerate(merged_subs, 1):
    sub.index = i

import shutil
shutil.copy2(INPUT, INPUT + '.bak')
print(f"Backup saved: {INPUT}.bak")

out_file = pysrt.SubRipFile(items=merged_subs)
out_file.save(OUTPUT, encoding='utf-8')
print(f"Fixed: {len(subs)} blocks -> {len(merged_subs)} blocks ({len(subs) - len(merged_subs)} merged)")
