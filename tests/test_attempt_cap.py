from test_leases import expire, worker
from test_workflow import balance, reserve

from agentix.models import Agent


def test_attempt_cap_preserves_live_lease_skips_exhausted_and_allows_refund(
    client, app, participants
):
    p = participants
    with app.state.sessions.begin() as db:
        db.get(Agent, p["agent"]["id"]).capacity = 2
    task = reserve(client, p, price=20).json()["id"]
    for attempt in range(1, 6):
        headers = worker(p, f"attempt-{attempt}-token-12345678901234567890")
        response = client.post(f"/v1/tasks/{task}/start", headers=headers, json={})
        assert response.status_code == 200
        assert response.json()["attempts"] == attempt
        assert response.json()["attempt_limit"] == 5
        if attempt < 5:
            expire(app, task)
    assert client.post(f"/v1/tasks/{task}/start", headers=headers, json={}).status_code == 200
    assert client.post(f"/v1/tasks/{task}/heartbeat", headers=headers, json={}).status_code == 200
    assert client.get("/v1/creator/recovery", headers=p["buyer"]).json() == []
    expire(app, task)
    queue = client.get("/v1/creator/recovery?limit=1", headers=p["buyer"]).json()
    assert [t["id"] for t in queue] == [task]
    assert client.get("/v1/creator/recovery?offset=1", headers=p["buyer"]).json() == []
    for auth in (p["seller"], p["outsider"]):
        assert client.get("/v1/creator/recovery", headers=auth).json() == []
    assert client.get("/v1/creator/recovery", headers=p["agent_auth"]).status_code == 403
    for query in ("limit=0", "limit=101", "offset=-1", "offset=abc"):
        assert client.get("/v1/creator/recovery?" + query, headers=p["buyer"]).status_code == 422
    before = client.get(f"/v1/tasks/{task}/events", headers=p["buyer"]).json()
    rejected = client.post(
        f"/v1/tasks/{task}/start",
        headers=worker(p, "sixth-token-123456789012345678901234"),
        json={},
    )
    assert rejected.status_code == 409
    assert "attempt limit" in rejected.json()["detail"]
    assert client.get(f"/v1/tasks/{task}/events", headers=p["buyer"]).json() == before
    assert (
        client.post(
            "/v1/tasks/claim", headers=worker(p, "empty-token-123456789012345678901234"), json={}
        ).status_code
        == 204
    )
    next_task = reserve(client, p, key="next", price=20).json()["id"]
    assert (
        client.post(
            "/v1/tasks/claim", headers=worker(p, "next-token-1234567890123456789012345"), json={}
        ).json()["id"]
        == next_task
    )
    assert client.post(f"/v1/tasks/{task}/cancel", headers=p["buyer"]).status_code == 200
    assert client.get("/v1/creator/recovery", headers=p["buyer"]).json() == []
    assert balance(client, p["buyer"], "project") == 680
    assert balance(client, p["seller"], "earnings") == 0
