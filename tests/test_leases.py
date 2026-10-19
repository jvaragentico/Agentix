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


def test_history_pagination_is_scoped_and_recovers_in_attempt_order(client, app, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]
    client.post("/v1/tasks/claim", headers=worker(p), json={}).raise_for_status()
    expire(app, task_id)
    assert client.post(f"/v1/tasks/{task_id}/start", headers=worker(p), json={}).status_code == 409
    client.post("/v1/tasks/claim", headers=worker(p, SECOND), json={}).raise_for_status()
    history = client.get(f"/v1/tasks/{task_id}/events", headers=p["buyer"]).json()
    assert [e["kind"] for e in history] == ["reserved", "claimed", "lease_expired", "claimed"]
    assert history[-1]["attempt"] == 2
    page = client.get(f"/v1/tasks/{task_id}/events?limit=2&offset=2", headers=p["agent_auth"])
    assert page.json() == history[2:4]
    for suffix in ("?limit=101", "?offset=-1"):
        assert (
            client.get(f"/v1/tasks/{task_id}/events{suffix}", headers=p["buyer"]).status_code == 422
        )
    assert client.get(f"/v1/tasks/{task_id}/events", headers=p["outsider"]).status_code == 404
    assert FIRST not in str(history) and SECOND not in str(history)


def test_admin_history_is_read_only_bounded_and_admin_scoped(client, app, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]
    client.post("/v1/tasks/claim", headers=worker(p), json={}).raise_for_status()
    expire(app, task_id)
    client.post("/v1/tasks/claim", headers=worker(p, SECOND), json={}).raise_for_status()
    endpoint = f"/v1/admin/tasks/{task_id}/events"
    admin = {"Authorization": "Bearer test-admin"}
    before = client.get(f"/v1/tasks/{task_id}", headers=p["buyer"]).json()
    wallet = client.get("/v1/wallet", headers=p["buyer"]).json()
    expected = client.get(f"/v1/tasks/{task_id}/events", headers=p["buyer"]).json()
    response = client.get(endpoint, headers=admin)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == expected
    assert set(expected[0]) == {
        "id",
        "kind",
        "attempt",
        "actor_owner_id",
        "actor_agent_id",
        "created_at",
    }
    assert client.get(endpoint + "?limit=2&offset=2", headers=admin).json() == expected[2:4]
    assert client.get(endpoint + "?offset=100", headers=admin).json() == []
    for suffix in ("?limit=0", "?limit=101", "?offset=-1", "?offset=9007199254740992"):
        assert client.get(endpoint + suffix, headers=admin).status_code == 422
    for auth in (p["buyer"], p["agent_auth"], p["outsider"], {}):
        assert client.get(endpoint, headers=auth).status_code in (401, 403)
        assert client.get("/v1/admin/tasks/missing/events", headers=auth).status_code in (401, 403)
    assert client.get("/v1/admin/tasks/missing/events", headers=admin).status_code == 404
    assert client.get(f"/v1/tasks/{task_id}", headers=p["buyer"]).json() == before
    assert client.get("/v1/wallet", headers=p["buyer"]).json() == wallet
    assert client.get(endpoint, headers=admin).json() == expected
