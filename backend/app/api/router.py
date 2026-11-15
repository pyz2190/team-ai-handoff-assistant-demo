from collections.abc import Generator

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.demo_data import reset_demo
from app.domain.errors import DomainError
from app.schemas.api import (
    AcceptAction,
    ConfirmDraft,
    DraftCreate,
    DraftUpdate,
    GenerateCreate,
    LinkMaterialCreate,
    MaterialVersionCreate,
    MembershipUpdate,
    PreviewCreate,
    ProjectCreate,
    RequestAction,
    RequestCreate,
    TaskCreate,
    TaskUpdate,
    TextMaterialCreate,
)
from app.services import CoreService

router = APIRouter(prefix="/api/v1")


def session_dependency() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def actor_dependency(
    x_demo_member_id: str | None = Header(default=None),
    session: Session = Depends(session_dependency),
) -> str:
    if not x_demo_member_id:
        raise DomainError("IDENTITY_REQUIRED", "请选择演示身份", 401)
    CoreService(session).member(x_demo_member_id)
    return x_demo_member_id


def service_dependency(session: Session = Depends(session_dependency)) -> CoreService:
    return CoreService(session)


@router.get("/demo/members")
def demo_members(service: CoreService = Depends(service_dependency)):
    return {"items": service.list_members()}


@router.post("/demo/reset")
def demo_reset(session: Session = Depends(session_dependency)):
    reset_demo(session)
    return {"ok": True}


@router.get("/projects")
def projects(
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return {"items": service.list_projects(actor)}


@router.post("/projects", status_code=201)
def project_create(
    data: ProjectCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.create_project(actor, data)


@router.get("/projects/{project_id}")
def project_get(
    project_id: str,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.get_project(actor, project_id)


@router.patch("/projects/{project_id}/members")
def project_membership(
    project_id: str,
    data: MembershipUpdate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.update_membership(actor, project_id, data)


@router.post("/projects/{project_id}/tasks", status_code=201)
def task_create(
    project_id: str,
    data: TaskCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.create_task(actor, project_id, data)


@router.get("/tasks/{task_id}")
def task_get(
    task_id: str,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.workspace(actor, task_id)


@router.patch("/tasks/{task_id}")
def task_update(
    task_id: str,
    data: TaskUpdate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.update_task(actor, task_id, data)


@router.post("/tasks/{task_id}/materials/text", status_code=201)
def text_material(
    task_id: str,
    data: TextMaterialCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.add_material(
        actor, task_id, data.title, data.source_note, "text", content=data.content
    )


@router.post("/tasks/{task_id}/materials/upload", status_code=201)
async def upload_material(
    task_id: str,
    title: str = Form(...),
    source_note: str = Form(""),
    file: UploadFile = File(...),
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    filename = file.filename or ""
    if not filename.lower().endswith((".txt", ".md")):
        raise DomainError("UNSUPPORTED_FILE", "仅支持 .txt 或 .md 文件", 422)
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise DomainError("UPLOAD_TOO_LARGE", "文件超过 1 MiB", 413)
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise DomainError("INVALID_UTF8", "文件必须使用 UTF-8 编码", 422) from error
    if not decoded.strip():
        raise DomainError("EMPTY_MATERIAL", "文件内容不能为空", 422)
    return service.add_material(actor, task_id, title, source_note, "text", content=decoded)


@router.post("/tasks/{task_id}/materials/link", status_code=201)
def link_material(
    task_id: str,
    data: LinkMaterialCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.add_material(
        actor, task_id, data.title, data.source_note, "link", url=str(data.url)
    )


@router.post("/materials/{material_id}/versions", status_code=201)
def material_version(
    material_id: str,
    data: MaterialVersionCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.add_material_version(actor, material_id, data.content)


@router.post("/tasks/{task_id}/generation-previews", status_code=201)
def generation_preview(
    task_id: str,
    data: PreviewCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.create_preview(actor, task_id, data.material_version_ids)


@router.post("/generation-previews/{preview_id}/runs", status_code=201)
def generation_run(
    preview_id: str,
    data: GenerateCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.generate(actor, preview_id, data.mode)


@router.post("/tasks/{task_id}/drafts", status_code=201)
def draft_create(
    task_id: str,
    data: DraftCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.create_manual_draft(actor, task_id, data)


@router.get("/drafts/{draft_id}")
def draft_get(
    draft_id: str,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.get_draft(actor, draft_id)


@router.patch("/drafts/{draft_id}")
def draft_update(
    draft_id: str,
    data: DraftUpdate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.update_draft(actor, draft_id, data)


@router.post("/drafts/{draft_id}/confirm", status_code=201)
def draft_confirm(
    draft_id: str,
    data: ConfirmDraft,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.confirm_draft(actor, draft_id, data.expected_revision)


@router.post("/tasks/{task_id}/handoff-requests", status_code=201)
def request_create(
    task_id: str,
    data: RequestCreate,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.create_request(actor, task_id, data)


@router.get("/handoff-requests/{request_id}")
def request_get(
    request_id: str,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.request_detail(actor, request_id)


@router.post("/handoff-requests/{request_id}/needs-info")
def request_needs_info(
    request_id: str,
    data: RequestAction,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.request_action(
        actor, request_id, data.expected_revision, "needs_info", data.reason
    )


@router.post("/handoff-requests/{request_id}/reject")
def request_reject(
    request_id: str,
    data: RequestAction,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.request_action(
        actor, request_id, data.expected_revision, "rejected", data.reason
    )


@router.post("/handoff-requests/{request_id}/accept")
def request_accept(
    request_id: str,
    data: AcceptAction,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.accept(actor, request_id, data.expected_revision)


@router.get("/tasks/{task_id}/history")
def task_history(
    task_id: str,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return {"items": service.history(actor, task_id)}


@router.get("/tasks/{task_id}/events")
def task_events(
    task_id: str,
    after_seq: int = Query(default=0, ge=0),
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return {"items": service.history(actor, task_id, after_seq)}


@router.get("/events/{event_ref}")
def event_get(
    event_ref: str,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.event_detail(actor, event_ref)


@router.get("/confirmed-handoffs/{handoff_id}/evidence-validation")
def confirmed_handoff_evidence(
    handoff_id: str,
    actor: str = Depends(actor_dependency),
    service: CoreService = Depends(service_dependency),
):
    return service.evidence_validation(actor, handoff_id)
