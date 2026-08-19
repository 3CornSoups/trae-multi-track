# 共用层（scripts + tests）

## 数据流

```
prepare.py ──→ outputs/intermediate/patent_route.csv、mainpath_nodes_by_window.csv
     ↓ embed_similarity.py（按 input_suffix 读写 patent_route{suffix}.csv）
entity_sim_by_topic{suffix}.csv
     ↓ run_all.py（读 intermediate + config.json）
替代风险指标总表{suffix}.csv（默认写根 outputs/）
     ↓ generate_report.py（读总表 + intermediate + 全景）
替代风险报告{suffix}.md
```

- 实验二支线：`实验二_主路径配对/scripts/path_routes.py` 生成路线路由表/配对表（_paths 版中间表），前置。
- 实验三支线：`实验三_要素凝练主题/scripts/theme_discovery.py`（LLM 主题凝练）+ `theme_pairs.py`（主题版专利表，_theme 版中间表），前置。
- 过滤版支线：`filter_relevance.py`（AI 相关性判定 → _filtered 版中间表），前置。
- `paths_overview.py`：生成主路径全景概况（独立运行写 `outputs/主路径全景概况.md`；被 generate_report 导入嵌入路线版报告）。

## 7 个共用脚本职责

| 脚本 | 职责 |
|---|---|
| `prepare.py` | KG zip → 每专利一行路由表 + 主路径窗口长表 |
| `embed_similarity.py` | bge-small-zh 编码三类实体集 → 主题对相似度表 |
| `indicators.py` | 纯函数指标库（R=S×(M+V)/2 各层公式，无 IO） |
| `filter_relevance.py` | BCI 相关性判定任务/解析/过滤（LLM） |
| `run_all.py` | 读中间表 + config.json → 指标总表（input_suffix 切版本） |
| `generate_report.py` | 总表 → Markdown 报告（路线版含结论摘要与全景） |
| `paths_overview.py` | 主路径全景概况（独立运行 + 被导入） |

## 复现顺序

```powershell
cd 替代风险计算   # 项目根（所有脚本 ROOT 均解析到项目根）
python 共用/scripts/prepare.py            # 中间表（需本地原始数据）
python 共用/scripts/filter_relevance.py   # 过滤版前置（需 DEEPSEEK_API_KEY）
python 共用/scripts/embed_similarity.py   # 实体嵌入相似度
python 共用/scripts/run_all.py            # 指标总表（config.json input_suffix 切版本）
python 共用/scripts/generate_report.py    # 报告
```

实验二/三前置脚本见各实验 README；`python 共用/scripts/paths_overview.py` 可单独生成全景。

## ROOT 约定

所有脚本 `ROOT = dirname(dirname(dirname(abspath(__file__))))`（脚本在 X/scripts/ → 上三级 = 项目根 替代风险计算）；config.json 读 ROOT、中间表写 `ROOT/outputs/intermediate/`、重跑产物默认写 `ROOT/outputs/`（已归档副本在各实验 outputs/）。

## 测试

10 个测试文件共 69 个用例，`conftest.py` 统一注入 sys.path（共用 + 实验二 + 实验三 scripts），两种跑法均全绿：

```powershell
cd 替代风险计算
python -m pytest 共用/tests -q          # 从项目根跑
cd 共用/tests; python -m pytest -q      # 从 tests 目录跑
```
