# -*- coding: utf-8 -*-
"""主路径全景概况：6 窗口全部主路径 + 3 条概括路线沿革。

- 独立运行：生成 outputs/主路径全景概况.md（一级标题）
- 被 generate_report 导入：render_paths_overview(level=2) 嵌入路线版报告
"""
import json
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 脚本在 X/scripts/ → 上三级=项目根
MP_DIR = os.path.join(ROOT, '..', '主路径识别', 'outputs')
SUM_DIR = os.path.join(ROOT, '..', '路径概括与拓展', 'outputs')
OUT_DIR = os.path.join(ROOT, 'outputs')

WINDOWS = ['pre2000', '2000_2005', '2000_2010', '2000_2015', '2000_2020', '2000_2026']
LABELS = {'pre2000': '2000 前', '2000_2005': '2000-2005', '2000_2010': '2000-2010',
          '2000_2015': '2000-2015', '2000_2020': '2000-2020', '2000_2026': '2000-2026'}


def route_desc(summary: dict, pid: int) -> str:
    """概括路线的一句话主题（功能侧重.描述，完整显示不截断）。"""
    for p in summary.get('paths', []):
        if int(p.get('path_id')) == pid:
            feat = p.get('差异化特征') or {}
            if isinstance(feat, dict):
                for key in ('功能侧重', '问题侧重'):
                    sub = feat.get(key) or {}
                    if isinstance(sub, dict) and sub.get('描述'):
                        return str(sub['描述']).strip()
            return str(feat).strip()
    return ''


def _load_summary(w: str) -> dict | None:
    sp = os.path.join(SUM_DIR, f'period_{w}_summary.json')
    if os.path.exists(sp):
        with open(sp, encoding='utf-8') as f:
            return json.load(f)
    return None


def render_paths_overview(level: int = 1, title: str = '主路径全景概况') -> str:
    """生成概况正文；level=1 为独立文件（#/##/###），level=2 嵌入报告（##/###/####）。"""
    h1, h2, h3 = '#' * level, '#' * (level + 1), '#' * (level + 2)

    lines = [f'{h1} {title}\n',
             '> 来源：主路径识别（SPC 权重前 30 条路径）+ 路径概括与拓展'
             '（每窗口概括为 3 条路线）\n']

    win_data = {}
    for w in WINDOWS:
        p = os.path.join(MP_DIR, f'窗口_{w}_全部路径.csv')
        win_data[w] = pd.read_csv(p, dtype=str)

    # 一、总览
    lines.append(f'{h2} 一、各窗口主路径总览\n')
    lines.append('| 窗口 | 路径数 | 年份跨度 | 三条概括路线的主题（一句话） |')
    lines.append('|---|---|---|---|')
    for w in WINDOWS:
        df = win_data[w]
        y_min = int(df['year_start'].astype(float).min())
        y_max = int(df['year_end'].astype(float).max())
        s = _load_summary(w)
        if s is None:
            d1 = d2 = d3 = '—'
        else:
            d1, d2, d3 = route_desc(s, 1), route_desc(s, 2), route_desc(s, 3)
        lines.append(f'| {LABELS[w]} | {len(df)} | {y_min}–{y_max} | '
                     f'P1：{d1}<br>P2：{d2}<br>P3：{d3} |')
    lines.append('')

    # 二、明细
    lines.append(f'{h2} 二、各窗口路径明细（按 SPC 权重排名）\n')
    for w in WINDOWS:
        df = win_data[w]
        lines.append(f'{h3} {LABELS[w]}（{len(df)} 条）\n')
        lines.append('| 排名 | 时间跨度 | 节点数 | SPC 总权重(万) | 起点 → 终点 |')
        lines.append('|---|---|---|---|---|')
        for _, r in df.iterrows():
            ys = f'{int(float(r["year_start"]))}→{int(float(r["year_end"]))}'
            spc = float(r['total_spc']) / 1e4
            lines.append(f'| {int(r["rank_by_spc"])} | {ys} | {r["node_count"]} '
                         f'| {spc:.0f} | {r["seed_source"]} → {r["seed_target"]} |')
        lines.append('')

    # 三、概括路线沿革
    lines.append(f'{h2} 三、三条概括路线的跨窗口沿革\n')
    final_sum = _load_summary('2000_2026')
    for pid in (1, 2, 3):
        lines.append(f'{h3} P{pid}\n')
        if final_sum is not None:
            lines.append(f'- 最终态（2000-2026）主题：{route_desc(final_sum, pid)}\n')
        lines.append('| 窗口 | 该路线主题（功能侧重） |')
        lines.append('|---|---|')
        for w in WINDOWS:
            s = _load_summary(w)
            lines.append(f'| {LABELS[w]} | {route_desc(s, pid) if s else "—"} |')
        lines.append('')

    return '\n'.join(lines)


def main() -> None:
    out = os.path.join(OUT_DIR, '主路径全景概况.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(render_paths_overview(level=1))
    print(f'已写 {out}')


if __name__ == '__main__':
    main()
