# 团队 AI 工作交接助手 Demo — Python 技术方案

## 1. 技术栈变更

本版将核心后端和业务逻辑统一改为 Python 开发。浏览器界面仍采用 React + TypeScript：Python 负责 API、权限、业务规则、事务、数据库、演示生成器和静态站点托管，React 负责高交互工作台。这样既满足“用 Python 开发”，也保留完整 Web Demo 所需的交互体验。

- Python：3.12
- API：FastAPI
- 数据模型与校验：Pydantic 2
- ORM：SQLAlchemy 2.x，同步 Session
- 迁移：Alembic
- 数据库：SQLite
- 运行：Uvicorn，演示环境单进程单端口
- 前端：React 19、TypeScript、Vite、React Router
- 后端测试：pytest、FastAPI TestClient/httpx、pytest-cov
- 前端测试：Vitest、React Testing Library、Playwright、axe
- 代码质量：Ruff；Mypy 检查核心领域和服务接口

实现时使用锁定版本，不把浮动依赖提交为可复现环境。Python 依赖集中在 backend/pyproject.toml；前端依赖由 frontend/package-lock.json 锁定。

## 2. 总体架构

    浏览器（React SPA）
        │ JSON / Multipart；开发时 Vite 代理 /api
        ▼
    FastAPI
        ├── API 路由与 Pydantic 请求/响应模型
        ├── 当前演示身份与服务端授权
        ├── 应用服务：版本、审核、交接与事务规则
        ├── Repository：SQLAlchemy 查询与条件更新
        ├── DemoGenerator：本地确定性五项草稿
        └── SQLite：不可变版本、请求、接收和事件历史

采用单仓库、模块化单体。HTTP 层不直接操作 ORM；业务规则集中在 Service，持久化细节由 Repository 隔离。FastAPI 每个请求通过依赖注入获得独立 SQLAlchemy Session，不在线程或请求之间共享 Session。

演示模式先构建 React，再由 FastAPI 提供 /api/v1 接口和 frontend/dist 静态文件，并对非 API 路由做 SPA 回退。无需外部 AI 密钥。

## 3. Python 后端设计

### 3.1 分层

- app/api：路由、身份解析、请求限制、错误映射、响应模型。
- app/schemas：Pydantic 输入输出模型，默认拒绝多余字段。
- app/domain：枚举、领域值对象、领域错误和纯校验规则，不依赖 FastAPI 或 SQLAlchemy。
- app/services：授权、状态转换、失效规则、事务编排和事件记录。
- app/repositories：SQLAlchemy 查询、写入、条件更新及约束错误映射。
- app/generator：生成协议、本地确定性 DemoGenerator、失败和超时模拟。
- app/database.py：Engine、Session 工厂、SQLite 连接配置和请求级 Session 依赖。
- app/demo_data.py：A/B/C 三个身份和可复现场景的重置数据。
- alembic：编号迁移，测试和启动使用同一迁移路径。

### 3.2 领域枚举和值对象

- WorkProgress：not_started、in_progress、blocked、completed
- ReviewState：draft、confirmed、needs_review
- RequestStatus：pending、needs_info、rejected、accepted、expired
- MaterialKind：text、link
- DraftOrigin：manual、demo_generator
- GenerationStatus：pending、succeeded、failed、timed_out
- HandoffSections：completed、decisions、verification、open_issues、next_steps
- Citation：material_version_id、section、start_line、end_line、quote

所有文本入库前统一换行为 LF。引用使用一基行号和引用文本，不在浏览器与 Python 之间传递字符偏移。内部 ID 使用 UUID4 字符串，业务界面另显示 T-014、S-02、R-008 等连续编号。时间统一保存为 UTC。

### 3.3 服务接口

服务按领域拆分，不建立万能 Service：

- ProjectService：list_projects、create_project、list_members、change_membership
- TaskService：create_task、update_task、get_workspace、list_history
- MaterialService：add_text、add_link、add_version
- DraftService：preview_generation、generate_draft、create_manual、update、confirm
- HandoffService：create_request、request_more_info、reject、accept
- DemoService：list_members、reset

每个修改方法接收 actor_id；涉及可变对象时还接收 expected_revision。领域错误统一映射到 400、401、403、404、409、413、422、500、504，并返回机器可读错误码、用户说明、当前修订号和恢复建议。

