# Task 2 实施报告 — data_loader.py（主路径节点解析 + 全量专利中文摘要提取）

日期：2026-08-05
状态：DONE_WITH_CONCERNS（核心功能全部通过；简报中 3 处与磁盘真实数据/环境不符，详见"偏离决策"）

## 创建的文件清单（绝对路径）

| 文件 | 说明 |
|---|---|
| `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\scripts\data_loader.py` | 实现：normalize_pubnum / parse_node_sequence / resolve_abstract / load_top_paths / load_patent_texts / path_abstracts（逐字使用简报代码） |
| `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\tests\test_data_loader.py` | 测试：7 个测试函数（逐字使用简报代码） |
| `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\logs\step5_verify.txt` | Step 5 抽查输出存档（UTF-8，exit=0） |
| `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\logs\step5_extended.txt` | 扩展诊断输出存档（覆盖率、节点匹配、唯一性） |
| `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\logs\step5_sample.txt` | 摘要样本文档存档 |

未执行任何 git 命令（项目不是 git 仓库，按指示跳过简报全部 Commit 步骤）。

## pytest 运行输出

Step 2（写测试后先跑，确认失败）：

```
tests\test_data_loader.py:3: in <module>
    from data_loader import normalize_pubnum, parse_node_sequence, resolve_abstract
E   ModuleNotFoundError: No module named 'data_loader'
============================== 1 error in 0.49s ===============================
```

与简报 Expected 一致（FAIL，ModuleNotFoundError）。

Step 4（写实现后重跑）：

```
collected 7 items

tests/test_data_loader.py::test_normalize_pubnum PASSED                  [ 14%]
tests/test_data_loader.py::test_parse_node_sequence PASSED               [ 28%]
tests/test_data_loader.py::test_resolve_abstract_translation_first PASSED [ 42%]
tests/test_data_loader.py::test_resolve_abstract_cjk_fallback PASSED     [ 57%]
tests/test_data_loader.py::test_resolve_abstract_skip_non_cjk PASSED     [ 71%]
tests/test_data_loader.py::test_resolve_abstract_both_missing PASSED     [ 85%]
tests/test_data_loader.py::test_load_top_paths_real_file PASSED          [100%]

============================== 7 passed in 0.31s ==============================
```

注意：简报 Step 4 预期写"PASS（6 个测试）"，但简报自身给出的测试文件包含 **7 个测试函数**（6 个纯单元 + 1 个真实文件 `test_load_top_paths_real_file`），实际按测试文件内容收集到 7 项、全部 PASS。测试文件逐字使用简报代码，未增删。

## Step 5 真实数据抽查输出与解释

运行命令（简报原文 + 必要环境修复 `PYTHONPATH=scripts`，原因见"偏离决策"第 2 条），输出重定向至 `logs/step5_verify.txt`（UTF-8，exit=0）：

```
有摘要: 31650 / 72583
1 摘要条数: 11
2 摘要条数: 10
3 摘要条数: 10
```

解释：

- **有摘要 31650 / 72583**：磁盘上的 `merged_all_patents.xlsx` 实际共 **31899 行**（非简报预期的 72583），其中 31650 行（99.2%）经 `resolve_abstract` 得到中文摘要文本（28012 行用"摘要——翻译"列，其余用含 CJK 的原文摘要），249 行因无中英摘要被跳过。简报的"约 70000"与磁盘文件不符，属真实数据与简报预期不一致（详见偏离决策第 4 条）。
- **各路径摘要条数 11/10/10**：与 `window_2000_2010_paths_all.csv` 的 internal_nodes（11/10/10）**完全一致**，全部内部节点均在全量专利表中命中摘要。逐字满足"每路径摘要条数 ≈ internal_nodes"的验证目标。

扩展诊断（logs/step5_extended.txt，exit=0）：

```
xlsx总行数(load_patent_texts前): 31899
有text行数: 31650
有text占比: 99.2%
唯一pub数: 31650
text列长度统计: min=1 max=1603 mean=235.9
列: ['pub', 'text', 'title', 'apply_date', 'pub_date', 'source']
翻译列非空行数: 28012
path 1 nodes= 15 missing_in_df= ['US20090024448A1', 'US20110237971A1', 'US20090024475A1', 'US20090030717A1']
path 2 nodes= 13 missing_in_df= ['US20090024448A1', 'US20090030717A1', 'US20090024475A1']
path 3 nodes= 14 missing_in_df= ['US20090024448A1', 'US20090030717A1', 'US20090083129A1', 'US8270814B2']
```

- 唯一 pub 数与总行数相等（31650 = 31650），规范化后**无重复公开号**。
- 各路径未命中节点数（4/3/4）与 paths_all.csv 的 **external_nodes 列（4/3/4）一一对应**——未命中的全部是外部节点（表外专利，本无摘要记录），内部节点命中率 100%。这是符合预期的行为，非 bug。

样本（logs/step5_sample.txt）：

