from threading import Event

import httpx
import pytest
from test_workflow import reserve

from agentix.adapter import AgentixAdapter, LeaseLostError


def test_adapter_calls_existing_runtime_and_submits_without_provider_keys(client, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]

    def transport(request):
        response = client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        return httpx.Response(response.status_code, content=response.content)

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


@pytest.mark.parametrize("renewal_fails", [False, True])
def test_adapter_renews_during_work_and_withholds_result_on_failure(
    client, participants, monkeypatch, renewal_fails
):
    p = participants
    task_id = reserve(client, p).json()["id"]
    renewed = Event()

    class ImmediateFirstWait(Event):
        def __init__(self):
            super().__init__()
            self.first = True

        def wait(self, timeout=None):
            if self.first:
                self.first = False
                return False
            return super().wait(timeout)

    monkeypatch.setattr("agentix.adapter.Event", ImmediateFirstWait)

    def transport(request):
        if request.url.path.endswith("/heartbeat") and renewal_fails:
            renewed.set()
            return httpx.Response(409, json={"detail": "Lease lost"})
        response = client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        if request.url.path.endswith("/heartbeat"):
            renewed.set()
        return httpx.Response(response.status_code, content=response.content)

    bridge = AgentixAdapter(
        "http://testserver", p["agent"]["api_key"], transport=httpx.MockTransport(transport)
    )

    def handler(task):
        assert renewed.wait(2), "Expected a lease renewal while the handler was running"
        return {"result": "completed"}

    try:
        if renewal_fails:
            with pytest.raises(LeaseLostError):
                bridge.run_once(handler)
        else:
            assert bridge.run_once(handler) == task_id
    finally:
        bridge.close()
    task = client.get(f"/v1/tasks/{task_id}", headers=p["buyer"]).json()
    assert task["state"] == ("running" if renewal_fails else "submitted")
