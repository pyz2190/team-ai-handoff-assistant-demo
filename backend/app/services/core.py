from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import EventLifecycle, EventSource, EventStatus, EvidenceState
from app.domain.errors import DomainError, require
from app.domain.evidence import (
    HASH_ALGORITHM,
    aggregate_evidence,
    build_quote,
    canonicalize_text,
    quote_fingerprint,
    sha256_text,
)
from app.generator import DemoGenerator
from app.models import (
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
    utcnow,
)
from app.repositories import EventRepository

SECTION_KEYS = ("completed", "decisions", "verification", "open_issues", "next_steps")


def iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def found[T](
    value: T | None,
    code: str,
    message: str,
    status_code: int = 404,
) -> T:
    if value is None:
        raise DomainError(code, message, status_code)
    return value


class CoreService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.events = EventRepository(session)

    def member(self, member_id: str) -> Member:
        return found(
            self.session.get(Member, member_id),
            "UNKNOWN_MEMBER",
            "演示身份不存在",
            401,
        )

    def membership(self, actor_id: str, project_id: str) -> ProjectMembership:
        row = self.session.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.member_id == actor_id,
                ProjectMembership.active.is_(True),
            )
        )
        return found(row, "PROJECT_ACCESS_DENIED", "无权访问该项目", 403)

    def task(self, actor_id: str, task_id: str) -> Task:
        task = found(self.session.get(Task, task_id), "TASK_NOT_FOUND", "任务不存在")
        self.membership(actor_id, task.project_id)
        return task

    def require_owner(self, actor_id: str, task: Task) -> None:
        require(task.owner_id == actor_id, "OWNER_REQUIRED", "仅当前负责人可以执行此操作", 403)

    def project_owner(self, actor_id: str, project_id: str) -> Project:
        project = found(self.session.get(Project, project_id), "PROJECT_NOT_FOUND", "项目不存在")
        require(project.owner_id == actor_id, "PROJECT_OWNER_REQUIRED", "仅项目负责人可操作", 403)
        return project

    def event(
        self,
        task_id: str,
        actor_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any] | None = None,
        *,
        status: EventStatus = EventStatus.SUCCEEDED,
        lifecycle: EventLifecycle = EventLifecycle.ACTIVE,
        source: EventSource = EventSource.USER,
        subject_key: str | None = None,
        parent_event_id: str | None = None,
        correlation_id: str | None = None,
    ) -> TaskEvent:
        return self.events.append(
            task_id=task_id,
            actor_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            status=status,
            lifecycle=lifecycle,
            source=source,
            subject_key=subject_key,
            parent_event_id=parent_event_id,
            correlation_id=correlation_id,
        )

    def list_members(self) -> list[dict]:
        members = self.session.scalars(select(Member).order_by(Member.display_name)).all()
        return [
            {"id": member.id, "display_name": member.display_name, "role_label": member.role_label}
            for member in members
        ]

    def list_projects(self, actor_id: str) -> list[dict]:
        self.member(actor_id)
        rows = self.session.execute(
            select(Project, ProjectMembership)
            .join(ProjectMembership, ProjectMembership.project_id == Project.id)
            .where(
                ProjectMembership.member_id == actor_id,
                ProjectMembership.active.is_(True),
            )
            .order_by(Project.created_at)
        ).all()
        return [
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "owner_id": project.owner_id,
                "role": membership.role,
                "created_at": iso(project.created_at),
            }
            for project, membership in rows
        ]

    def create_project(self, actor_id: str, data: Any) -> dict:
        self.member(actor_id)
        project = Project(name=data.name, description=data.description, owner_id=actor_id)
        self.session.add(project)
        self.session.flush()
        selected = set(data.member_ids) | {actor_id}
        for member_id in selected:
            self.member(member_id)
            self.session.add(
                ProjectMembership(
                    project_id=project.id,
                    member_id=member_id,
                    role="owner" if member_id == actor_id else "member",
                )
            )
        self.session.flush()
        return self.project_dict(project)

    def project_dict(self, project: Project) -> dict:
        memberships = self.session.scalars(
            select(ProjectMembership)
            .options(selectinload(ProjectMembership.member))
            .where(ProjectMembership.project_id == project.id)
            .order_by(ProjectMembership.created_at)
        ).all()
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "owner_id": project.owner_id,
            "created_at": iso(project.created_at),
            "members": [
                {
                    "member_id": row.member_id,
                    "display_name": row.member.display_name,
                    "role": row.role,
                    "active": row.active,
                }
                for row in memberships
            ],
        }

    def get_project(self, actor_id: str, project_id: str) -> dict:
        self.membership(actor_id, project_id)
        project = found(self.session.get(Project, project_id), "PROJECT_NOT_FOUND", "项目不存在")
        result = self.project_dict(project)
        tasks = self.session.scalars(
            select(Task).where(Task.project_id == project_id).order_by(Task.created_at)
        ).all()
        result["tasks"] = [self.task_summary(task) for task in tasks]
        return result

    def update_membership(self, actor_id: str, project_id: str, data: Any) -> dict:
        project = self.project_owner(actor_id, project_id)
        require(data.member_id != project.owner_id, "OWNER_CANNOT_BE_REMOVED", "不能移除项目负责人")
        self.member(data.member_id)
        membership = self.session.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.member_id == data.member_id,
            )
        )
        if membership is None:
            membership = ProjectMembership(
                project_id=project_id,
                member_id=data.member_id,
                role="member",
                active=data.active,
            )
            self.session.add(membership)
        else:
            membership.active = data.active
            membership.revoked_at = None if data.active else utcnow()
        self.session.flush()
        return self.project_dict(project)

    def create_task(self, actor_id: str, project_id: str, data: Any) -> dict:
        self.membership(actor_id, project_id)
        owner_id = data.owner_id or actor_id
        self.membership(owner_id, project_id)
        count = self.session.scalar(
            select(func.count()).select_from(Task).where(Task.project_id == project_id)
        )
        task = Task(
            project_id=project_id,
            display_no=f"T-{int(count or 0) + 1:03d}",
            title=data.title,
            goal=data.goal,
            description=data.description,
            acceptance_criteria=data.acceptance_criteria,
            progress=data.progress,
            owner_id=owner_id,
        )
        self.session.add(task)
        self.session.flush()
        self.event(task.id, actor_id, "task_created", "task", task.id)
        return self.task_summary(task)

    def task_summary(self, task: Task) -> dict:
        owner = self.session.get(Member, task.owner_id)
        latest_request = self.session.scalar(
            select(HandoffRequest)
            .where(HandoffRequest.task_id == task.id)
            .order_by(HandoffRequest.created_at.desc())
            .limit(1)
        )
        return {
            "id": task.id,
            "project_id": task.project_id,
            "display_no": task.display_no,
            "title": task.title,
            "goal": task.goal,
            "description": task.description,
            "acceptance_criteria": task.acceptance_criteria,
            "progress": task.progress,
            "review_state": task.review_state,
            "request_state": latest_request.status if latest_request else "none",
            "pending_request_id": (
                latest_request.id if latest_request and latest_request.status == "pending" else None
            ),
            "owner_id": task.owner_id,
            "owner_name": owner.display_name if owner else "未知",
            "revision": task.revision,
            "created_at": iso(task.created_at),
            "updated_at": iso(task.updated_at),
        }

    def workspace(self, actor_id: str, task_id: str) -> dict:
        task = self.task(actor_id, task_id)
        result = self.task_summary(task)
        materials = self.session.scalars(
            select(Material)
            .options(selectinload(Material.versions))
            .where(Material.task_id == task.id)
            .order_by(Material.created_at)
        ).all()
        result["materials"] = [self.material_dict(row) for row in materials]
        drafts = self.session.scalars(
            select(HandoffDraft)
            .where(HandoffDraft.task_id == task.id)
            .order_by(HandoffDraft.updated_at.desc())
        ).all()
        result["drafts"] = [self.draft_dict(row) for row in drafts]
        confirmed = self.session.scalars(
            select(ConfirmedHandoff)
            .where(ConfirmedHandoff.task_id == task.id)
            .order_by(ConfirmedHandoff.version_no.desc())
        ).all()
        result["confirmed_handoffs"] = [self.confirmed_dict(row) for row in confirmed]
        requests = self.session.scalars(
            select(HandoffRequest)
            .where(HandoffRequest.task_id == task.id)
            .order_by(HandoffRequest.created_at.desc())
        ).all()
        result["requests"] = [self.request_summary(row) for row in requests]
        return result

    def update_task(self, actor_id: str, task_id: str, data: Any) -> dict:
        task = self.task(actor_id, task_id)
        self.require_owner(actor_id, task)
        require(
            task.revision == data.expected_revision,
            "STALE_REVISION",
            "任务已被其他操作更新，请刷新后重试",
            409,
        )
        important = False
        for field in ("title", "goal", "description", "acceptance_criteria", "progress"):
            value = getattr(data, field)
            if value is not None and value != getattr(task, field):
                setattr(task, field, value)
                if field in {"goal", "acceptance_criteria"}:
                    important = True
        task.revision += 1
        if important:
            self.expire_pending(task, actor_id, "任务目标或验收标准已变化")
        self.event(task.id, actor_id, "task_updated", "task", task.id, {"important": important})
        self.session.flush()
        return self.task_summary(task)

    def material_dict(self, material: Material) -> dict:
        versions = sorted(material.versions, key=lambda value: value.version_no)
        return {
            "id": material.id,
            "task_id": material.task_id,
            "display_no": material.display_no,
            "kind": material.kind,
            "title": material.title,
            "source_note": material.source_note,
            "created_by": material.created_by,
            "created_at": iso(material.created_at),
            "latest_version_id": versions[-1].id if versions else None,
            "versions": [self.material_version_dict(value) for value in versions],
        }

    def material_version_dict(self, version: MaterialVersion) -> dict:
        return {
            "id": version.id,
            "material_id": version.material_id,
            "version_no": version.version_no,
            "content": version.content,
            "url": version.url,
            "unread_body": bool(version.url and not version.content),
            "created_by": version.created_by,
            "created_at": iso(version.created_at),
        }

    def add_material(
        self,
        actor_id: str,
        task_id: str,
        title: str,
        source_note: str,
        kind: str,
        content: str | None = None,
        url: str | None = None,
    ) -> dict:
        task = self.task(actor_id, task_id)
        self.require_owner(actor_id, task)
        count = self.session.scalar(
            select(func.count()).select_from(Material).where(Material.task_id == task_id)
        )
        normalized = canonicalize_text(content) if content else None
        material = Material(
            task_id=task_id,
            display_no=f"S-{int(count or 0) + 1:02d}",
            kind=kind,
            title=title,
            source_note=source_note,
            created_by=actor_id,
        )
        self.session.add(material)
        self.session.flush()
        version = MaterialVersion(
            material_id=material.id,
            version_no=1,
            content=normalized,
            url=url,
            content_hash=sha256_text(normalized or url or ""),
            created_by=actor_id,
        )
        self.session.add(version)
        self.session.flush()
        self.session.refresh(material)
        self.event(task_id, actor_id, "material_added", "material", material.id)
        return self.material_dict(material)

    def add_material_version(self, actor_id: str, material_id: str, content: str) -> dict:
        material = found(
            self.session.get(Material, material_id), "MATERIAL_NOT_FOUND", "材料不存在"
        )
        task = self.task(actor_id, material.task_id)
        self.require_owner(actor_id, task)
        require(material.kind == "text", "LINK_VERSION_UNSUPPORTED", "链接材料不能添加正文版本")
        last_no = self.session.scalar(
            select(func.max(MaterialVersion.version_no)).where(
                MaterialVersion.material_id == material.id
            )
        )
        normalized = canonicalize_text(content)
        version = MaterialVersion(
            material_id=material.id,
            version_no=int(last_no or 0) + 1,
            content=normalized,
            content_hash=sha256_text(normalized),
            created_by=actor_id,
        )
        self.session.add(version)
        self.session.flush()
        cited_pending = self.session.scalar(
            select(HandoffRequest.id)
            .join(
                ConfirmedCitation,
                ConfirmedCitation.handoff_id == HandoffRequest.confirmed_handoff_id,
            )
            .join(MaterialVersion, MaterialVersion.id == ConfirmedCitation.material_version_id)
            .where(
                HandoffRequest.task_id == task.id,
                HandoffRequest.status == "pending",
                MaterialVersion.material_id == material.id,
            )
            .limit(1)
        )
        if cited_pending:
            self.expire_pending(task, actor_id, "被引用材料出现新版本")
        self.event(task.id, actor_id, "material_version_added", "material_version", version.id)
        return self.material_version_dict(version)

    def create_preview(self, actor_id: str, task_id: str, version_ids: list[str]) -> dict:
        task = self.task(actor_id, task_id)
        self.require_owner(actor_id, task)
        versions = self.session.scalars(
            select(MaterialVersion)
            .join(Material, Material.id == MaterialVersion.material_id)
            .where(MaterialVersion.id.in_(version_ids), Material.task_id == task.id)
        ).all()
        require(
            len(versions) == len(set(version_ids)),
            "INVALID_GENERATION_SCOPE",
            "选择中包含不存在或无权访问的材料",
            422,
        )
        require(
            all(value.content is not None for value in versions),
            "UNREAD_LINK_BODY",
            "链接正文未读取，不能发送",
        )
        materials: list[dict[str, Any]] = [
            {
                "version_id": value.id,
                "material_id": value.material_id,
                "version_no": value.version_no,
                "content": value.content or "",
            }
            for value in versions
        ]
        snapshot = {
            "task": {
                "title": task.title,
                "goal": task.goal,
                "acceptance_criteria": task.acceptance_criteria,
            },
            "materials": materials,
        }
        character_count = sum(len(value["content"]) for value in materials)
        require(
            character_count <= 20_000,
            "GENERATION_INPUT_TOO_LARGE",
            "生成正文超过 20,000 字符，请缩小选择范围",
            413,
        )
        preview = GenerationPreview(
            task_id=task.id,
            actor_id=actor_id,
            material_version_ids=version_ids,
            input_snapshot=snapshot,
            character_count=character_count,
            expires_at=utcnow() + timedelta(minutes=15),
        )
        self.session.add(preview)
        self.session.flush()
        return {
            "id": preview.id,
            "task_id": preview.task_id,
            "input_snapshot": preview.input_snapshot,
            "character_count": preview.character_count,
            "expires_at": iso(preview.expires_at),
        }

    def generate(self, actor_id: str, preview_id: str, mode: str) -> dict:
        preview = found(
            self.session.get(GenerationPreview, preview_id),
            "PREVIEW_NOT_FOUND",
            "生成预览不存在",
        )
        task = self.task(actor_id, preview.task_id)
        self.require_owner(actor_id, task)
        require(
            preview.actor_id == actor_id, "PREVIEW_OWNER_REQUIRED", "只能确认自己的生成预览", 403
        )
        expires = preview.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=utcnow().tzinfo)
        require(expires > utcnow(), "PREVIEW_EXPIRED", "生成预览已过期，请重新预览", 409)
        run = GenerationRun(
            preview_id=preview.id,
            mode=mode,
            status="pending",
            character_count=preview.character_count,
        )
        self.session.add(run)
        self.session.flush()
        started_event = self.event(
            task.id,
            actor_id,
            "generation_started",
            "generation_run",
            run.id,
            status=EventStatus.STARTED,
            source=EventSource.GENERATOR,
            subject_key=f"generation:{run.id}",
            correlation_id=run.id,
        )
        try:
            generated = DemoGenerator().generate(preview.input_snapshot, mode)
        except DomainError as error:
            run.status = "timed_out" if error.status_code == 504 else "failed"
            run.error_code = error.code
            terminal_status = (
                EventStatus.TIMED_OUT if error.status_code == 504 else EventStatus.FAILED
            )
            self.event(
                task.id,
                actor_id,
                "generation_finished",
                "generation_run",
                run.id,
                {"error_code": error.code},
                status=terminal_status,
                source=EventSource.GENERATOR,
                subject_key=f"generation:{run.id}",
                parent_event_id=started_event.id,
                correlation_id=run.id,
            )
            self.session.flush()
            self.session.commit()
            raise
        run.status = "succeeded"
        self.event(
            task.id,
            actor_id,
            "generation_finished",
            "generation_run",
            run.id,
            status=EventStatus.SUCCEEDED,
            source=EventSource.GENERATOR,
            subject_key=f"generation:{run.id}",
            parent_event_id=started_event.id,
            correlation_id=run.id,
        )
        draft = HandoffDraft(
            task_id=task.id,
            origin="demo_generator",
            sections=generated.sections,
            generation_run_id=run.id,
            edited_by=actor_id,
        )
        self.session.add(draft)
        self.session.flush()
        for item in generated.citations:
            self.session.add(DraftCitation(draft_id=draft.id, **item))
        task.review_state = "draft"
        self.event(task.id, actor_id, "draft_generated", "draft", draft.id)
        self.session.flush()
        return self.draft_dict(draft)

    def create_manual_draft(self, actor_id: str, task_id: str, data: Any) -> dict:
        task = self.task(actor_id, task_id)
        self.require_owner(actor_id, task)
        draft = HandoffDraft(
            task_id=task.id,
            origin="manual",
            sections=data.sections.model_dump(),
            edited_by=actor_id,
        )
        self.session.add(draft)
        self.session.flush()
        self.replace_citations(task, draft, data.citations)
        task.review_state = "draft"
        self.event(task.id, actor_id, "draft_created", "draft", draft.id)
        self.session.flush()
        return self.draft_dict(draft)

    def get_draft(self, actor_id: str, draft_id: str) -> dict:
        draft = found(self.session.get(HandoffDraft, draft_id), "DRAFT_NOT_FOUND", "草稿不存在")
        self.task(actor_id, draft.task_id)
        return self.draft_dict(draft)

    def draft_dict(self, draft: HandoffDraft) -> dict:
        citations = self.session.scalars(
            select(DraftCitation).where(DraftCitation.draft_id == draft.id)
        ).all()
        return {
            "id": draft.id,
            "task_id": draft.task_id,
            "origin": draft.origin,
            "sections": draft.sections,
            "citations": [self.citation_dict(value) for value in citations],
            "revision": draft.revision,
            "edited_by": draft.edited_by,
            "created_at": iso(draft.created_at),
            "updated_at": iso(draft.updated_at),
        }

    def citation_dict(self, citation: DraftCitation | ConfirmedCitation) -> dict:
        version = self.session.get(MaterialVersion, citation.material_version_id)
        material = self.session.get(Material, version.material_id) if version else None
        result = {
            "id": citation.id,
            "section": citation.section,
            "material_version_id": citation.material_version_id,
            "material_title": material.title if material else "未知材料",
            "material_display_no": material.display_no if material else "",
            "version_no": version.version_no if version else None,
            "start_line": citation.start_line,
            "end_line": citation.end_line,
            "quote": citation.quote,
        }
        if isinstance(citation, ConfirmedCitation):
            result.update(
                {
                    "source_material_id": citation.source_material_id,
                    "source_content_hash": citation.source_content_hash,
                    "quote_hash": citation.quote_hash,
                    "hash_algorithm": citation.hash_algorithm,
                }
            )
        return result

    def replace_citations(self, task: Task, draft: HandoffDraft, citations: list[Any]) -> None:
        self.session.execute(delete(DraftCitation).where(DraftCitation.draft_id == draft.id))
        for item in citations:
            version = self.session.scalar(
                select(MaterialVersion)
                .join(Material, Material.id == MaterialVersion.material_id)
                .where(MaterialVersion.id == item.material_version_id, Material.task_id == task.id)
            )
            version = found(
                version,
                "INVALID_CITATION",
                "引用材料不存在或不属于当前任务",
                422,
            )
            try:
                actual = build_quote(version.content or "", item.start_line, item.end_line)
            except ValueError as error:
                raise DomainError("INVALID_CITATION_RANGE", "引用行号超出材料范围", 422) from error
            require(
                actual.strip() == canonicalize_text(item.quote).strip(),
                "CITATION_MISMATCH",
                "引用文本与材料版本不一致",
                422,
            )
            self.session.add(
                DraftCitation(
                    draft_id=draft.id,
                    section=item.section,
                    material_version_id=item.material_version_id,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    quote=item.quote,
                )
            )

    def update_draft(self, actor_id: str, draft_id: str, data: Any) -> dict:
        draft = found(self.session.get(HandoffDraft, draft_id), "DRAFT_NOT_FOUND", "草稿不存在")
        task = self.task(actor_id, draft.task_id)
        self.require_owner(actor_id, task)
        require(
            draft.revision == data.expected_revision,
            "STALE_REVISION",
            "草稿已有新版本，请刷新",
            409,
        )
        draft.sections = data.sections.model_dump()
        draft.revision += 1
        draft.edited_by = actor_id
        self.replace_citations(task, draft, data.citations)
        task.review_state = "draft"
        self.event(task.id, actor_id, "draft_saved", "draft", draft.id)
        self.session.flush()
        return self.draft_dict(draft)

    def confirm_draft(self, actor_id: str, draft_id: str, expected_revision: int) -> dict:
        draft = found(self.session.get(HandoffDraft, draft_id), "DRAFT_NOT_FOUND", "草稿不存在")
        task = self.task(actor_id, draft.task_id)
        self.require_owner(actor_id, task)
        require(
            draft.revision == expected_revision, "STALE_REVISION", "草稿已有新版本，请刷新", 409
        )
        require(
            all(str(draft.sections.get(key, "")).strip() for key in SECTION_KEYS),
            "INCOMPLETE_HANDOFF",
            "五项交接内容必须全部填写",
            422,
        )
        last_version = self.session.scalar(
            select(func.max(ConfirmedHandoff.version_no)).where(ConfirmedHandoff.task_id == task.id)
        )
        handoff = ConfirmedHandoff(
            task_id=task.id,
            version_no=int(last_version or 0) + 1,
            task_snapshot={
                "title": task.title,
                "goal": task.goal,
                "acceptance_criteria": task.acceptance_criteria,
            },
            sections=dict(draft.sections),
            confirmed_by=actor_id,
        )
        self.session.add(handoff)
        self.session.flush()
        draft_citations = self.session.scalars(
            select(DraftCitation).where(DraftCitation.draft_id == draft.id)
        ).all()
        for item in draft_citations:
            version = found(
                self.session.get(MaterialVersion, item.material_version_id),
                "INVALID_CITATION",
                "引用材料版本不存在",
                422,
            )
            material = found(
                self.session.get(Material, version.material_id),
                "INVALID_CITATION",
                "引用材料不存在",
                422,
            )
            require(
                material.task_id == task.id,
                "INVALID_CITATION",
                "引用材料不属于当前任务",
                422,
            )
            try:
                actual_quote = build_quote(version.content or "", item.start_line, item.end_line)
            except ValueError as error:
                raise DomainError("INVALID_CITATION_RANGE", "引用行号超出材料范围", 422) from error
            require(
                actual_quote.strip() == canonicalize_text(item.quote).strip(),
                "CITATION_MISMATCH",
                "引用文本与材料版本不一致",
                422,
            )
            content_hash = sha256_text(version.content or version.url or "")
            require(
                version.content_hash == content_hash,
                "CITATION_MISMATCH",
                "材料内容哈希不一致",
                409,
            )
            self.session.add(
                ConfirmedCitation(
                    handoff_id=handoff.id,
                    section=item.section,
                    material_version_id=item.material_version_id,
                    source_material_id=material.id,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    quote=actual_quote,
                    source_content_hash=content_hash,
                    quote_hash=quote_fingerprint(
                        version.id,
                        item.section,
                        item.start_line,
                        item.end_line,
                        actual_quote,
                    ),
                    hash_algorithm=HASH_ALGORITHM,
                )
            )
        self.expire_pending(task, actor_id, "创建了新的确认版本")
        task.review_state = "confirmed"
        self.event(task.id, actor_id, "handoff_confirmed", "confirmed_handoff", handoff.id)
        self.session.flush()
        return self.confirmed_dict(handoff)

    def confirmed_dict(self, handoff: ConfirmedHandoff) -> dict:
        citations = self.session.scalars(
            select(ConfirmedCitation).where(ConfirmedCitation.handoff_id == handoff.id)
        ).all()
        confirmer = self.session.get(Member, handoff.confirmed_by)
        validation = self._validate_evidence(handoff, citations)
        return {
            "id": handoff.id,
            "task_id": handoff.task_id,
            "version_no": handoff.version_no,
            "task_snapshot": handoff.task_snapshot,
            "sections": handoff.sections,
            "citations": [self.citation_dict(value) for value in citations],
            "evidence_state": validation["state"],
            "confirmed_by": handoff.confirmed_by,
            "confirmed_by_name": confirmer.display_name if confirmer else "未知",
            "confirmed_at": iso(handoff.confirmed_at),
        }

    def _validate_evidence(
        self,
        handoff: ConfirmedHandoff,
        citations: Sequence[ConfirmedCitation] | None = None,
    ) -> dict:
        rows = citations
        if rows is None:
            rows = list(
                self.session.scalars(
                    select(ConfirmedCitation).where(ConfirmedCitation.handoff_id == handoff.id)
                ).all()
            )
        items: list[dict[str, Any]] = []
        states: list[EvidenceState] = []
        for citation in rows:
            state = EvidenceState.CURRENT
            version = self.session.get(MaterialVersion, citation.material_version_id)
            material: Material | None = None
            reason = "引用内容与当前固定版本一致"
            if version is None:
                state = EvidenceState.MISSING
                reason = "固定材料版本不存在"
            else:
                material = self.session.get(Material, version.material_id)
                if (
                    material is None
                    or material.task_id != handoff.task_id
                    or citation.source_material_id != version.material_id
                ):
                    state = EvidenceState.UNAUTHORIZED
                    reason = "引用材料不属于当前任务"
                else:
                    content_hash = sha256_text(version.content or version.url or "")
                    try:
                        quote = build_quote(
                            version.content or "", citation.start_line, citation.end_line
                        )
                    except ValueError:
                        quote = ""
                    expected_quote_hash = quote_fingerprint(
                        version.id,
                        citation.section,
                        citation.start_line,
                        citation.end_line,
                        quote,
                    )
                    if (
                        citation.hash_algorithm != HASH_ALGORITHM
                        or version.content_hash != content_hash
                        or citation.source_content_hash != content_hash
                        or canonicalize_text(citation.quote) != quote
                        or citation.quote_hash != expected_quote_hash
                    ):
                        state = EvidenceState.MISMATCH
                        reason = "固定正文、行号或哈希不一致"
                    else:
                        latest = self.session.scalar(
                            select(func.max(MaterialVersion.version_no)).where(
                                MaterialVersion.material_id == material.id
                            )
                        )
                        if int(latest or 0) > version.version_no:
                            state = EvidenceState.STALE
                            reason = "被引用材料已有更新版本"
            states.append(state)
            items.append(
                {
                    "citation_id": citation.id,
                    "material_version_id": citation.material_version_id,
                    "state": state.value,
                    "reason": reason,
                }
            )
        overall = aggregate_evidence(states)
        return {
            "confirmed_handoff_id": handoff.id,
            "task_id": handoff.task_id,
            "state": overall.value,
            "items": items,
        }

    def evidence_validation(self, actor_id: str, handoff_id: str) -> dict:
        handoff = found(
            self.session.get(ConfirmedHandoff, handoff_id),
            "CONFIRMED_HANDOFF_NOT_FOUND",
            "确认版本不存在",
        )
        self.task(actor_id, handoff.task_id)
        return self._validate_evidence(handoff)

    def create_request(self, actor_id: str, task_id: str, data: Any) -> dict:
        task = self.task(actor_id, task_id)
        self.require_owner(actor_id, task)
        self.membership(data.recipient_id, task.project_id)
        require(data.recipient_id != actor_id, "SELF_HANDOFF", "不能把任务交接给自己", 422)
        handoff = found(
            self.session.get(ConfirmedHandoff, data.confirmed_handoff_id),
            "INVALID_CONFIRMED_VERSION",
            "确认版本不存在或不属于当前任务",
            422,
        )
        require(
            handoff.task_id == task.id,
            "INVALID_CONFIRMED_VERSION",
            "确认版本不存在或不属于当前任务",
            422,
        )
        latest = self.session.scalar(
            select(ConfirmedHandoff)
            .where(ConfirmedHandoff.task_id == task.id)
            .order_by(ConfirmedHandoff.version_no.desc())
            .limit(1)
        )
        require(
            latest is not None and latest.id == handoff.id,
            "STALE_HANDOFF",
            "必须使用最新确认版本",
            409,
        )
        evidence = self._validate_evidence(handoff)
        if evidence["state"] == EvidenceState.STALE.value:
            raise DomainError(
                "STALE_EVIDENCE",
                "交接引用的材料已有新版本，请重新审核",
                409,
                evidence,
            )
        if evidence["state"] != EvidenceState.CURRENT.value:
            raise DomainError(
                "INVALID_EVIDENCE",
                "交接引用已缺失、失配或越权，不能发起",
                409,
                evidence,
            )
        pending = self.session.scalar(
            select(HandoffRequest).where(
                HandoffRequest.task_id == task.id, HandoffRequest.status == "pending"
            )
        )
        require(pending is None, "PENDING_REQUEST_EXISTS", "任务已有待处理请求", 409)
        request = HandoffRequest(
            task_id=task.id,
            confirmed_handoff_id=handoff.id,
            sender_id=actor_id,
            recipient_id=data.recipient_id,
        )
        self.session.add(request)
        self.session.flush()
        self.event(task.id, actor_id, "handoff_requested", "handoff_request", request.id)
        return self.request_detail(actor_id, request.id)

    def request_summary(self, request: HandoffRequest) -> dict:
        sender = self.session.get(Member, request.sender_id)
        recipient = self.session.get(Member, request.recipient_id)
        return {
            "id": request.id,
            "task_id": request.task_id,
            "confirmed_handoff_id": request.confirmed_handoff_id,
            "sender_id": request.sender_id,
            "sender_name": sender.display_name if sender else "未知",
            "recipient_id": request.recipient_id,
            "recipient_name": recipient.display_name if recipient else "未知",
            "status": request.status,
            "reason": request.reason,
            "revision": request.revision,
            "created_at": iso(request.created_at),
            "updated_at": iso(request.updated_at),
        }

    def request_detail(self, actor_id: str, request_id: str) -> dict:
        request = found(
            self.session.get(HandoffRequest, request_id),
            "REQUEST_NOT_FOUND",
            "交接请求不存在",
        )
        task = self.task(actor_id, request.task_id)
        handoff = found(
            self.session.get(ConfirmedHandoff, request.confirmed_handoff_id),
            "CONFIRMED_HANDOFF_NOT_FOUND",
            "请求绑定的确认版本不存在",
            500,
        )
        result = self.request_summary(request)
        result["task"] = self.task_summary(task)
        result["confirmed_handoff"] = self.confirmed_dict(handoff)
        receipt = self.session.scalar(
            select(HandoffReceipt).where(HandoffReceipt.request_id == request.id)
        )
        result["receipt"] = (
            {
                "id": receipt.id,
                "recipient_id": receipt.recipient_id,
                "accepted_at": iso(receipt.accepted_at),
            }
            if receipt
            else None
        )
        return result

    def request_action(
        self,
        actor_id: str,
        request_id: str,
        expected_revision: int,
        status: str,
        reason: str,
    ) -> dict:
        request = found(
            self.session.get(HandoffRequest, request_id),
            "REQUEST_NOT_FOUND",
            "交接请求不存在",
        )
        task = self.task(actor_id, request.task_id)
        require(request.recipient_id == actor_id, "RECIPIENT_REQUIRED", "仅指定接手者可操作", 403)
        require(request.status == "pending", "REQUEST_NOT_PENDING", "请求已不再待处理", 409)
        require(
            request.revision == expected_revision, "STALE_REVISION", "请求已有新状态，请刷新", 409
        )
        request.status = status
        request.reason = reason
        request.revision += 1
        self.event(
            task.id,
            actor_id,
            f"handoff_{status}",
            "handoff_request",
            request.id,
            {"reason": reason},
        )
        self.session.flush()
        return self.request_detail(actor_id, request.id)

    def accept(self, actor_id: str, request_id: str, expected_revision: int) -> dict:
        request = found(
            self.session.get(HandoffRequest, request_id),
            "REQUEST_NOT_FOUND",
            "交接请求不存在",
        )
        task = self.task(actor_id, request.task_id)
        if request.status == "accepted":
            receipt = self.session.scalar(
                select(HandoffReceipt).where(HandoffReceipt.request_id == request.id)
            )
            receipt = found(receipt, "INCONSISTENT_RECEIPT", "接收记录不完整", 500)
            return self.request_detail(actor_id, request.id)
        require(request.recipient_id == actor_id, "RECIPIENT_REQUIRED", "仅指定接手者可接收", 403)
        self.membership(actor_id, task.project_id)
        handoff = found(
            self.session.get(ConfirmedHandoff, request.confirmed_handoff_id),
            "CONFIRMED_HANDOFF_NOT_FOUND",
            "请求绑定的确认版本不存在",
            409,
        )
        evidence = self._validate_evidence(handoff)
        if evidence["state"] == EvidenceState.STALE.value:
            raise DomainError(
                "STALE_EVIDENCE",
                "交接引用的材料已有新版本，请重新审核并发起",
                409,
                evidence,
            )
        require(request.status == "pending", "REQUEST_NOT_PENDING", "请求已不再待处理", 409)
        require(
            request.revision == expected_revision, "STALE_REVISION", "请求已有新状态，请刷新", 409
        )
        if evidence["state"] != EvidenceState.CURRENT.value:
            raise DomainError(
                "INVALID_EVIDENCE",
                "交接引用已缺失、失配或越权，不能接收",
                409,
                evidence,
            )
        changed = self.session.execute(
            update(HandoffRequest)
            .where(
                HandoffRequest.id == request.id,
                HandoffRequest.status == "pending",
                HandoffRequest.revision == expected_revision,
            )
            .values(status="accepted", revision=expected_revision + 1, updated_at=utcnow())
        )
        require(
            getattr(changed, "rowcount", 0) == 1, "ACCEPT_CONFLICT", "请求已被其他操作处理", 409
        )
        self.session.add(HandoffReceipt(request_id=request.id, recipient_id=actor_id))
        owner_changed = self.session.execute(
            update(Task)
            .where(Task.id == task.id, Task.owner_id == request.sender_id)
            .values(owner_id=actor_id, revision=Task.revision + 1, updated_at=utcnow())
        )
        require(
            getattr(owner_changed, "rowcount", 0) == 1,
            "OWNER_CHANGED",
            "任务负责人已变化，不能接收旧请求",
            409,
        )
        self.event(task.id, actor_id, "handoff_accepted", "handoff_request", request.id)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise DomainError("ACCEPT_CONFLICT", "请求已被接收", 409) from error
        self.session.expire_all()
        return self.request_detail(actor_id, request.id)

    def expire_pending(self, task: Task, actor_id: str, reason: str) -> None:
        pending = self.session.scalars(
            select(HandoffRequest).where(
                HandoffRequest.task_id == task.id, HandoffRequest.status == "pending"
            )
        ).all()
        for request in pending:
            request.status = "expired"
            request.reason = reason
            request.revision += 1
            self.event(
                task.id,
                actor_id,
                "handoff_expired",
                "handoff_request",
                request.id,
                {"reason": reason},
            )
        if pending:
            task.review_state = "needs_review"

    def event_dict(self, row: TaskEvent) -> dict:
        actor = self.session.get(Member, row.actor_id)
        parent = self.session.get(TaskEvent, row.parent_event_id) if row.parent_event_id else None
        return {
            "id": row.id,
            "event_ref": row.event_ref,
            "task_id": row.task_id,
            "seq": row.seq,
            "event_type": row.event_type,
            "status": row.status,
            "lifecycle": row.lifecycle,
            "subject_key": row.subject_key,
            "parent_event_ref": parent.event_ref if parent else None,
            "correlation_id": row.correlation_id,
            "source": row.source,
            "schema_version": row.schema_version,
            "actor_id": row.actor_id,
            "actor_name": actor.display_name if actor else "未知",
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "details": row.details,
            "created_at": iso(row.created_at),
        }

    def history(self, actor_id: str, task_id: str, after_seq: int = 0) -> list[dict]:
        self.task(actor_id, task_id)
        return [self.event_dict(row) for row in self.events.list_for_task(task_id, after_seq)]

    def event_detail(self, actor_id: str, event_ref: str) -> dict:
        row = found(self.events.get_by_ref(event_ref), "EVENT_NOT_FOUND", "事件不存在")
        self.task(actor_id, row.task_id)
        return self.event_dict(row)
