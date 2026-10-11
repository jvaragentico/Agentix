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
