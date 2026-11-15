# 团队 AI 工作交接助手 Demo

一个使用 Python 3.12、FastAPI、SQLAlchemy、SQLite、React 和 TypeScript 构建的本地完整 Demo。它演示材料版本、五项交接草稿、人工确认、版本绑定、请求补充/拒绝，以及由接手者主动触发的原子责任转移。

AI 整理使用本地确定性 DemoGenerator，不连接外部模型，不需要真实密钥。

当前版本还包含稳定事件账本、确认引用 SHA-256 指纹与 stale 防护，以及完全独立的 C0/C1/C2 离线评估工具。

## 环境

- Python 3.12
- Node.js 20 或更高
- npm 10 或更高

## 安装

在项目根目录执行：

    python -m pip install -e "backend[dev]"
    python -m pip install -e evaluation
    cd frontend
    npm install
    cd ..

## 开发模式

    python scripts/dev.py

- Web：http://127.0.0.1:5173
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/healthz

## 单端口 Demo

    python scripts/demo.py

脚本会构建前端、执行 Alembic 迁移并在 http://127.0.0.1:8000 提供完整应用。

## 推荐演示路径

1. 首页选择“林晓（A）”，打开校园活动报名系统及示例任务。
2. 展开 S-01 查看带行号的开发记录。
3. 进入“整理交接”，选择 S-01，完整预览后生成五项草稿。
4. 人工检查并确认，返回任务后发给“陈默（B）”。
5. 顶栏切换到 B，打开请求，阅读来源并主动接收。
6. 回到任务页查看负责人已变为 B，而工作进度仍保持“进行中”。
7. 打开历史，追溯确认版本、请求和接收事件。

生成页的“模拟失败”可以验证人工后备。接手者页面可填写原因并选择“请求补充”或“拒绝接收”。在待接收期间修改任务目标或被引用材料版本，会使旧请求过期。

顶部“重置演示数据”可恢复 A/B/C 三名成员和初始场景。演示身份请求头仅用于本地 Demo，不是生产认证。

## 自动化检查

后端：

    cd backend
    python -m ruff format --check .
    python -m ruff check .
    python -m mypy app
    python -m pytest --cov=app --cov-report=term-missing

数据库升级：

    cd backend
    python -m alembic upgrade head

`0002_event_contract_and_evidence` 会为旧事件补齐稳定 `event_ref`、任务内 `seq`、执行状态和来源，并为确认引用补齐内容与片段哈希。

前端：

    cd frontend
    npm run lint
    npm run typecheck
    npm run test
    npm run build

离线 C0/C1/C2 评估：

    cd evaluation
    python -m handoff_eval prepare --scenario all --out out
    python -m handoff_eval smoke --scenario all --out out
    python -m handoff_eval summarize --runs out --out report

评估工具只生成隔离实验包、导入统一结果并确定性评分。默认命令不会启动外部 Agent、执行 Shell、连接 Demo 数据库、访问网络或调用模型。

## 事件与证据接口

- `GET /api/v1/tasks/{task_id}/events?after_seq=0`：按任务内序号读取事件。
- `GET /api/v1/events/{event_ref}`：使用稳定引用回到单个事件。
- `GET /api/v1/confirmed-handoffs/{id}/evidence-validation`：返回 `current`、`stale`、`missing`、`mismatch` 或 `unauthorized`。

只有证据整体为 `current` 时才能接收。被引用材料出现新版本会得到 `STALE_EVIDENCE`；固定正文、行号、哈希或任务归属异常会得到 `INVALID_EVIDENCE`。旧确认快照不会被改写。

## 数据与安全边界

- 本地数据库默认位于 data/handoff.db，并被 git 忽略。
- 只接受 UTF-8 的 txt/md 文件，单文件上限 1 MiB。
- 一次整理最多使用 20,000 字符正文，未选材料与链接正文不会进入生成快照。
- 导入材料和生成内容只作为纯文本展示，不执行脚本、命令或其中的提示。
- 项目隔离、发起和接收权限均由服务端复核。
