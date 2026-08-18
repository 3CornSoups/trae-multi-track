# 路径概括与拓展 — SDD 执行进度

- 任务采用无 git 工作流（项目非 git 仓库）：实现者不 commit，靠 brief/report 文件与审查者传接。
- Pre-Flight 修正（2026-08-05，已并入计划文件）：①Task4 矛盾测试残留清理 ②greedy_assign 参数化 theta2/k ③敏感性表改用 greedy_assign 精确计算 ④late 判断 startswith("") 恒真 bug 修复 ⑤Task5 api.log 落盘 ⑥main.py 复用 build_candidates。

Task 1: complete (review clean; minor: __pycache__/step5_verify.txt 可后续清理)
Task 2: complete (review clean; minor: brief 测试数笔误 6vs7、load_top_paths head(3)、astype NaN、Step5 logging 预期)
Task 3: complete (review clean; 实现者修正简报测试/实现语义矛盾：出现次数计数+中英max去重；审查后补 null 维度防御已修复)
Task 4: complete (review clean; minor: 空输入返回原对象、极端平局回退行序、NaN 排序不可达、iterrows 性能 Task7 观察)
Task 5: complete (review clean; 补 summarize_period 断点续跑测试 27 passed; minor: PERIODS 未用导入、key import 时快照)
Task 6: complete (review clean; write_report 契约已修：条件 merge+_x/_y 清理，29 passed)
Task 7: complete (阶段A+B 全部完成; 全量 1245 归属/31650=3.9%, 12 路径满 100, 3 路径阈值生效)


数据源变更（用户 2026-08-05 拍板）：匹配对象与路径摘要统一使用 merged_patent_info.csv（31899 条，引文管道 CSV 版，翻译列名"摘要_中文"，公开号已补零规范）。不再使用 xlsx 版本与 72583 匹配管道数据。

参数调整（用户 2026-08-05 拍板，收紧档）：
- 得分尺度实测 0-3（每维命中封顶 3），原 0.3 阈值按 0-1 直觉设定过松（候选 22%）
- THETA1: 0.3→0.6（s_period 中位），THETA2: 0.3→1.0，SENSITIVE_THETAS: [0.2..0.4]→[0.5..1.5]
- test_assign/test_report 同步：显式传 theta2/k 解耦默认值
- 2000-2005 端到端验证：候选 12846、归属 300（每路径 top-100 全 ≥1.5 质量档）、抽查并入专利与差异化特征吻合
- 模型：DEEPSEEK_MODEL 改为 deepseek-v4-flash（用户指定）

终审（2026-08-05, opus）：APPROVE WITH MINOR NOTES。
- 核验：29 passed、归属唯一性、敏感性表重算一致、5 时期 LLM JSON 键名精确匹配、申请日计数 100% 复核、无 key 泄漏
- Important I-1（README 陈旧）已修复；9 项 Minor 全部记录接受（跳过数统计、申请日比例列、api.log 重试记录、JSON 重试强化、单时期覆写警示等可选增强）
- 临时文件已清理（14 个根目录 _*.txt + 3 个 step5 验证产物；全量运行日志归档 logs/run_full_20260805.txt）
- 全量结果：1245 归属 / 31650（3.9%），12 路径满 100，3 路径阈值生效；发现主路径含神经营销分支（2010 起）与 CN 专利时段（2020 起）——数据真实反映
项目完成。

语义相似度匹配项目（2026-08-06 完成）：
- 方法：bge-small-zh-v1.5 余弦预筛（每路径专利 top-300 ∪ cos>0.72，66094 对）→ deepseek-v4-flash 批量精判（10 对/prompt，8 并发，thinking disabled）
- 结果：LLM 打分 66119 对，阈值 0.55 归属 1787 条（比规则匹配 1245 多 44%）；敏感性 0.4→2550 / 0.7→818
- 交叉验证：两方法都并入 173 条（高置信）
- 排坑记录：config 同名→sem_config；cos>0.4 预筛爆炸 452 万对→实测分布收紧；推理 token 耗尽→max_tokens 4000+thinking disabled(3.6x)；半行 JSON→load_scores 容错；跨进程重复→pkill+sleep；sys.path insert(0) 遮蔽→append；静默丢弃→警告
- 输出：语义相似度匹配/outputs/（semantic_assignments.csv、semantic_scores.jsonl、semantic_report.md、prefilter_candidates.csv、embedding_cache/）

