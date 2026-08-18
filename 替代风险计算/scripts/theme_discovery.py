# -*- coding: utf-8 -*-
"""技术主题凝练（文档 3.2）：LLM 逐条打主题标签 → LLM 归并 → patent_theme.csv。"""
import json
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
INTER_DIR = os.path.join(ROOT, 'outputs', 'intermediate')
WORK_DIR = os.path.join(INTER_DIR, 'relevance')
BATCH_LLM = r'C:\Users\26610\.claude\skills\batch-glm-llm\scripts\batch_llm.py'

TAG_SYSTEM = (
    '你是专利技术分类专家。下面给出若干专利（每条以"公开号|方法|问题|场景"列出），'
    '请为每一条专利给出一个精确的技术主题标签。\n'
    '要求：标签不超过 12 个字，命名风格如"侵入式电极信号采集""非侵入脑电范式识别"'
    '"神经刺激装置""脑电数据分析算法"；只输出 JSON：'
    '{"tags": {"公开号": "标签", ...}}，每个公开号一个标签，不要输出其他内容。')
MERGE_SYSTEM = (
    '你是技术术语归并专家。把含义相同的技术主题标签归并成组。\n'
    '只输出 JSON：{"groups": [["标签1","标签2"], ...]}，每组是同义标签，'
    '含义不同的标签不要归并，不要输出其他内容。')
NAME_SYSTEM = (
    '你是专利技术主题命名专家。下面按编号给出若干技术主题'
    '（每个主题含若干技术标签），请为每个主题给出一个不超过 12 字的主题名称'
    '（命名风格如"侵入式电极信号采集""非侵入脑电范式识别"'
    '"神经刺激装置""脑电数据分析算法"）。\n'
    '只输出 JSON：{"names": {"C0": "名称", ...}}，编号必须齐全，不要输出其他内容。')


def _ensure_key_from_registry() -> None:
    if os.environ.get('DEEPSEEK_API_KEY'):
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
        val, _ = winreg.QueryValueEx(k, 'DEEPSEEK_API_KEY')
    os.environ['DEEPSEEK_API_KEY'] = val


def run_batch(tasks_path: str, results_path: str, max_tokens: int = 1200) -> None:
    _ensure_key_from_registry()
    cmd = [sys.executable, BATCH_LLM, '--input', tasks_path,
           '--output', results_path, '--provider', 'deepseek',
           '--concurrency', '10', '--max-tokens', str(max_tokens),
           '--temperature', '0.2', '--retries', '3', '--resume']
    subprocess.run(cmd, check=True)


def _compact(entities: str, top: int = 8) -> str:
    """要素列表截断（控制单批 prompt 长度）。"""
    parts = [p for p in str(entities).split('|') if p and p != 'nan']
    return '、'.join(parts[:top]) or '（无）'


def build_tag_tasks(df: pd.DataFrame, out_path: str, batch: int = 10) -> int:
    """批量设计：每批 batch 条专利合成一个 LLM 调用（降低费用与调用次数）。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n = 0
    rows = df.to_dict('records')
    with open(out_path, 'w', encoding='utf-8') as f:
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            lines = []
            for r in chunk:
                lines.append(f'{r["pub"]}|{_compact(r["tech_methods"])}|'
                             f'{_compact(r["tech_problems"])}|'
                             f'{_compact(r["tech_scenarios"])}')
            user = ('专利列表（公开号|技术方法|技术问题|应用场景）：\n'
                    + '\n'.join(lines)
                    + '\n请为每条专利给出技术主题标签。')
            f.write(json.dumps(
                {'id': f'batch{i // batch}',
                 'messages': [{'role': 'system', 'content': TAG_SYSTEM},
                              {'role': 'user', 'content': user}]},
                ensure_ascii=False) + '\n')
            n += 1
    return n


def _extract_json(text: str) -> dict | None:
    """提取响应中最外层完整 JSON 对象（支持嵌套 dict 与 ```json 代码围栏）。

    注：plan 原版正则 \\{[^{}]*\\} 无法跨嵌套花括号，会把
    {"tags": {...}} 误截成内层 dict，导致 tags 全部丢失——此处改为
    括号配平扫描取最外层对象（唯一对 plan 代码的修正，测试驱动）。"""
    if not text:
        return None
    t = text.strip()
    if t.startswith('```'):
        t = t.lstrip('`').strip()
        if t.startswith('json'):
            t = t[4:].strip()
        t = t.rstrip('`').strip()
    start = t.find('{')
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(t[start:i + 1])
                    except json.JSONDecodeError:
                        return None
                    return obj if isinstance(obj, dict) else None
    return None


