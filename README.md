# TRAE 多轨道专利技术替代风险研究

基于 **专利引文网络 + 主路径识别 + 知识图谱** 的脑机接口（BCI）领域技术替代风险量化研究。

## 研究流程

```
原始专利数据 → 引文网络构建 → 主路径识别（6 时间窗口） → 语义相似度拓展研究数据集
→ LLM 实体抽取与知识图谱（2863 专利 / 23029 节点 / 51193 边）
→ BCI 相关性过滤（LLM 逐条判定 2969 条）
→ 技术替代风险计算（双口径 × 过滤前后四版本）
```

## 核心结论（2026-08-18）

- **IPC 主题版（过滤后）**：133 主题 / 38 参与排名 / 9 达标；Top-3 = G06Q30 商业交易系统（神经营销，R=0.463）、A61N2 磁疗器械（0.430）、G06F17 数据处理（0.429）
- **主路径配对版（过滤后）**：6 个跨路线配对中，"国外 P1（推送+测量）替代国内 P2（数据平台）"风险最高（R=0.442）；唯一达标候选 = "国外 P2（数据平台）替代国内 P1（推送+测量）"（R=0.428）
- **性质**：风险排名靠前的主题/配对均为"国外主导 + 国内缺位"型——核心技术 95%+ 在国外、中国高价值专利占比仅 1~3%

## 目录结构

| 目录 | 内容 |
|---|---|
| `替代风险计算/` | 替代风险全流程：scripts（prepare/indicators/embed_similarity/run_all/generate_report/path_routes/filter_relevance/paths_overview）、tests（59 个测试）、outputs（四版指标总表与报告） |
| `主路径识别/` | 6 窗口主路径识别结果（SPC 权重路径 + 报告） |
| `路径概括与拓展/` | 每窗口原生路径 → 3 条跨窗口技术路线（LLM 概括） |
| `语义相似度匹配/` | bge-small-zh-v1.5 预筛 + LLM 精判（主路径相似专利拓展） |
| `数据集合并/` | 研究数据集 05_合并数据集.csv（2863 专利） |
| `实体抽取，知识图谱构建/` | KG 数据包（graph_nodes/graph_edges/canonical_map）与流程报告 |
| `专利数据合并与引文网络构建/` | 引文网络构建脚本 + nodes.csv（26 万节点入度） |
| `docs/` | 设计文档（specs）、实现计划（plans）、方法讨论与全文思路 |
| `多智能体叙事/` | 多智能体情报分析方案 |

## 复现

```powershell
cd 替代风险计算
python -m pytest tests -v          # 59 个测试全绿
python scripts/prepare.py          # 中间表（需本地数据文件，见 数据清单.md）
python scripts/embed_similarity.py # 实体嵌入相似度（需 bge-small-zh-v1.5，本地 HF 缓存）
python scripts/run_all.py          # 指标总表
python scripts/generate_report.py  # Markdown 报告
python scripts/path_routes.py      # 主路径路线版中间表
python scripts/paths_overview.py   # 主路径全景概况
```

版本切换：`config.json` 的 `input_suffix` 取 `""`（IPC 版）/ `"_filtered"`（IPC 过滤版）/ `"_paths"`（配对版）/ `"_paths_filtered"`（配对过滤版）。

LLM 相关性判定（`filter_relevance.py`）需要 `DEEPSEEK_API_KEY` 环境变量（不落盘），输入任务已附于 `outputs/intermediate/relevance/`。

## 方法要点

- **替代风险** R_AB = S_AB × (M_AB + V_B)/2：S=可替代性（功能/场景相似度+原理差异，bge 嵌入对称最佳匹配）、M=替代成熟度（增长优势 G + 主路径地位转移 T）、V=安全暴露度（国外核心专利控制度 K + 国内自主能力缺口 1−A）
- **口径**：国内外=公开国家；软阈值（文档阈值作达标参考标记）；高价值=被引 top10%（44 次）；sigmoid 归一
- 大文件（原始 xlsx、GraphML、嵌入缓存等）不随仓库分发，见 `数据清单.md`

## 免责

数据与结论仅供研究使用；公开数据不包含任何 API 密钥。