### 3.4 生成器协议

Generator 是 Python Protocol，输入包含任务目标、验收标准和用户明确勾选的材料版本，输出包含固定五部分、分区引用和警告。

DemoGenerator 使用确定性规则提取完成项、决定与原因、检查/测试、问题/阻塞和下一步。找不到验证证据时明确写“未验证”；无法归类的信息标记为未知，不包装成事实。它支持 normal、error、timeout 三种演示模式，所有结果都先保存为待审核草稿。

生成预览保存确切输入快照、操作者、获准材料版本、字符摘要和过期时间。只有创建预览的成员可以在有效期内确认生成。

## 4. 数据库设计

### 4.1 实体

| 实体 | 关键字段与用途 |
|---|---|
| Member | 显示名；演示身份 |
| Project | 名称、负责人、创建时间 |
| ProjectMembership | 项目、成员、角色、有效状态、撤权时间 |
| Task | 展示编号、目标、验收标准、进度、审核状态、当前负责人、revision |
| Material | 展示编号、任务、类型、说明、创建者 |
| MaterialVersion | 版本号、正文或 URL、摘要、创建时间；不可变 |
| GenerationPreview | 操作者、完整输入快照、摘要、失效时间 |
| GenerationRun | 状态、耗时、字符用量、错误 |
| HandoffDraft | 来源、五项正文、revision、编辑者、生成运行 |
| DraftCitation | 草稿分区、材料版本、行号、引用 |
| ConfirmedHandoff | 版本号、任务背景快照、五项正文、确认者与时间；不可变 |
| ConfirmedCitation | 确认版本中的固定来源 |
| HandoffRequest | 确认版本、发起者、接手者、状态、原因、revision |
| HandoffReceipt | 请求、实际接收者、接收时间 |
| TaskEvent | 稳定事件引用、任务内序号、状态、来源、关联/父事件、操作者、实体、详情、契约版本、时间；只追加 |

### 4.2 约束和 SQLite 配置

- 每条连接启用 foreign_keys=ON、WAL 和 busy_timeout。
- material_versions(material_id, version_no) 唯一。
- confirmed_handoffs(task_id, version_no) 唯一。
- handoff_receipts(request_id) 唯一。
- 使用部分唯一索引保证每个任务最多一个 pending 请求。
- Task、HandoffDraft、HandoffRequest 使用递增 revision；更新必须带 revision 条件。
- 迁移仅由 Alembic 管理，不在 ORM 启动时隐式 create_all 生产结构。

### 4.3 原子接收

HandoffService.accept 在一个 Session.begin 事务中：

1. 校验成员资格、指定接手者、请求状态、revision 和绑定确认版本。
2. 条件更新 pending → accepted，影响行数必须为 1。
3. 插入唯一 HandoffReceipt。
4. 条件更新任务负责人，且不改变工作进度。
5. 追加 TaskEvent。
6. 任一步失败回滚全部写入。

重要变化也在单一事务中处理：修改目标或验收标准、被引用材料出现新版本、创建新的确认版本时，将 pending 请求改为 expired、审核状态改为 needs_review 并追加事件。新增未被确认版本引用的独立材料不触发失效。

## 5. HTTP API

所有演示请求通过 X-Demo-Member-ID 传递当前身份。依赖函数只解析 Actor，各服务方法仍重新检查项目资格和操作权限。

