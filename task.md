# 团队 AI 工作交接助手 Demo — Python 实施任务

## 文件清单

| 操作 | 文件或目录 | 职责 |
|---|---|---|
| 新建 | README.md | 安装、启动、演示身份和验收说明 |
| 新建 | scripts/dev.py | 同时启动 FastAPI 与 Vite |
| 新建 | scripts/demo.py | 迁移、初始化、构建并启动单端口 Demo |
| 新建 | backend/pyproject.toml | Python 依赖、Ruff、Mypy、pytest 配置 |
| 新建 | backend/alembic.ini | Alembic 配置 |
| 新建 | backend/alembic/env.py | 使用应用数据库元数据执行迁移 |
| 新建 | backend/alembic/versions/0001_initial.py | 完整初始表、约束和索引 |
| 新建 | backend/app/config.py | 环境配置和路径 |
| 新建 | backend/app/database.py | Engine、Session 工厂与 SQLite pragma |
| 新建 | backend/app/models.py | SQLAlchemy 实体与关系 |
| 新建 | backend/app/domain/* | 枚举、值对象、错误、状态规则 |
| 新建 | backend/app/schemas/* | Pydantic 请求与响应模型 |
| 新建 | backend/app/repositories/* | 查询、写入、条件更新和分页 |
| 新建 | backend/app/services/* | 项目、任务、材料、草稿、交接、Demo 服务 |
| 新建 | backend/app/generator/* | Generator Protocol 与 DemoGenerator |
| 新建 | backend/app/api/* | FastAPI 依赖、路由、错误映射 |
| 新建 | backend/app/demo_data.py | A/B/C 身份及可重置场景 |
| 新建 | backend/app/main.py | 应用工厂、路由、静态文件和 SPA 回退 |
| 新建 | backend/tests/* | 单元、数据库、API、并发和安全测试 |
| 新建 | frontend/package.json | React 工具链与测试依赖 |
| 新建 | frontend/src/api/* | 类型化 API 客户端 |
| 新建 | frontend/src/app/* | 路由、SessionProvider、AppShell |
| 新建 | frontend/src/features/* | 项目、任务、材料、生成、草稿、交接、历史 |
| 新建 | frontend/src/components/* | 通用状态、错误、加载和空状态组件 |
| 新建 | frontend/src/styles/* | OKLCH 令牌、布局、响应式与可访问性 |
| 新建 | frontend/src/test/* | Vitest/Testing Library 配置与组件测试 |
| 新建 | frontend/e2e/* | Playwright 核心流程和 axe 测试 |
| 修改 | .gitignore | 忽略虚拟环境、缓存、构建物和本地数据库 |

## T1：建立 Python 项目骨架

**文件：** backend/pyproject.toml、backend/app/__init__.py、backend/tests/__init__.py、.gitignore
**依赖：** 无

**步骤：**
1. 声明 Python 3.12 与 FastAPI、Uvicorn、SQLAlchemy、Alembic、Pydantic、multipart 依赖。
2. 声明 pytest、coverage、httpx、Ruff 和 Mypy 开发依赖。
3. 配置 Ruff、Mypy、pytest、coverage 和源码导入路径。
4. 补全 Python、Node、SQLite 和构建物忽略项。

**验证：** 在 backend 执行 Python -m pip install -e ".[dev]"，随后运行 Python -m pytest --collect-only，期望无配置错误。

## T2：建立配置和数据库连接

**文件：** backend/app/config.py、backend/app/database.py
**依赖：** T1

**步骤：**
1. 定义数据库 URL、Demo 模式、生成超时、上传和字符限制。
2. 建立 SQLAlchemy Engine 与 sessionmaker。
3. 在 SQLite 连接事件中启用外键、WAL 与 busy_timeout。
4. 提供请求级 Session 依赖和测试可替换的应用状态。

**验证：** 运行数据库连接单元测试，期望三个 pragma 均生效且两个 Session 对象互不相同。

## T3：定义领域类型和错误

**文件：** backend/app/domain/enums.py、values.py、errors.py、rules.py
**依赖：** T1

**步骤：**
1. 定义工作进度、审核、请求、材料、草稿来源和生成状态枚举。
2. 定义五项正文和 Citation 不可变值对象。
3. 定义带 code、message、details 的领域错误族。
4. 实现五项完整性、行号、链接和状态转换纯校验。

**验证：** 运行 domain 测试，期望有效转换通过、非法状态和非法引用返回确定错误码。

## T4：定义 SQLAlchemy 实体

**文件：** backend/app/models.py
**依赖：** T2、T3

**步骤：**
1. 定义 Member、Project、ProjectMembership、Task。
2. 定义 Material、MaterialVersion、GenerationPreview、GenerationPreviewMaterial、GenerationRun。
3. 定义 HandoffDraft、DraftCitation、ConfirmedHandoff、ConfirmedCitation。
4. 定义 HandoffRequest、HandoffReceipt、TaskEvent。
5. 配置 UUID、UTC 时间、revision、关系、级联和唯一约束。

**验证：** 运行模型元数据测试，期望全部表、外键和命名约束可被枚举。

## T5：建立 Alembic 初始迁移

**文件：** backend/alembic.ini、backend/alembic/env.py、backend/alembic/versions/0001_initial.py
**依赖：** T4

**步骤：**
1. 让 Alembic 读取应用配置和 Base.metadata。
2. 创建全部表、普通索引和唯一约束。
3. 创建每任务单 pending 请求的部分唯一索引。
4. 确保 downgrade 按依赖逆序删除。

**验证：** 对空临时 SQLite 执行 upgrade head、downgrade base、再次 upgrade head，期望全部成功。

## T6：定义 Pydantic 边界模型

**文件：** backend/app/schemas/common.py、projects.py、tasks.py、materials.py、drafts.py、handoffs.py、demo.py
**依赖：** T3

**步骤：**
1. 所有输入模型设置 extra=forbid 和明确长度限制。
2. 定义项目、成员、任务和三状态响应。
3. 定义材料、预览、五项草稿、引用和确认版本响应。
4. 定义请求动作、历史事件和统一错误响应。

**验证：** 运行 schema 测试，期望合法 JSON 往返一致，多余字段和越界值被拒绝。

## T7：实现 Repository 基础与项目查询

**文件：** backend/app/repositories/base.py、projects.py、tasks.py
**依赖：** T4、T5

**步骤：**
1. 提供 UUID/UTC 工具与数据库异常到领域错误的映射。
2. 实现成员资格、项目可见性、负责人权限查询。
3. 实现任务创建、读取、列表和 revision 条件更新。
4. 确保普通任务更新不能直接更改负责人。

**验证：** 运行 repository 集成测试，期望跨项目查询为空、旧 revision 更新影响零行。

## T8：实现材料与草稿 Repository

**文件：** backend/app/repositories/materials.py、drafts.py
**依赖：** T7

**步骤：**
1. 实现材料及不可变版本创建、读取和版本递增。
2. 实现生成预览、获准版本和运行记录。
3. 实现草稿、引用替换、revision 更新。
4. 实现确认版本与确认引用的不可变快照。

**验证：** 运行集成测试，期望历史版本不被覆盖、草稿冲突返回零行、确认快照不随草稿修改。

## T9：实现请求与历史 Repository

**文件：** backend/app/repositories/handoffs.py、events.py
**依赖：** T7

**步骤：**
1. 实现请求创建、读取和 revision 条件状态更新。
2. 实现 Receipt 唯一写入和负责人条件转移。
3. 实现 pending 失效查询。
4. 实现事件只追加写入与时间线排序。

**验证：** 运行集成测试，期望第二个 pending 请求和第二条 Receipt 均被数据库拒绝。

## T10：实现项目与任务服务

**文件：** backend/app/services/projects.py、tasks.py、authz.py
**依赖：** T6、T7、T9

**步骤：**
1. 实现项目创建、成员列表和负责人维护成员。
2. 实现任务创建、工作区读取和普通字段更新。
3. 每个操作重新校验有效成员资格。
4. 目标或验收标准改变时调用统一失效逻辑并记录事件。

**验证：** 运行服务测试，期望撤权成员被拒绝、进度更新不改负责人、重要变化使 pending 请求过期。

## T11：实现材料服务

**文件：** backend/app/services/materials.py、backend/app/utils/text.py
**依赖：** T8、T10

**步骤：**
1. 处理粘贴文本、UTF-8 文件和链接输入。
2. 统一 LF，拒绝超过 1 MiB、非法 UTF-8 和非 txt/md 文件。
3. 链接只保存 URL 和说明，不抓取或伪造正文。
4. 被确认版本引用的材料新增版本时触发 needs_review 和请求失效。

**验证：** 运行材料服务测试，期望大小、编码和扩展名边界正确，未引用的新材料不触发失效。

## T12：实现本地生成器

**文件：** backend/app/generator/protocol.py、demo.py
**依赖：** T3

**步骤：**
1. 定义 GenerateInput、GenerateOutput、Usage 和 Generator Protocol。
2. 根据关键词和材料顺序确定性生成五部分。
3. 生成一基行号引用，验证区无证据时明确“未验证”。
4. 实现 error 与 timeout 模式，不连接网络。

**验证：** 运行生成器单元测试两次，期望相同输入产生相同结构和引用，错误模式返回受控异常。

## T13：实现预览、草稿与确认服务

**文件：** backend/app/services/drafts.py
**依赖：** T8、T10、T11、T12

**步骤：**
1. 校验所选材料版本属于任务且总字符不超过 20,000。
2. 保存确切预览快照并限制创建者和有效期。
3. 生成或创建人工草稿，保存失败运行且保留人工入口。
4. 按 revision 更新草稿和引用。
5. 确认时保存任务背景、五项正文和引用快照，并使旧 pending 请求失效。

**验证：** 运行服务测试，期望未选择材料、过期预览、超限、旧 revision 和跨任务引用均被拒绝。

## T14：实现交接服务和原子接收

**文件：** backend/app/services/handoffs.py
**依赖：** T9、T10、T13

**步骤：**
1. 只允许当前负责人向有效项目成员发起确认版本请求。
2. 仅指定接手者可补充、拒绝或接收。
3. needs-info 和 reject 保存原因、递增 revision 并追加事件。
4. accept 在单一事务内完成条件状态更新、Receipt、负责人转移和事件。
5. 保持工作进度不变并把数据库竞争映射为 409。

**验证：** 运行并发集成测试，期望两个 Session 同时接收只有一个成功，失败路径无部分写入。

## T15：建立 Demo 数据

**文件：** backend/app/demo_data.py、backend/app/services/demo.py
**依赖：** T10、T11、T13、T14

**步骤：**
1. 定义稳定的 A、B、C 成员和示例项目。
2. 创建正常交接、待审核、材料更新和历史延续的示例任务。
3. reset 在事务内清理并重建所有合成数据。
4. reset 不读取用户目录或外部服务。

**验证：** 连续执行 reset 两次，期望数据计数和展示编号完全一致。

## T16：实现 FastAPI 依赖和错误边界

**文件：** backend/app/api/dependencies.py、errors.py
**依赖：** T2、T6、T10

**步骤：**
1. 解析 X-Demo-Member-ID，缺失或未知身份返回 401。
2. 注入请求级 Session 和服务实例。
3. 映射领域错误为统一 JSON 和对应 HTTP 状态。
4. 确保错误响应不暴露堆栈、SQL、绝对路径或输入材料正文。

**验证：** 运行 API 错误测试，期望 401/403/404/409/413/422/500/504 结构一致且无敏感内容。

## T17：实现项目、任务和材料 API

**文件：** backend/app/api/projects.py、tasks.py、materials.py
**依赖：** T11、T16

**步骤：**
1. 实现项目、成员、任务列表和修改路由。
2. 实现任务工作区与历史路由。
3. 实现文本粘贴、multipart 文件、链接和新版本路由。
4. 设置 response_model 和上传流大小限制。

**验证：** 运行 API 测试，期望正常 CRUD、跨项目 403、超限 413 和无效 UTF-8 422。

## T18：实现草稿、交接和 Demo API

**文件：** backend/app/api/drafts.py、handoffs.py、demo.py
**依赖：** T14、T15、T16

**步骤：**
1. 实现预览、生成、人工草稿、保存和确认路由。
2. 实现发起、查看、补充、拒绝和接收路由。
3. 实现身份列表与 reset。
4. 将 expected_revision 作为必填输入，不允许客户端省略并覆盖新状态。

**验证：** 运行 API 流程测试，期望 A 发起、B 接收后负责人为 B，工作进度保持原值。

## T19：建立应用入口和静态站点托管

**文件：** backend/app/main.py
**依赖：** T17、T18

**步骤：**
1. 建立 create_app 工厂并注册全部 /api/v1 路由。
2. 提供 /healthz。
3. 在构建产物存在时托管 assets 和 SPA 回退。
4. 保证 /api 未知路径返回 JSON 404，不回退 index.html。

**验证：** 启动 Uvicorn，期望 healthz、OpenAPI、API 404 和非 API SPA 路径行为正确。

## T20：建立前端工具链与设计令牌

**文件：** frontend/package.json、tsconfig.json、vite.config.ts、index.html、src/main.tsx、src/styles/*
**依赖：** T19

**步骤：**
1. 配置 React、TypeScript、Vite、Vitest、Testing Library 和 ESLint。
2. 配置开发代理 /api 到 FastAPI。
3. 实现 PRODUCT.md 中的 OKLCH 色彩、排版、间距、焦点和响应式基础。
4. 建立 reduced-motion 和通用无障碍样式。

**验证：** 运行 npm run typecheck、npm run lint、npm run build，期望全部通过。

## T21：实现类型化 API 客户端和应用壳

**文件：** frontend/src/api/*、src/app/*、src/components/feedback/*
**依赖：** T20

**步骤：**
1. 实现统一 fetch 客户端、身份请求头和结构化错误。
2. 建立 SessionProvider、路由和 AppShell。
3. 实现身份切换、Demo 标签、重置和错误恢复。
4. 实现 Notice、FieldError、Toast、Skeleton 和 EmptyState。

**验证：** 运行组件测试，期望身份切换改变请求头，401/409 显示可恢复提示。

## T22：实现项目、任务与材料界面

**文件：** frontend/src/features/projects/*、tasks/*、materials/*
**依赖：** T17、T21

**步骤：**
1. 实现首页、项目成员与任务列表。
2. 实现任务创建、编辑和 StatusTriplet。
3. 实现材料列表、文本/文件/链接添加及版本查看。
4. 窄屏把任务表转换为带字段名的纵向列表。

**验证：** 运行组件测试和 375px/1440px 截图检查，期望核心操作无水平滚动且状态文字完整。

## T23：实现生成与审核工作台

**文件：** frontend/src/features/generation/*、drafts/*
**依赖：** T18、T21、T22

**步骤：**
1. 实现材料勾选、完整输入预览与确认生成。
2. 实现失败/超时后的重试和人工草稿入口。
3. 实现 FiveSectionEditor、保存状态和 revision 冲突恢复。
4. 实现 EvidencePanel、引用定位和 VersionBanner。

**验证：** 运行组件测试，期望未确认预览不能生成、点击引用定位正确材料行、冲突不会覆盖新版本。

## T24：实现交接处理与历史界面

**文件：** frontend/src/features/handoffs/*、history/*
**依赖：** T18、T21、T23

**步骤：**
1. 实现接手者选择、版本核对和发起请求。
2. 实现接手者阅读、补充、拒绝和主动接收。
3. 非指定成员隐藏操作并对服务端拒绝给出解释。
4. 实现 TaskEvent 时间线和继续工作入口。

**验证：** 运行组件测试，期望 A/B/C 的可见操作符合权限，接受后页面同时更新负责人和请求状态。

## T25：建立浏览器端到端与无障碍测试

**文件：** frontend/playwright.config.ts、frontend/e2e/handoff.spec.ts、accessibility.spec.ts
**依赖：** T24

**步骤：**
1. 启动测试数据库、FastAPI 和 Vite。
2. 覆盖 A 创建/审核/发起、B 阅读/接收、B 继续记录。
3. 覆盖人工后备、补充、拒绝、旧页面、C 冒名和重要变化失效。
4. 对关键页面运行 axe 并验证键盘焦点。

**验证：** 运行 npm run test:e2e，期望全部场景和 axe 检查通过。

## T26：建立一键脚本与说明

**文件：** scripts/dev.py、scripts/demo.py、README.md
**依赖：** T19、T25

**步骤：**
1. dev.py 检查工具并同时管理 Uvicorn 与 Vite 子进程。
2. demo.py 执行迁移、重置、前端构建并启动单端口服务。
3. README 写明 Python 环境、安装、开发、Demo、测试、身份和限制。
4. 脚本在 Ctrl+C 时正常终止子进程，不删除用户数据。

**验证：** 在干净虚拟环境按 README 执行，期望浏览器可完成正常交接流程。

## T27：执行全量质量门禁与验收准备

**文件：** 全项目
**依赖：** T26

**步骤：**
1. 执行 Ruff、Mypy、pytest 和覆盖率。
2. 执行前端 lint、typecheck、组件测试和生产构建。
3. 执行 Playwright 和 axe。
4. 检查 git diff，不提交数据库、密钥、缓存或构建物。
5. 依据 checklist.md 逐项记录实际证据。

**验证：** 所有质量命令返回 0，核心 Python 业务分支覆盖率不低于 80%，演示流程可复现。

## 本轮 Harness 思想移植的增量文件

| 操作 | 文件或目录 | 职责 |
|---|---|---|
| 新建 | backend/app/domain/events.py | 事件状态分类、关联链校验和 lifecycle 归约 |
| 新建 | backend/app/domain/evidence.py | 文本规范化、内容/片段哈希和证据状态归约 |
| 新建 | backend/app/repositories/events.py | 任务内原子序号分配与事件只追加查询 |
| 新建 | backend/alembic/versions/0002_event_contract_and_evidence.py | 事件契约与确认引用哈希迁移、旧数据回填 |
| 新建 | backend/tests/event_contract/* | 事件状态、序号、关联和 lifecycle 的确定性测试 |
| 新建 | backend/tests/evidence/* | 引用哈希、stale、篡改和接收保护测试 |
| 新建 | backend/tests/fixtures/* | 事件序列和证据案例夹具 |
| 新建 | evaluation/* | 独立 C0/C1/C2 准备、评分、汇总和场景 |
| 修改 | backend/app/domain/enums.py | 增加 EventStatus、EventLifecycle、EventSource、EvidenceState |
| 修改 | backend/app/models.py | 扩展 Task、TaskEvent、MaterialVersion、ConfirmedCitation |
| 修改 | backend/app/schemas/api.py | 新事件、证据校验和历史响应边界 |
| 修改 | backend/app/services/core.py | 接入事件仓库、确认哈希与 accept 二次验证 |
| 修改 | backend/app/api/router.py | 增加事件详情和确认版本证据校验 API |
| 修改 | frontend/src/api.ts | 增加事件与证据状态类型和请求函数 |
| 修改 | frontend/src/App.tsx、frontend/src/styles.css | 展示事件引用、状态、关系和证据恢复提示 |
| 修改 | README.md、.gitignore | 增加迁移、离线评估命令和输出忽略项 |

## T28：定义事件契约与证据纯领域逻辑

**文件：** backend/app/domain/enums.py、backend/app/domain/events.py、backend/app/domain/evidence.py
**依赖：** T27

**步骤：**
1. 增加 EventStatus、EventLifecycle、EventSource 和 EvidenceState 枚举，值与 plan.md 完全一致。
2. 实现事件 start/finish 分类、父事件或 correlation 关联校验，以及按 seq 归约 subject lifecycle 的纯函数。
3. 规定 started 缺少完成证据时只能得到 unknown，失败、取消、超时和未执行不能归为成功。
4. 实现 NFC + LF + UTF-8 规范化、SHA-256 内容哈希、服务端行号提取和长度前缀片段指纹。
5. 让所有函数不访问数据库、网络、当前时间或随机源。

**验证：** 运行领域单元测试，期望全部状态、异常链、Unicode/换行差异和相同输入重复哈希得到确定结果。

## T29：扩展模型和 API Schema

**文件：** backend/app/models.py、backend/app/schemas/api.py
**依赖：** T28

**步骤：**
1. Task 增加 event_sequence；TaskEvent 增加 event_ref、seq、status、lifecycle、subject_key、parent_event_id、correlation_id、source 和 schema_version。
2. 为事件增加任务内序号、稳定引用、父事件和 correlation 所需 ORM 约束与索引声明。
3. MaterialVersion 增加统一 content_hash；ConfirmedCitation 增加 source_material_id、source_content_hash、quote_hash 和 hash_algorithm。
4. 扩展历史、事件详情、证据验证响应模型；所有外部输入继续 extra=forbid。
5. 保持已有 API 字段兼容，新增响应字段不改变原有操作语义。

**验证：** 运行模型与 Schema 测试，期望字段、枚举、唯一约束、外键和 JSON 往返均可枚举且非法状态被拒绝。

## T30：建立并验证 0002 数据库迁移

**文件：** backend/alembic/versions/0002_event_contract_and_evidence.py、backend/tests/test_migrations.py
**依赖：** T29

**步骤：**
1. 使用 SQLite batch_alter_table 增加全部新列，并在回填完成后建立约束和索引。
2. 按 task_id、created_at、id 稳定回填旧事件 seq；event_ref 使用 evt:加旧事件 UUID。
3. 将可证明已提交的旧业务事件回填 succeeded/active/migration，其他事件回填 unknown；Task.event_sequence 取最大 seq。
4. 从不可变材料版本回填 content_hash 和确认引用哈希；无法可靠回填时保留可被验证器识别的无效值，不伪造 current。
5. 实现 downgrade，并在从 0001 创建的真实临时 SQLite 上验证 upgrade、回填、约束和 downgrade。

**验证：** 执行迁移测试及 `alembic upgrade head`，期望旧 Demo 数据可读、每任务 seq 连续、event_ref 唯一、引用哈希与领域函数一致。

## T31：实现原子事件仓库并接入业务事务

**文件：** backend/app/repositories/events.py、backend/app/services/core.py
**依赖：** T30

**步骤：**
1. EventRepository.append 在当前 Session 事务中原子递增 Task.event_sequence，并用返回值创建只追加事件。
2. 实现按 task_id/after_seq 分页查询和按 event_ref 查询；所有查询继续执行项目成员授权。
3. 把现有创建、材料、生成、确认、请求、补充、拒绝、接收事件改为统一 append，不再直接构造不完整 TaskEvent。
4. 为 start/finish 操作保存 parent_event_id 或 correlation_id；为可替代事项保存稳定 subject_key。
5. 确保业务事务失败时计数器和事件同时回滚，不留下假成功或序号占用。

**验证：** 运行两个 Session 的竞争追加、失败回滚和历史排序集成测试，期望 seq 不重复且回滚后无孤立事件。

## T32：实现确认引用哈希和证据验证

**文件：** backend/app/services/core.py、backend/app/domain/evidence.py
**依赖：** T30、T31

**步骤：**
1. 保存材料版本时由服务端计算 content_hash；不得接受客户端提供的可信哈希。
2. 确认草稿时重新读取材料正文和一基闭区间行号，重新提取 quote 并计算 source_content_hash 与 quote_hash。
3. 校验引用版本、材料和任务归属；跨任务或客户端 quote 不一致时拒绝确认。
4. 实现 current、stale、missing、mismatch、unauthorized 的逐条与整体归约；新增未引用材料不造成 stale。
5. 在 accept 同一事务中二次验证绑定确认版本，仅 current 可继续；stale 映射 STALE_EVIDENCE，其他无效状态映射 INVALID_EVIDENCE。

**验证：** 运行确认、材料新版本、未引用材料、内容篡改、跨任务引用和旧页面接收测试，期望状态及 409 错误码符合 spec.md。

## T33：暴露事件和证据验证 API

**文件：** backend/app/api/router.py、backend/app/schemas/api.py、backend/tests/test_api_flow.py
**依赖：** T31、T32

**步骤：**
1. 增加 GET /api/v1/tasks/{task_id}/events，支持 after_seq 且稳定按 seq 排序。
2. 增加 GET /api/v1/events/{event_ref}，只允许当前有效项目成员读取。
3. 增加 GET /api/v1/confirmed-handoffs/{id}/evidence-validation。
4. 在原历史与交接详情响应中加入 event_ref、status、lifecycle、关联关系和 evidence_state。
5. 保持统一错误结构，避免在无效哈希响应中泄露其他任务正文。

**验证：** 运行 API 授权与流程测试，期望成员可追溯稳定引用，撤权/跨项目读取被拒绝，stale 请求无法接收。

## T34：建立独立确定性 pytest Harness

**文件：** backend/tests/event_contract/*、backend/tests/evidence/*、backend/tests/fixtures/*、backend/tests/conftest.py
**依赖：** T31、T32、T33

**步骤：**
1. 建立显式事件序列夹具，覆盖 proposed、started、succeeded、failed、cancelled、timed_out、not_executed、unknown。
2. 覆盖 finish 无 start、错误 parent/correlation、跨任务关联、superseded、withdrawn 和 reopened。
3. 建立 current/stale/missing/mismatch/unauthorized 证据夹具，覆盖行号、正文、哈希、任务归属及被引用/未引用材料变化。
4. 覆盖确认时服务端重算、accept 二次校验、并发 seq 和全事务回滚。
5. 所有数据库测试只使用 pytest 临时路径；加入保护断言，禁止连接配置中的 Demo 数据库。
6. 连续执行关键夹具两次，比较归约结果与哈希，不依赖网络、模型或执行顺序。

**验证：** 连续两次运行 `python -m pytest -q`，期望结果一致，且 Demo 数据库文件的大小和修改时间不变。

## T35：建立独立 evaluation 包与安全边界

**文件：** evaluation/pyproject.toml、evaluation/src/handoff_eval/models.py、io.py、prepare.py、__main__.py、evaluation/tests/test_prepare.py、test_isolation.py
**依赖：** T28

**步骤：**
1. 建立不导入 FastAPI 应用、不连接生产数据库的独立 Python 包和命令入口。
2. 定义 Scenario、ConditionBundle、AgentResult、GradeResult 的版本化 JSON 边界，并拒绝多余字段。
3. 实现 prepare，为同一场景生成物理隔离的 C0、C1、C2 目录和清单哈希。
4. C0 只复制任务与公开基线，C1 额外复制原始事件，C2 只额外复制确认交接和引用索引。
5. 扫描输出，拒绝隐藏 rubric 泄漏、符号链接、绝对路径、父目录跳转和条件间非预期文件。
6. CLI 默认不执行 subprocess、不访问网络、不调用模型，也不读取用户目录。

**验证：** 运行 evaluation 的 prepare/isolation 测试，期望三条件文件白名单准确，任何构造泄漏均使命令非零退出。

## T36：实现 C0/C1/C2 场景、评分与报告

**文件：** evaluation/src/handoff_eval/grade.py、summarize.py、evaluation/scenarios/*、evaluation/tests/test_grade.py、test_summarize.py、README.md
**依赖：** T35

**步骤：**
1. 建立 easy-inferable 和 policy-context 两个合成场景，隐藏规则只放在 hidden/rubric.json。
2. 为每个条件准备统一 result.json 合成夹具；真实 Agent 或人工结果只通过同一 Schema 导入。
3. 实现 required/forbidden claims、required actions、unsupported claims、引用有效性和 unknowns 覆盖的确定性评分。
4. 实现 summary.json 与 report.md，按场景和条件比较通过率、正确性、遗漏、无依据结论、引用、tokens、steps、duration_ms。
5. 缺失运行指标显示 unknown，不记为 0；重复评分不得改变输出内容。
6. smoke 证明简单场景允许 C0 与 C2 同分，policy 场景的合成 C0 失分而 C1/C2 通过。

**验证：** 连续两次运行 prepare、smoke、grade、summarize，期望评分和报告字节一致且不产生网络请求或模型费用。

## T37：在前端展示事件契约与证据状态

**文件：** frontend/src/api.ts、frontend/src/App.tsx、frontend/src/styles.css、frontend/src/api.test.ts
**依赖：** T33

**步骤：**
1. 增加 EventStatus、EventLifecycle、EvidenceState 及验证明细的 TypeScript 类型。
2. 时间线显示稳定 event_ref、任务序号、状态、lifecycle 和父/关联事件入口。
3. 确认版本与待处理请求显示 current、stale、missing、mismatch、unauthorized 状态及文字解释。
4. stale/mismatch 时禁用接收并提供返回材料、重新审核或重新发起的恢复动作；服务端 409 仍为最终依据。
5. 状态不只依赖颜色，窄屏保持事件引用与恢复操作可读。

**验证：** 运行 Vitest、类型检查、lint 和生产构建，期望每种状态均有文字标签，旧响应缺少增量字段时安全降级。

## T38：更新文档并执行增量验收

**文件：** README.md、.gitignore、全项目
**依赖：** T34、T36、T37

**步骤：**
1. README 增加 0002 迁移、事件查询、证据状态、pytest Harness 和 evaluation 四条命令的说明。
2. .gitignore 忽略 evaluation/out、导入结果和本地报告，但保留场景、fixture 与测试金标。
3. 执行后端迁移测试、全量 pytest、Ruff 和 Mypy。
4. 执行 evaluation 全量测试、smoke 和确定性重复验证。
5. 执行前端测试、lint、typecheck 和 build，并手工复核历史及 stale 恢复流程。
6. 对照 AC16–AC19 收集命令、响应与报告证据，更新 checklist.md 的实际结果。

**验证：** 所有增量质量门禁返回 0；AC16–AC19 有可复现证据；测试未修改 Demo 数据且默认没有真实模型、Shell Agent 或网络调用。

## 执行顺序

    T1 → T2 → T3 → T4 → T5 → T6
                     ├────────→ T12
    T6 → T7 → T8 → T9 → T10 → T11 → T13 → T14 → T15
                                      └────────────→ T16
    T16 → T17 → T18 → T19 → T20 → T21 → T22 → T23 → T24 → T25 → T26 → T27

T12 可在 T4–T11 的数据库工作期间独立实现；其余任务按依赖顺序执行。

本轮增量：

    T28 → T29 → T30 → T31 → T32 → T33 → T34 ─┐
      └────────────────→ T35 → T36 ────────────┼→ T38
                                  T33 → T37 ───┘

T35 可在数据库迁移工作期间并行实施，但 T38 必须等待后端 Harness、evaluation 和前端展示全部完成。

## 覆盖自检

- plan.md 中的 domain、schemas、database、repositories、services、generator、api、demo data、React 页面和一键运行均有任务。
- 每项任务具有文件、依赖、明确步骤和可运行验证。
- F1–F15 分别落实在 T10–T18、T22–T25；N1–N11 落实在 T2、T5、T14、T16、T20、T25–T27。
- F16 落实在 T28–T31、T33、T34、T37；F17 落实在 T28–T34、T37；F18 落实在 T30–T34；F19 落实在 T35–T36。
- N12–N14 落实在 T28、T30、T34–T36、T38；AC16–AC19 的证据由 T38 汇总。
- 依赖图无环，最终验收只依赖全部实现完成。