```
node: US20090062629A1
title: STIMULUS PLACEMENT SYSTEM USING SUBJECT NEURO-RESPONSE MEASUREMENTS
text前80字: 一种系统评估和选择用于引入刺激材料的时间和空间位置。 分析视频流、物理位置、印刷广告、商店货架、图像、广告等，以识别用于引入刺激材料的位置，例如消息、品牌图像、
```

中文摘要文本质量正常。

## 对简报的偏离决策及原因

1. **未执行任何 git 命令**：项目不是 git 仓库，按指示跳过全部 Commit 步骤。
2. **Step 5 命令增加 `PYTHONPATH=scripts` 环境变量**：简报原文 `python -c "from scripts import data_loader as dl; ..."` 直接运行会失败——`from scripts import data_loader` 把 `data_loader` 作为命名空间包 `scripts` 的子模块加载，其内部的 `from config import ...` 找不到顶层模块 `config`（`scripts/` 不在 sys.path），报 `ModuleNotFoundError: No module named 'config'`（首跑 exit=1，见验证过程）。pytest 场景不触发此问题（conftest.py 已将 scripts/ 加入 sys.path）。修复方式：`PYTHONPATH=scripts` 指向 scripts/，其余命令逐字保留。
3. **测试数量预期偏差**：简报 Step 4 预期"6 个测试"，但简报给出的测试文件实含 7 个测试函数，全部 PASS（7 passed）。测试文件本身逐字使用简报代码，未做增删。
4. **有摘要条数 31650 而非"约 70000"**：`merged_all_patents.xlsx`（122MB，2024-08-04 15:14 生成）实有 31899 行，任何实现都不可能产出约 70000 条摘要。简报的 72583/约 70000 与磁盘文件不一致（可能简报撰写时预期的是更大数据集）。按简报"实现代码逐字使用"原则，data_loader.py 未做任何适配性改动——`load_patent_texts()` 返回实际命中中文摘要的全部行，上游任务按 31650 条规模即可。**路径级验证（11/10/10 = internal_nodes）不受影响、完全通过。**
5. **新增扩展诊断存档**：logs/step5_extended.txt 与 step5_sample.txt 为验证凭证，遵循 Task 1 先例（logs/step5_verify.txt）保留在 logs/ 下。

## 自查发现

- 测试 7/7 通过；TDD 三步（先失败 → 写实现 → 全通过）按流程执行，失败原因与简报 Expected 一致。
- 真实文件列名核验：`公开号 / 专利标题 / 摘要 / 摘要——翻译 / 申请日 / 公开日 / 数据来源` 七列全部存在于 merged_all_patents.xlsx，`usecols` 无 KeyError。
- 节点匹配健康度：内部节点 100% 命中；未命中节点恰为 external_nodes（4/3/4），与 paths_all.csv 的 external_nodes 列逐一对应。
- 数据质量：规范化后公开号无重复（31650 唯一）；摘要文本长度均值 235.9 字符，样本为规范中文翻译文本。
- openpyxl stylesheet 警告在运行中确实出现，属 pandas 读取 xlsx 的无害警告，已忽略（输出中 grep 过滤）。
- 遗留验证产物：logs/step5_verify.txt、logs/step5_extended.txt、logs/step5_sample.txt 保留作凭证；`.pytest_cache/` 为 pytest 正常产物。

---

## 数据源切换修复（2026-08-05，修复子代理）

### 修改内容
1. `路径概括与拓展/scripts/config.py`：`PATENTS_FILE` 由 `BASE_DIR / "专利数据合并与引文网络构建" / "merged_all_patents.xlsx"` 改为 `BASE_DIR / "merged_patent_info.csv"`。
2. `路径概括与拓展/scripts/data_loader.py`：`load_patent_texts` 改为 `pd.read_csv(PATENTS_FILE, encoding="utf-8-sig", ...)`，翻译列名由 `摘要——翻译` 改为 `摘要_中文`；其余函数未动。

### 验证 1：pytest
命令：`python -m pytest tests/test_data_loader.py -v`（目录：路径概括与拓展）
结果：**7 passed in 0.32s**（test_normalize_pubnum / test_parse_node_sequence / test_resolve_abstract_translation_first / test_resolve_abstract_cjk_fallback / test_resolve_abstract_skip_non_cjk / test_resolve_abstract_both_missing / test_load_top_paths_real_file）

### 验证 2：真实数据抽查
命令：`PYTHONPATH=scripts python -c "import data_loader as dl; df=dl.load_patent_texts(); print('有摘要:',len(df)); pa=dl.path_abstracts('2000_2010', dl.load_top_paths('2000_2010'), df); [print(p['path_id'], len(p['items'])) for p in pa]"`
实际输出：
```
有摘要: 31650
1 11
2 10
3 10
```
- 有摘要 31650 条，落在预期区间 31000-32000。
- 2000_2010 三路径摘要条数 11/10/10，与 `主路径识别/outputs/window_2000_2010_paths_all.csv` 的 internal_nodes 列（11/10/10）逐一对应一致。