def parse_tag_results(path: str) -> pd.DataFrame:
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not rec.get('ok'):
                continue
            parsed = _extract_json(rec.get('response', ''))
            tags = (parsed or {}).get('tags') or {}
            if isinstance(tags, dict):
                for pub, tag in tags.items():
                    rows.append({'pub': str(pub).strip(),
                                 'tag': str(tag).strip()})
    return pd.DataFrame(rows, columns=['pub', 'tag'])


def build_merge_tasks(tags: pd.DataFrame, out_path: str, batch: int = 50,
                      system: str | None = None) -> int:
    """tags 列 [tag]（去重）；每批 batch 个标签求归并组。system 可换提示词（第二层凝练）。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    uniq = sorted(tags['tag'].unique())
    n = 0
    sys_prompt = system or MERGE_SYSTEM
    with open(out_path, 'w', encoding='utf-8') as f:
        for i in range(0, len(uniq), batch):
            chunk = uniq[i:i + batch]
            f.write(json.dumps(
                {'id': f'batch{i // batch}',
                 'messages': [{'role': 'system', 'content': sys_prompt},
                              {'role': 'user',
                               'content': '标签列表：\n' + '\n'.join(chunk) +
                                          '\n请归并同义标签。'}]},
                ensure_ascii=False) + '\n')
            n += 1
    return n


def encode_reps(reps: list[str]) -> np.ndarray:
    """bge-small-zh 编码主题代表标签 → 归一化向量。"""
    from sentence_transformers import SentenceTransformer
    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    model = SentenceTransformer(cfg['embed_model'])
    return model.encode(reps, batch_size=256, normalize_embeddings=True)


def cluster_reps(vecs: np.ndarray, n_clusters: int = 45) -> np.ndarray:
    """凝聚聚类 → 每行一个簇标签（确定性）。

    实测对比（本数据集 1125 个代表、专利加权）：cosine+average 产生 71% 巨簇
    （链式效应），cosine+complete 与 ward（归一化向量上的欧氏）均衡良好；
    采用 ward，k=45 时最大簇约 5% 专利、最小簇 ≥9 专利。encode_reps 已归一化，
    归一化向量上的欧氏距离 ≈ 余弦距离。
    """
    from sklearn.cluster import AgglomerativeClustering
    return AgglomerativeClustering(n_clusters=n_clusters,
                                   linkage='ward').fit_predict(vecs)


def build_name_tasks(comps: list[list[str]], out_path: str,
                     batch: int = 10) -> int:
    """为每个簇（主题候选）生成命名任务；comps 为簇成员列表，簇编号 C0..C{n-1}。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for i in range(0, len(comps), batch):
            block = []
            for j, members in enumerate(comps[i:i + batch]):
                lines = '\n'.join(f'- {m}' for m in members[:30])
                block.append(f'主题 C{i + j}：\n{lines}')
            f.write(json.dumps(
                {'id': f'name{i // batch}',
                 'messages': [{'role': 'system', 'content': NAME_SYSTEM},
                              {'role': 'user',
                               'content': '\n\n'.join(block) +
                                          '\n请给出每个主题的名称。'}]},
                ensure_ascii=False) + '\n')
            n += 1
    return n