## 2026-08-17 目录重构（spec: docs/superpowers/specs/2026-08-17-项目目录重构-design.md, plan: docs/superpowers/plans/2026-08-17-项目目录重构.md）
Task 1: complete (5 文档抢救到 docs/，review clean)
Task 2: complete (4 文件重命名+5 脚本同步，13 处功能性引用清零，import 验证通过，review clean)
  minor: 6 处 docstring/注释旧名残留（data_loader.py:46, export_path_extension.py:24, merge_datasets.py:5/35, 01_prepare_tasks.py:5/74）→ Task 7 清理
Task 3: complete (6 窗口文件+04/05 改名，生成者+消费者全部同步，grep 0 残留，pytest 7 passed，review clean)
  minor: 主路径识别报告.md 旧名指引（重跑自动更新）、路径概括与拓展_README.md 旧名 → Task 7 清理
Task 4: complete (3 zip 归档成功，unzip -t 全过；subagent 后台进程被终止导致 zip 截断，主会话同步重生成修复)
  minor: 报告大小旧数据已修正；paper-project 实际 341MB
Task 5: complete (4 zip unzip -t 全过，匹配.zip 移入 _archived/，3 冗余 zip 已删，MD5 两组一致，review clean)
Task 6: complete (用户确认后删除 4 旧目录，释放约 2GB，顶层仅剩 8 流水线目录+_archived/+docs/+3 中文数据文件)
Task 7: complete (README.md + ARCHIVE_README.md 已写，12+1 处 docstring 旧名清理，review clean)
全部任务完成。最终结构：8 流水线目录 + _archived/(4 zip) + docs/(5 抢救文档+superpowers) + 3 中文数据文件 + 替代风险计算(1).doc
终审（2026-08-17, opus）：READY 可交付。全部维度独立验证通过；Minor 3 项（.pytest_cache 已删、data_overview 旧名文本留档、注释概念词 cosmetic）
重构项目完成。最终磁盘占用 2.8G（原 ~3.7G+）

## 2026-08-17 替代风险计算（spec: docs/superpowers/specs/2026-08-17-替代风险计算-design.md, plan: docs/superpowers/plans/2026-08-17-替代风险计算.md）
（无 git 工作流，同旧项目惯例；brief/report 位于 .superpowers/sdd/alt-risk/）
Task 1: complete (review clean; minor: growth_slope 负输入→NaN 为计划既定可接受、len==0 分支未测、__pycache__/.pytest_cache 项目末尾统一清理)
Task 2: complete (review clean; 数据格式修正 属于=名称(代码) 与测试 NaN 兼容已入 brief 修正记录; minor: in_degree 浮点型[Task4 已按 float 读]、正则理论缝隙、无 try/except、CSV 列序 in_degree 在尾[按列名消费不受影响])
Task 3: complete (review clean; minor: happy-path A/V 对称场景无法捕获方向性错误[终审判定是否补非对称测试]、报告"25 指标"实为 24 键+risk_rank、docstring 缺参数说明、零权重 ZeroDivision 不可达)
用户拍板（2026-08-17）：软阈值+全量排名——S 全量计算，文档阈值 F≥0.6/C≥0.5/H≥0.3 改作"未达标"参考标记（真实数据下 147 主题全部达不到硬阈值，排名会为空）。波及 Task3（indicators 语义）/Task4（eligibility= R.notna()）/Task5（报告口径）。
Task 3 修订（软阈值）: complete (re-review Approved; minor: R 守卫中 S is not None 已冗余、brief 接口行文字未同步[修正记录优先])
Task 4: complete (review clean; 46/147 参与排名、达标 0、阈值 44.0 实测复算命中; minor: '未达标' 魔法字符串跨模块耦合[终审留意]、read_csv 未显式 encoding、>=1 断言为数据依赖)
Task 5: complete (review clean; 24/24 全绿、全流程复跑 147主题/46排名/0达标/44.0; minor: 报告"未参与排名"措辞与46参与并存易误导、修正②改动无测试保护、int()/median 无 NaN 防护、事实硬编码——全部记录交终审判定)
终审（2026-08-17, opus）: WITH FIXES → 修复代理一轮完成全部 2 Critical+5 Important+建议修项（报告措辞、解读小节、A 方向性测试、阈值来源测试、THRESHOLD_FLAG 统一、entity_relations 删除、缓存清理），28/28 全绿。控制器独立复跑验证 28 passed + 报告逐行核对 + 缓存清零；另修一处"研究数据集→引文网络内部节点"措辞并重生成报告。
项目完成。交付：替代风险计算/{config.json, scripts×4, tests×4, outputs/{替代风险指标总表.csv(147×25), 替代风险报告.md, intermediate/}}；147 主题/46 参与排名/0 达标(软阈值)/Top3=G06F17,A61N5,G06Q30/阈值44.0。