| 方法与路径 | 用途 |
|---|---|
| GET /api/v1/demo/members | 获取可切换的演示身份 |
| POST /api/v1/demo/reset | 重建合成演示数据 |
| GET/POST /api/v1/projects | 项目列表与创建 |
| GET/PATCH /api/v1/projects/{id}/members | 查看和维护成员 |
| GET/POST /api/v1/projects/{id}/tasks | 任务列表与创建 |
| GET/PATCH /api/v1/tasks/{id} | 获取工作区与维护任务 |
| POST /api/v1/tasks/{id}/materials/text | 粘贴或上传 UTF-8 文本 |
| POST /api/v1/tasks/{id}/materials/link | 保存链接，不抓取正文 |
| POST /api/v1/materials/{id}/versions | 新增不可变材料版本 |
| POST /api/v1/tasks/{id}/generation-previews | 创建并返回完整输入预览 |
| POST /api/v1/generation-previews/{id}/runs | 确认后生成草稿或模拟失败 |
| POST /api/v1/tasks/{id}/drafts | 创建人工草稿 |
| PATCH /api/v1/drafts/{id} | 按 revision 保存五项与引用 |
| POST /api/v1/drafts/{id}/confirm | 固定确认版本 |
| POST /api/v1/tasks/{id}/handoff-requests | 选择接手者并发起 |
| GET /api/v1/handoff-requests/{id} | 查看绑定版本、未知和来源 |
| POST /api/v1/handoff-requests/{id}/needs-info | 请求补充并终结旧入口 |
| POST /api/v1/handoff-requests/{id}/reject | 拒绝并记录原因 |
| POST /api/v1/handoff-requests/{id}/accept | 原子接收与责任转移 |
| GET /api/v1/tasks/{id}/history | 获取事件时间线 |

文本上传超过 1 MiB 立即返回 413；仅接受 UTF-8 的 .txt、.md 或文本粘贴。一次生成正文总量不超过 20,000 字符，不静默截断。生成调用设置 60 秒硬超时。

## 6. 前端页面与设计

### 6.1 路由

- /：项目选择、身份切换、Demo 重置和流程引导
- /projects/:projectId：成员、任务列表、创建任务
- /tasks/:taskId：任务概览、三类状态、材料和下一步
- /tasks/:taskId/generate：选择材料、完整预览、生成或人工后备
- /tasks/:taskId/drafts/:draftId：五项编辑、证据核对、保存与确认
- /tasks/:taskId/handoff/new：确认版本、接手者与发起
- /requests/:requestId：补充、拒绝或主动接收
- /tasks/:taskId/history：确认、请求、回应、失效和接收时间线

### 6.2 组件

- AppShell：项目、当前身份与 Demo 标识
- StatusTriplet：工作进度、内容审核、交接处理三种独立状态
- TaskTable：桌面表格，窄屏变为带字段名的纵向列表
- MaterialList / MaterialViewer：版本、类型、行号和“未读取正文”提示
- FiveSectionEditor：五项内容、引用管理、保存状态和 revision 冲突恢复
- EvidencePanel：引用定位和来源逐行核对
- VersionBanner：确认版本、确认者、时间和失效状态
- RequestActions：补充、拒绝、接收的权限化操作
- HistoryTimeline：人员、版本、动作和结果
- InlineNotice、FieldError、ToastRegion、Skeleton、EmptyState

### 6.3 视觉与可访问性

保持 PRODUCT.md 中“共享实验室午后白光”的克制方向：白色工作区、深红主操作、蓝绿色信息与证据定位。分区依靠标题、留白和细分隔线，不使用卡片墙、玻璃拟态、渐变或宽阴影。

- 正文阅读宽度 65–75 字符。
- 768px 以下将证据栏移到正文后，版本和关键操作保持可见。
- 反馈动画 150–200ms；reduced-motion 时取消位移。
- 控件覆盖默认、悬停、焦点、按下、禁用、加载和错误状态。
- 颜色对比、键盘顺序和焦点可见性满足 WCAG 2.1 AA。

## 7. 文件组织

    系统设计与分析/
    ├── spec.md
    ├── plan.md
    ├── task.md
    ├── checklist.md
    ├── PRODUCT.md
    ├── README.md
    ├── scripts/
    │   ├── dev.py
    │   └── demo.py
    ├── backend/
    │   ├── pyproject.toml
    │   ├── alembic.ini
    │   ├── app/
    │   │   ├── main.py
    │   │   ├── config.py
    │   │   ├── database.py
    │   │   ├── models.py
    │   │   ├── schemas/
    │   │   ├── domain/
    │   │   ├── services/
    │   │   ├── repositories/
    │   │   ├── api/
    │   │   ├── generator/
    │   │   └── demo_data.py
    │   ├── alembic/
    │   │   ├── env.py
    │   │   └── versions/0001_initial.py
    │   └── tests/
    ├── frontend/
    │   ├── package.json
    │   ├── vite.config.ts
    │   ├── playwright.config.ts
    │   ├── src/
    │   │   ├── app/
    │   │   ├── routes/
    │   │   ├── features/
    │   │   ├── components/
    │   │   ├── api/
    │   │   ├── styles/
    │   │   └── test/
    │   └── e2e/
    └── data/

