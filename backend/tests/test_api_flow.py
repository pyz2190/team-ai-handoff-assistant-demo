from app.demo_data import MATERIAL_ID, MATERIAL_VERSION_ID, PROJECT_ID, TASK_ID

from .conftest import headers

SECTIONS = {
    "completed": "已完成审核接口。",
    "decisions": "采用幂等键避免重复。",
    "verification": "测试输出 18 passed。",
    "open_issues": "窄屏仍需调整。",
    "next_steps": "建议修复窄屏并补测。",
}


def confirm_demo_handoff(client, ids):
    preview = client.post(
        f"/api/v1/tasks/{TASK_ID}/generation-previews",
        headers=headers(ids["a"]),
        json={"material_version_ids": [MATERIAL_VERSION_ID]},
    )
    assert preview.status_code == 201, preview.text
    draft = client.post(
        f"/api/v1/generation-previews/{preview.json()['id']}/runs",
        headers=headers(ids["a"]),
        json={"mode": "normal"},
    )
    assert draft.status_code == 201, draft.text
    confirmed = client.post(
        f"/api/v1/drafts/{draft.json()['id']}/confirm",
        headers=headers(ids["a"]),
        json={"expected_revision": draft.json()["revision"]},
    )
    assert confirmed.status_code == 201, confirmed.text
    return confirmed.json()