## 2026-08-18 嵌入相似度升级（spec: docs/superpowers/specs/2026-08-18-嵌入相似度升级-design.md, plan: docs/superpowers/plans/2026-08-18-嵌入相似度升级.md）
用户拍板：F/C/H 升级为 bge-small-zh-v1.5 嵌入对称最佳匹配均值（H=1−P_sim），Jaccard 保留对照列 F_J/C_J/H_J，总表 25→28 列，文档阈值仍作达标参考标记（软阈值）。背景：Jaccard 口径 147 主题全部未达标（F>0 仅 8.2%，诊断=实体碎片化+字符串零容错+阈值尺度错配）。
Task 6: complete (review clean; 嵌入效果: F_sim>0=48/48 理论上限、A61B5 F 0.039→0.762、16 主题 F>0.6; minor: 缓存无失效机制[建议加注释提示]交终审)
Task 7: complete (run_all/generate_report 集成嵌入口径，总表 25→28 列加 F_J/C_J/H_J 对照；全流程重跑 147 主题/46 参与排名/达标 10/阈值 44.0，Top3=G06Q30,A61N2,H04N21；35/35 pytest 全绿。修正记录（协调裁定）：①brief 原断言 F_AB 均值>0.3 与数据不符（实测 0.189，99/147 零匹配），改为 F_AB>F_J 方向断言+非零均值>0.5（实测 0.58）；②test_report.py 合成 fixture 补 F_J/C_J/H_J=0.3/0.2/0.4，属 render_report 访问 F_J 的机械连带修复。缓存已清，entity_vecs.npy/entity_names.csv/entity_sim_by_topic.csv 保留)
Task 7: complete (review clean; 28 列全链路可证 F_AB==F_sim 0 偏差、达标 10/46 排名/44.0 四源互证; minor: Top-20 标记列 5 行显示 nan、sim_map KeyError 无友好提示、report 措辞矛盾[文档级]交终审)
终审修复（2026-08-18）：9 项终审发现全部修复——I1 达标主题清单（10 行含 G06N3）、I2 S=1/3 缺失数据地板披露（46 排名中 26 个位于地板，动态计算）、I3 复现指令补 embed_similarity + 缓存失效注释、M1 Top-20 nan 守卫、M2 对称最佳匹配公式、M3 局限#4 92% 动态化（135/147）、M4 报告头补 2026-08-18 spec、M5 TestEmbedAssembly 交叉验证固化。全流程重跑 147/46 排名/达标 10/阈值 44.0，36/36 pytest 全绿无警告；缓存已清理（entity_vecs.npy/entity_names.csv/entity_sim_by_topic.csv 保留）。
终审（2026-08-18, opus）: WITH FIXES → 修复代理一轮完成 3 Important + 5 Minor（达标清单含 G06N3、S=1/3 地板披露 26/46、复现命令补 embed_similarity+缓存注释、nan 守卫、公式入方法段、92% 动态化、spec 引用、H=1−P_sim 测试固化）。控制器独立复跑 36/36 + 报告逐行核对 + 缓存清零。
嵌入升级项目完成。最终：147 主题/46 排名/达标 10（Jaccard 口径 0）/阈值 44.0；Top-3=G06Q30 0.4567, A61N2 0.4299, H04N21 0.4285；F_AB 可定义子集均值 0.58 vs F_J 0.007。