scripts/dev.py 启动 Uvicorn 与 Vite；scripts/demo.py 检查依赖、执行 Alembic 迁移、初始化演示数据、构建前端并启动单端口服务。

## 8. 测试与验收

- Python 单元测试：权限矩阵、状态分离、引用校验、人工确认、失效规则、补充、拒绝、重复接收。
- SQLAlchemy/SQLite 集成测试：临时数据库执行真实 Alembic 迁移，验证外键、部分唯一索引、事务回滚和竞争提交。
- API 测试：FastAPI TestClient 覆盖身份缺失、跨项目访问、撤权、上传限制、无效 UTF-8、409 冲突和错误结构。
- 并发测试：两个独立 Session/线程同时接收时只有一个成功；编辑与接收竞争不会产生部分状态。
- 前端测试：Vitest + Testing Library 覆盖表单、状态三联、证据定位、错误恢复和权限差异。
- E2E：Playwright 切换 A/B/C，覆盖正常交接、人工后备、补充、拒绝、过期页面、冒名接收和历史延续。
- 可访问性：关键页面执行 axe 自动检查，再人工检查键盘、焦点和窄屏流程。

质量门禁：

1. Ruff 格式和静态检查通过。
2. Mypy 对核心领域、服务和 repository 协议通过。
3. pytest 全部通过，核心业务分支覆盖率达到 80% 以上。
4. 前端 lint、类型检查、组件测试和生产构建通过。
5. Playwright 核心流程与 axe 检查通过。
6. 在干净目录中按 README 可完成一键初始化和启动。

## 9. Spec 覆盖

| Spec | 实现归属 |
|---|---|
| F1 | Demo 身份依赖、ProjectService、服务端授权 |
| F2 | TaskService、任务表单、StatusTriplet |
| F3–F4 | MaterialService、不可变版本、上传限制、来源行号 |
| F5 | GenerationPreview、完整预览和输入摘要 |
| F6–F7 | Generator Protocol、五项结构、引用与结构检查 |
| F8 | 草稿 revision、确认快照、审核工作台 |
| F9 | HandoffService、单 pending 唯一索引 |
| F10 | needs-info、reject、处理页和事件历史 |
| F11 | accept 事务、唯一收据、重复提交保护 |
| F12 | 重要变化失效、revision、409 恢复 |
| F13 | 新负责人授权、材料追加、历史时间线 |
| F14 | GenerationRun、超时、受控失败和人工入口 |
| F15 | demo_data、身份切换和一键重置 |
| F16 | EventLedger、稳定事件引用、任务内序号分配、状态归约和历史 API |
| F17 | EvidenceValidator、确认引用哈希、stale/mismatch 校验和接收二次复核 |
| F18 | 隔离 pytest 夹具、临时 SQLite、事件/引用/事务确定性测试 |
| F19 | 独立 evaluation 包、C0/C1/C2 实验包、确定性评分和对比报告 |

不存在未分配的功能需求。N1–N14 由组件状态、服务端授权、输入快照、不可信文本边界、事务、事件历史、超时、响应式布局、隔离测试与可复现评估覆盖。

## 10. 关键技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI | 符合指定语言，类型化 API、依赖注入和自动文档适合 Demo |
| 校验 | Pydantic 2 | 统一请求、响应和边界验证，拒绝意外字段 |
| ORM | SQLAlchemy 2 同步 Session | SQLite Demo 无需引入异步复杂度，事务边界更直观 |
| 迁移 | Alembic | 使用 SQLAlchemy 官方生态的可追踪迁移方案 |
| 并发保护 | revision CAS + 唯一约束 + 事务 | 同时防止旧页面、重复提交和数据库级竞争 |
| 前端 | React + TypeScript + Vite | 保留完整、响应式、可测试的浏览器工作台 |
| 样式 | 原生 CSS + OKLCH 令牌 | 精确实现克制界面，不依赖重型组件库 |
| AI 演示 | Protocol + 本地确定性生成器 | 无密钥即可完整演示，且保留未来替换真实模型的边界 |
| 部署 | FastAPI 托管构建后的 SPA | 单进程单端口，降低演示环境成本 |

## 11. Harness 思想移植设计

