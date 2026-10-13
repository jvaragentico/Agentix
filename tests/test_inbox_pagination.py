import pytest
from test_workflow import reserve

from agentix.models import Agent


def test_provider_inbox_pages_filter_and_scope(client, app, participants):
    p = participants
    with app.state.sessions.begin() as db:
        db.get(Agent, p["agent"]["id"]).capacity = 3
    tasks = [reserve(client, p, key=str(i), price=10).json() for i in range(3)]
    cancelled = tasks[1]["id"]
    assert client.post(f"/v1/tasks/{cancelled}/cancel", headers=p["buyer"]).status_code == 200
    ids = sorted(t["id"] for t in tasks)
    for auth in (p["seller"], p["agent_auth"]):
        pages = [client.get(f"/v1/tasks?limit=1&offset={i}", headers=auth).json() for i in range(4)]
        assert [page[0]["id"] for page in pages[:3]] == ids
        assert pages[3] == []
        response = client.get("/v1/tasks?state=cancelled&limit=1", headers=auth).json()
        assert [t["id"] for t in response] == [cancelled]
        assert all("lease_token_hash" not in t for page in pages for t in page)
        assert client.get("/v1/tasks?state=unknown", headers=auth).json() == []
    assert client.get("/v1/tasks", headers=p["buyer"]).json() == []
    assert client.get("/v1/tasks", headers=p["outsider"]).json() == []
    sibling = client.post(
        "/v1/agents",
        headers=p["seller"],
        json={"name": "Sibling", "framework": "generic", "endpoint": "https://owner.example/agent"},
    ).json()
    assert (
        client.get("/v1/tasks", headers={"Authorization": "Bearer " + sibling["api_key"]}).json()
        == []
    )


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "limit=1.5", "offset=-1", "offset=abc", "offset=9007199254740992"],
)
def test_invalid_inbox_pagination(client, participants, query):
    response = client.get("/v1/tasks?" + query, headers=participants["agent_auth"])
    assert response.status_code == 422
    assert response.json()["error"]["retryable"] is False
