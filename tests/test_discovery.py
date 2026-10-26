def test_machine_discovery_and_error_correlation(client):
    manifest = client.get("/.well-known/agentix.json")
    assert manifest.status_code == 200
    assert manifest.json()["agent_discovery"]["max_offset"] == 9007199254740991
    assert manifest.json()["agent_discovery"]["default_limit"] == 50
    assert manifest.json()["request_limits"]["max_body_bytes"] == 100000
    assert manifest.json()["execution"]["empty_inbox_status"] == 204
    assert manifest.json()["settlement"]["redeemable"] is False
    assert "X-Execution-Token" in client.get("/llms.txt").text
    denied = client.get("/v1/tasks")
    assert denied.status_code == 401
    assert denied.json()["error"]["request_id"] == denied.headers["X-Request-ID"]
    assert denied.json()["error"]["retryable"] is False


def test_agent_discovery_pages_after_filters(client, participants):
    p = participants
    ids = [p["agent"]["id"]]
    for i in range(51):
        response = client.post(
            "/v1/agents",
            headers=p["seller"],
            json={
                "name": f"Discovery {i}",
                "framework": "owner-runtime",
                "endpoint": "https://owner.example",
            },
        )
        response.raise_for_status()
        agent = response.json()
        ids.append(agent["id"])
        client.patch(
            f"/v1/agents/{agent['id']}/availability", headers=p["seller"], json={"available": True}
        ).raise_for_status()
    ids.sort()

    def page(query=""):
        response = client.get("/v1/agents" + query, headers=p["buyer"])
        response.raise_for_status()
        return response.json()

    assert [a["id"] for a in page()] == ids[:50]
    assert [a["id"] for a in page("?limit=1&offset=50")] == ids[50:51]
    assert [a["id"] for a in page("?offset=50")] == ids[50:]
    assert page("?offset=52") == page("?offset=9007199254740991") == []
    for version in ["1", "2"]:
        client.post(
            f"/v1/agents/{ids[-1]}/skills",
            headers=p["seller"],
            json={"slug": "discovery-target", "version": version, "description": "Find this skill"},
        ).raise_for_status()
    assert [a["id"] for a in page("?skill=discovery-target&limit=1")] == ids[-1:]
    assert page("?skill=discovery-target&offset=1") == []
    assert all("api_key" not in a and "token_hash" not in a for a in page())
    client.patch(
        f"/v1/agents/{ids[0]}/availability", headers=p["seller"], json={"available": False}
    ).raise_for_status()
    assert [a["id"] for a in page("?limit=1")] == ids[1:2]
    for query in ["?limit=0", "?limit=101", "?offset=-1", "?offset=9007199254740992"]:
        assert client.get("/v1/agents" + query, headers=p["buyer"]).status_code == 422
    client.patch(
        f"/v1/admin/owners/{p['seller_id']}",
        headers={"Authorization": "Bearer test-admin"},
        json={"active": False},
    ).raise_for_status()
    assert page() == []
