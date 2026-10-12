"""Local-only smoke test: lose committed claim/submit responses and verify replay safety."""

import os
from urllib.parse import urlsplit

import httpx

from agentix.adapter import AgentixAdapter

base = os.environ["AGENTIX_BROWSER_URL"]
if urlsplit(base).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("This fixture creates test accounts and only permits loopback URLs")
admin = os.environ["AGENTIX_ADMIN_TOKEN"]


def auth(key):
    return {"Authorization": f"Bearer {key}"}


with httpx.Client(base_url=base, timeout=30, follow_redirects=False) as client:

    def post(path, key, body=None, **headers):
        response = client.post(path, headers={**auth(key), **headers}, json=body)
        response.raise_for_status()
        return response.json()

    buyer = post("/v1/admin/owners", admin, {"name": "Retry smoke buyer"})
    seller = post("/v1/admin/owners", admin, {"name": "Retry smoke provider"})
    post(
        f"/v1/admin/owners/{buyer['id']}/test-funding",
        admin,
        {"amount": 200},
        **{"Idempotency-Key": "smoke-funding"},
    )
    agent = post(
        "/v1/agents",
        seller["api_key"],
        {
            "name": "Retry worker",
            "framework": "owner-managed",
            "endpoint": "https://owner.example/agent",
        },
    )
    client.patch(
        f"/v1/agents/{agent['id']}/availability",
        headers=auth(agent["api_key"]),
        json={"available": True},
    ).raise_for_status()
    skill = post(
        f"/v1/agents/{agent['id']}/skills",
        seller["api_key"],
        {"slug": "coding", "version": "1", "description": "Review code"},
    )
    project = post(
        "/v1/projects",
        buyer["api_key"],
        {"title": "Lost response recovery", "budget": 100},
        **{"Idempotency-Key": "smoke-project"},
    )
    task = post(
        f"/v1/projects/{project['id']}/tasks",
        buyer["api_key"],
        {
            "agent_id": agent["id"],
            "skill_id": skill["id"],
            "instructions": "Review code",
            "acceptance_criteria": "Useful findings",
            "price": 40,
        },
        **{"Idempotency-Key": "smoke-task"},
    )
    lost = set()
    executions = []

    def transport(request):
        response = client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        if (
            response.status_code == 200
            and request.url.path.endswith(("/claim", "/submit"))
            and request.url.path not in lost
        ):
            lost.add(request.url.path)
            raise httpx.ReadTimeout("Simulated response loss after commit", request=request)
        return httpx.Response(
            response.status_code, content=response.content, headers=response.headers
        )

    def handler(work):
        executions.append(work["id"])
        return {"text": "Executed once in an owner-managed runtime"}

    with AgentixAdapter(base, agent["api_key"], transport=httpx.MockTransport(transport)) as bridge:
        assert bridge.run_once(handler) == task["id"]
    assert executions == [task["id"]] and len(lost) == 2
    events = client.get(f"/v1/tasks/{task['id']}/events", headers=auth(buyer["api_key"])).json()
    assert sum(e["kind"] == "claimed" for e in events) == 1
    assert sum(e["kind"] == "submitted" for e in events) == 1
    assert client.get("/v1/wallet", headers=auth(seller["api_key"])).json()["earnings"] == 0
    for _ in range(2):
        post(f"/v1/tasks/{task['id']}/accept", buyer["api_key"])
    assert client.get("/v1/wallet", headers=auth(seller["api_key"])).json()["earnings"] == 40
print("Lost-response smoke passed: one execution, one submission, one creator settlement.")
