from sqlalchemy import func, select

from agentix.models import Account, Entry, Journal

EXECUTION_TOKEN = "initial-execution-token-1234567890"


def execution_headers(auth):
    return {**auth, "X-Execution-Token": EXECUTION_TOKEN}


def reserve(client, p, key="task", price=200):
    return client.post(
        f"/v1/projects/{p['project']['id']}/tasks",
        headers={**p["buyer"], "Idempotency-Key": key},
        json={
            "agent_id": p["agent"]["id"],
            "skill_id": p["skill"]["id"],
            "instructions": "Review the implementation",
            "acceptance_criteria": "Deliver a review with reproducible findings",
            "price": price,
        },
    )


def balance(client, auth, kind):
    return sum(
        a["balance"]
        for a in client.get("/v1/wallet", headers=auth).json()["accounts"]
        if a["kind"] == kind
    )


def complete(client, p, task_id):
    assert (
        client.post(
            f"/v1/tasks/{task_id}/start", headers=execution_headers(p["agent_auth"]), json={}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/v1/tasks/{task_id}/submit",
            headers=execution_headers(p["agent_auth"]),
            json={"artifact": {"review": "Reviewed; see test evidence"}},
        ).status_code
        == 200
    )


def test_cross_owner_work_settles_once_and_ledger_balances(client, app, participants):
    p = participants
    found = client.get("/v1/agents?skill=code-review", headers=p["buyer"]).json()
    assert [a["id"] for a in found] == [p["agent"]["id"]]
    assert "token_hash" not in found[0] and "api_key" not in found[0]
    result = reserve(client, p)
    assert result.status_code == 201
    task = result.json()
    assert reserve(client, p).json()["id"] == task["id"]
    assert reserve(client, p, price=201).status_code == 409
    assert balance(client, p["buyer"], "project") == 500
    assert balance(client, p["seller"], "earnings") == 0
    assert client.post(f"/v1/tasks/{task['id']}/accept", headers=p["buyer"]).status_code == 409
    complete(client, p, task["id"])
    for _ in range(2):
        accepted = client.post(f"/v1/tasks/{task['id']}/accept", headers=p["buyer"])
        assert accepted.status_code == 200 and accepted.json()["state"] == "accepted"
    assert balance(client, p["seller"], "earnings") == 200
    assert balance(client, p["buyer"], "task") == 0
    with app.state.sessions() as db:
        assert db.scalar(select(func.sum(Account.balance))) == 0
        journal_sums = db.execute(
            select(Entry.journal_id, func.sum(Entry.amount)).group_by(Entry.journal_id)
        ).all()
        assert journal_sums and all(amount == 0 for _, amount in journal_sums)
        assert (
            db.scalar(
                select(func.count())
                .select_from(Journal)
                .where(Journal.operation == "task_acceptance")
            )
            == 1
        )


def test_unauthorized_owners_and_agent_keys_are_isolated(client, participants):
    p = participants
    task = reserve(client, p).json()
    assert client.get(f"/v1/tasks/{task['id']}", headers=p["outsider"]).status_code == 404
    assert client.get(f"/v1/projects/{p['project']['id']}", headers=p["seller"]).status_code == 404
    assert (
        client.post(
            f"/v1/tasks/{task['id']}/start", headers=execution_headers(p["buyer"]), json={}
        ).status_code
        == 403
    )
    assert client.post(f"/v1/tasks/{task['id']}/accept", headers=p["seller"]).status_code == 403
    assert client.get("/v1/wallet", headers=p["agent_auth"]).status_code == 403
    assert (
        client.post(
            "/v1/projects",
            headers={**p["agent_auth"], "Idempotency-Key": "no"},
            json={"title": "Unauthorized", "budget": 10},
        ).status_code
        == 403
    )
    other = client.post(
        "/v1/agents",
        headers=p["seller"],
        json={"name": "Other", "framework": "openclaw", "endpoint": "https://other.example"},
    ).json()
    other_auth = {"Authorization": f"Bearer {other['api_key']}"}
    assert client.get(f"/v1/tasks/{task['id']}", headers=other_auth).status_code == 404
    assert client.get("/v1/tasks", headers=other_auth).json() == []
    rotated = client.post(f"/v1/agents/{p['agent']['id']}/rotate-key", headers=p["seller"])
    assert rotated.status_code == 200
    assert client.get("/v1/me", headers=p["agent_auth"]).status_code == 401


def test_reserved_cancellation_refunds_once_and_frees_capacity(client, participants):
    p = participants
    task = reserve(client, p).json()
    assert reserve(client, p, key="busy").status_code == 409
    for _ in range(2):
        assert client.post(f"/v1/tasks/{task['id']}/cancel", headers=p["buyer"]).status_code == 200
    assert balance(client, p["buyer"], "project") == 700
    assert reserve(client, p, key="new").status_code == 201
    assert (
        client.post(
            f"/v1/tasks/{task['id']}/start", headers=execution_headers(p["agent_auth"]), json={}
        ).status_code
        == 409
    )


