from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def config_for(database: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    return config


def test_migration_round_trip_uses_real_revisions(tmp_path):
    database = tmp_path / "migration.db"
    config = config_for(database)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert {item["name"] for item in inspect(engine).get_columns("task_events")} >= {
        "event_ref",
        "seq",
        "status",
        "lifecycle",
    }
    assert {item["name"] for item in inspect(engine).get_columns("confirmed_citations")} >= {
        "source_content_hash",
        "quote_hash",
    }
    engine.dispose()

    command.downgrade(config, "0001_initial")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert "event_ref" not in {item["name"] for item in inspect(engine).get_columns("task_events")}
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO members (id, display_name, role_label, created_at) "
                "VALUES ('m1', 'A', 'owner', '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO projects (id, name, description, owner_id, created_at) "
                "VALUES ('p1', 'P', '', 'm1', '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks (id, project_id, display_no, title, goal, description, "
                "acceptance_criteria, progress, review_state, owner_id, revision, created_at, "
                "updated_at) VALUES ('t1', 'p1', 'T-1', 'T', 'G', '', 'A', 'in_progress', "
                "'confirmed', 'm1', 1, '2026-01-01', '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO materials (id, task_id, display_no, kind, title, source_note, "
                "created_by, created_at) VALUES ('mat1', 't1', 'S-1', 'text', 'M', '', 'm1', "
                "'2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO material_versions (id, material_id, version_no, content, url, "
                "content_hash, created_by, created_at) VALUES ('mv1', 'mat1', 1, 'line one', "
                "NULL, 'legacy', 'm1', '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO confirmed_handoffs (id, task_id, version_no, task_snapshot, "
                "sections, confirmed_by, confirmed_at) VALUES ('h1', 't1', 1, '{}', '{}', "
                "'m1', '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO confirmed_citations (id, handoff_id, section, material_version_id, "
                "start_line, end_line, quote) VALUES ('c1', 'h1', 'completed', 'mv1', 1, 1, "
                "'line one')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO task_events (id, task_id, actor_id, event_type, entity_type, "
                "entity_id, details, created_at) VALUES ('e1', 't1', 'm1', 'task_created', "
                "'task', 't1', '{}', '2026-01-01')"
            )
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    assert "event_ref" in {item["name"] for item in inspect(engine).get_columns("task_events")}
    with engine.connect() as connection:
        event = (
            connection.execute(
                text("SELECT event_ref, seq, status, source FROM task_events WHERE id='e1'")
            )
            .mappings()
            .one()
        )
        assert dict(event) == {
            "event_ref": "evt:e1",
            "seq": 1,
            "status": "succeeded",
            "source": "migration",
        }
        citation = (
            connection.execute(
                text(
                    "SELECT source_material_id, source_content_hash, quote_hash, hash_algorithm "
                    "FROM confirmed_citations WHERE id='c1'"
                )
            )
            .mappings()
            .one()
        )
        assert citation["source_material_id"] == "mat1"
        assert len(citation["source_content_hash"]) == 64
        assert len(citation["quote_hash"]) == 64
        assert citation["hash_algorithm"] == "sha256-v1"
    engine.dispose()