### 11.1 事件契约

TaskEvent 扩展为不可变事件信封：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID 字符串 | 数据库主键，不复用 |
| event_ref | 字符串 | 稳定外部引用，格式 evt:UUID；唯一且不可修改 |
| task_id | UUID 字符串 | 所属任务 |
| seq | 正整数 | 任务内严格递增；与 task_id 组成唯一键 |
| event_type | 字符串 | 业务事件类型，例如 handoff_accepted |
| status | EventStatus | proposed、started、succeeded、failed、cancelled、timed_out、not_executed、unknown |
| lifecycle | EventLifecycle | active、superseded、withdrawn、reopened |
| subject_key | 可空字符串 | 同一可更新事项的稳定逻辑键 |
| parent_event_id | 可空 UUID | 直接父事件，用于 start/finish 或重开关系 |
| correlation_id | 可空 UUID | 一次请求或事务内多个事件的共同关联 |
| source | EventSource | user、system、generator、evaluation、migration |
| actor_id | UUID 字符串 | 操作者 |
| entity_type/entity_id | 字符串 | 关联业务实体 |
| details | JSON | 小型结构化详情，不保存完整敏感正文 |
| schema_version | 正整数 | 当前为 1，支持将来升级 |
| created_at | UTC 时间 | 追加时写入 |

Task 增加 event_sequence 计数器。EventRepository.append 在现有业务事务中执行条件更新：

    UPDATE tasks
    SET event_sequence = event_sequence + 1
    WHERE id = :task_id
    RETURNING event_sequence

返回值作为 seq，再插入 TaskEvent。这样避免用 MAX(seq)+1 导致并发重复；事务回滚时计数器和事件一起回滚。数据库增加：

- UNIQUE(event_ref)
- UNIQUE(task_id, seq)
- INDEX(task_id, created_at)
- INDEX(correlation_id)
- parent_event_id 自引用外键

EventLedger 是纯领域模块，提供 classify_execution(start, finish)、reduce_subject(events) 和 validate_chain(events)。规则：

- started 没有匹配完成事件时归为 unknown，不推断成功。
- finish 必须通过 parent_event_id 或 correlation_id 关联 start。
- superseded、withdrawn、reopened 通过新事件表达；旧事件不更新。
- reduce_subject 按 seq 得到当前 lifecycle，同时保留完整变化链。
- 历史业务事件若本身代表已提交的原子结果，迁移时回填 succeeded；无法证明完成的旧事件回填 unknown。

新增只读 API：

- GET /api/v1/tasks/{task_id}/events?after_seq={n}
- GET /api/v1/events/{event_ref}

原有 /tasks/{task_id}/history 使用相同 EventLedger 输出，并额外返回 event_ref、seq、status、lifecycle、correlation_id。

### 11.2 引用哈希与证据验证

新增 app/domain/evidence.py：

- canonicalize_text：Unicode NFC、CRLF/CR 转 LF；保留正文空格和行结构。
- sha256_text：对规范化 UTF-8 字节计算小写十六进制 SHA-256。
- build_quote：按一基闭区间从材料正文重新提取引用。
- quote_fingerprint：对 material_version_id、section、start_line、end_line 和规范化 quote 的长度前缀编码计算 SHA-256，避免简单拼接歧义。

ConfirmedCitation 增加：

- source_material_id
- source_content_hash
- quote_hash
- hash_algorithm，固定 sha256-v1

确认草稿时不信任客户端 quote 或哈希。服务端重新读取 MaterialVersion，按行号提取 quote，校验与草稿引用一致后计算两个哈希并保存。MaterialVersion.content_hash 统一使用同一 canonicalize_text 算法。

EvidenceValidator.validate_confirmed_handoff 返回每条引用及整体结果：

| 状态 | 条件 |
|---|---|
| current | 材料版本属于当前任务，内容和片段哈希匹配，且没有更新材料版本 |
| stale | 原版本与哈希仍匹配，但同一材料存在更高版本 |
| missing | 固定材料版本不存在 |
| mismatch | 当前存储内容、行号片段或固定哈希不一致 |
| unauthorized | 材料或版本不属于确认版本的任务 |

整体状态按 unauthorized → mismatch → missing → stale → current 的严重度排序。旧确认版本不被修改；验证是相对于当前数据库状态的派生结果。

