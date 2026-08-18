# Task 1 实施简报

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

项目脚手架 + config.py

**Files:**
- Create: `路径概括与拓展/scripts/__init__.py`（空文件）
- Create: `路径概括与拓展/scripts/config.py`
- Create: `路径概括与拓展/tests/__init__.py`（空文件）
- Create: `路径概括与拓展/tests/conftest.py`（把 scripts/ 加入 sys.path）
- Create: `路径概括与拓展/路径概括与拓展_README.md`

**Interfaces:**
- Produces: `config.PERIODS`（list[str]）、`config.BASE_DIR`（Path，项目根）、`config.OUTPUT_DIR`/`PROMPT_DIR`/`LOG_DIR`（Path，自动创建）、`config.PATHS_DIR`/`PATENTS_FILE`（Path）、`config.TOP_N_PATHS=3`、`config.WEIGHTS`（dict[str,float]）、`config.OVERALL_DIM_MAP`/`config.PATH_DIM_MAP`（dict[str,str]）、`config.THETA1=0.3`、`config.THETA2=0.3`、`config.K=100`、`config.deepseek_headers()`（dict，含 Authorization）

- [ ] **Step 1: 创建目录与空包文件**

```bash
mkdir -p "路径概括与拓展/scripts" "路径概括与拓展/tests" "路径概括与拓展/prompts" "路径概括与拓展/outputs" "路径概括与拓展/logs"
touch "路径概括与拓展/scripts/__init__.py" "路径概括与拓展/tests/__init__.py"
```

- [ ] **Step 2: 写 config.py**

```python
# -*- coding: utf-8 -*-
"""全局配置：路径、参数、DeepSeek 接入。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根（TRAE/多轨道）
SCRIPTS_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "路径概括与拓展" / "outputs"
PROMPT_DIR = BASE_DIR / "路径概括与拓展" / "prompts"
LOG_DIR = BASE_DIR / "路径概括与拓展" / "logs"
for d in (OUTPUT_DIR, PROMPT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- 时期与路径 ----
PERIODS = ["2000_2005", "2000_2010", "2000_2015", "2000_2020", "2000_2026"]
PATHS_DIR = BASE_DIR / "主路径识别" / "outputs"
PATENTS_FILE = BASE_DIR / "专利数据合并与引文网络构建" / "merged_all_patents.xlsx"
TOP_N_PATHS = 3

# ---- 匹配参数（对齐论文三大指标 + 问题维度）----
WEIGHTS = {"功能": 0.35, "解决问题": 0.30, "应用场景": 0.20, "技术原理": 0.15}
THETA1 = 0.3   # 时期整体门槛
THETA2 = 0.3   # 路径差异化门槛
K = 100        # 每路径并入上限

# LLM JSON 键名 → 内部维度键名（LLM 输出为中文键，此处做映射容错）
OVERALL_DIM_MAP = {"功能主线": "功能", "解决问题": "解决问题",
                   "应用场景": "应用场景", "技术原理": "技术原理"}
PATH_DIM_MAP = {"功能侧重": "功能", "问题侧重": "解决问题",
                "场景侧重": "应用场景", "原理差异": "技术原理"}

# ---- DeepSeek ----
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def deepseek_headers() -> dict:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("环境变量 DEEPSEEK_API_KEY 未设置：请执行 `$env:DEEPSEEK_API_KEY=\"sk-xxx\"`")
    return {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
```

- [ ] **Step 3: 写 conftest.py**

```python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
```

- [ ] **Step 4: 写 README**

`路径概括与拓展/路径概括与拓展_README.md` 内容：项目说明（目的、流程 5 步、运行方式 `python scripts/main.py`、参数、输出文件说明、阈值调参入口 config.py）。

- [ ] **Step 5: 验证 import**

Run: `cd "D:/论文和代码项目/论文/TRAE/多轨道/路径概括与拓展" && python -c "from scripts import config; print(config.PERIODS, config.WEIGHTS)"`
Expected: `['2000_2005', '2000_2010', '2000_2015', '2000_2020', '2000_2026'] {'功能': 0.35, '解决问题': 0.3, '应用场景': 0.2, '技术原理': 0.15}`

---