def parse_name_results(path: str) -> dict:
    """簇编号 C0.. → 主题名称；解析失败或缺失的簇由调用方回退。"""
    names = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not rec.get('ok'):
                continue
            parsed = _extract_json(rec.get('response', ''))
            for cid, name in (parsed or {}).get('names', {}).items():
                names[str(cid).strip()] = str(name).strip()
    return names


def parse_merge_results(path: str) -> pd.DataFrame:
    rows = []
    gid = 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not rec.get('ok'):
                continue
            parsed = _extract_json(rec.get('response', ''))
            groups = (parsed or {}).get('groups', [])
            for grp in groups:
                for tag in grp:
                    rows.append({'tag': str(tag).strip(), 'group_id': f'T{gid}'})
                gid += 1
    return pd.DataFrame(rows, columns=['tag', 'group_id'])


def finalize_themes(tags: pd.DataFrame, l1: pd.DataFrame,
                    l2: pd.DataFrame) -> pd.DataFrame:
    """两级归并收尾：pub → (theme_id, theme_name)。

    tags=[pub, tag]；l1/l2 为 parse_merge_results 输出（[tag, group_id]）。
    一级未入组标签各自成组；一级组代表=组内频次最高标签；
    二级未入组的代表各自成主题；主题名=二级组内频次最高代表。
    """
    g1 = set(l1['tag'])
    solo1 = pd.DataFrame([{'tag': t, 'group_id': f'T{len(set(l1["group_id"])) + i}'}
                          for i, t in enumerate(sorted(set(tags['tag']) - g1))])
    l1 = l1.drop_duplicates('tag')                     # LLM 偶发重复标签行
    l1 = pd.concat([l1, solo1], ignore_index=True)
    t1 = tags.merge(l1, on='tag')                      # pub, tag, group_id(一级)
    rep_map = (t1.groupby('group_id')['tag']
               .agg(lambda s: s.value_counts().index[0]).to_dict())  # 一级组→代表
    t1['rep'] = t1['group_id'].map(rep_map)
    g2 = set(l2['tag'])
    solo2 = pd.DataFrame([{'tag': t, 'group_id': f'T{len(set(l2["group_id"])) + i}'}
                          for i, t in enumerate(sorted(set(rep_map.values()) - g2))])
    l2 = pd.concat([l2, solo2], ignore_index=True)
    t2 = t1.merge(l2.rename(columns={'tag': 'rep', 'group_id': 'theme_id'}),
                  on='rep')                            # pub, tag, rep, theme_id
    name_map = (t2.groupby('theme_id')['rep']
                .agg(lambda s: s.value_counts().index[0]).to_dict())
    t2['theme_name'] = t2['theme_id'].map(name_map)
    return t2[['pub', 'tag', 'theme_id', 'theme_name']]


