from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .database import Base, engine
from .domain.evidence import sha256_text
from .models import (
    ConfirmedCitation,
    ConfirmedHandoff,
    DraftCitation,
    GenerationPreview,
    GenerationRun,
    HandoffDraft,
    HandoffReceipt,
    HandoffRequest,
    Material,
    MaterialVersion,
    Member,
    Project,
    ProjectMembership,
    Task,
    TaskEvent,
)

MEMBER_A = "00000000-0000-4000-8000-00000000000a"
MEMBER_B = "00000000-0000-4000-8000-00000000000b"
MEMBER_C = "00000000-0000-4000-8000-00000000000c"
PROJECT_ID = "10000000-0000-4000-8000-000000000001"
TASK_ID = "20000000-0000-4000-8000-000000000001"
MATERIAL_ID = "30000000-0000-4000-8000-000000000001"
MATERIAL_VERSION_ID = "31000000-0000-4000-8000-000000000001"


DELETE_ORDER = (
    HandoffReceipt,
    TaskEvent,
    HandoffRequest,
    ConfirmedCitation,
    ConfirmedHandoff,
    DraftCitation,
    HandoffDraft,
    GenerationRun,
    GenerationPreview,
    MaterialVersion,
    Material,
    Task,
    ProjectMembership,
    Project,
    Member,
)


def reset_demo(session: Session) -> None:
    for model in DELETE_ORDER:
        session.execute(delete(model))
    members = [
        Member(id=MEMBER_A, display_name="林晓（A）", role_label="项目负责人 / 交接者"),
        Member(id=MEMBER_B, display_name="陈默（B）", role_label="接手者"),
        Member(id=MEMBER_C, display_name="周然（C）", role_label="团队成员"),
    ]
    session.add_all(members)
    session.flush()
    project = Project(
        id=PROJECT_ID,
        name="校园活动报名系统",
        description="用于完整演示材料整理、人工审核与主动接收。",
        owner_id=MEMBER_A,
    )
    session.add(project)
    session.flush()
    session.add_all(
        [
            ProjectMembership(project_id=PROJECT_ID, member_id=MEMBER_A, role="owner"),
            ProjectMembership(project_id=PROJECT_ID, member_id=MEMBER_B, role="member"),
            ProjectMembership(project_id=PROJECT_ID, member_id=MEMBER_C, role="member"),
        ]
    )
    session.flush()
    task = Task(
        id=TASK_ID,
        project_id=PROJECT_ID,
        display_no="T-001",
        title="完成报名审核与通知流程",
        goal="让管理员能够审核报名，并向申请人显示明确结果。",
        description="当前已完成审核接口，仍需核对异常分支和前端状态。",
        acceptance_criteria="通过、拒绝和网络失败均有明确页面反馈；重复提交不会创建重复记录。",
        progress="in_progress",
        review_state="draft",
        owner_id=MEMBER_A,
        event_sequence=1,
    )
    session.add(task)
    session.flush()
    material = Material(
        id=MATERIAL_ID,
        task_id=TASK_ID,
        display_no="S-01",
        kind="text",
        title="开发记录 11 月 10 日",
        source_note="林晓整理的本地开发日志",
        created_by=MEMBER_A,
    )
    session.add(material)
    session.flush()
    material_content = (
        "已完成：新增报名审核接口和权限检查。\n"
        "决定：采用幂等键避免重复提交，原因是移动网络可能重试。\n"
        "测试：接口单元测试输出 18 passed。\n"
        "遗留问题：拒绝原因在窄屏页面会换行错位。\n"
        "下一步：修复窄屏样式并补充网络失败场景。"
    )
    session.add(
        MaterialVersion(
            id=MATERIAL_VERSION_ID,
            material_id=MATERIAL_ID,
            version_no=1,
            content=material_content,
            content_hash=sha256_text(material_content),
            created_by=MEMBER_A,
        )
    )
    session.add(
        TaskEvent(
            event_ref=f"evt:{TASK_ID}",
            task_id=TASK_ID,
            seq=1,
            actor_id=MEMBER_A,
            event_type="task_created",
            status="succeeded",
            lifecycle="active",
            source="system",
            entity_type="task",
            entity_id=TASK_ID,
            details={"seeded": True},
            schema_version=1,
        )
    )
    session.flush()


def ensure_demo(session: Session) -> None:
    Base.metadata.create_all(engine)
    if session.scalar(select(Member.id).limit(1)) is None:
        reset_demo(session)
        session.commit()
