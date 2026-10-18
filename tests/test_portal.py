ADMIN = {"Authorization": "Bearer test-admin"}


def test_dashboard_roles_and_safe_overviews(client, participants):
    p = participants
    for auth, role in [(ADMIN, "superadmin"), (p["buyer"], "creator"), (p["agent_auth"], "agent")]:
        assert client.get("/v1/session", headers=auth).json()["role"] == role
        path = f"/v1/{'admin' if role == 'superadmin' else role}/overview"
        response = client.get(path, headers=auth)
        assert response.status_code == 200
        assert "token_hash" not in response.text
        assert "api_key" not in response.text
    assert client.get("/v1/admin/overview", headers=p["buyer"]).status_code == 403
    assert client.get("/v1/creator/overview", headers=p["agent_auth"]).status_code == 403
    assert client.get("/v1/agent/overview", headers=p["buyer"]).status_code == 403
    for path in ["/", "/creator", "/agent", "/superadmin", "/assets/app.js"]:
        assert client.get(path).status_code == 200


def test_board_visibility_matching_and_suspended_owners(client, participants):
    p = participants
    response = client.post(
        "/v1/projects",
        headers={**p["buyer"], "Idempotency-Key": "public"},
        json={
            "title": "<script>safe</script>",
            "budget": 100,
            "description": "Review API",
            "published": True,
            "required_skills": ["code-review"],
        },
    )
    assert response.status_code == 201
    project = response.json()["id"]
    board = client.get("/v1/marketplace/projects?skill=code-review", headers=p["outsider"]).json()
    assert [item["id"] for item in board] == [project]
    matches = client.get(f"/v1/projects/{project}/matches", headers=p["buyer"]).json()
    assert matches[0]["id"] == p["agent"]["id"]
    assert matches[0]["matched_skills"] == ["code-review"]
    assert client.get(f"/v1/projects/{project}/matches", headers=p["outsider"]).status_code == 404
    assert (
        client.patch(
            f"/v1/admin/owners/{p['seller_id']}", headers=ADMIN, json={"active": False}
        ).status_code
        == 200
    )
    assert client.get(f"/v1/projects/{project}/matches", headers=p["buyer"]).json() == []
    assert client.get("/v1/session", headers=p["agent_auth"]).status_code == 401


def test_ai_spending_allowance_idempotency_and_project_isolation(client, participants):
    p = participants
    body = {
        "title": "AI requests a collaborator",
        "budget": 80,
        "published": True,
        "required_skills": ["marketing"],
    }
    headers = {**p["agent_auth"], "Idempotency-Key": "ai-post"}
    assert client.post("/v1/projects", headers=headers, json=body).status_code == 403
    assert (
        client.post(
            f"/v1/admin/owners/{p['seller_id']}/test-funding",
            headers={**ADMIN, "Idempotency-Key": "seller-fund"},
            json={"amount": 200},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/v1/agents/{p['agent']['id']}/allowance",
            headers=p["seller"],
            json={"project_allowance": 100},
        ).status_code
        == 200
    )
    first = client.post("/v1/projects", headers=headers, json=body)
    assert first.status_code == 201
    assert first.json()["source"] == "ai"
    assert client.post("/v1/projects", headers=headers, json=body).json() == first.json()
    assert (
        client.get("/v1/agent/overview", headers=p["agent_auth"]).json()["allowance_remaining"]
        == 20
    )
    assert (
        client.post(
            "/v1/projects", headers={**headers, "Idempotency-Key": "over-budget"}, json=body
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/v1/agents/{p['agent']['id']}/allowance",
            headers=p["seller"],
            json={"project_allowance": 79},
        ).status_code
        == 409
    )
    sibling = client.post(
        "/v1/agents",
        headers=p["seller"],
        json={"name": "Sibling", "framework": "claude", "endpoint": "https://sibling.example/api"},
    ).json()
    sibling_auth = {"Authorization": f"Bearer {sibling['api_key']}"}
    assert client.get(f"/v1/projects/{first.json()['id']}", headers=sibling_auth).status_code == 404
    assert client.get(f"/v1/projects/{first.json()['id']}", headers=p["seller"]).status_code == 200


