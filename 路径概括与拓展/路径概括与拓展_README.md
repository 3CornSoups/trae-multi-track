# 路径概括与拓展（BCI 专利引文网络论文 · 第二步）

## 项目说明

论文第二步：以语义相似度在全数据集筛选与主路径专利高度相似的专利，并入各时期主路径，搭建研究（扩展）数据集，供后续知识图谱构建与技术替代风险计算使用。

- **数据源**：`merged_patent_info.csv`（项目根目录，31899 条记录，utf-8-sig；翻译列名为 `摘要_中文`，公开号已按项目规范补零格式化）。其中 31650 条可得到中文摘要文本。
- **路径输入**：`主路径识别/outputs/window_{时期}_paths_all.csv`，5 个研究时期（2000_2005 / 2000_2010 / 2000_2015 / 2000_2020 / 2000_2026，不含 pre2000），每时期取 rank_by_spc ≤ 3 的 top-3 路径。
- **LLM**：DeepSeek `deepseek-v4-flash`（chat completions），API key 从环境变量 `DEEPSEEK_API_KEY` 读取（在进程启动前设置）。
- **归属规则**：全局贪心唯一归属——每专利只并入一个时期的一条路径，每路径并入上限 K=100。

## 流程（5 步）

1. **路径摘要提取（本地）**：解析 `window_{时期}_paths_all.csv` 的 node_sequence，取 rank_by_spc ≤ 3 的路径节点，在 `merged_patent_info.csv` 中按规范化公开号（去连字符、大写）匹配，提取中文摘要。规则：`摘要_中文` 非空用翻译 → 否则 `摘要` 含 CJK 字符用原文 → 否则跳过该专利。
2. **时期级 LLM 概括（每时期 1 次 API 调用）**：DeepSeek 概括该时期整体特征 + 3 条路径的差异化特征，输出严格 JSON。整体 4 维度（功能主线/解决问题/应用场景/技术原理）与路径 4 维度（功能侧重/问题侧重/场景侧重/原理差异），各含一句话描述与中英关键词（每维度 8-15 个，必须可自摘要文本中直接命中）。
3. **全数据集关键词匹配（本地）**：中文关键词子串包含匹配、英文关键词词边界（\b）匹配；按维度权重计算时期整体得分 S_period 与路径差异化得分 S_path（得分尺度 0-3，每维度命中次数封顶 3）。
4. **全局贪心唯一归属**：每专利只保留 S_path 最高的 (时期, 路径)；同时满足 S_period ≥ θ₁ 且 S_path ≥ θ₂ 才归属；每 (时期, 路径) 并入上限 K=100。默认 θ₁=0.6、θ₂=1.0。
5. **报告**：生成 extension_report.md（每时期每路径并入统计、申请日晚于时期终点标注、阈值敏感性表、每路径最高分抽查），并输出 assignments.csv / matching_scores.csv / extension_results.xlsx。

## 运行方式

```bash
cd 路径概括与拓展
python scripts/main.py                      # 全 5 时期
python scripts/main.py --period 2000_2005   # 单时期（调试）
python scripts/main.py --force              # 强制重新调用 LLM（忽略断点缓存）
```

前置要求：

- 环境变量 `DEEPSEEK_API_KEY` 已设置（PowerShell：`$env:DEEPSEEK_API_KEY = "sk-你的key"`，须在启动进程前设置）。
- 输入数据就位：`主路径识别/outputs/window_{时期}_paths_all.csv` 与项目根目录 `merged_patent_info.csv`。
- API 调用失败自动重试 3 次 + 指数退避（1s/2s/4s），单次超时 300s。
- **断点续跑**：`outputs/period_{时期}_summary.json` 已存在则跳过该时期 LLM 调用，只重算匹配，全量运行约 10 分钟。
- ⚠️ **单时期运行会覆写 `outputs/assignments.csv` 与 `outputs/extension_report.md`**（只含该时期内容），重跑全量即恢复。

## 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| PERIODS | 5 个时期列表 | 研究时期（不含 pre2000） |
| TOP_N_PATHS | 3 | 每时期取 rank_by_spc ≤ 3 的路径 |
| WEIGHTS | 功能 0.35 / 解决问题 0.30 / 应用场景 0.20 / 技术原理 0.15 | 维度权重（对齐论文指标） |
| THETA1 | 0.6 | 时期整体门槛 θ₁ |
| THETA2 | 1.0 | 路径差异化门槛 θ₂ |
| K | 100 | 每路径并入上限 |

得分尺度 0-3：每维度命中关键词数封顶 3（中/英关键词视为同一概念，取次数多者），加权归一化后即为维度得分上限 3。

## 输出文件说明

```
路径概括与拓展/
├─ prompts/period_{时期}_prompt.txt   5 个 prompt 存档（可复现）
├─ outputs/
│  ├─ assignments.csv                 全局归属表（专利→时期-路径，含得分/摘要文本/申请日/数据来源）——论文扩展数据集核心
│  ├─ matching_scores.csv             过时期门槛的全部候选得分（专利 × 时期 × 路径）
│  ├─ extension_results.xlsx          归属 + 候选得分双 sheet，供知识图谱/替代风险计算
│  ├─ extension_report.md             每时期每路径并入统计、申请日标注、θ₂ 阈值敏感性表、每路径最高分抽查
│  ├─ period_{时期}_summary.json      每时期 LLM 特征概括（原始 JSON，断点续跑依据）
│  └─ period_{时期}_summary.md        可读版（维度描述+中英关键词，可进论文附录）
└─ logs/                              API 调用日志（period_{时期}_api.log）
```

当前结果（2026-08-05 全量运行）：1245 条归属（占全量 3.9%），12 条路径满 100 上限、3 条路径受阈值限制（2010-3: 11、2020-1: 10、2020-2: 24）。

## 调参入口

`scripts/config.py`：修改 `THETA1`、`THETA2`、`K`、`WEIGHTS` 即可调整匹配门槛与规模；LLM 相关配置（模型 `DEEPSEEK_MODEL`、URL、key 读取）也在该文件。报告中的 θ₂ 敏感性表档位在 `scripts/report.py` 的 `SENSITIVE_THETAS = [0.50, 0.75, 1.00, 1.25, 1.50]`（对齐 0-3 得分尺度，θ₁ 固定为 config.THETA1）。

## 测试

```bash
# PowerShell
$env:DEEPSEEK_API_KEY = "sk-test"; $env:PYTHONUTF8 = "1"; python -m pytest tests/ -q
```

当前 29 passed（覆盖数据加载、关键词匹配、贪心归属、LLM 解析与报告）。

## 复现

- LLM 输入已存档：`prompts/period_{时期}_prompt.txt` 与 `outputs/period_{时期}_summary.json` 一一对应；保留 summary json 即可跳过 LLM 重算匹配，得到完全一致的归属结果。
- 重新概括（`--force` 或删 json）后结果由 LLM 内容决定，关键词命中规则（步骤 3-4）为纯本地确定性计算。
