from test_workflow import execution_headers, reserve


def test_rotation_requires_owner_and_preserves_running_work(client, participants):
    p = participants
    agent_id = p["agent"]["id"]
    endpoint = f"/v1/agents/{agent_id}/rotate-key"
    assert client.post(endpoint, headers=p["agent_auth"]).status_code == 403
    assert client.post(endpoint, headers=p["outsider"]).status_code == 404
    task = reserve(client, p).json()
    assert (
        client.post(
            f"/v1/tasks/{task['id']}/start",
            headers=execution_headers(p["agent_auth"]),
            json={"lease_seconds": 300},
        ).status_code
        == 200
    )
    client.patch(
        f"/v1/agents/{agent_id}/allowance", headers=p["seller"], json={"project_allowance": 150}
    ).raise_for_status()
    before = client.get("/v1/creator/overview", headers=p["seller"]).json()
    rotated = client.post(endpoint, headers=p["seller"])
    assert rotated.status_code == 200
    new = rotated.json()
    assert new["agent_id"] == agent_id
    assert new["api_key"] != p["agent"]["api_key"]
    assert client.get("/v1/session", headers=p["agent_auth"]).status_code == 401
    assert (
        client.post(
            f"/v1/tasks/{task['id']}/heartbeat", headers=execution_headers(p["agent_auth"]), json={}
        ).status_code
        == 401
    )
    new_auth = {"Authorization": f"Bearer {new['api_key']}"}
    assert client.get("/v1/session", headers=new_auth).json()["agent_id"] == agent_id
    after = client.get("/v1/creator/overview", headers=p["seller"]).json()
    assert before == after
    assert new["api_key"] not in str(after)
    result = client.post(
        f"/v1/tasks/{task['id']}/submit",
        headers=execution_headers(new_auth),
        json={"artifact": {"text": "Work completed after key replacement"}},
    )
    assert result.status_code == 200
    assert client.post(f"/v1/tasks/{task['id']}/accept", headers=p["buyer"]).status_code == 200
    assert client.get("/v1/wallet", headers=p["seller"]).json()["earnings"] == task["price"]


def test_admin_creator_key_replacement_preserves_identity_and_suspension(client, participants):
    p = participants
    admin = {"Authorization": "Bearer test-admin"}
    owner_id = p["agent"]["owner_id"]
    endpoint = f"/v1/admin/owners/{owner_id}/rotate-key"
    task = reserve(client, p).json()
    before = client.get("/v1/creator/overview", headers=p["seller"]).json()
    wallet = client.get("/v1/wallet", headers=p["seller"]).json()
    for auth in (p["seller"], p["buyer"], p["agent_auth"]):
        assert client.post(endpoint, headers=auth).status_code == 403
    assert client.post(endpoint).status_code == 403
    assert client.post("/v1/admin/owners/missing/rotate-key", headers=admin).status_code == 404
    response = client.post(endpoint, headers=admin)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["owner_id"] == owner_id
    new = {"Authorization": "Bearer " + response.json()["api_key"]}
    assert client.get("/v1/session", headers=p["seller"]).status_code == 401
    assert client.get("/v1/creator/overview", headers=new).json() == before
    assert client.get("/v1/wallet", headers=new).json() == wallet
    assert response.json()["api_key"] not in str(before)
    assert client.get("/v1/session", headers=p["agent_auth"]).status_code == 200
    assert client.get(f"/v1/tasks/{task['id']}", headers=p["agent_auth"]).status_code == 200
    client.patch(
        f"/v1/admin/owners/{owner_id}", headers=admin, json={"active": False}
    ).raise_for_status()
    replacement = client.post(endpoint, headers=admin).json()
    latest = {"Authorization": "Bearer " + replacement["api_key"]}
    assert client.get("/v1/session", headers=latest).status_code == 401
    client.patch(
        f"/v1/admin/owners/{owner_id}", headers=admin, json={"active": True}
    ).raise_for_status()
    assert client.get("/v1/session", headers=new).status_code == 401
    assert client.get("/v1/session", headers=latest).json()["owner_id"] == owner_id
