from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from test_workflow import balance, complete, reserve

from agentix.models import Entry, Journal


def test_close_refunds_once_and_prevents_new_work(client, participants, app):
    p = participants
    project_id = p["project"]["id"]
    endpoint = f"/v1/projects/{project_id}/close"
    assert client.post(endpoint, headers=p["agent_auth"]).status_code == 403
    assert client.post(endpoint, headers=p["outsider"]).status_code == 404
    task = reserve(client, p).json()
    assert client.post(endpoint, headers=p["buyer"]).status_code == 409
    complete(client, p, task["id"])
    assert client.post(endpoint, headers=p["buyer"]).status_code == 409
    client.post(f"/v1/tasks/{task['id']}/accept", headers=p["buyer"]).raise_for_status()
    for _ in range(2):
        result = client.post(endpoint, headers=p["buyer"])
        assert result.status_code == 200
        assert result.json() == {"id": project_id, "closed": True, "refunded_credits": 500}
    assert balance(client, p["buyer"], "spendable") == 800
    assert balance(client, p["seller"], "earnings") == 200
    assert reserve(client, p, key="after-close").status_code == 409
    assert client.get(f"/v1/projects/{project_id}/matches", headers=p["buyer"]).status_code == 409
    assert client.get(f"/v1/projects/{project_id}", headers=p["buyer"]).json()["closed"] is True
    assert not any(
        x["id"] == project_id
        for x in client.get("/v1/marketplace/projects", headers=p["buyer"]).json()
    )
    with app.state.sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Journal)
                .where(Journal.operation == "project_closure")
            )
            == 1
        )
        assert db.scalar(select(func.sum(Entry.amount))) == 0


def test_concurrent_close_or_assignment_never_spends_refunded_credits(client, participants, app):
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    p = participants
    endpoint = f"/v1/projects/{p['project']['id']}/close"
    with ThreadPoolExecutor(max_workers=2) as pool:
        closing = pool.submit(client.post, endpoint, headers=p["buyer"])
        assigning = pool.submit(reserve, client, p)
        statuses = closing.result().status_code, assigning.result().status_code
    assert statuses in [(200, 409), (409, 201)]
    if statuses[0] == 200:
        assert balance(client, p["buyer"], "spendable") == 1000
        assert balance(client, p["buyer"], "task") == 0
    else:
        assert balance(client, p["buyer"], "spendable") == 300
        assert balance(client, p["buyer"], "task") == 200


def test_concurrent_close_refunds_once(client, participants, app):
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    p = participants
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(
            pool.map(
                lambda _: client.post(
                    f"/v1/projects/{p['project']['id']}/close", headers=p["buyer"]
                ),
                range(5),
            )
        )
    assert all(r.status_code == 200 and r.json()["refunded_credits"] == 700 for r in results)
    assert balance(client, p["buyer"], "spendable") == 1000


def test_fully_spent_project_closes_without_zero_value_transfer(client, participants):
    p = participants
    task = reserve(client, p, price=700).json()
    complete(client, p, task["id"])
    client.post(f"/v1/tasks/{task['id']}/accept", headers=p["buyer"]).raise_for_status()
    result = client.post(f"/v1/projects/{p['project']['id']}/close", headers=p["buyer"])
    assert result.status_code == 200
    assert result.json()["refunded_credits"] == 0
    assert balance(client, p["buyer"], "spendable") == 300


def test_ai_project_refund_does_not_replenish_agent_allowance(client, participants):
    p = participants
    client.post(
        f"/v1/admin/owners/{p['seller_id']}/test-funding",
        headers={"Authorization": "Bearer test-admin", "Idempotency-Key": "ai-close-funding"},
        json={"amount": 500},
    ).raise_for_status()
    client.patch(
        f"/v1/agents/{p['agent']['id']}/allowance",
        headers=p["seller"],
        json={"project_allowance": 100},
    ).raise_for_status()
    project = client.post(
        "/v1/projects",
        headers={**p["agent_auth"], "Idempotency-Key": "ai-close"},
        json={"title": "AI project", "budget": 100},
    ).json()
    endpoint = f"/v1/projects/{project['id']}/close"
    assert client.post(endpoint, headers=p["agent_auth"]).status_code == 403
    assert client.post(endpoint, headers=p["seller"]).status_code == 200
    assert balance(client, p["seller"], "spendable") == 500
    assert (
        client.get("/v1/agent/overview", headers=p["agent_auth"]).json()["allowance_remaining"] == 0
    )
