from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .enums import EventLifecycle, EventStatus

TERMINAL_STATUSES = frozenset(
    {
        EventStatus.SUCCEEDED,
        EventStatus.FAILED,
        EventStatus.CANCELLED,
        EventStatus.TIMED_OUT,
        EventStatus.NOT_EXECUTED,
    }
)


@dataclass(frozen=True)
class EventFact:
    event_ref: str
    task_id: str
    seq: int
    status: EventStatus
    lifecycle: EventLifecycle = EventLifecycle.ACTIVE
    subject_key: str | None = None
    parent_event_ref: str | None = None
    correlation_id: str | None = None


def classify_execution(start: EventFact, finish: EventFact | None) -> EventStatus:
    """Return the proven outcome of a start/finish pair without optimistic inference."""
    if start.status != EventStatus.STARTED:
        return start.status
    if finish is None:
        return EventStatus.UNKNOWN
    related = finish.parent_event_ref == start.event_ref or (
        bool(start.correlation_id) and finish.correlation_id == start.correlation_id
    )
    if not related or finish.task_id != start.task_id:
        return EventStatus.UNKNOWN
    return finish.status if finish.status in TERMINAL_STATUSES else EventStatus.UNKNOWN


def validate_chain(events: Iterable[EventFact]) -> list[str]:
    rows = sorted(events, key=lambda value: (value.task_id, value.seq))
    by_ref = {value.event_ref: value for value in rows}
    errors: list[str] = []
    seen_seq: set[tuple[str, int]] = set()
    for event in rows:
        seq_key = (event.task_id, event.seq)
        if seq_key in seen_seq:
            errors.append(f"duplicate-seq:{event.task_id}:{event.seq}")
        seen_seq.add(seq_key)
        if event.parent_event_ref:
            parent = by_ref.get(event.parent_event_ref)
            if parent is None:
                errors.append(f"missing-parent:{event.event_ref}")
            elif parent.task_id != event.task_id:
                errors.append(f"cross-task-parent:{event.event_ref}")
            elif parent.seq >= event.seq:
                errors.append(f"non-causal-parent:{event.event_ref}")
    return errors


def reduce_subject(events: Iterable[EventFact], subject_key: str) -> EventLifecycle | None:
    matching = sorted(
        (value for value in events if value.subject_key == subject_key),
        key=lambda value: value.seq,
    )
    return matching[-1].lifecycle if matching else None
