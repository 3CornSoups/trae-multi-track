# -*- coding: utf-8 -*-
"""BCI 相关性过滤：构造 LLM 判定任务 → 调 batch_llm.py → 解析 → 过滤中间表。

判定口径（用户 2026-08-18 拍板）：含 BCI 边缘应用——涉及脑信号采集/解码/
神经调控技术，或直接消费脑信号的系统（神经营销、BCI 教育、神经反馈媒体）为
relevant；仅通用广告/一般医疗/纯算法工具等为 irrelevant。

终审修正（2026-08-18）：build_tasks 中单字段 NaN 的占位由字面量 'nan' 改为
'（无）'。注意：现有 outputs/intermediate/relevance/results.jsonl 是旧占位下
判定的，不要重跑判定（--resume 按 id 跳过已完成任务，仅影响未来重跑）。
"""
import json
import os
import re
import subprocess
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE_DIR)
INTER_DIR = os.path.join(ROOT, 'outputs', 'intermediate')
WORK_DIR = os.path.join(INTER_DIR, 'relevance')
# 外部工具（batch-glm-llm 用户级 skill，项目外依赖）
BATCH_LLM = r'C:\Users\26610\.claude\skills\batch-glm-llm\scripts\batch_llm.py'

DS_PATH = os.path.join(ROOT, '..', '数据集合并', 'outputs', '05_合并数据集.csv')
META_PATH = os.path.join(ROOT, '..', '专利数据合并与引文网络构建',
                         '03_合并专利信息_精简.csv')

SYSTEM_PROMPT = (
    '你是专利技术领域判定专家。判断专利是否属于脑机接口（BCI）领域或其直接应用。\n'
    '判定标准：\n'
    '- 属于（relevant=true）：技术涉及脑信号的采集、解码、处理或神经调控'
    '（电/磁/光/超声刺激），或系统直接消费脑信号/神经状态——含神经营销（测脑电反应的）、'
    'BCI 教育训练、神经反馈媒体、BCI 康复/义肢/机器人控制等边缘应用。\n'
    '- 不属于（relevant=false）：与脑信号无关（如仅基于位置或一般用户数据的广告、'
    '不涉及脑信号的一般医疗器械、纯通用算法工具）；脑信号仅为众多生理信号之一'
    '且非系统核心功能。\n'
    '只输出一个 JSON 对象，格式：'
    '{"relevant": true/false, "category": "核心|边缘应用|无关", "reason": "不超过30字"}，'
    '不要输出任何其他内容。')


def normalize_pub(pub: str) -> str:
    return str(pub).replace('-', '').strip().upper()


def collect_texts() -> pd.DataFrame:
    """研究数据集 ∪ 主路径节点 → 每专利一行 [pub, title, abstract]（无文本的保留空值）。"""
    ds = pd.read_csv(DS_PATH, dtype=str)
    ds['pub'] = ds['pub'].map(normalize_pub)
    texts = (ds.drop_duplicates('pub')[['pub', '标题_中文', '摘要_中文']]
             .rename(columns={'标题_中文': 'title', '摘要_中文': 'abstract'}))

    mp = pd.read_csv(os.path.join(INTER_DIR, 'mainpath_nodes_by_window.csv'), dtype=str)
    mp_pubs = set(mp['pub'].map(normalize_pub))
    extra = mp_pubs - set(texts['pub'])
    if extra:
        meta = pd.read_csv(META_PATH, dtype=str)
        meta['公开号'] = meta['公开号'].map(normalize_pub)
        back = (meta[meta['公开号'].isin(extra)]
                .rename(columns={'公开号': 'pub', '专利标题（中文）': 'title',
                                 '摘要_中文': 'abstract'})[['pub', 'title', 'abstract']])
        texts = pd.concat([texts, back], ignore_index=True)
    missing = sorted(mp_pubs - set(texts['pub']))
    if missing:
        texts = pd.concat([texts, pd.DataFrame(
            [{'pub': p, 'title': '', 'abstract': ''} for p in missing])],
            ignore_index=True)
    return texts


