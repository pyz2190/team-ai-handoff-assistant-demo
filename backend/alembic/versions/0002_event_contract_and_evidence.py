"""event contract and evidence fingerprints

Revision ID: 0002_event_contract_and_evidence
Revises: 0001_initial
Create Date: 2026-11-15
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op
from app.domain.evidence import HASH_ALGORITHM, quote_fingerprint, sha256_text

revision = "0002_event_contract_and_evidence"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    task_columns = _columns("tasks")
    if "event_sequence" not in task_columns:
        op.add_column(
            "tasks", sa.Column("event_sequence", sa.Integer(), nullable=False, server_default="0")
        )

    event_columns = _columns("task_events")
    event_additions = (
        ("event_ref", sa.String(50), ""),
        ("seq", sa.Integer(), "0"),
        ("status", sa.String(30), "succeeded"),
        ("lifecycle", sa.String(30), "active"),
        ("subject_key", sa.String(160), None),
        ("parent_event_id", sa.String(36), None),
        ("correlation_id", sa.String(36), None),
        ("source", sa.String(30), "migration"),
        ("schema_version", sa.Integer(), "1"),
    )
    for name, type_, default in event_additions:
        if name not in event_columns:
            op.add_column(
                "task_events",
                sa.Column(
                    name,
                    type_,
                    nullable=default is None,
                    server_default=default,
                ),
            )

    bind = op.get_bind()
    event_rows = bind.execute(
        sa.text("SELECT id, task_id FROM task_events ORDER BY task_id, created_at, id")
    ).mappings()
    sequence_by_task: dict[str, int] = {}
    for row in event_rows:
        sequence_by_task[row["task_id"]] = sequence_by_task.get(row["task_id"], 0) + 1
        bind.execute(
            sa.text(
                "UPDATE task_events SET event_ref=:event_ref, seq=:seq, status='succeeded', "
                "lifecycle='active', source='migration', schema_version=1 WHERE id=:id"
            ),
            {
                "event_ref": f"evt:{row['id']}",
                "seq": sequence_by_task[row["task_id"]],
                "id": row["id"],
            },
        )
    for task_id, seq in sequence_by_task.items():
        bind.execute(
            sa.text("UPDATE tasks SET event_sequence=:seq WHERE id=:task_id"),
            {"seq": seq, "task_id": task_id},
        )

    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("task_events")}
    if "uq_task_events_event_ref" not in indexes:
        op.create_index("uq_task_events_event_ref", "task_events", ["event_ref"], unique=True)
    if "uq_task_events_task_seq" not in indexes:
        op.create_index("uq_task_events_task_seq", "task_events", ["task_id", "seq"], unique=True)
    if "ix_task_events_task_created" not in indexes:
        op.create_index(
            "ix_task_events_task_created", "task_events", ["task_id", "created_at"], unique=False
        )
    if "ix_task_events_correlation" not in indexes:
        op.create_index(
            "ix_task_events_correlation", "task_events", ["correlation_id"], unique=False
        )

    citation_columns = _columns("confirmed_citations")
    citation_additions = (
        ("source_material_id", sa.String(36), ""),
        ("source_content_hash", sa.String(64), ""),
        ("quote_hash", sa.String(64), ""),
        ("hash_algorithm", sa.String(20), HASH_ALGORITHM),
    )
    for name, type_, default in citation_additions:
        if name not in citation_columns:
            op.add_column(
                "confirmed_citations",
                sa.Column(name, type_, nullable=False, server_default=default),
            )

    material_rows = bind.execute(
        sa.text("SELECT id, content, url FROM material_versions")
    ).mappings()
    for row in material_rows:
        digest = sha256_text(row["content"] or row["url"] or "")
        bind.execute(
            sa.text("UPDATE material_versions SET content_hash=:digest WHERE id=:id"),
            {"digest": digest, "id": row["id"]},
        )
    citations = bind.execute(
        sa.text(
            "SELECT cc.id, cc.section, cc.material_version_id, cc.start_line, cc.end_line, "
            "cc.quote, mv.material_id, mv.content_hash FROM confirmed_citations cc "
            "JOIN material_versions mv ON mv.id=cc.material_version_id"
        )
    ).mappings()
    for row in citations:
        digest = quote_fingerprint(
            row["material_version_id"],
            row["section"],
            row["start_line"],
            row["end_line"],
            row["quote"],
        )
        bind.execute(
            sa.text(
                "UPDATE confirmed_citations SET source_material_id=:material_id, "
                "source_content_hash=:content_hash, quote_hash=:quote_hash, "
                "hash_algorithm=:algorithm WHERE id=:id"
            ),
            {
                "material_id": row["material_id"],
                "content_hash": row["content_hash"],
                "quote_hash": digest,
                "algorithm": HASH_ALGORITHM,
                "id": row["id"],
            },
        )

    event_foreign_keys = {
        tuple(item["constrained_columns"])
        for item in sa.inspect(bind).get_foreign_keys("task_events")
    }
    if ("parent_event_id",) not in event_foreign_keys:
        with op.batch_alter_table("task_events") as batch:
            batch.create_foreign_key(
                "fk_task_events_parent_event_id",
                "task_events",
                ["parent_event_id"],
                ["id"],
            )
    citation_foreign_keys = {
        tuple(item["constrained_columns"])
        for item in sa.inspect(bind).get_foreign_keys("confirmed_citations")
    }
    if ("source_material_id",) not in citation_foreign_keys:
        with op.batch_alter_table("confirmed_citations") as batch:
            batch.create_foreign_key(
                "fk_confirmed_citations_source_material_id",
                "materials",
                ["source_material_id"],
                ["id"],
            )


def downgrade() -> None:
    citation_columns = _columns("confirmed_citations")
    citation_drops = [
        name
        for name in ("hash_algorithm", "quote_hash", "source_content_hash", "source_material_id")
        if name in citation_columns
    ]
    if citation_drops:
        with op.batch_alter_table("confirmed_citations") as batch:
            for name in citation_drops:
                batch.drop_column(name)

    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("task_events")}
    for name in (
        "ix_task_events_correlation",
        "ix_task_events_task_created",
        "uq_task_events_task_seq",
        "uq_task_events_event_ref",
    ):
        if name in indexes:
            op.drop_index(name, table_name="task_events")
    event_columns = _columns("task_events")
    event_drops = [
        name
        for name in (
            "schema_version",
            "source",
            "correlation_id",
            "parent_event_id",
            "subject_key",
            "lifecycle",
            "status",
            "seq",
            "event_ref",
        )
        if name in event_columns
    ]
    if event_drops:
        with op.batch_alter_table("task_events") as batch:
            for name in event_drops:
                batch.drop_column(name)
    if "event_sequence" in _columns("tasks"):
        with op.batch_alter_table("tasks") as batch:
            batch.drop_column("event_sequence")
