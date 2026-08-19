# -*- coding: utf-8 -*-
"""Task 14 验收统计：标签解析率 / 归并统计 / Top 主题 / 示例（读成品文件，不依赖实现细节）。"""
import json
import os

import pandas as pd

INTER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     'outputs', 'intermediate')
WORK = os.path.join(INTER, 'relevance')


def count_lines(p):
    n = 0
    with open(p, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                n += 1
    return n


n_tasks = count_lines(os.path.join(WORK, 'theme_tasks.jsonl'))
n_t_res = count_lines(os.path.join(WORK, 'theme_results.jsonl'))
ok = 0
tagged = set()
with open(os.path.join(WORK, 'theme_results.jsonl'), encoding='utf-8') as f:
    for line in f:
        rec = json.loads(line)
        if rec.get('ok'):
            ok += 1
            tagged.update(rec.get('response', ''))
print(f'tag tasks: {n_tasks} | result lines: {n_t_res} | ok batches: {ok} | '
      f'failed: {n_t_res - ok}')

route = pd.read_csv(os.path.join(INTER, 'patent_route_filtered.csv'),
                    dtype={'pub': str})
terms = pd.read_csv(os.path.join(INTER, 'theme_terms.csv'))
patent_theme = pd.read_csv(os.path.join(INTER, 'patent_theme.csv'))
# 终审修复（M-建议-8）：缺失统计以 patent_route_filtered.csv 的 pub 为全集求差集。
# 旧口径 patent_theme['pub'].nunique()=2493 会把 LLM 回显乱码公开号（13 条，如
# CN108417248A vs 路由表 CN108417249A）误计为"全解析"——实际 13 条专利未入任何主题。
all_pubs = set(route['pub'])
tagged_pubs = set(patent_theme['pub'])
missing = sorted(all_pubs - tagged_pubs)
garbled = sorted(tagged_pubs - all_pubs)
rate = len(tagged_pubs & all_pubs) / len(all_pubs) * 100
uniq = terms['tag'].nunique()
print(f'tagged pubs: {len(tagged_pubs & all_pubs)}/{len(all_pubs)} ({rate:.2f}%) | '
      f'missing: {len(missing)}（示例 {missing[:3]}）| garbled echoes: {len(garbled)} | '
      f'unique tags: {uniq}')

print(f'name tasks: {count_lines(os.path.join(WORK, "theme_name_tasks.jsonl"))} | '
      f'name results: {count_lines(os.path.join(WORK, "theme_name_results.jsonl"))}')
n_grp1 = patent_theme['theme_id'].nunique()
print(f'final themes: {n_grp1} | patents: {len(patent_theme)} | '
      f'avg patents/theme: {len(patent_theme) / n_grp1:.1f}')
print(f'theme_terms rows: {len(terms)}')

cnt = patent_theme['theme_name'].value_counts()
print('\nTop-10 themes (by patent count):')
for name, c in cnt.head(10).items():
    print(f'  {c:4d}  {name}')

print('\nExample: 5 patents + tags:')
ex = patent_theme.merge(terms[['tag', 'theme_name']].drop_duplicates(),
                        on='theme_name').drop_duplicates('pub').head(5)
for _, r in ex.iterrows():
    print(f"  {r['pub']}  tag={r['tag']}  theme={r['theme_name']}")