## 2026-08-18 路径路线版（用户拍板"做法一"：3 条主路径当技术路线，替代 IPC 分组）
（spec 即 plan: docs/superpowers/plans/2026-08-18-路径路线版替代风险.md）
数据事实：每窗口原生主路径 15-30 条已概括为 3 条跨窗口路线（period_*_summary.json paths=3，差异化特征可作路线名）；05 数据集 15 个 (period,path) 组合 CN 全部≥3；路线版 T_AB 分母沿用原窗口全节点口径。LLM 相关性过滤（等 key）作为后续叠加层。
Task 8: complete (review clean; P1 966/CN212、P2 866/CN232、P3 1031/CN261，归属重算全量对账; 补回退链+平局测试后 40 passed; minor: 列序 in_degree 位置差异、SUMMARY_DIR 隐式全局交终审)
Task 9: complete (input_suffix 基础设施：三脚本+config.json 读 `input_suffix`，全流程带后缀；路线版 3 主题/3 参与排名/达标 0/阈值 44.0，P2 排名1 R=0.4344、P1 排名2 R=0.4308、P3 排名3 R=0.4133；原始版回归 147/46/10/44.0 无回归；41/41 pytest 全绿（40+TestPathsRun 1）；缓存已清。minor: 报告局限#5"参与排名的 46 个主题"与解读节 G06F17/G06Q30 段为 IPC 版事实硬编码/措辞，render_report 未动，路线版 3 主题下偏旧，交终审)
Task 9: complete (review clean; 路线版结果 P2 0.4344 > P1 0.4308 > P3 0.4133、达标 0[H=1−P_sim<0.3 全未达标——同路线原理趋同是构造性结果]、装配三式全行成立、原始版回归 147/46/10; Important: 报告_paths.md 5 处 IPC 版陈旧措辞交终审)
终审修复（2026-08-18）：5 处陈旧措辞全部修复——render_report 加 caliber 参数（默认 'ipc' 保持原文；main() 按 input_suffix 推断 'paths'）：①配对口径路线句 ②解读节 G06F17 段仅 ipc 渲染，paths 版替换 3 个新 bullets（达标 0 结构性解释[P_sim>0.7→H<0.3]、S 0.60~0.61 相近 M 驱动排序[P2=0.485]、3 行粒度 caveat）③局限#5 数字动态化 n_zero_fcp/ranked_n（IPC 99/46 不变，paths 自动 0/3；floor_n 原已动态不动）④局限#6 去"40 个无有效主IPC"句、13 条无摘要说明两版保留 ⑤Top 标题加"（本版全部 3 条路线）"。Minor：build_patent_routes 加 summary_dir 参数（默认 SUMMARY_DIR，测试注入解耦）；embed_similarity/run_all docstring 补 input_suffix 机制说明；新增 TestPathsEmbedAssembly 装配测试（F_AB==F_sim、H_AB==1−P_sim 对 3 行成立）。验证：IPC 版报告与修复前 diff 逐字节一致（零回归）；paths 版 5 项核对通过（方法段路线句/3 新 bullets 无 G06F17/局限 0/3/13 条保留/Top 标题）；42/42 pytest 全绿无警告；缓存已清理（中间表缓存保留）。
终审（2026-08-18, opus）: WITH FIXES → 修复代理一轮完成（caliber 参数化报告：路线口径句/解读 bullets×3/动态数字/13条保留；IPC 版报告逐字节无回归；summary_dir 注入；paths 装配测试）。控制器独立复跑 42/42 + 报告逐行核对 + 缓存清零。
路径路线版完成。最终：P2 0.4344 > P1 0.4308 > P3 0.4133（M 主导排名，S≈0.60-0.61）；达标 0 为路线口径结构性结果（同路线原理趋同 P_sim>0.7）。

## 2026-08-18 跨路线配对替代（用户拍板"修改逻辑让结论可用"；plan: docs/superpowers/plans/2026-08-18-跨路线配对替代.md）
动机：路线版同路线配对口下"原理差异"H=1−P_sim 恒<0.3→达标恒 0（结构性失效）。改为 6 个跨路线有序配对（国外Y 替代 国内X，X≠Y）；K/A/V 按 B 路线(Y)全集计算（doc 口径，indicators 加 exposure 参数）；同路线 3 行旧结果归档过程记录。
Task 10: complete (review clean; exposure 双向等价+配对表 5726=2×705+2×2158 逐对核验; minor: is_cn get 缺省、iloc[0] 行序隐式锁定交终审)
Task 11: complete (run_all 配对模式 suffix='_paths' 时 exposure=Y 路线全集 + 报告配对版；6 配对排名：P2→P1 0.4346 > P1→P2 0.4258 > P3→P1 0.4233 > P2→P3 0.4227 > P3→P2 0.4187 > P1→P3 0.4135；达标 1/6=P1→P2（H=0.3014 恰过 0.3 阈值）；原始版回归 147/46/10/44.0 不变；46/46 pytest 全绿；缓存已清（中间表保留）。修正记录：brief 解读 bullet"未达标者主要因功能/场景相似度不足"与实测不符（6 对 F/C 全部达阈值、未达标全因原理差异 P_sim>0.7→H<0.3），按 brief"以实际为准"改为数据驱动表述并附代码注释)
Task 11: complete (review clean; 6 对排名 P2→P1 0.435 最高、达标 1/6[P1→P2 H=0.3014 恰过]、装配/K/A/V 全独立重算吻合、原始版回归零变化; minor: 摘要 S 0.60~0.60 舍入巧合、ROUTE_SHORT 冗余、静态文案、exposure 无测试钉住交终审)
终审修复（2026-08-18）：9 项终审发现全部修复——I1 达标临界敏感性披露（解读节"临界提示"bullet H 范围动态注入 0.289~0.301 + 局限第 8 条"达标判定随数据刷新可能翻转"；路径版局限 9 条，IPC 版保持 8 条零回归）；I2 一句话结论改写（披露"风险最高对 P2→P1 本身不构成替代候选，唯一达标的是 P1→P2 R=0.426/H=0.301 恰过 0.3 线"，动态取 qualified 首行）；M1 摘要 S 三位小数（S≈0.596~0.603）+ "排序主要由增长与主路径地位决定"措辞；M2 解读归因动态统计（H 未达阈 5 对、F/C 各 0 对未达阈值）；M3 删除 ROUTE_SHORT 常量；M4 TestPathsRun 追加 exposure 等价断言（P1→P2/P3→P2 的 K_B 相等）；M5 indicators exposure 分支 p.get('is_cn')→p['is_cn']（缺键 KeyError 优于静默按国外）+ test_path_routes 行序显式化（sub['pub']=='CNX'）；M6 run_all exposure_map 下标访问（KeyError 优于静默回落）；M7 局限#3 K_B 句尾加"（路线版按 B 路线全集计算）"（仅路线版渲染）。验证：run_all 原版 147/46/10/44.0 回归正常；IPC 版报告重生成逐字节零回归；47/47 pytest 全绿无警告；报告核对 5 项全过（注意分句/临界提示/动态归因/局限第 8 条/S 三位小数）；缓存已清（中间表缓存保留）。
终审（2026-08-18, opus）: WITH FIXES → 修复代理一轮完成（I-1 临界披露[H 0.289~0.301 窄带/局限第8条]、I-2 一句话结论补"注意"分句、M-1~M-7 全部；IPC 版逐字节零回归）。控制器独立复跑 47/47 + 报告逐行核对 + 缓存清零。
跨路线配对完成。最终结论：6 对中风险最高=国外P1(推送+测量)替代国内P2(数据平台) R=0.435（不构成候选）；唯一达标=国外P2替代国内P1 R=0.426（H=0.301 临界）；排序由 M 主导（S 0.596~0.603 近乎相同）；国内缺位警报贯穿（K 95~96%、A 1.1~2.9%）。

## 2026-08-18 BCI 相关性过滤（用户已 setx DEEPSEEK_API_KEY；plan: docs/superpowers/plans/2026-08-18-BCI相关性过滤重算.md 任务 8/9 适配）
口径：LLM 逐条判定"是否属脑机接口领域"（含边缘应用），排除位置广告等外溢；主路径分母=过滤后域。注意：子进程读不到旧环境变量，filter_relevance.py 从注册表用户环境注入 key（不落盘不进命令文本）。
Task 12: complete (review clean; 2969/2969 成功 0 失败、相关 2582/无关 387、核心 1258+边缘 1324、过滤后 2493/CN660/主题 147→133、主路径 358→231[127=74 无文本+23 判无关+重复窗口行]、判定质量抽样无假阳假阴模式; minor: 87 个无完整中文本（74 双空未判定 + 13 单字段占位判定）无清单文件[交终审补]、报告两处统计措辞小误差)
Task 13: complete (过滤版全流程重算；path_routes/run_all/generate_report 加 suffix 支持 + 报告研究域界定节；过滤版 IPC：133 主题/38 参与排名/达标 9/阈值 44.0，Top-3=G06Q30 0.4625, A61N2 0.4299, G06F17 0.4287；过滤版路径配对：6 对全参与排名，P2→P1 0.4420 > P1→P2 0.4283(达标,唯一) > P3→P1 0.4281 > P2→P3 0.4262 > P3→P2 0.4204 > P1→P3 0.4154，H 窄带 0.288~0.303；原始版回归 147/46/10/44.0 零变化，两份未过滤报告逐字节零回归；54/54 pytest 全绿；缓存已清（中间表+relevance 保留）。修正记录①：brief 测试断言 len==147 与实测不符（过滤后主题 133，stats topics_kept=133），按数据驱动改为 133（Task 7 同类先例）；修正记录②：路径版报告静态句"0.289~0.301/超阈 0.001"对过滤版失真（实测 0.288~0.303/0.003），改为动态注入，未过滤路径版报告逐字节零回归验证)
Task 13: complete (review clean; 过滤版 IPC 133 主题/38 排名/9 达标/Top3=G06Q30 0.4625,A61N2 0.4299,G06F17 0.4287；过滤版配对 P2→P1 0.442 最高、达标 1/6；两版未过滤零回归、54/54; minor: 过滤版路径报告对照句/局限#9 数字陈旧、过滤版测试仅 smoke 交终审)
终审修复（2026-08-18）：BCI 相关性过滤终审全部完成——I1 报告局限尾注专利数按 suffix 参数化（过滤版 _filtered/_paths_filtered 输出 2493，未过滤版 2863 逐字节零回归）；I2 研究域界定节补三行披露（判定规模 LLM 2969 条[相关 2582/无关 387，约 61% 仅凭摘要]、74 个无文本主路径节点默认排除+清单 intermediate/no_text_mainpath_nodes.csv、14 主题整体退出+8 主题退出排名）；I3 G06Q30 过滤后居首系脑电广告/神经营销边缘应用（纳入口径，非管道错误）；M1 路径版对照句参数化（过滤版 133 主题）；M2 路径过滤版运行参数显式标注"基于 BCI 相关性过滤后的数据（2493 条）"；M3 新增测试（test_domain_stats_section/TestExpSuffix/TestNoTextListSmoke+nan 占位+stats 字段）；M4 无文本清单 74 行；M5 单字段 NaN 占位 nan→（无）（results.jsonl 未重判，resume 按 id 跳过 2969 条）；M6 台账措辞修正（摘要计数按口径"摘要非 nan 且 >50 字"重数为 2949/2969、Task 12 行改"87 个无完整中文本（74 双空未判定 + 13 单字段占位判定）"）。stats CSV 新增 judged/relevant/irrelevant/mainpath_no_text 字段。验证：四版报告重生成，未过滤两份逐字节零回归（md5 00bc4e88…/270da638…）；59/59 pytest 全绿无警告；缓存已清（中间表+relevance 保留）。
终审（2026-08-18, opus）: WITH FIXES → 修复代理一轮完成（I-1 2863→2493 参数化、I-2 研究域界定三行披露、I-3 G06Q30 边缘应用句、M-1~M-6 全部；未过滤两版 md5 零回归）。控制器独立复跑 59/59 + 过滤版报告逐行核对 + 缓存清零。
相关性过滤完成。四版本齐备：未过滤 IPC(147/46/10) + 未过滤配对(6对) + 过滤 IPC(133/38/9，Top3=G06Q30 0.4625[过滤后达标]/A61N2/G06F17) + 过滤配对(P2→P1 0.442 最高/达标 1/6)。判定 2969 条 100% 成功、相关 2582/无关 387、排除 370 条带理由清单。
