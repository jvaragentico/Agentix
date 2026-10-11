import httpx
from test_workflow import reserve

from agentix.adapter import AgentixAdapter


def test_adapter_calls_existing_runtime_and_submits_without_provider_keys(client, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]

    def transport(request):
        response = client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        return httpx.Response(response.status_code, json=response.json())

    adapter = AgentixAdapter(
        "http://testserver", p["agent"]["api_key"], transport=httpx.MockTransport(transport)
    )
    local_calls = []

    def hermes_handler(task):
        local_calls.append(task["id"])
        return {"review": "Result from the owner's existing agent"}

    try:
        assert adapter.run_once(hermes_handler) == task_id
        assert adapter.run_once(hermes_handler) is None
    finally:
        adapter.close()
    assert local_calls == [task_id]
    task = client.get(f"/v1/tasks/{task_id}", headers=p["buyer"]).json()
    assert task["state"] == "submitted"