def create_request(client, ids):
    confirmed = confirm_demo_handoff(client, ids)
    response = client.post(
        f"/api/v1/tasks/{TASK_ID}/handoff-requests",
        headers=headers(ids["a"]),
        json={"confirmed_handoff_id": confirmed["id"], "recipient_id": ids["b"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_identity_and_project_isolation(client, ids):
    assert client.get("/api/v1/projects").status_code == 401
    projects = client.get("/api/v1/projects", headers=headers(ids["a"]))
    assert projects.status_code == 200
    assert projects.json()["items"][0]["id"] == PROJECT_ID
    denied = client.patch(
        f"/api/v1/projects/{PROJECT_ID}/members",
        headers=headers(ids["b"]),
        json={"member_id": ids["c"], "active": False},
    )
    assert denied.status_code == 403


def test_workspace_has_three_independent_states(client, ids):
    task = client.get(f"/api/v1/tasks/{TASK_ID}", headers=headers(ids["a"])).json()
    assert task["progress"] == "in_progress"
    assert task["review_state"] == "draft"
    assert task["request_state"] == "none"
    assert task["materials"][0]["versions"][0]["content"].startswith("已完成")


def test_normal_handoff_is_atomic_and_keeps_progress(client, ids):
    request = create_request(client, ids)
    before = client.get(f"/api/v1/tasks/{TASK_ID}", headers=headers(ids["b"])).json()
    assert before["owner_id"] == ids["a"]
    accepted = client.post(
        f"/api/v1/handoff-requests/{request['id']}/accept",
        headers=headers(ids["b"]),
        json={"expected_revision": request["revision"]},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["receipt"]["recipient_id"] == ids["b"]
    after = client.get(f"/api/v1/tasks/{TASK_ID}", headers=headers(ids["b"])).json()
    assert after["owner_id"] == ids["b"]
    assert after["progress"] == "in_progress"
    assert after["request_state"] == "accepted"
    repeated = client.post(
        f"/api/v1/handoff-requests/{request['id']}/accept",
        headers=headers(ids["b"]),
        json={"expected_revision": request["revision"]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["receipt"]["id"] == accepted.json()["receipt"]["id"]


def test_non_recipient_cannot_accept(client, ids):
    request = create_request(client, ids)
    denied = client.post(
        f"/api/v1/handoff-requests/{request['id']}/accept",
        headers=headers(ids["c"]),
        json={"expected_revision": request["revision"]},
    )
    assert denied.status_code == 403
    task = client.get(f"/api/v1/tasks/{TASK_ID}", headers=headers(ids["a"])).json()
    assert task["owner_id"] == ids["a"]


def test_needs_info_records_reason_without_transfer(client, ids):
    request = create_request(client, ids)
    result = client.post(
        f"/api/v1/handoff-requests/{request['id']}/needs-info",
        headers=headers(ids["b"]),
        json={"expected_revision": request["revision"], "reason": "请补充窄屏截图"},
    )
    assert result.status_code == 200
    assert result.json()["status"] == "needs_info"
    assert result.json()["reason"] == "请补充窄屏截图"
    assert result.json()["receipt"] is None
    assert result.json()["task"]["owner_id"] == ids["a"]


def test_important_task_change_expires_request(client, ids):
    request = create_request(client, ids)
    task = client.get(f"/api/v1/tasks/{TASK_ID}", headers=headers(ids["a"])).json()
    updated = client.patch(
        f"/api/v1/tasks/{TASK_ID}",
        headers=headers(ids["a"]),
        json={"goal": "更新后的目标", "expected_revision": task["revision"]},
    )
    assert updated.status_code == 200
    stale = client.post(
        f"/api/v1/handoff-requests/{request['id']}/accept",
        headers=headers(ids["b"]),
        json={"expected_revision": request["revision"]},
    )
    assert stale.status_code == 409
    detail = client.get(
        f"/api/v1/handoff-requests/{request['id']}", headers=headers(ids["b"])
    ).json()
    assert detail["status"] == "expired"
    assert detail["task"]["owner_id"] == ids["a"]


def test_cited_material_change_expires_but_unreferenced_material_does_not(client, ids):
    request = create_request(client, ids)
    added = client.post(
        f"/api/v1/tasks/{TASK_ID}/materials/text",
        headers=headers(ids["a"]),
        json={"title": "未引用材料", "source_note": "补充", "content": "新的独立记录"},
    )
    assert added.status_code == 201
    still_pending = client.get(
        f"/api/v1/handoff-requests/{request['id']}", headers=headers(ids["b"])
    )
    assert still_pending.json()["status"] == "pending"
    changed = client.post(
        f"/api/v1/materials/{MATERIAL_ID}/versions",
        headers=headers(ids["a"]),
        json={"content": "已完成：内容发生重要变化。"},
    )
    assert changed.status_code == 201
    expired = client.get(f"/api/v1/handoff-requests/{request['id']}", headers=headers(ids["b"]))
    assert expired.json()["status"] == "expired"


def test_generation_failure_does_not_create_draft(client, ids):
    preview = client.post(
        f"/api/v1/tasks/{TASK_ID}/generation-previews",
        headers=headers(ids["a"]),
        json={"material_version_ids": [MATERIAL_VERSION_ID]},
    ).json()
    failed = client.post(
        f"/api/v1/generation-previews/{preview['id']}/runs",
        headers=headers(ids["a"]),
        json={"mode": "error"},
    )
    assert failed.status_code == 500
    workspace = client.get(f"/api/v1/tasks/{TASK_ID}", headers=headers(ids["a"])).json()
    assert workspace["drafts"] == []
    events = client.get(f"/api/v1/tasks/{TASK_ID}/events", headers=headers(ids["a"])).json()[
        "items"
    ]
    generation = [item for item in events if item["entity_type"] == "generation_run"]
    assert [item["status"] for item in generation] == ["started", "failed"]
    assert generation[1]["parent_event_ref"] == generation[0]["event_ref"]


def test_manual_draft_requires_all_sections_for_confirmation(client, ids):
    draft = client.post(
        f"/api/v1/tasks/{TASK_ID}/drafts",
        headers=headers(ids["a"]),
        json={"sections": {**SECTIONS, "verification": ""}, "citations": []},
    )
    assert draft.status_code == 201
    rejected = client.post(
        f"/api/v1/drafts/{draft.json()['id']}/confirm",
        headers=headers(ids["a"]),
        json={"expected_revision": 1},
    )
    assert rejected.status_code == 422
