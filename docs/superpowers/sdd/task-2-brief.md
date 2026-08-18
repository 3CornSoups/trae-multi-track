# Task 2 实施简报

## 项目全局约束（必须遵守）

- 时期（PERIODS）：`["2000_2005", "2000_2010", "2000_2015", "2000_2020", "2000_2026"]`（不含 pre2000）
- 每时期取 `rank_by_spc` ≤ 3 的路径（按 total_spc 降序，见 paths_all.csv）
- 数据文件：`主路径识别/outputs/window_{period}_paths_all.csv` 与 `专利数据合并与引文网络构建/merged_all_patents.xlsx`（相对 `D:\论文和代码项目\论文\TRAE\多轨道` 解析为绝对路径）
- 维度权重（对齐论文指标）：功能 0.35、解决问题 0.30、应用场景 0.20、技术原理 0.15
- 阈值默认：θ₁ = 0.3（时期门槛）、θ₂ = 0.3（路径门槛）、每路径上限 K = 100
- 中文摘要文本规则：优先"摘要——翻译"列 → 否则"摘要"列含 CJK 用原文 → 否则跳过该专利
- LLM：DeepSeek `deepseek-chat`，base_url `https://api.deepseek.com`，key 从环境变量 `DEEPSEEK_API_KEY` 读取
- 公开号规范化：去连字符、大写（US A 类补零沿用项目规范）
- 输出目录：`路径概括与拓展/`（prompts/、outputs/、logs/ 子目录）
- 所有输出文件 UTF-8 编码
- API 失败重试 3 次 + 指数退避（1s/2s/4s）；JSON 解析失败重试并要求"仅输出 JSON 代码块"
- 断点续跑：`outputs/period_{period}_summary.json` 已存在则跳过该时期 LLM 调用

## 任务正文（需求与完整代码）

data_loader.py — 路径解析与中文摘要提取（Step 1）

**Files:**
- Create: `路径概括与拓展/scripts/data_loader.py`
- Test: `路径概括与拓展/tests/test_data_loader.py`

**Interfaces:**
- Consumes: `config.PATHS_DIR`、`config.PATENTS_FILE`、`config.TOP_N_PATHS`
- Produces:
  - `normalize_pubnum(pub: str) -> str` — 去连字符、大写
  - `parse_node_sequence(seq: str) -> list[str]` — "A → B → C" → 规范化节点列表
  - `load_top_paths(period: str) -> list[dict]` — 该时期 top-3 路径，每项含 `path_id`(int)、`nodes`(list[str])
  - `load_patent_texts() -> pd.DataFrame` — 全量专利，列：`pub`(规范化)、`text`(中文摘要文本)、`title`、`apply_date`、`pub_date`、`source`；text 为空的排除
  - `path_abstracts(period, paths, patents_df) -> list[dict]` — 每路径 `{path_id, nodes, items: [{node, title, text}]}`，仅 internal 节点（在 patents_df 命中的）

- [ ] **Step 1: 写失败测试**

`tests/test_data_loader.py`:

```python
# -*- coding: utf-8 -*-
import pandas as pd
from data_loader import normalize_pubnum, parse_node_sequence, resolve_abstract


def test_normalize_pubnum():
    assert normalize_pubnum("US-2009-0024475-A1") == "US20090024475A1"


def test_parse_node_sequence():
    assert parse_node_sequence("A1 → B2 → C3") == ["A1", "B2", "C3"]
    assert parse_node_sequence("") == []


def test_resolve_abstract_translation_first():
    # 翻译列非空 → 用翻译
    assert resolve_abstract("English abstract here", "中文翻译摘要") == "中文翻译摘要"


def test_resolve_abstract_cjk_fallback():
    # 翻译列为空但摘要含中文 → 用原文
    assert resolve_abstract("这是一条中文摘要", "") == "这是一条中文摘要"


def test_resolve_abstract_skip_non_cjk():
    # 翻译列空且摘要无中文 → None（跳过）
    assert resolve_abstract("English only abstract", "") is None


def test_resolve_abstract_both_missing():
    assert resolve_abstract(None, None) is None


def test_load_top_paths_real_file():
    from config import PATHS_DIR
    df = pd.read_csv(PATHS_DIR / "window_2000_2010_paths_all.csv", encoding="utf-8-sig")
    top = df[df["rank_by_spc"] <= 3]
    assert len(top) == 3
    assert top["path_id"].tolist() == [1, 2, 3]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_data_loader.py -v`
