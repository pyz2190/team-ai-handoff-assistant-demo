from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select

from app.demo_data import MEMBER_A, TASK_ID
from app.models import Task, TaskEvent
from app.repositories import EventRepository


def test_competing_event_appends_get_unique_monotonic_sequences(client, session_factory):
    barrier = Barrier(2)

    def append(label: str) -> int:
        with session_factory() as session:
            barrier.wait()
            row = EventRepository(session).append(
                task_id=TASK_ID,
                actor_id=MEMBER_A,
                event_type="concurrent_check",
                entity_type="test",
                entity_id=label,
            )
            session.commit()
            return row.seq

    with ThreadPoolExecutor(max_workers=2) as pool:
        sequences = sorted(pool.map(append, ("one", "two")))
    assert sequences == [2, 3]
    with session_factory() as session:
        rows = session.scalars(
            select(TaskEvent).where(TaskEvent.task_id == TASK_ID).order_by(TaskEvent.seq)
        ).all()
        assert [row.seq for row in rows] == [1, 2, 3]
        assert len({row.event_ref for row in rows}) == 3
        assert session.get(Task, TASK_ID).event_sequence == 3
