from sqlalchemy import select, text

from app.demo_data import MATERIAL_VERSION_ID, PROJECT_ID
from app.models import ConfirmedCitation, Material, MaterialVersion, Task

from ..conftest import headers
from ..test_api_flow import create_request


def test_unreferenced_material_does_not_stale_confirmation(client, ids):
    request = create_request(client, ids)
    handoff_id = request["confirmed_handoff_id"]
    task_id = request["task_id"]
    added = client.post(
        f"/api/v1/tasks/{task_id}/materials/text",
        headers=headers(ids["a"]),
        json={"title": "独立记录", "source_note": "未引用", "content": "不影响确认版本"},
    )
    assert added.status_code == 201
    validation = client.get(
        f"/api/v1/confirmed-handoffs/{handoff_id}/evidence-validation",
        headers=headers(ids["a"]),
    )
    assert validation.json()["state"] == "current"


def test_content_tampering_is_mismatch_and_blocks_accept(client, session_factory, ids):
    request = create_request(client, ids)
    with session_factory() as session:
        version = session.scalar(
            select(MaterialVersion).where(MaterialVersion.id == MATERIAL_VERSION_ID)
        )
        assert version is not None
        version.content = "数据库内容被篡改，但固定哈希未更新。"
        session.commit()

    validation = client.get(
        f"/api/v1/confirmed-handoffs/{request['confirmed_handoff_id']}/evidence-validation",
        headers=headers(ids["b"]),
    )
    assert validation.json()["state"] == "mismatch"
    rejected = client.post(
        f"/api/v1/handoff-requests/{request['id']}/accept",
        headers=headers(ids["b"]),
        json={"expected_revision": request["revision"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "INVALID_EVIDENCE"
    detail = client.get(
        f"/api/v1/handoff-requests/{request['id']}", headers=headers(ids["b"])
    ).json()
    assert detail["status"] == "pending"
    assert detail["receipt"] is None
    assert detail["task"]["owner_id"] == ids["a"]


def test_cross_task_source_is_unauthorized(client, session_factory, ids):
    request = create_request(client, ids)
    with session_factory() as session:
        other_task = Task(
            project_id=PROJECT_ID,
            display_no="T-OTHER",
            title="其他任务",
            goal="隔离",
            acceptance_criteria="不得串用来源",
            owner_id=ids["a"],
        )
        session.add(other_task)
        session.flush()
        other_material = Material(
            task_id=other_task.id,
            display_no="S-OTHER",
            kind="text",
            title="其他材料",
            created_by=ids["a"],
        )
        session.add(other_material)
        session.flush()
        citation = session.scalar(
            select(ConfirmedCitation).where(
                ConfirmedCitation.handoff_id == request["confirmed_handoff_id"]
            )
        )
        assert citation is not None
        citation.source_material_id = other_material.id
        session.commit()
    validation = client.get(
        f"/api/v1/confirmed-handoffs/{request['confirmed_handoff_id']}/evidence-validation",
        headers=headers(ids["a"]),
    ).json()
    assert validation["state"] == "unauthorized"


def test_missing_fixed_version_is_reported_without_leaking_content(client, session_factory, ids):
    request = create_request(client, ids)
    engine = session_factory.kw["bind"]
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.execute(
            text(
                "UPDATE confirmed_citations SET material_version_id='missing-version' "
                "WHERE handoff_id=:handoff_id"
            ),
            {"handoff_id": request["confirmed_handoff_id"]},
        )
        connection.commit()
    response = client.get(
        f"/api/v1/confirmed-handoffs/{request['confirmed_handoff_id']}/evidence-validation",
        headers=headers(ids["a"]),
    )
    assert response.status_code == 200
    assert response.json()["state"] == "missing"
    assert "quote" not in response.text