def main() -> None:
    os.makedirs(WORK_DIR, exist_ok=True)
    # 输入：过滤后研究数据集的每专利要素。
    # func/scene/princ 来自 patent_route_filtered；技术问题（解决实体）从 KG 边表补。
    patent = pd.read_csv(os.path.join(INTER_DIR, 'patent_route_filtered.csv'),
                         dtype={'pub': str, 'topic_code': str})

    import io
    import zipfile
    KG_ZIP = os.path.join(ROOT, '..', '实体抽取，知识图谱构建', 'bci知识图谱数据包.zip')
    problem_map = {}
    with zipfile.ZipFile(KG_ZIP) as zf:
        with zf.open('graph_edges.csv') as f:
            edges = pd.read_csv(io.TextIOWrapper(f, encoding='utf-8-sig'), dtype=str)
    for _, r in edges.loc[edges['relation'] == '解决'].iterrows():
        suffix = r['target'].split(':', 1)[1] if ':' in r['target'] else r['target']
        problem_map.setdefault(r['patent_pub'], set()).add(suffix)
    patent['problem'] = patent['pub'].map(
        lambda p: '|'.join(sorted(problem_map.get(p, set()))))
    df = patent[['pub', 'func', 'scene', 'princ', 'problem']].rename(
        columns={'func': 'tech_methods', 'scene': 'tech_scenarios',
                 'princ': 'tech_principles', 'problem': 'tech_problems'})
    t_tasks = os.path.join(WORK_DIR, 'theme_tasks.jsonl')
    t_results = os.path.join(WORK_DIR, 'theme_results.jsonl')
    n = build_tag_tasks(df, t_tasks)
    print(f'tag tasks: {n}')
    run_batch(t_tasks, t_results)
    tags = parse_tag_results(t_results)
    print(f'tags parsed: {len(tags)}（唯一 {tags["tag"].nunique()}）')
    m_tasks = os.path.join(WORK_DIR, 'theme_merge_tasks.jsonl')
    m_results = os.path.join(WORK_DIR, 'theme_merge_results.jsonl')
    nb = build_merge_tasks(tags, m_tasks)
    print(f'merge batches: {nb}')
    run_batch(m_tasks, m_results)
    l1 = parse_merge_results(m_results)
    l1 = l1.drop_duplicates('tag')                     # LLM 偶发重复标签行
    # 第二层凝练（经验证调整）：一级归并按 50 标签/批独立进行，同义标签无法跨批相遇；
    # LLM 宽泛归并三版提示词均失败（模型只做细粒度同义归并，收敛在 ~800 个代表，
    # 且 5~15 组/批与 2~20 标签/组两种约束下均输出 1:1 组，长响应截断）→
    # 改用 bge-small-zh 嵌入 + 凝聚聚类（确定性、主题数固定 35 落在验收 10~60）
    # + LLM 命名（模型擅长领域）。全部一级组代表（含未入组标签）参与聚类。
    g1 = set(l1['tag'])
    t1 = tags.merge(l1, on='tag')
    rep_map = (t1.groupby('group_id')['tag']
               .agg(lambda s: s.value_counts().index[0]).to_dict())
    reps = sorted(set(rep_map.values()) | (set(tags['tag']) - g1))
    print(f'level2 reps: {len(reps)}')
    vecs = encode_reps(reps)
    labels = cluster_reps(vecs, n_clusters=45)
    comps = [[] for _ in range(45)]
    for r, lab in zip(reps, labels):
        comps[lab].append(r)
    l2 = pd.DataFrame([{'tag': r, 'group_id': f'C{i}'}
                       for i, c in enumerate(comps) for r in c])
    name_tasks = os.path.join(WORK_DIR, 'theme_name_tasks.jsonl')
    name_results = os.path.join(WORK_DIR, 'theme_name_results.jsonl')
    nn = build_name_tasks(comps, name_tasks)
    print(f'name tasks: {nn}（{len(comps)} 个簇）')
    run_batch(name_tasks, name_results, max_tokens=2000)
    cnames = parse_name_results(name_results)
    out = finalize_themes(tags, l1, l2)
    # 主题名优先取 LLM 命名；缺失簇回退为组内最高频标签
    out['theme_name'] = out.apply(
        lambda r: cnames.get(r['theme_id']) or r['theme_name'], axis=1)
    out[['pub', 'theme_id', 'theme_name']].to_csv(
        os.path.join(INTER_DIR, 'patent_theme.csv'),
        index=False, encoding='utf-8-sig')
    out[['tag', 'theme_id', 'theme_name']].rename(
        columns={'theme_id': 'group_id'}).drop_duplicates().to_csv(
        os.path.join(INTER_DIR, 'theme_terms.csv'),
        index=False, encoding='utf-8-sig')
    print(f'themes: {out["theme_id"].nunique()}')
    print(f'patent_theme 已写')


if __name__ == '__main__':
    main()
