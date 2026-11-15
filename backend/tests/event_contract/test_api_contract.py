from app.demo_data import MATERIAL_ID, TASK_ID

from ..conftest import headers
from ..test_api_flow import confirm_demo_handoff, create_request


def test_history_exposes_stable_refs_and_after_seq(client, ids):
    confirm_demo_handoff(client, ids)
    response = client.get(f"/api/v1/tasks/{TASK_ID}/events", headers=headers(ids["a"]))
    assert response.status_code == 200
    events = response.json()["items"]
    assert [item["seq"] for item in events] == sorted(item["seq"] for item in events)
    assert len({item["event_ref"] for item in events}) == len(events)
    assert all(item["event_ref"].startswith("evt:") for item in events)
    last = events[-1]
    detail = client.get(f"/api/v1/events/{last['event_ref']}", headers=headers(ids["a"]))
    assert detail.status_code == 200
    assert detail.json()["id"] == last["id"]
    tail = client.get(
        f"/api/v1/tasks/{TASK_ID}/events?after_seq={last['seq']}",
        headers=headers(ids["a"]),
    )
    assert tail.json()["items"] == []


def test_confirmed_evidence_is_current_then_stale(client, ids):
    request = create_request(client, ids)
    handoff_id = request["confirmed_handoff_id"]
    current = client.get(
        f"/api/v1/confirmed-handoffs/{handoff_id}/evidence-validation",
        headers=headers(ids["b"]),
    )
    assert current.status_code == 200
    assert current.json()["state"] == "current"
    assert current.json()["items"]

    changed = client.post(
        f"/api/v1/materials/{MATERIAL_ID}/versions",
        headers=headers(ids["a"]),
        json={"content": "新版本：原有决策需要重新审核。"},
    )
    assert changed.status_code == 201
    stale = client.get(
        f"/api/v1/confirmed-handoffs/{handoff_id}/evidence-validation",
        headers=headers(ids["b"]),
    )
    assert stale.json()["state"] == "stale"
    rejected = client.post(
        f"/api/v1/handoff-requests/{request['id']}/accept",
        headers=headers(ids["b"]),
        json={"expected_revision": request["revision"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "STALE_EVIDENCE"
