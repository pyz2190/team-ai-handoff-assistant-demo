from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.enums import EventLifecycle, EventSource, EventStatus
from app.domain.errors import DomainError
from app.models import Task, TaskEvent


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append(
        self,
        *,
        task_id: str,
        actor_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any] | None = None,
        status: EventStatus = EventStatus.SUCCEEDED,
        lifecycle: EventLifecycle = EventLifecycle.ACTIVE,
        source: EventSource = EventSource.USER,
        subject_key: str | None = None,
        parent_event_id: str | None = None,
        correlation_id: str | None = None,
    ) -> TaskEvent:
        seq = self.session.scalar(
            update(Task)
            .where(Task.id == task_id)
            .values(event_sequence=Task.event_sequence + 1)
            .returning(Task.event_sequence)
        )
        if seq is None:
            raise DomainError("TASK_NOT_FOUND", "任务不存在", 404)
        row = TaskEvent(
            event_ref=f"evt:{uuid4()}",
            task_id=task_id,
            seq=int(seq),
            actor_id=actor_id,
            event_type=event_type,
            status=status.value,
            lifecycle=lifecycle.value,
            source=source.value,
            subject_key=subject_key,
            parent_event_id=parent_event_id,
            correlation_id=correlation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            schema_version=1,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_for_task(self, task_id: str, after_seq: int = 0) -> list[TaskEvent]:
        return list(
            self.session.scalars(
                select(TaskEvent)
                .where(TaskEvent.task_id == task_id, TaskEvent.seq > after_seq)
                .order_by(TaskEvent.seq)
            ).all()
        )

    def get_by_ref(self, event_ref: str) -> TaskEvent | None:
        return self.session.scalar(select(TaskEvent).where(TaskEvent.event_ref == event_ref))