def test_capacity_counts_all_commitments_not_recent_tasks(client, app, participants):
    from test_workflow import reserve

    from agentix.models import Task

    p = participants

    def occupancy():
        creator = client.get("/v1/creator/overview", headers=p["seller"]).json()["agents"][0]
        agent = client.get("/v1/agent/overview", headers=p["agent_auth"]).json()["agent"]
        assert creator["occupied_slots"] == agent["occupied_slots"]
        return agent["occupied_slots"]

    def capacity_check():
        response = client.get("/v1/admin/overview", headers=ADMIN)
        assert response.status_code == 200
        return response.json()["capacity_check"]

    healthy = {
        "healthy": True,
        "overcommitted_agents": 0,
        "excess_assignments": 0,
        "agents": [],
        "truncated": False,
    }
    assert capacity_check() == healthy
    assert occupancy() == 0
    task_id = reserve(client, p).json()["id"]
    assert occupancy() == 1
    assert capacity_check() == healthy
    # Diagnostic fixtures: expired running work still occupies capacity; terminal work does not.
    for state in ("running", "submitted", "accepted", "cancelled"):
        with app.state.sessions.begin() as db:
            db.get(Task, task_id).state = state
        assert occupancy() == (1 if state in ("running", "submitted") else 0)
    with app.state.sessions.begin() as db:
        task = db.get(Task, task_id)
        fields = {c.name: getattr(task, c.name) for c in Task.__table__.columns if c.name != "id"}
        fields.update(state="reserved")
        db.add_all(Task(**fields) for _ in range(101))
    assert occupancy() == 101  # Never silently clamp drift to configured capacity.
    assert len(client.get("/v1/agent/overview", headers=p["agent_auth"]).json()["tasks"]) == 100
    assert client.get("/v1/creator/overview", headers=p["outsider"]).json()["agents"] == []

    expected = {
        "healthy": False,
        "overcommitted_agents": 1,
        "excess_assignments": 100,
        "agents": [
            {
                "agent_id": p["agent"]["id"],
                "agent_name": p["agent"]["name"],
                "owner_id": p["seller_id"],
                "capacity": 1,
                "occupied_slots": 101,
                "excess_assignments": 100,
            }
        ],
        "truncated": False,
    }
    before = client.get("/v1/wallet", headers=p["seller"]).json()
    assert capacity_check() == expected
    assert capacity_check() == expected
    assert occupancy() == 101
    assert client.get("/v1/wallet", headers=p["seller"]).json() == before


def test_capacity_detail_sample_is_bounded_and_ordered(client, app, participants):
    from test_workflow import reserve

    from agentix.models import Agent

    p = participants
    ids = []
    for i in range(11):
        creator_auth = p["seller"] if i % 2 == 0 else p["buyer"]
        agent = client.post(
            "/v1/agents",
            headers=creator_auth,
            json={
                "name": f"Sample {i}",
                "framework": "owner-managed",
                "capacity": 2,
                "endpoint": "https://example.test/agent",
            },
        ).json()
        client.patch(
            f"/v1/agents/{agent['id']}/availability", headers=creator_auth, json={"available": True}
        ).raise_for_status()
        skill = client.post(
            f"/v1/agents/{agent['id']}/skills",
            headers=creator_auth,
            json={
                "slug": "review",
                "version": "1",
                "description": "Review work",
            },
        ).json()
        for j in range(2):
            reserve(
                client, {**p, "agent": agent, "skill": skill}, key=f"sample-{i}-{j}", price=1
            ).raise_for_status()
        ids.append(agent["id"])
    # Simulate configuration drift after valid, funded assignments.
    with app.state.sessions.begin() as db:
        for aid in ids:
            db.get(Agent, aid).capacity = 1
    check = client.get("/v1/admin/overview", headers=ADMIN).json()["capacity_check"]
    assert check["overcommitted_agents"] == check["excess_assignments"] == 11
    assert check["truncated"] is True
    assert [a["agent_id"] for a in check["agents"]] == sorted(ids)[:10]
    assert all(
        set(a)
        == {
            "agent_id",
            "agent_name",
            "owner_id",
            "capacity",
            "occupied_slots",
            "excess_assignments",
        }
        for a in check["agents"]
    )
    pages = [
        client.get(f"/v1/admin/capacity?limit=5&offset={offset}", headers=ADMIN)
        for offset in (0, 5, 10, 15)
    ]
    assert all(
        page.status_code == 200 and page.headers["cache-control"] == "no-store" for page in pages
    )
    assert [len(page.json()) for page in pages] == [5, 5, 1, 0]
    items = [item for page in pages for item in page.json()]
    assert [item["agent_id"] for item in items] == sorted(ids)
    assert items[:10] == check["agents"]
    assert client.get("/v1/admin/capacity", headers=ADMIN).json() == items
    for query in ("limit=0", "limit=101", "offset=-1", "offset=abc", "offset=9007199254740992"):
        assert client.get("/v1/admin/capacity?" + query, headers=ADMIN).status_code == 422
    for auth in (p["buyer"], p["seller"], p["agent_auth"]):
        assert client.get("/v1/admin/capacity", headers=auth).status_code == 403

    filtered = [a for a in items if a["owner_id"] == p["seller_id"]]
    assert len(filtered) == 6
    url = "/v1/admin/capacity?owner_id=" + p["seller_id"]
    assert client.get(url, headers=ADMIN).json() == filtered
    assert client.get(url + "&limit=2&offset=1", headers=ADMIN).json() == filtered[1:3]
    assert client.get("/v1/admin/capacity?owner_id=missing", headers=ADMIN).json() == []
    assert client.get("/v1/admin/capacity?owner_id=" + "x" * 129, headers=ADMIN).status_code == 422
    assert client.get(url, headers=p["seller"]).status_code == 403
