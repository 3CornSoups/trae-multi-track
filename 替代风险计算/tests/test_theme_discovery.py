# tests/test_theme_discovery.py
# -*- coding: utf-8 -*-
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from theme_discovery import (build_tag_tasks, parse_tag_results,  # noqa: E402
                              build_merge_tasks, parse_merge_results,
                              finalize_themes, cluster_reps, parse_name_results)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTER = os.path.join(ROOT, 'outputs', 'intermediate')


class TestTagTasks:
    def test_build_batched(self, tmp_path):
        # 批量设计（用户拍板，降费用降调用次数）：每批 10 条专利一个 LLM 调用
        df = pd.DataFrame([
            {'pub': f'P{i}', 'tech_methods': f'方法{i}', 'tech_problems': f'问题{i}',
             'tech_scenarios': f'场景{i}'}
            for i in range(25)
        ])
        out = os.path.join(str(tmp_path), 't.jsonl')
        assert build_tag_tasks(df, out, batch=10) == 3    # 25 条 → 3 批
        with open(out, encoding='utf-8') as f:
            tasks = [json.loads(line) for line in f]
        assert tasks[0]['id'] == 'batch0'
        assert '技术主题' in tasks[0]['messages'][0]['content']
        user0 = tasks[0]['messages'][1]['content']
        assert 'P0' in user0 and 'P9' in user0          # 第一批含 10 条
        assert 'P10' not in user0                        # 且不越批

    def test_parse_batched(self, tmp_path):
        p = os.path.join(str(tmp_path), 'r.jsonl')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'id': 'batch0', 'ok': True,
                                'response': '{"tags": {"P1": "侵入式电极信号采集", '
                                            '"P2": "脑电信号采集"}}',
                                'provider': 'deepseek'}, ensure_ascii=False) + '\n')
            f.write(json.dumps({'id': 'batch1', 'ok': True,
                                'response': '```json\n{"tags": {"P3": "神经刺激装置"}}\n```',
                                'provider': 'deepseek'}, ensure_ascii=False) + '\n')
            f.write(json.dumps({'id': 'batch2', 'ok': False, 'error': 'x'},
                               ensure_ascii=False) + '\n')
        df = parse_tag_results(p)
        assert len(df) == 3
        assert df.loc[df['pub'] == 'P1', 'tag'].iloc[0] == '侵入式电极信号采集'


