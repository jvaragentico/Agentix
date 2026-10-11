from datetime import UTC, datetime, timedelta

from test_workflow import balance, reserve

from agentix.models import Task

FIRST = "first-worker-token-1234567890123456"
SECOND = "second-worker-token-123456789012345"


def worker(p, token=FIRST):
    return {**p["agent_auth"], "X-Execution-Token": token}


def expire(app, task_id):
    with app.state.sessions.begin() as db:
        db.get(Task, task_id).lease_expires_at = datetime.now(UTC) - timedelta(seconds=10)


def test_claim_is_exclusive_and_replay_is_safe(client, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]
    first = client.post("/v1/tasks/claim", headers=worker(p), json={})
    assert first.status_code == 200 and first.json()["id"] == task_id
    assert first.json()["attempts"] == 1
    assert client.post("/v1/tasks/claim", headers=worker(p), json={}).json() == first.json()
    assert client.post("/v1/tasks/claim", headers=worker(p, SECOND), json={}).status_code == 204
    assert (
        client.post(f"/v1/tasks/{task_id}/start", headers=worker(p, SECOND), json={}).status_code
        == 409
    )
    events = client.get(f"/v1/tasks/{task_id}/events", headers=p["buyer"]).json()
    assert sorted(e["kind"] for e in events) == ["claimed", "reserved"]
    assert client.get(f"/v1/tasks/{task_id}/events", headers=p["outsider"]).status_code == 404
    assert "lease_token_hash" not in first.json()


def test_recovery_fences_old_worker_without_moving_credits(client, app, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]
    client.post("/v1/tasks/claim", headers=worker(p), json={})
    expire(app, task_id)
    artifact = {"artifact": {"answer": "result"}}
    assert (
        client.post(f"/v1/tasks/{task_id}/submit", headers=worker(p), json=artifact).status_code
        == 409
    )
    assert (
        client.post(f"/v1/tasks/{task_id}/heartbeat", headers=worker(p), json={}).status_code == 409
    )
    assert client.post("/v1/tasks/claim", headers=worker(p), json={}).status_code == 409
    recovered = client.post("/v1/tasks/claim", headers=worker(p, SECOND), json={})
    assert recovered.status_code == 200 and recovered.json()["attempts"] == 2
    assert balance(client, p["buyer"], "task") == 200
    assert balance(client, p["seller"], "earnings") == 0
    for endpoint in ("submit", "heartbeat"):
        assert (
            client.post(
                f"/v1/tasks/{task_id}/{endpoint}",
                headers=worker(p),
                json=artifact if endpoint == "submit" else {},
            ).status_code
            == 409
        )
    assert (
        client.post(
            f"/v1/tasks/{task_id}/submit", headers=worker(p, SECOND), json=artifact
        ).status_code
        == 200
    )
    for _ in range(2):
        assert client.post(f"/v1/tasks/{task_id}/accept", headers=p["buyer"]).status_code == 200
    assert balance(client, p["seller"], "earnings") == 200
    assert (
        client.post(
            f"/v1/tasks/{task_id}/submit", headers=worker(p, SECOND), json=artifact
        ).status_code
        == 200
    )
    events = client.get(f"/v1/tasks/{task_id}/events", headers=p["buyer"]).json()
    assert sum(e["kind"] == "claimed" for e in events) == 2
    assert sum(e["kind"] == "lease_expired" for e in events) == 1
    assert sum(e["kind"] == "accepted" for e in events) == 1


def test_heartbeat_requires_current_token_and_renews(client, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]
    first = client.post("/v1/tasks/claim", headers=worker(p), json={"lease_seconds": 30}).json()
    assert (
        client.post(
            f"/v1/tasks/{task_id}/heartbeat", headers=worker(p, SECOND), json={}
        ).status_code
        == 409
    )
    good = client.post(
        f"/v1/tasks/{task_id}/heartbeat", headers=worker(p), json={"lease_seconds": 300}
    )
    assert good.status_code == 200
    assert datetime.fromisoformat(good.json()["lease_expires_at"]) > datetime.fromisoformat(
        first["lease_expires_at"]
    )
    assert good.json()["attempts"] == 1


def test_claim_rejects_owner_keys_and_invalid_duration(client, participants):
    p = participants
    assert (
        client.post(
            "/v1/tasks/claim", headers={**p["seller"], "X-Execution-Token": FIRST}, json={}
        ).status_code
        == 403
    )
    assert (
        client.post("/v1/tasks/claim", headers=worker(p), json={"lease_seconds": 10000}).status_code
        == 422
    )
