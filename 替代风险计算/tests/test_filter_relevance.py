# -*- coding: utf-8 -*-
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from filter_relevance import build_tasks, parse_results, apply_filter, normalize_pub  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTER = os.path.join(ROOT, 'outputs', 'intermediate')


class TestBuildTasks:
    def test_task_shape(self, tmp_path):
        df = pd.DataFrame([
            {'pub': 'US20040102828A1', 'title': '颅内电极方法',
             'abstract': '本发明涉及颅内电极和用于植入颅内电极的方法'},
        ])
        out = os.path.join(str(tmp_path), 'tasks.jsonl')
        n = build_tasks(df, out)
        assert n == 1
        with open(out, encoding='utf-8') as f:
            task = json.loads(f.readline())
        assert task['id'] == 'US20040102828A1'
        assert task['messages'][0]['role'] == 'system'
        assert '脑机接口' in task['messages'][0]['content']
        assert task['messages'][1]['role'] == 'user'
        assert '颅内电极' in task['messages'][1]['content']

    def test_empty_input(self, tmp_path):
        out = os.path.join(str(tmp_path), 'tasks.jsonl')
        assert build_tasks(pd.DataFrame(columns=['pub', 'title', 'abstract']), out) == 0

    def test_nan_placeholder(self, tmp_path):
        # 终审修正（M-5）：单字段 NaN 以 '（无）' 占位，不再出现字面量 'nan'
        df = pd.DataFrame([
            {'pub': 'US20040102828A1', 'title': 'nan', 'abstract': '本发明涉及颅内电极'},
        ])
        out = os.path.join(str(tmp_path), 'tasks.jsonl')
        assert build_tasks(df, out) == 1
        with open(out, encoding='utf-8') as f:
            task = json.loads(f.readline())
        user = task['messages'][1]['content']
        assert '（无）' in user
        assert 'nan' not in user


class TestParseResults:
    def test_normal_json(self, tmp_path):
        p = os.path.join(str(tmp_path), 'r.jsonl')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'id': 'P1', 'ok': True,
                                'response': '{"relevant": true, "category": "核心", "reason": "BCI植入电极"}',
                                'provider': 'deepseek'}, ensure_ascii=False) + '\n')
            f.write(json.dumps({'id': 'P2', 'ok': True,
                                'response': '```json\n{"relevant": false, "category": "无关", "reason": "位置广告"}\n```',
                                'provider': 'deepseek'}, ensure_ascii=False) + '\n')
            f.write(json.dumps({'id': 'P3', 'ok': False, 'error': 'HTTP 429'}, ensure_ascii=False) + '\n')
        df = parse_results(p)
        assert len(df) == 2                       # 失败的 P3 不入判定表
        assert df.loc[df['pub'] == 'P1', 'relevant'].iloc[0] == True
        assert df.loc[df['pub'] == 'P2', 'relevant'].iloc[0] == False

    def test_malformed_response_tolerated(self, tmp_path):
        p = os.path.join(str(tmp_path), 'r.jsonl')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(json.dumps({'id': 'P1', 'ok': True,
                                'response': '这不是JSON',
                                'provider': 'deepseek'}, ensure_ascii=False) + '\n')
        df = parse_results(p)
        assert len(df) == 0                       # 无法解析 → 丢弃（保守：不默认纳入）


class TestApplyFilter:
    def test_filter_basic(self, tmp_path):
        patent = pd.DataFrame([
            {'pub': 'P1', 'topic_code': 'A61B5', 'is_cn': '1'},
            {'pub': 'P2', 'topic_code': 'A61B5', 'is_cn': '0'},
        ])
        mainpath = pd.DataFrame([
            {'window': 'pre2000', 'pub': 'P1'},
            {'window': 'pre2000', 'pub': 'P3'},   # 无文本未判定 → 默认排除
        ])
        rel = pd.DataFrame([
            {'pub': 'P1', 'relevant': True, 'category': '核心', 'reason': 'BCI'},
            {'pub': 'P2', 'relevant': False, 'category': '无关', 'reason': '广告'},
        ])
        stats = apply_filter(patent, mainpath, rel, str(tmp_path))
        assert stats['patent_kept'] == 1 and stats['patent_dropped'] == 1
        assert stats['mainpath_kept'] == 1 and stats['mainpath_dropped'] == 1
        # 终审修正（I-2）：stats 含判定规模与主路径无文本字段
        assert stats['judged'] == 2
        assert stats['relevant'] == 1 and stats['irrelevant'] == 1
        assert stats['mainpath_no_text'] == 1   # P3 未判定 → 无文本

    def test_stats_csv_fields(self, tmp_path):
        patent = pd.DataFrame([
            {'pub': 'P1', 'topic_code': 'A61B5', 'is_cn': '1'},
            {'pub': 'P2', 'topic_code': 'A61B5', 'is_cn': '0'},
        ])
        mainpath = pd.DataFrame([
            {'window': 'pre2000', 'pub': 'P1'},
            {'window': 'pre2000', 'pub': 'P3'},
        ])
        rel = pd.DataFrame([
            {'pub': 'P1', 'relevant': True, 'category': '核心', 'reason': 'BCI'},
            {'pub': 'P2', 'relevant': False, 'category': '无关', 'reason': '广告'},
        ])
        apply_filter(patent, mainpath, rel, str(tmp_path))
        csv = pd.read_csv(os.path.join(str(tmp_path), 'relevance_filter_stats.csv'))
        for col in ['judged', 'relevant', 'irrelevant', 'mainpath_no_text']:
            assert col in csv.columns


class TestNoTextListSmoke:
    def test_no_text_mainpath_list(self):
        # 真实数据生成后才存在（与 TestPrepareSmoke 同风格）
        p = os.path.join(INTER, 'no_text_mainpath_nodes.csv')
        assert os.path.exists(p)
        df = pd.read_csv(p, dtype=str)
        assert len(df) == 74                      # 74 个无任何文本的主路径节点