新增 API：

- GET /api/v1/confirmed-handoffs/{id}/evidence-validation

请求详情和任务确认版本摘要嵌入 evidence_state。HandoffService.accept 在责任转移事务内重新运行验证，只允许整体 current；stale 返回 409 STALE_EVIDENCE，mismatch/missing/unauthorized 返回 409 INVALID_EVIDENCE。该检查是现有“重要变化使请求过期”的防御性第二层。

### 11.3 数据库迁移

新增 Alembic 0002_event_contract_and_evidence：

1. 为 tasks 增加 event_sequence，默认 0。
2. 为 task_events 增加 event_ref、seq、status、lifecycle、subject_key、parent_event_id、correlation_id、source、schema_version。
3. 按 task_id、created_at、id 稳定排序回填 seq；event_ref 使用 evt:加原 UUID。
4. 将已有已提交业务事件回填 succeeded/active/migration，task.event_sequence 回填为最大 seq。
5. 为 confirmed_citations 增加 source_material_id、source_content_hash、quote_hash、hash_algorithm。
6. 从不可变 MaterialVersion 回填引用哈希；无法回填的行保留空哈希并由验证器报告 missing 或 mismatch，不伪造有效证据。
7. 建立唯一索引和外键；迁移测试验证 upgrade、数据回填和 downgrade。

SQLite 增列和约束变更使用 Alembic batch_alter_table；迁移在临时真实数据库上测试，不只验证 Base.metadata.create_all。

### 11.4 确定性 pytest 夹具

新增测试模块：

    backend/tests/event_contract/
      test_status_classification.py
      test_event_sequence.py
      test_lifecycle_reducer.py
      test_interruption_recovery.py
    backend/tests/evidence/
      test_hashes.py
      test_validation_states.py
      test_confirmation_hashing.py
      test_acceptance_guard.py
    backend/tests/fixtures/
      event_sequences.py
      evidence_cases.py

覆盖矩阵：

- proposed/started/succeeded/failed/cancelled/timed_out/not_executed/unknown。
- start 无 finish、finish 无 start、错误 parent/correlation 和跨任务链。
- active → superseded、active → withdrawn、withdrawn → reopened。
- 两个 Session 竞争追加事件时 seq 不重复。
- current、stale、missing、mismatch、unauthorized。
- 被引用材料增加版本变 stale；新增未引用材料不变 stale。
- 引用正文、行号、任务归属或哈希被篡改时拒绝接收。
- 接收事务失败后 Event、Receipt、Request、Task 全部回滚。
- 同一 fixture 连续执行两次产生相同状态和哈希。
- 测试 Session 只连接 pytest 临时目录，运行前后真实 Demo 数据快照不变。

### 11.5 独立 evaluation 模块

evaluation 不导入 FastAPI 应用，不连接生产数据库，不启动 subprocess，不调用网络或模型。实现为可单独运行的 Python 包：

    evaluation/
      README.md
      pyproject.toml
      src/handoff_eval/
        __main__.py
        models.py
        prepare.py
        grade.py
        summarize.py
        io.py
      scenarios/
        easy-inferable/
          scenario.json
          public/
          hidden/rubric.json
          fixtures/
        policy-context/
          scenario.json
          public/
          hidden/rubric.json
          fixtures/
      tests/
        test_prepare.py
        test_isolation.py
        test_grade.py
        test_summarize.py

场景：

1. easy-inferable：下一步可以从任务说明和公开材料直接推断，用来证明交接不一定比 C0 更有价值。
2. policy-context：关键产品决策、被否决方案、未知项和停止条件只存在于事件账本与确认交接中，用来检验 C1/C2 是否优于 C0。

prepare 为每个场景生成三个物理隔离目录：

| 条件 | 可见输入 |
|---|---|
| C0 | task.md 与 public/ 基线材料 |
| C1 | C0 输入 + raw_events.jsonl |
| C2 | C0 输入 + handoff.json + citations.json |

hidden/rubric.json 永不复制到实验包。prepare 完成后扫描三个目录，拒绝符号链接、绝对路径、父目录跳转和条件间文件泄漏。