def build_tasks(df: pd.DataFrame, out_path: str) -> int:
    """df 列 [pub, title, abstract] → tasks.jsonl（无文本的行跳过）。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    n = 0
    with open(out_path, 'w', encoding='utf-8') as f:
        for _, r in df.iterrows():
            if not str(r['title']).strip() and not str(r['abstract']).strip():
                continue
            # 终审修正（M-5）：单字段 NaN 以 '（无）' 占位（旧实现为字面量 'nan'）
            title = str(r['title']).strip() if str(r['title']).strip() not in ('', 'nan', 'NaN') else '（无）'
            abstract = str(r['abstract']).strip() if str(r['abstract']).strip() not in ('', 'nan', 'NaN') else '（无）'
            user = (f'专利公开号：{r["pub"]}\n标题：{title}\n'
                    f'摘要：{abstract}\n请判定该专利是否属于脑机接口领域。')
            f.write(json.dumps(
                {'id': r['pub'],
                 'messages': [{'role': 'system', 'content': SYSTEM_PROMPT},
                              {'role': 'user', 'content': user}]},
                ensure_ascii=False) + '\n')
            n += 1
    return n


def _ensure_key_from_registry() -> None:
    """用户已 setx 到注册表用户环境；子进程继承的是旧环境，故从注册表读取注入
    （key 不落任何文件、不出现在命令文本）。"""
    if os.environ.get('DEEPSEEK_API_KEY'):
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
        val, _ = winreg.QueryValueEx(k, 'DEEPSEEK_API_KEY')
    os.environ['DEEPSEEK_API_KEY'] = val


def run_batch(tasks_path: str, results_path: str) -> None:
    """调用 batch_llm.py（DeepSeek 直连，key 从注册表用户环境注入）。"""
    _ensure_key_from_registry()
    cmd = [sys.executable, BATCH_LLM, '--input', tasks_path,
           '--output', results_path, '--provider', 'deepseek',
           '--concurrency', '10', '--max-tokens', '300',
           '--temperature', '0.2', '--retries', '3', '--resume']
    subprocess.run(cmd, check=True)


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    m = re.search(r'\{[^{}]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def parse_results(path: str) -> pd.DataFrame:
    """batch_llm 输出 → [pub, relevant, category, reason]（失败/无法解析行丢弃）。"""
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
            if parsed is None or 'relevant' not in parsed:
                continue
            rows.append({
                'pub': normalize_pub(rec['id']),
                'relevant': bool(parsed['relevant']),
                'category': str(parsed.get('category', '')),
                'reason': str(parsed.get('reason', '')),
            })
    return pd.DataFrame(rows, columns=['pub', 'relevant', 'category', 'reason'])


def apply_filter(patent: pd.DataFrame, mainpath: pd.DataFrame,
                 rel: pd.DataFrame, out_dir: str) -> dict:
    """按判定结果过滤两中间表 → *_filtered.csv + 统计/排除清单。"""
    os.makedirs(out_dir, exist_ok=True)
    keep = set(rel.loc[rel['relevant'], 'pub'])

    p_f = patent[patent['pub'].isin(keep)]
    p_f.to_csv(os.path.join(out_dir, 'patent_route_filtered.csv'),
               index=False, encoding='utf-8-sig')
    m_f = mainpath[mainpath['pub'].isin(keep)]
    m_f.to_csv(os.path.join(out_dir, 'mainpath_nodes_by_window_filtered.csv'),
               index=False, encoding='utf-8-sig')

    dropped = patent[~patent['pub'].isin(keep)]
    excluded = dropped.merge(rel[rel['relevant'] == False], on='pub', how='left')
    excluded.to_csv(os.path.join(out_dir, 'excluded_patents.csv'),
                    index=False, encoding='utf-8-sig')

    # 终审修正（I-2）：补判定规模/主路径无文本披露字段（供报告研究域界定节）
    judged = len(rel)
    stats = {
        'patent_total': len(patent), 'patent_kept': len(p_f),
        'patent_dropped': len(dropped),
        'mainpath_total': len(mainpath), 'mainpath_kept': len(m_f),
        'mainpath_dropped': len(mainpath) - len(m_f),
        'topics_total': patent['topic_code'].nunique(),
        'topics_kept': p_f['topic_code'].nunique(),
        'cn_kept': int((p_f['is_cn'].astype(int) == 1).sum()),
        'judged': judged,
        'relevant': int(rel['relevant'].sum()),
        'irrelevant': int((~rel['relevant']).sum()),
        'mainpath_no_text': len(set(mainpath['pub'].map(normalize_pub)) - set(rel['pub'])),
    }
    pd.DataFrame([stats]).to_csv(os.path.join(out_dir, 'relevance_filter_stats.csv'),
                                 index=False, encoding='utf-8-sig')
    return stats


def main() -> None:
    os.makedirs(WORK_DIR, exist_ok=True)
    texts = collect_texts()
    tasks_path = os.path.join(WORK_DIR, 'tasks.jsonl')
    results_path = os.path.join(WORK_DIR, 'results.jsonl')
    n = build_tasks(texts, tasks_path)
    print(f'tasks: {n}（无文本跳过 {len(texts) - n}）')
    run_batch(tasks_path, results_path)
    rel = parse_results(results_path)
    print(f'results 解析: {len(rel)} 条（relevant {rel["relevant"].sum()} / '
          f'irrelevant {(~rel["relevant"]).sum()}）')

    patent = pd.read_csv(os.path.join(INTER_DIR, 'patent_route.csv'),
                         dtype={'pub': str, 'topic_code': str})
    mainpath = pd.read_csv(os.path.join(INTER_DIR, 'mainpath_nodes_by_window.csv'),
                           dtype=str)
    stats = apply_filter(patent, mainpath, rel, INTER_DIR)
    print('过滤统计:', stats)

    # 终审修正（M-4）：无任何文本的主路径节点去重清单（pub 不在判定任务集）
    task_ids = set()
    with open(tasks_path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                task_ids.add(json.loads(line)['id'])
    mp_pubs = mainpath['pub'].drop_duplicates()
    no_text = sorted(mp_pubs.loc[~mp_pubs.map(normalize_pub).isin(task_ids)])
    no_text_path = os.path.join(INTER_DIR, 'no_text_mainpath_nodes.csv')
    pd.DataFrame({'pub': no_text}).to_csv(no_text_path, index=False,
                                          encoding='utf-8-sig')
    print(f'no_text 主路径节点清单已写: {len(no_text)} 行 → {no_text_path}')


if __name__ == '__main__':
    main()