Expected: FAIL，ModuleNotFoundError: No module named 'data_loader'

- [ ] **Step 3: 写实现**

`scripts/data_loader.py`:

```python
# -*- coding: utf-8 -*-
"""Step 1: 主路径节点解析 + 全量专利中文摘要提取。"""
import re
import unicodedata
import pandas as pd

from config import PATHS_DIR, PATENTS_FILE, TOP_N_PATHS

_CJK_RE = re.compile(r"[一-鿿㐀-䶿]")
_ARROW_RE = re.compile(r"\s*→\s*")


def normalize_pubnum(pub: str) -> str:
    """规范化公开号：去连字符、大写。"""
    if not isinstance(pub, str):
        return ""
    return unicodedata.normalize("NFKC", pub).replace("-", "").upper()


def parse_node_sequence(seq: str) -> list[str]:
    """'A → B → C' → ['A','B','C']（已规范化）"""
    if not isinstance(seq, str) or not seq.strip():
        return []
    return [normalize_pubnum(n) for n in _ARROW_RE.split(seq.strip())]


def resolve_abstract(abstract, translated) -> str | None:
    """统一为中文摘要文本；无法获得则返回 None。
    规则：翻译列非空用它；否则摘要含 CJK 用原文；否则 None。"""
    if translated and isinstance(translated, str) and translated.strip():
        return translated.strip()
    if abstract and isinstance(abstract, str) and _CJK_RE.search(abstract):
        return abstract.strip()
    return None


def load_top_paths(period: str) -> list[dict]:
    """该时期 rank_by_spc ≤ TOP_N_PATHS 的路径。"""
    df = pd.read_csv(PATHS_DIR / f"window_{period}_paths_all.csv", encoding="utf-8-sig")
    top = df.sort_values("rank_by_spc").head(TOP_N_PATHS)
    return [{"path_id": int(r["path_id"]), "nodes": parse_node_sequence(r["node_sequence"])}
            for _, r in top.iterrows()]


def load_patent_texts() -> pd.DataFrame:
    """全量专利，统一中文摘要文本；text 为空的排除。"""
    df = pd.read_excel(PATENTS_FILE,
                       usecols=["公开号", "专利标题", "摘要", "摘要——翻译",
                                "申请日", "公开日", "数据来源"])
    df["pub"] = df["公开号"].astype(str).map(normalize_pubnum)
    df["text"] = [resolve_abstract(a, t) for a, t in zip(df["摘要"], df["摘要——翻译"])]
    df = df.dropna(subset=["text"]).rename(columns={
        "专利标题": "title", "申请日": "apply_date", "公开日": "pub_date", "数据来源": "source"})
    return df[["pub", "text", "title", "apply_date", "pub_date", "source"]].copy()


def path_abstracts(period: str, paths: list[dict], patents_df: pd.DataFrame) -> list[dict]:
    """每路径内部节点（能命中全量表的）及其摘要文本。"""
    pub_set = set(patents_df["pub"])
    by_pub = {p: row for p, row in zip(patents_df["pub"], patents_df.to_dict("records"))}
    result = []
    for p in paths:
        items = []
        for node in p["nodes"]:
            if node in pub_set:
                row = by_pub[node]
                items.append({"node": node, "title": row["title"], "text": row["text"]})
        result.append({"path_id": p["path_id"], "nodes": p["nodes"], "items": items})
    return result
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_data_loader.py -v`
Expected: PASS（6 个测试）

- [ ] **Step 5: 真实数据抽查**

Run: `python -c "from scripts import data_loader as dl; from scripts import config; df=dl.load_patent_texts(); print('有摘要:',len(df),'/',72583); paths=dl.load_top_paths('2000_2010'); pa=dl.path_abstracts('2000_2010',paths,df); [print(p['path_id'],'摘要条数:',len(p['items'])) for p in pa]"`
Expected: 有摘要约 70000；每路径摘要条数 ≈ internal_nodes（11/10/10 左右），日志记录无中英摘要被跳过的节点。

---
