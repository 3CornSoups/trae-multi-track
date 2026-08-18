# Task 4 实施报告 — assign.py（全局贪心唯一归属 + top-K 上限）

- 日期：2026-08-05
- 状态：DONE（TDD 流程完整执行，全部测试通过）
- 说明：本项目非 git 仓库，简报中的 Commit 步骤按全局约束跳过，未执行任何 git 命令。

## 创建的文件（绝对路径）

1. `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\tests\test_assign.py`
   — 测试文件，代码逐字取自简报（含 CAND 样例数据与 5 个测试函数）
2. `D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展\scripts\assign.py`
   — 实现文件，代码逐字取自简报（`build_candidates` + `greedy_assign` + 两个私有打分包装）

未修改任何既有文件；验证用的临时 pytest 日志文件（4 个）已在使用后删除，工作树无残留。

## TDD 执行记录

### Step 1-2：写失败测试并确认失败

写入测试后运行 `python -m pytest tests/test_assign.py -v`（`PYTHONUTF8=1`），输出（重定向至临时文件确认）：

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展
collected 0 items / 1 error

ERROR collecting tests/test_assign.py
ImportError while importing test module ...
tests\test_assign.py:3: in <module>
    from assign import greedy_assign
E   ModuleNotFoundError: No module named 'assign'
============================== 1 error in 0.51s ==============================
```

失败点与简报预期完全一致：`ModuleNotFoundError: No module named 'assign'`。

### Step 3：写实现

`scripts/assign.py` 逐字使用简报代码，未做任何改写。`greedy_assign` 使用简报修正后的签名 `(candidates, theta2=THETA2, k=K)`（已验证 `__defaults__ == (0.3, 100)`，与 config 中 `THETA2=0.3`、`K=100` 一致）。

### Step 4：确认通过

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\论文和代码项目\论文\TRAE\多轨道\路径概括与拓展
collected 5 items

tests/test_assign.py::test_unique_per_pub PASSED                         [ 20%]
tests/test_assign.py::test_best_path_wins PASSED                         [ 40%]
tests/test_assign.py::test_threshold2_filters PASSED                     [ 60%]
tests/test_assign.py::test_topk_cap PASSED                               [ 80%]
tests/test_assign.py::test_empty_input PASSED                            [100%]

============================== 5 passed in 0.32s ==============================
```

### 回归：全量测试套件

```
collected 20 items
tests/test_assign.py::... 5 passed
tests/test_data_loader.py::... 5 passed
tests/test_keyword_match.py::... 10 passed
============================== 20 passed in 0.34s ==============================
```

Task 1-3 的 15 个既有测试无回归。

## 偏离简报的决策及原因

- **无实现偏离**：`assign.py`、`test_assign.py` 均逐字取自简报，未自行改写。
- **唯一需要说明的"数量差异"（非偏离）**：简报正文及执行指令称"4 个测试"，但简报测试代码块实际包含 **5** 个测试函数（多了 `test_empty_input`）。因约束为"简报代码逐字使用"，故按代码块原样写入全部 5 个测试，最终 5 个全部通过。此差异已如实记录，未对测试做增删。

## 自查发现

1. **空输入短路**：`greedy_assign` 对空 DataFrame 直接 `return candidates`（返回原对象而非副本）——函数立即返回、无后续变异，不存在别名风险；行为与 `test_empty_input` 一致。
2. **处理顺序符合语义**：先按 `(s_path, 0.5*s_path+0.5*s_period)` 降序排序 → 每 pub 去重取最高 → 过 θ₂ 过滤 → 每 `(period, path_id)` 组内 `cumcount < K` 截断。即 top-k 作用于"已完成唯一归属"的 pub 集合，与简报接口说明（"每 pub 唯一 + 每路径组内取 top-k"）一致。
3. **`build_candidates` 无单测**：简报未为本任务提供 `build_candidates` 的测试，其正确性依赖 `keyword_match` 的既测函数与真实数据，目前仅以模块导出检查验证（`hasattr` 通过）。建议后续任务（接入真实 pipeline 时）补充集成测试。
4. **无中文乱码问题**：全部 pytest 输出以 `PYTHONUTF8=1` 重定向到 UTF-8 文件后读取确认，无乱码；最终验证日志已清理。
