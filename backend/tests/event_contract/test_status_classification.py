from app.domain.enums import EventLifecycle, EventStatus
from app.domain.events import EventFact, classify_execution, reduce_subject, validate_chain


def fact(
    ref: str,
    seq: int,
    status: EventStatus,
    *,
    task: str = "task-1",
    parent: str | None = None,
    correlation: str | None = None,
    lifecycle: EventLifecycle = EventLifecycle.ACTIVE,
    subject: str | None = None,
) -> EventFact:
    return EventFact(
        event_ref=ref,
        task_id=task,
        seq=seq,
        status=status,
        parent_event_ref=parent,
        correlation_id=correlation,
        lifecycle=lifecycle,
        subject_key=subject,
    )


def test_unfinished_or_unrelated_start_is_unknown():
    start = fact("evt:start", 1, EventStatus.STARTED, correlation="run-1")
    assert classify_execution(start, None) == EventStatus.UNKNOWN
    unrelated = fact("evt:finish", 2, EventStatus.SUCCEEDED, correlation="run-2")
    assert classify_execution(start, unrelated) == EventStatus.UNKNOWN


def test_terminal_statuses_are_preserved_for_related_finish():
    start = fact("evt:start", 1, EventStatus.STARTED)
    for status in (
        EventStatus.SUCCEEDED,
        EventStatus.FAILED,
        EventStatus.CANCELLED,
        EventStatus.TIMED_OUT,
        EventStatus.NOT_EXECUTED,
    ):
        finish = fact(f"evt:{status}", 2, status, parent=start.event_ref)
        assert classify_execution(start, finish) == status


def test_chain_and_lifecycle_reduction_keep_history():
    events = [
        fact("evt:1", 1, EventStatus.SUCCEEDED, subject="decision"),
        fact(
            "evt:2",
            2,
            EventStatus.SUCCEEDED,
            lifecycle=EventLifecycle.WITHDRAWN,
            subject="decision",
            parent="evt:1",
        ),
        fact(
            "evt:3",
            3,
            EventStatus.SUCCEEDED,
            lifecycle=EventLifecycle.REOPENED,
            subject="decision",
            parent="evt:2",
        ),
    ]
    assert validate_chain(events) == []
    assert reduce_subject(events, "decision") == EventLifecycle.REOPENED
    broken = fact("evt:4", 4, EventStatus.SUCCEEDED, task="task-2", parent="evt:1")
    assert "cross-task-parent:evt:4" in validate_chain([*events, broken])
