# -*- coding: utf-8 -*-
"""导出每个时期每条路径的完整成员表：原始主路径专利 + 拓展并入专利。

用法: python scripts/export_path_extension.py
输出: outputs/path_extension_combined.csv (utf-8-sig, Excel 可直接打开)
列: period, path_id, 类型(原始主路径/拓展并入), 序列位置,
    pub, title, 摘要_中文, 申请日, 数据来源, s_period, s_path, 备注
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PATHS_DIR, PATENTS_FILE, OUTPUT_DIR, PERIODS
from data_loader import load_patent_texts, normalize_pubnum, parse_node_sequence


def main():
    patents = load_patent_texts()
    by_pub = {p: row for p, row in zip(patents["pub"], patents.to_dict("records"))}

    # 中文标题列（论文阅读用；03_合并专利信息_精简.csv 的"专利标题（中文）"）
    full = pd.read_csv(PATENTS_FILE, encoding="utf-8-sig",
                       usecols=["公开号", "专利标题（中文）"])
    full["pub"] = full["公开号"].astype(str).map(normalize_pubnum)
    zh_title = dict(zip(full["pub"], full["专利标题（中文）"]))

    assignments = pd.read_csv(OUTPUT_DIR / "assignments.csv")

    rows = []
    for period in PERIODS:
        paths_df = pd.read_csv(PATHS_DIR / f"窗口_{period}_全部路径.csv", encoding="utf-8-sig")
        for _, r in paths_df.sort_values("rank_by_spc").head(3).iterrows():
            path_id = int(r["path_id"])

            # 原始主路径节点（按演化链顺序）
            for i, node in enumerate(parse_node_sequence(r["node_sequence"]), 1):
                info = by_pub.get(node)
                rows.append({
                    "period": period, "path_id": path_id,
                    "类型": "原始主路径", "序列位置": i,
                    "pub": node,
                    "title": info["title"] if info else "",
                    "标题_中文": zh_title.get(node, ""),
                    "摘要_中文": info["text"] if info else "",
                    "申请日": info["apply_date"] if info else "",
                    "数据来源": info["source"] if info else "",
                    "s_period": "", "s_path": "",
                    "备注": "" if info else "外部节点(引文网络中无元数据)",
                })

            # 拓展并入专利（按 s_path 降序）
            ext = assignments[(assignments["period"] == period)
                              & (assignments["path_id"] == path_id)] \
                .sort_values("s_path", ascending=False)
            for j, (_, e) in enumerate(ext.iterrows(), 1):
                rows.append({
                    "period": period, "path_id": path_id,
                    "类型": "拓展并入", "序列位置": j,
                    "pub": e["pub"], "title": e.get("title", ""),
                    "标题_中文": zh_title.get(e["pub"], ""),
                    "摘要_中文": e.get("text", ""),
                    "申请日": e.get("apply_date", ""), "数据来源": e.get("source", ""),
                    "s_period": f"{e['s_period']:.3f}", "s_path": f"{e['s_path']:.3f}",
                    "备注": "",
                })

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_DIR / "path_extension_combined.csv", index=False, encoding="utf-8-sig")
    n_orig = (out["类型"] == "原始主路径").sum()
    n_ext = (out["类型"] == "拓展并入").sum()
    print(f"总行数: {len(out)} | 原始主路径专利: {n_orig} | 拓展并入专利: {n_ext}")
    print(f"输出: {OUTPUT_DIR / 'path_extension_combined.csv'}")
    print("\n各时期×路径成员数:")
    grp = out.groupby(["period", "path_id", "类型"]).size().unstack(fill_value=0)
    print(grp.to_string())


if __name__ == "__main__":
    main()