外部 Agent 或人工实验将统一 result.json 写入指定目录：

    {
      "schema_version": 1,
      "scenario_id": "policy-context",
      "condition": "c2",
      "answer": {
        "claims": [{"key": "...", "value": "...", "citations": ["evt:..."]}],
        "next_actions": ["..."],
        "unknowns": ["..."]
      },
      "metrics": {
        "tokens": 0,
        "steps": 0,
        "duration_ms": 0
      }
    }

grade 只读取场景隐藏 rubric、一个条件包和对应 result.json。评分包含：

- required_claims 命中数
- forbidden_claims 违规数
- required_actions 命中数
- unsupported_claims 数量
- valid_citations / invalid_citations
- unknowns 覆盖
- 总分和 pass/fail

所有匹配使用规范化键和值，不调用语义模型。fixtures 提供合成 C0/C1/C2 结果：easy-inferable 允许 C0 与 C2 同分；policy-context 的 C0 必须因缺少隐藏于上下文的决策而失分，C1/C2 通过。

summarize 聚合多个 grade.json，输出 summary.json 和 report.md，按场景与条件比较通过率、正确性、遗漏、无依据结论、引用、tokens、steps 和 duration_ms。缺失指标显示 unknown，不当作 0。

命令：

    python -m handoff_eval prepare --scenario policy-context --out evaluation/out
    python -m handoff_eval smoke --scenario all --out evaluation/out
    python -m handoff_eval grade --scenario policy-context --condition c2 --result result.json
    python -m handoff_eval summarize --runs evaluation/out --out evaluation/report

### 11.6 文件变更

后端新增或修改：

- backend/app/domain/events.py
- backend/app/domain/evidence.py
- backend/app/models.py
- backend/app/repositories/events.py
- backend/app/services/handoffs.py 或现有 CoreService 的对应拆分
- backend/app/api/events.py
- backend/app/api/handoffs.py
- backend/alembic/versions/0002_event_contract_and_evidence.py
- backend/tests/event_contract/*
- backend/tests/evidence/*

前端增量：

- 历史时间线显示 event_ref、status、lifecycle 和关联事件。
- 确认版本与请求页显示 current/stale/mismatch 等证据状态。
- stale/mismatch 使用文字、图标和恢复建议，不只依赖颜色。

evaluation 使用独立 pyproject.toml，不加入 FastAPI 生产依赖；根 README 增加离线评估操作说明。

### 11.7 扩展技术决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 事件序号 | Task 计数器原子递增 | 避免 MAX(seq)+1 并发冲突，和业务事务一起回滚 |
| 事件更新 | 追加 superseded/withdrawn/reopened 事件 | 保持审计历史，不原地改写 |
| 稳定引用 | evt:UUID | 不受排序、迁移和显示编号变化影响 |
| 文本规范化 | Unicode NFC + LF + UTF-8 | Windows、浏览器和 Python 间产生一致哈希 |
| 哈希 | SHA-256，带算法版本 | 标准库可实现、确定性强、便于将来升级 |
| stale | 动态派生，不修改旧快照 | 同时保留历史真实性和当前有效性 |
| 接收保护 | 失效事务 + accept 时再次验证 | 防止漏失效、旧页面和并发竞态 |
| evaluation | 离线准备、导入结果、确定性评分 | 不隐式运行 Agent、Shell 或消耗模型额度 |
| C0/C1/C2 | 两类难度场景 | 避免只在可从仓库推断的简单任务上得出虚假收益 |
| 外部代码 | 独立实现，不复制来源仓库 | 规避许可证不明确和路径/依赖耦合 |

## 12. 文档依据

- FastAPI Dependencies：https://fastapi.tiangolo.com/tutorial/dependencies/
- FastAPI Testing：https://fastapi.tiangolo.com/tutorial/testing/
- SQLAlchemy Session Basics：https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- SQLAlchemy Session API：https://docs.sqlalchemy.org/en/20/orm/session_api.html
- Alembic Tutorial：https://alembic.sqlalchemy.org/en/latest/tutorial.html

SQLAlchemy 文档明确 Session 是有状态且不可在线程间共享的，因此本方案使用“一请求一 Session”；事务通过 Session.begin 上下文统一提交或回滚。Context7 的 resolve-library-id 与 query-docs 在本会话没有可调用入口，本次按项目指令采用官方一手文档作为兜底；进入依赖安装时若 Context7 恢复，将先核对目标版本。
