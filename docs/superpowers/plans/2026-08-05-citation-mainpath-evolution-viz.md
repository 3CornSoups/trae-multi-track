# 引文网络与主路径演化可视化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `引文网络和主路径演化/` 交付静态 HTML+D3 同心环页面，展示 2000 年起 5 个窗口的主路径演化（Top-5 路径 + 高被引背景点）。

**Architecture:** Python 预处理产出精简 `viz_data.json`；前端用 D3 画同心环、贝塞尔路径与轻交互；无构建工具。

**Tech Stack:** Python 3 + pandas；HTML/CSS；D3 v7（CDN）

## Global Constraints

- 交付目录：`引文网络和主路径演化/`
- 窗口仅：`2000_2005` … `2000_2026`（不含 pre2000）
- 每窗口主路径 Top-5；背景点每窗口 in_degree Top-20
- 落环：首次进入主路径 / 首次进入背景 Top，全局只画一次
- 所有自写函数须有中文函数级注释
- 当前工作区无 git：跳过所有 commit 步骤
- 规格：`docs/superpowers/specs/2026-08-05-citation-mainpath-evolution-viz-design.md`

## File Structure

| 文件 | 职责 |
|------|------|
| `引文网络和主路径演化/prepare_viz_data.py` | 读 CSV/JSON → 裁剪 → 写 `data/viz_data.json` |
| `引文网络和主路径演化/data/viz_data.json` | 前端唯一数据源 |
| `引文网络和主路径演化/index.html` | 页面壳 |
| `引文网络和主路径演化/css/style.css` | 布局与视觉 |
| `引文网络和主路径演化/js/ring-chart.js` | 同心环布局与绘制 |
| `引文网络和主路径演化/js/main.js` | 加载数据、图例、详情、交互接线 |
| `引文网络和主路径演化/README.md` | 用法说明 |

---

### Task 1: 数据预处理脚本

**Files:**
- Create: `引文网络和主路径演化/prepare_viz_data.py`
- Create: `引文网络和主路径演化/data/`（运行后生成 `viz_data.json`）

**Interfaces:**
- Produces: `viz_data.json`，结构见规格 §7.2；`meta.windows[].ring` 为 0–4；`nodes[].type` 为 `"mainpath"` | `"background"`；`paths[].nodes` 为公开号有序数组

- [ ] **Step 1: 编写 `prepare_viz_data.py`**

实现要点：
1. `WINDOWS` 有序列表 5 项，配色固定。
2. 对每个窗口读 `主路径识别/outputs/window_{id}_summary.json` 取 Top-5 `path_id`（按 paths 顺序即 SPC 序），再读 `window_{id}_sequences.csv` 过滤这些 path_id。
3. 按窗口顺序扫主路径节点：未见过则登记 `ring/first_window/type=mainpath` 及 sequences 中的 title/year/country。
4. 对每个窗口读 `nodes_window_{id}.csv`，按 `in_degree_window` Top-20，跳过已是 mainpath 或已登记 background 的，登记 background。
5. 输出 paths：每窗口 Top-5，`nodes` 为序列公开号列表；`total_spc` 来自 summary。
6. 写 JSON 到 `data/viz_data.json`，打印节点/路径计数。

路径基准：脚本所在目录的父目录为项目根 `多轨道/`。

- [ ] **Step 2: 运行脚本并核验**

Run: `python prepare_viz_data.py`（工作目录为 `引文网络和主路径演化`）

Expected:
- `paths` 长度 = 25
- 每个 `id` 在 `nodes` 中唯一
- `ring` ∈ {0,1,2,3,4}
- mainpath + background 数量合理（百级）

---

### Task 2: 页面壳与样式

**Files:**
- Create: `引文网络和主路径演化/index.html`
- Create: `引文网络和主路径演化/css/style.css`

- [ ] **Step 1: 写 HTML**

结构：header（标题+说明）→ 三栏（`#legend` | `#chart` SVG 容器 | `#detail`）→ 引入 D3 CDN、`ring-chart.js`、`main.js`。

- [ ] **Step 2: 写 CSS**

浅色学术风；CSS 变量定义环色；三栏布局桌面优先，窄屏堆叠；详情卡空态文案。

---

### Task 3: 同心环图表（D3）

**Files:**
- Create: `引文网络和主路径演化/js/ring-chart.js`

**Interfaces:**
- Produces: `createRingChart(container, data, callbacks)` → `{ updateVisibility, clearHighlight, destroy }`
- `callbacks`: `{ onNodeHover(node|null), onBackgroundClick() }`

- [ ] **Step 1: 实现布局**

- 半径：`base + ring * step`
- 主路径节点：同环内按「所属路径聚类」分配角度（取该节点首次出现的路径），再均匀/轻微斥力
- 背景点：同环空隙插值角度
- 返回每个 node 的 `x,y,angle,radius`

- [ ] **Step 2: 实现绘制**

- 环带弧、背景点、路径贝塞尔（控制点 = 两端点中点向圆心外推一点）、主路径节点
- zoom/pan 绑定 SVG
- 入场：环 opacity → 节点 → 路径 stroke-dashoffset 短动画

- [ ] **Step 3: 实现高亮与显隐 API**

- `updateVisibility({ pathKeys: Set, backgroundRings: Set })`
- 悬停节点：加 class `highlighted` 到相关 path/node
- 点击空白：`onBackgroundClick`

---

### Task 4: 主入口交互

**Files:**
- Create: `引文网络和主路径演化/js/main.js`

- [ ] **Step 1: 加载 `data/viz_data.json`，渲染图例**

- 环图例：切换该环 background 显隐（默认全开）
- 路径图例：按窗口分组，默认全开，点击切换

- [ ] **Step 2: 详情卡**

悬停显示 id、title/title_cn、app_year、country、type、first_window、in_degree；离开保留最后一项或显示提示。

- [ ] **Step 3: 接线 createRingChart**

---

### Task 5: README 与验收

**Files:**
- Create: `引文网络和主路径演化/README.md`

- [ ] **Step 1: 写 README**（如何跑 prepare、如何用 `python -m http.server` 打开）
- [ ] **Step 2: 本地起服务，确认 5 环、25 路径、悬停与显隐可用**

---

## Spec Coverage

| 规格项 | Task |
|--------|------|
| 5 环窗口 / Top-5 / 背景 Top-20 / 首次落环 | Task 1 |
| 页面布局壳 | Task 2 |
| 同心环布局与路径曲线 | Task 3 |
| 轻交互与详情 | Task 4 |
| README 与验收 | Task 5 |
| 非目标（全量网、滑块、播放） | 不做 |