class TestFinalize:
    def test_two_level(self, tmp_path):
        # 第二层凝练：一级组代表跨批归并 → 最终主题（验收 10~60 需要跨批合并）
        tags = pd.DataFrame([
            {'pub': 'P1', 'tag': 'A'}, {'pub': 'P2', 'tag': 'A'},
            {'pub': 'P3', 'tag': 'B'}, {'pub': 'P4', 'tag': 'C'},
            {'pub': 'P5', 'tag': 'D'}, {'pub': 'P6', 'tag': 'E'},
        ])
        l1 = pd.DataFrame([{'tag': 'A', 'group_id': 'T0'},
                           {'tag': 'B', 'group_id': 'T0'}])
        l2 = pd.DataFrame([{'tag': 'A', 'group_id': 'U0'},
                           {'tag': 'D', 'group_id': 'U1'}])
        out = finalize_themes(tags, l1, l2)
        assert len(out) == 6
        # A/B 同组（一级 T0，代表 A）→ 二级并入 U0，主题名取组内最高频代表 A
        assert out.loc[out['pub'] == 'P1', 'theme_id'].iloc[0] == 'U0'
        assert out.loc[out['pub'] == 'P1', 'theme_name'].iloc[0] == 'A'
        assert out.loc[out['pub'] == 'P3', 'theme_id'].iloc[0] == 'U0'
        # C 一级未入组 → 自成组；二级亦未入组 → 独立主题
        assert out.loc[out['pub'] == 'P4', 'theme_name'].iloc[0] == 'C'
        # D 一级独组，二级并入 U1
        assert out.loc[out['pub'] == 'P5', 'theme_id'].iloc[0] == 'U1'
        assert out['theme_id'].nunique() == 4

    def test_dup_tag_dedup(self, tmp_path):
        # LLM 归并输出偶发重复标签行 → 按 tag 去重，专利行不得膨胀
        tags = pd.DataFrame([{'pub': 'P1', 'tag': 'A'},
                             {'pub': 'P2', 'tag': 'B'}])
        l1 = pd.DataFrame([{'tag': 'A', 'group_id': 'T0'},
                           {'tag': 'B', 'group_id': 'T0'},
                           {'tag': 'A', 'group_id': 'T1'}])
        out = finalize_themes(tags, l1, pd.DataFrame(columns=['tag', 'group_id']))
        assert len(out) == 2          # 每专利一行，不因 l1 重复行膨胀

    def test_cluster_reps(self, tmp_path):
        # 第二层凝练：LLM 多次拒绝宽泛归并 → 嵌入聚类（确定性、主题数可控）
        import numpy as np
        rng = np.random.RandomState(0)
        # 余弦距离下按"方向"区分三个簇：各自只在某一维上有强分量
        base = rng.randn(30, 8) * 0.5
        base[:10, 0] += 3          # 簇 0：第 0 维方向
        base[10:20, 1] += 3        # 簇 1：第 1 维方向
        base[20:30, 2] += 3        # 簇 2：第 2 维方向
        vecs = base
        labels = cluster_reps(vecs, n_clusters=3)
        assert len(set(labels)) == 3                     # 恰好 3 簇
        assert labels[0] == labels[1]                    # 同 blob 同簇
        assert labels[0] != labels[10]                   # 不同 blob 异簇
        # 确定性：同输入同输出
        labels2 = cluster_reps(vecs, n_clusters=3)
        assert (labels == labels2).all()

    def test_parse_names(self, tmp_path):
        # 主题命名结果解析：{"names": {"C0": "名称"}}
        p = os.path.join(str(tmp_path), 'n.jsonl')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'id': 'name0', 'ok': True,
                                'response': '{"names": {"C0": "脑电信号采集", '
                                            '"C1": "神经刺激装置"}}',
                                'provider': 'deepseek'}, ensure_ascii=False) + '\n')
            f.write(json.dumps({'id': 'name1', 'ok': False, 'error': 'x'},
                               ensure_ascii=False) + '\n')
        names = parse_name_results(p)
        assert names['C0'] == '脑电信号采集'
        assert names['C1'] == '神经刺激装置'
        assert len(names) == 2
        # 第二层凝练：一级组代表跨批归并 → 最终主题（验收 10~60 需要跨批合并）
        tags = pd.DataFrame([
            {'pub': 'P1', 'tag': 'A'}, {'pub': 'P2', 'tag': 'A'},
            {'pub': 'P3', 'tag': 'B'}, {'pub': 'P4', 'tag': 'C'},
            {'pub': 'P5', 'tag': 'D'}, {'pub': 'P6', 'tag': 'E'},
        ])
        l1 = pd.DataFrame([{'tag': 'A', 'group_id': 'T0'},
                           {'tag': 'B', 'group_id': 'T0'}])
        l2 = pd.DataFrame([{'tag': 'A', 'group_id': 'U0'},
                           {'tag': 'D', 'group_id': 'U1'}])
        out = finalize_themes(tags, l1, l2)
        assert len(out) == 6
        # A/B 同组（一级 T0，代表 A）→ 二级并入 U0，主题名取组内最高频代表 A
        assert out.loc[out['pub'] == 'P1', 'theme_id'].iloc[0] == 'U0'
        assert out.loc[out['pub'] == 'P1', 'theme_name'].iloc[0] == 'A'
        assert out.loc[out['pub'] == 'P3', 'theme_id'].iloc[0] == 'U0'
        # C 一级未入组 → 自成组；二级亦未入组 → 独立主题
        assert out.loc[out['pub'] == 'P4', 'theme_name'].iloc[0] == 'C'
        # D 一级独组，二级并入 U1
        assert out.loc[out['pub'] == 'P5', 'theme_id'].iloc[0] == 'U1'
        assert out['theme_id'].nunique() == 4


class TestMergeTasks:
    def test_parse_groups(self, tmp_path):
        p = os.path.join(str(tmp_path), 'm.jsonl')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'id': 'batch1', 'ok': True,
                                'response': '{"groups": [["EEG信号采集", "脑电信号采集"]]}',
                                'provider': 'deepseek'}, ensure_ascii=False) + '\n')
        df = parse_merge_results(p)
        assert len(df) == 2
        assert df.loc[df['tag'] == 'EEG信号采集', 'group_id'].iloc[0] == \
               df.loc[df['tag'] == '脑电信号采集', 'group_id'].iloc[0]
