from concurrent.futures import ThreadPoolExecutor

import pytest
from test_leases import expire, worker
from test_workflow import balance, reserve


@pytest.fixture(autouse=True)
def require_postgres(app):
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("Concurrent cancellation requires PostgreSQL row locks")


def test_expired_cancellation_refunds_once_and_fences_worker(client, app, participants):
    p = participants
    task = reserve(client, p).json()["id"]
    assert client.post(f"/v1/tasks/{task}/start", headers=worker(p), json={}).status_code == 200
    assert client.post(f"/v1/tasks/{task}/cancel", headers=p["buyer"]).status_code == 409
    expire(app, task)
    for auth in (p["seller"], p["agent_auth"], p["outsider"]):
        assert client.post(f"/v1/tasks/{task}/cancel", headers=auth).status_code in (403, 404)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(f"/v1/tasks/{task}/cancel", headers=p["buyer"]), range(4)
            )
        )
    assert all(r.status_code == 200 for r in responses)
    assert balance(client, p["buyer"], "project") == 700
    assert balance(client, p["seller"], "earnings") == 0
    for action, body in (
        ("heartbeat", {}),
        ("submit", {"artifact": {"text": "Late"}}),
        ("start", {}),
    ):
        assert (
            client.post(f"/v1/tasks/{task}/{action}", headers=worker(p), json=body).status_code
            == 409
        )
    events = client.get(f"/v1/tasks/{task}/events", headers=p["buyer"]).json()
    assert sum(e["kind"] == "cancelled" for e in events) == 1
    assert reserve(client, p, key="replacement").status_code == 201


def test_cancellation_racing_recovery_keeps_funds_consistent(client, app, participants):
    p = participants
    task = reserve(client, p).json()["id"]
    client.post(f"/v1/tasks/{task}/start", headers=worker(p), json={})
    expire(app, task)
    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel = pool.submit(client.post, f"/v1/tasks/{task}/cancel", headers=p["buyer"])
        recover = pool.submit(
            client.post,
            f"/v1/tasks/{task}/start",
            headers=worker(p, "replacement-token-1234567890123456789"),
            json={},
        )
    assert sorted([cancel.result().status_code, recover.result().status_code]) == [200, 409]
    state = client.get(f"/v1/tasks/{task}", headers=p["buyer"]).json()["state"]
    assert balance(client, p["buyer"], "project") == (700 if state == "cancelled" else 500)
    assert balance(client, p["seller"], "earnings") == 0


def test_submitted_and_accepted_work_remain_protected_after_expiry(client, app, participants):
    p = participants
    task = reserve(client, p).json()["id"]
    client.post(f"/v1/tasks/{task}/start", headers=worker(p), json={})
    assert (
        client.post(
            f"/v1/tasks/{task}/submit", headers=worker(p), json={"artifact": {"text": "Done"}}
        ).status_code
        == 200
    )
    expire(app, task)
    assert client.post(f"/v1/tasks/{task}/cancel", headers=p["buyer"]).status_code == 409
    assert client.post(f"/v1/tasks/{task}/accept", headers=p["buyer"]).status_code == 200
    assert client.post(f"/v1/tasks/{task}/cancel", headers=p["buyer"]).status_code == 409
    assert balance(client, p["seller"], "earnings") == 200
