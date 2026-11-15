# Handoff Evaluation

这是一个独立、离线、确定性的 C0/C1/C2 评估包。它不导入 FastAPI 应用、不读取 Demo 数据库、不启动外部 Agent，也不调用网络或模型。

在 `evaluation/` 安装后执行：

    python -m handoff_eval prepare --scenario all --out out
    python -m handoff_eval smoke --scenario all --out out
    python -m handoff_eval summarize --runs out --out report

- C0：任务说明与公开基线材料。
- C1：C0 加完整原始事件账本。
- C2：C0 加确认交接和引用索引。

真实 Agent 或人工实验只需按 fixture 展示的 Schema 写出 `result.json`，再用 `grade` 导入。隐藏评分规则不会复制到实验包。
