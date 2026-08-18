# BCI 相关性过滤后重算 — 设计文档

> 日期：2026-08-18
> 动机：Top 风险主题混入非 BCI 专利（G06Q30 位置广告等）。诊断实证：研究数据集 2863 条中 BCI 源仅 1084（38%）、incoPat 1779（62%）；外溢链条=主路径含非 BCI 外部节点 → 语义匹配以之为锚捞入无关专利。

## 1. 目标

对研究数据集（2863 专利）+ 主路径节点（358 去重）做"是否属脑机接口领域"判定，滤除无关专利后在过滤域上重算替代风险全指标，输出过滤版总表与报告（原始版保留）。

## 2. 口径决策（2026-08-18 用户确认）

1. **判定方法**：LLM 批量判定（batch-glm-llm skill：GLM-4.7-Flash 免费优先 / DeepSeek 兜底；key 走环境变量）。
2. **领域边界**：含 BCI 边缘应用——神经营销（测脑电反应的）、BCI 教育、媒体神经反馈等保留；只排除与脑信号无关的（位置广告、一般医疗设备等）。
3. **主路径口径**：主路径节点同样过过滤；T_AB 分母=窗口主路径中通过过滤的节点数（过滤后域）。无摘要无法判定的主路径节点默认排除并出清单。

## 3. 判定设计

- **判定对象**：研究数据集 2863 唯一专利 ∪ 主路径 358 去重节点（合并去重一次判定）。
- **输入文本**：标题_中文 + 摘要_中文（05_合并数据集.csv 优先；缺失回查 `专利数据合并与引文网络构建/03_合并专利信息_精简.csv`；仍缺失→默认排除 + 清单）。
- **Prompt**：判定专利是否属于脑机接口(BCI)领域或其直接应用；输出 JSON `{"relevant": true/false, "category": "核心/边缘应用/无关", "reason": "≤30字"}`。判定标准写入 prompt：涉及脑信号采集/解码/神经调控技术，或直接消费脑信号的系统（神经营销、BCI 教育、神经反馈媒体）为 relevant；仅通用广告/一般医疗/纯算法工具等为 irrelevant。
- **边界情形**：脑信号仅作为一般生理信号之一且非系统核心功能 → irrelevant（prompt 中明确）。

## 4. 管道改动

| 文件 | 改动 |
|---|---|
| `scripts/filter_relevance.py` | 新增：任务 JSONL 构造（调 batch_llm.py）→ 解析 relevance 结果 → 输出 `outputs/intermediate/patent_route_filtered.csv`、`mainpath_nodes_by_window_filtered.csv`、`relevance_filter_stats.csv`、`excluded_patents.csv`（被排除清单+理由） |
| `scripts/embed_similarity.py` | 加 `input_suffix`（config 键），读 `patent_route{suffix}.csv`；实体向量缓存复用全量缓存（过滤不产生新实体，命中即秒级） |
| `scripts/run_all.py` | 同样支持 `input_suffix`；输出文件名加同后缀（`替代风险指标总表{suffix}.csv`） |
| `scripts/generate_report.py` | 支持 suffix；新增「研究域界定」节（判定方法、边界、过滤前后统计、被排除清单摘要）；局限节更新 |
| `config.json` | 加 `"input_suffix": ""`（过滤版运行设 `"_filtered"`） |
| `tests/` | 新增 test_filter_relevance.py（任务构造/结果解析/统计单测 + smoke）；test_run_all/test_embed 加 suffix 用例 |

## 5. 执行方式

SDD 两任务：Task 8（filter_relevance + LLM 判定跑完 + 单测）、Task 9（suffix 管道 + 过滤版全流程重算 + 报告研究域界定节 + 验证）；最后终审。原始版产出全部保留，过滤版写入 `outputs/filtered/`（或同目录带 `_filtered` 后缀，实现时统一）。

## 6. 预期效果

- 排除位置广告类外溢（如 G06Q30 中 31/39 来自 incoPat 的部分）；保留 BCI 边缘应用
- 过滤后域主题分布更聚焦；达标/样本不足构成改善；报告给出过滤前后对比表