def test_insufficient_budget_rolls_back_reservation(client, app, participants):
    p = participants
    assert reserve(client, p, price=701).status_code == 409
    assert balance(client, p["buyer"], "project") == 700
    assert balance(client, p["buyer"], "task") == 0
    with app.state.sessions() as db:
        assert (
            db.scalar(select(func.count()).select_from(Account).where(Account.kind == "task")) == 0
        )
    assert reserve(client, p, price=700).status_code == 201


def test_unavailable_agent_cannot_receive_work(client, participants):
    p = participants
    client.patch(
        f"/v1/agents/{p['agent']['id']}/availability",
        headers=p["agent_auth"],
        json={"available": False},
    )
    assert reserve(client, p).status_code == 409
    assert client.get("/v1/agents", headers=p["buyer"]).json() == []


def test_started_work_cannot_be_unilaterally_cancelled(client, participants):
    p = participants
    task = reserve(client, p).json()
    complete(client, p, task["id"])
    assert client.post(f"/v1/tasks/{task['id']}/cancel", headers=p["buyer"]).status_code == 409
    assert (
        client.post(
            f"/v1/tasks/{task['id']}/submit",
            headers=execution_headers(p["agent_auth"]),
            json={"artifact": {"changed": True}},
        ).status_code
        == 409
    )
    assert balance(client, p["buyer"], "task") == 200


def test_credentials_and_input_validation(client, app, participants):
    assert client.get("/v1/wallet").status_code == 401
    assert client.get("/v1/wallet", headers={"Authorization": "Bearer invalid"}).status_code == 401
    p = participants
    assert (
        client.post(
            "/v1/projects",
            headers={**p["buyer"], "Idempotency-Key": "bad"},
            json={"title": "Bad", "budget": 1.5},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/agents",
            headers=p["seller"],
            json={"name": "Bad", "framework": "custom", "endpoint": "http://example.com"},
        ).status_code
        == 422
    )
    app.state.settings.enable_test_funding = False
    assert (
        client.post(
            f"/v1/admin/owners/{p['buyer_id']}/test-funding",
            json={"amount": 5},
            headers={"Authorization": "Bearer test-admin", "Idempotency-Key": "disabled"},
        ).status_code
        == 403
    )


def test_framework_names_are_open_and_no_provider_key_is_collected(client, participants):
    p = participants
    for framework in ("openclaw", "meta-muse", "claude", "openai-agents", "deepseek", "custom"):
        response = client.post(
            "/v1/agents",
            headers=p["seller"],
            json={
                "name": framework,
                "framework": framework,
                "endpoint": "https://example.com/agent",
            },
        )
        assert response.status_code == 201
        assert response.json()["framework"] == framework
    response = client.post(
        "/v1/agents",
        headers=p["seller"],
        json={
            "name": "No secret upload",
            "framework": "custom",
            "endpoint": "https://example.com",
            "provider_api_key": "must-stay-local",
        },
    )
    assert response.status_code == 422


def test_different_runtimes_collaborate_on_same_project(client, participants):
    p = participants
    first_id = reserve(client, p).json()["id"]
    complete(client, p, first_id)
    first_result = client.post(f"/v1/tasks/{first_id}/accept", headers=p["buyer"]).json()
    second = client.post(
        "/v1/agents",
        headers=p["seller"],
        json={
            "name": "Claude reviewer",
            "framework": "claude",
            "endpoint": "https://claude.example",
        },
    ).json()
    second_auth = {"Authorization": f"Bearer {second['api_key']}"}
    client.patch(
        f"/v1/agents/{second['id']}/availability", headers=second_auth, json={"available": True}
    )
    skill = client.post(
        f"/v1/agents/{second['id']}/skills",
        headers=p["seller"],
        json={
            "slug": "verify-review",
            "version": "1",
            "description": "Verify another agent's review",
        },
    ).json()
    response = client.post(
        f"/v1/projects/{p['project']['id']}/tasks",
        headers={**p["buyer"], "Idempotency-Key": "second-runtime"},
        json={
            "agent_id": second["id"],
            "skill_id": skill["id"],
            "instructions": f"Verify the first result: {first_result['artifact']}",
            "acceptance_criteria": "Independent verification with evidence",
            "price": 100,
        },
    )
    assert response.status_code == 201
    task_id = response.json()["id"]
    client.post(
        f"/v1/tasks/{task_id}/start",
        headers={**second_auth, "X-Execution-Token": "second-execution-token-1234567890"},
        json={},
    )
    client.post(
        f"/v1/tasks/{task_id}/submit",
        headers={**second_auth, "X-Execution-Token": "second-execution-token-1234567890"},
        json={"artifact": {"verification": "Checked the prior agent's review"}},
    )
    assert client.post(f"/v1/tasks/{task_id}/accept", headers=p["buyer"]).status_code == 200
    assert balance(client, p["seller"], "earnings") == 300
    assert balance(client, p["buyer"], "project") == 400
