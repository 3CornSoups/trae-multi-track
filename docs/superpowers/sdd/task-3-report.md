# Task 3 实施报告 — keyword_match.py 两段式关键词匹配引擎

日期：2026-08-05
状态：DONE（8/8 测试通过）

## 一、创建的文件清单

1. `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\tests\test_keyword_match.py`（测试，与简报 Step 1 逐字一致，未作任何改动）
2. `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\scripts\keyword_match.py`（实现）

接口：`count_hits(text, keywords) -> int`、`score_dim_groups(text, dims, dim_map, weights) -> float`、`score_overall(text, summary) -> float`、`score_path_diff(text, path_summary) -> float`，并从 `config` 导入 `WEIGHTS` / `OVERALL_DIM_MAP` / `PATH_DIM_MAP`（Task 1-2 产出，接口核对无误）。

## 二、pytest 输出（最终）

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\26610\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展
plugins: anyio-3.7.1
collecting ... collected 8 items

tests/test_keyword_match.py::test_chinese_substring PASSED               [ 12%]
tests/test_keyword_match.py::test_english_boundary_and_plural PASSED     [ 25%]
tests/test_keyword_match.py::test_english_in_chinese_text PASSED         [ 37%]
tests/test_keyword_match.py::test_empty_keywords PASSED                  [ 50%]
tests/test_keyword_match.py::test_score_overall_single_dim PASSED        [ 62%]
tests/test_keyword_match.py::test_score_overall_cap3 PASSED              [ 75%]
tests/test_keyword_match.py::test_score_overall_no_hit PASSED            [ 87%]
tests/test_keyword_match.py::test_score_path_hit PASSED                  [100%]

============================== 8 passed in 0.02s ==============================
```

执行方式：`cd "D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展" && PYTHONUTF8=1 python -m pytest tests/test_keyword_match.py -v`（`PYTHONUTF8=1` 仅为规避 Windows 终端 GBK 输出乱码，输出重定向至临时文件后 Read 确认，真实通过）。

TDD 流程：先写测试 → 首次运行报 `ModuleNotFoundError: No module named 'keyword_match'`（符合预期）→ 写实现 → 二次运行 8 passed。

## 三、偏离简报的决策及原因（重要）

简报 Step 1（测试）与 Step 3（实现）之间存在**语义矛盾**，无法在不改测试且不改实现的情况下让 8 个测试全部通过。以简报 Step 4 的验收标准（"PASS（8 个测试）"）为准，对实现做了两处必要修正；**测试文件保持简报原样一字未改**。

### 1. count_hits 语义：按"出现次数"计数（非"每关键词计 1"）

简报实现逻辑为"每个关键词最多 +1"，但其测试明确要求计数：
- `test_english_boundary_and_plural`：`count_hits(text, ["electrode"]) == 2`（注释"两处"）
- `test_score_overall_cap3`：重复 5 次的"信号采集"经封顶后期望 `0.35*3 = 1.05`

实现在简报代码下分别只得 1、0.35。故改为 `hits += len(_kw_regex(kw).findall(text))`（同一关键词多次出现累加，不同关键词累加）。

### 2. score_dim_groups 语义：中/英关键词按"概念"聚合（取 max，不平铺求和）

简报实现将 `关键词_中 + 关键词_英` 平铺后合计命中数，但 `test_score_overall_single_dim` 的文本 "本发明涉及 signal acquisition 信号采集方法" 同时包含中英两个关键词——平铺语义下功能维度命中数为 2，得分必为 0.7，而测试期望 0.35（注释"只命中'功能'1 词"）。即简报作者的真实意图是：**中英关键词是同一概念的两种表述，命中只计 1 个概念**。

实现改为按维度先分别统计中频、英频，取 `max(中频, 英频)` 再封顶：
- 翻译对照文本（原文+译文同现，如 "signal acquisition 信号采集"）不再被双计 —— 这也是实际数据（LLM 摘要含中英对照）中更合理的语义；
- 全部 8 个测试在此语义下通过，且测试文件零改动。

### 3. 附加小容错（不影响测试语义）

`score_dim_groups` 中对 `关键词_中` / `关键词_英` 若为字符串（LLM 输出不合规时可能不是列表）包装为单元素列表，避免逐字符拆分导致的误命中。

### 4. 其他

- 本项目不是 git 仓库，简报中 Commit 相关步骤全部跳过，未执行任何 git 命令。
- 简报 Step 4 处测试数量表述与测试文件实际 8 个一致（简报标题/正文预期均为 8 个，无 6 个的出入）。

## 四、自查发现

1. **简报内部矛盾**（见上）：Step 1 测试与 Step 3 实现两处语义冲突（计数 vs 去重、平铺 vs 概念聚合），是本次任务唯一需要自主决策的点，已按测试意图（验收标准）修复实现并记录。
2. **归一化设计确认**：`score_dim_groups` 的分母 `den` 只累加 dims 中实际存在的维度权重（简报原设计即如此）。若 summary 只含 1 个维度且该维全命中，得分为 1.0（按存在维度归一化）；单维封顶 3 后得分可超 1（如 1.05），为简报注释明示的设计（路径对比用相对值）。
3. **边界健壮性**（自查脚本验证通过）：空 summary / `overall`/`差异化特征` 为 None / 空关键词列表 / 含 None 与空串的关键词 / 中文单字符关键词 / 英文单复数同现（`sig signal signals` → 2）均行为正确。
4. **终端中文乱码为环境编码问题**：pytest 输出经 `PYTHONUTF8=1` 重定向至 UTF-8 文件后 Read 确认，8 个测试真实通过，无编码导致的假阳性。

## 五、遗留说明

- 未实现/未涉及简报全局约束中属于后续 Task 的部分（LLM 调用、断点续跑、阈值过滤等），本任务仅交付纯函数匹配引擎。
- `config.py`、`tests/conftest.py` 为 Task 1-2 已有产物，本次未改动。

## 六、缺陷修复（Task 3 审查 Minor 缺陷）

- **缺陷**：`score_dim_groups` 中若维度值为 None（LLM 输出不合规，如 `"功能主线": null`），`meta.get(...)` 抛 AttributeError 崩溃。
- **修复**：`scripts/keyword_match.py` `score_dim_groups` for 循环内、`w = weights.get(...)` 之前插入防御行：
  ```python
  if not isinstance(meta, dict):
      continue  # LLM 输出不合规（维度为 null/非对象）时跳过该维度
  ```
  其余代码不变。
- **验证**：
  - `PYTHONUTF8=1 python -m pytest tests/test_keyword_match.py -v` → 8 passed。
  - 边界验证（临时命令）：`PYTHONUTF8=1 PYTHONPATH=scripts python -c "from keyword_match import score_overall; print(score_overall('任意文本', {'overall': {'功能主线': None}}))"` → 输出 `0.0`，不崩溃（None 维度被跳过，den=0 返回 0.0）。
  - 注：`python -c` 需加 `PYTHONPATH=scripts`（测试经 `tests/conftest.py` 注入 scripts 路径，直接命令行不注入）。
