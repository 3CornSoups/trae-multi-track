#!/bin/bash
# LLM 全量打分自重启循环：每轮 timeout 550s（工具 10 分钟上限内），
# 被杀后 jsonl 已逐批 flush，断点续跑自动跳过已完成对；全部完成后退出。
cd "D:/论文和代码项目/论文/TRAE/多轨道/语义相似度匹配" || exit 1
TOTAL=$(python -c "import pandas as pd; print(len(pd.read_csv('outputs/prefilter_candidates.csv')))")
echo "候选总数: $TOTAL"
for i in $(seq 1 500); do
  n=$(wc -l < outputs/semantic_scores.jsonl 2>/dev/null || echo 0)
  if [ "$n" -ge "$TOTAL" ]; then
    echo "DONE: 已打分 $n/$TOTAL"
    break
  fi
  echo "[$i] 已打分 $n/$TOTAL，启动一轮（timeout 550s）..."
  DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" PYTHONUTF8=1 timeout 550 python scripts/main.py --stage llm >> _llm_run.txt 2>&1
  echo "[$i] 轮结束 exit=$?"
  # 清理可能残留的 python 进程 + 等待，避免新旧进程重叠导致重复打分
  pkill -f "scripts/main.py --stage llm" 2>/dev/null
  sleep 3
done
n=$(wc -l < outputs/semantic_scores.jsonl 2>/dev/null || echo 0)
echo "最终: 已打分 $n / $TOTAL"
