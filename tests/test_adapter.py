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


def test_private_host_discovery_and_redirects_keep_credentials_on_origin():
    requests = []

    def transport(request):
        requests.append(request)
        if request.url.path == "/.well-known/agentix.json":
            return httpx.Response(200, json={"protocol": "agentix-rest"})
        return httpx.Response(307, headers={"Location": "https://other.example/claim"})

    with AgentixAdapter(
        "https://agentix.example",
        "agent-key",
        sites_service_token="site-key",
        transport=httpx.MockTransport(transport),
    ) as adapter:
        assert adapter.discover()["protocol"] == "agentix-rest"
        with pytest.raises(httpx.HTTPStatusError):
            adapter.run_once(lambda _: {"text": "must not run"})
    assert len(requests) == 2
    assert all(r.url.host == "agentix.example" for r in requests)
    assert all(r.headers["OAI-Sites-Authorization"] == "Bearer site-key" for r in requests)


def test_idle_polling_backs_off_and_can_be_stopped(monkeypatch):
    monkeypatch.setattr("agentix.adapter.random.uniform", lambda low, high: high)

    class Stop:
        def __init__(self):
            self.delays = []

        def is_set(self):
            return False

        def wait(self, delay):
            self.delays.append(delay)
            return len(self.delays) == 4

    stop = Stop()
    with AgentixAdapter(
        "https://agentix.example",
        "key",
        transport=httpx.MockTransport(lambda _: httpx.Response(204)),
    ) as adapter:
        adapter.run_forever(lambda _: {}, stop=stop, poll_seconds=2, max_poll_seconds=5)
    assert stop.delays == [2, 4, 5, 5]


def test_lost_claim_and_submission_responses_do_not_rerun_handler(
    client, participants, monkeypatch
):
    p = participants
    task_id = reserve(client, p).json()["id"]
    attempts, payloads, delays, calls = {}, {}, [], []
    monkeypatch.setattr("agentix.adapter.random.uniform", lambda low, high: high)
    monkeypatch.setattr("agentix.adapter.time.sleep", delays.append)

    def transport(request):
        path = request.url.path
        attempts[path] = attempts.get(path, 0) + 1
        payloads.setdefault(path, []).append(
            (request.content, request.headers.get("X-Execution-Token"))
        )
        response = client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        if attempts[path] == 1 and (path.endswith("/claim") or path.endswith("/submit")):
            assert response.status_code == 200  # Server committed; only the response is lost.
            raise httpx.ReadTimeout("Simulated lost response", request=request)
        return httpx.Response(response.status_code, content=response.content)

    with AgentixAdapter(
        "http://testserver", p["agent"]["api_key"], transport=httpx.MockTransport(transport)
    ) as adapter:

        def handler(task):
            calls.append(task["id"])
            return {"text": "Generated once in the owner's runtime"}

        assert adapter.run_once(handler) == task_id
    assert calls == [task_id]
    assert delays == [0.25, 0.25]
    assert all(len(values) == 2 and values[0] == values[1] for values in payloads.values())
    task = client.get(f"/v1/tasks/{task_id}", headers=p["buyer"]).json()
    assert task["state"] == "submitted" and task["attempts"] == 1
    events = client.get(f"/v1/tasks/{task_id}/events", headers=p["buyer"]).json()
    assert [e["kind"] for e in events].count("claimed") == 1
    assert [e["kind"] for e in events].count("submitted") == 1
    assert client.get("/v1/wallet", headers=p["seller"]).json()["earnings"] == 0
    for _ in range(2):
        client.post(f"/v1/tasks/{task_id}/accept", headers=p["buyer"]).raise_for_status()
    assert client.get("/v1/wallet", headers=p["seller"]).json()["earnings"] == 200


@pytest.mark.parametrize("status", [401, 403, 409, 413, 422])
def test_adapter_never_retries_permanent_errors(status, monkeypatch):
    requests = []
    monkeypatch.setattr("agentix.adapter.time.sleep", lambda _: pytest.fail("Unexpected retry"))

    def transport(request):
        requests.append(request)
        return httpx.Response(status, json={"detail": "Permanent failure"})

    with AgentixAdapter(
        "https://agentix.example", "key", transport=httpx.MockTransport(transport)
    ) as adapter:
        with pytest.raises(httpx.HTTPStatusError):
            adapter.run_once(lambda _: pytest.fail("Handler must not run"))
    assert len(requests) == 1


def test_adapter_retry_backoff_is_bounded_and_exhaustion_propagates(monkeypatch):
    requests, delays = [], []
    monkeypatch.setattr("agentix.adapter.random.uniform", lambda low, high: high)
    monkeypatch.setattr("agentix.adapter.time.sleep", delays.append)

    def transport(request):
        requests.append(request)
        return httpx.Response(503, json={"detail": "Temporary outage"})

    with AgentixAdapter(
        "https://agentix.example", "key", transport=httpx.MockTransport(transport)
    ) as adapter:
        with pytest.raises(httpx.HTTPStatusError):
            adapter.discover()
    assert len(requests) == 3 and delays == [0.25, 0.5]


@pytest.mark.parametrize(
    "retry_after,expected_requests,expected_delays",
    [("1", 2, [1]), ("60", 1, []), ("invalid", 2, [0.25])],
)
def test_adapter_respects_retry_after_without_exceeding_wait_budget(
    monkeypatch, retry_after, expected_requests, expected_delays
):
    requests, delays = [], []
    monkeypatch.setattr("agentix.adapter.random.uniform", lambda low, high: high)
    monkeypatch.setattr("agentix.adapter.time.sleep", delays.append)

    def transport(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429, headers={"Retry-After": retry_after}, json={"detail": "Busy"}
            )
        return httpx.Response(200, json={"protocol": "agentix-rest"})

    with AgentixAdapter(
        "https://agentix.example", "key", transport=httpx.MockTransport(transport)
    ) as adapter:
        if expected_requests == 1:
            with pytest.raises(httpx.HTTPStatusError):
                adapter.discover()
        else:
            assert adapter.discover()["protocol"] == "agentix-rest"
    assert len(requests) == expected_requests and delays == expected_delays


def test_adapter_does_not_retry_other_mutations(monkeypatch):
    monkeypatch.setattr("agentix.adapter.time.sleep", lambda _: pytest.fail("Unsafe retry"))
    with AgentixAdapter(
        "https://agentix.example",
        "key",
        transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    ) as adapter:
        with pytest.raises(httpx.HTTPStatusError):
            adapter._request("POST", "/v1/projects", json={"title": "No automatic replay"})


@pytest.mark.parametrize("fraction", [0, 0.5, 1])
def test_jitter_bounds_and_server_minimum(monkeypatch, fraction):
    monkeypatch.setattr(
        "agentix.adapter.random.uniform", lambda low, high: low + fraction * (high - low)
    )
    with AgentixAdapter("https://agentix.example", "key") as adapter:
        assert adapter._retry_delay(None, 0) == 0.125 + fraction * 0.125
        assert adapter._retry_delay(None, 10) == 2.5 + fraction * 2.5
        response = httpx.Response(429, headers={"Retry-After": "1"})
        assert adapter._retry_delay(response, 0) == 1
        assert adapter._retry_delay(httpx.Response(429, headers={"Retry-After": "60"}), 0) is None


def test_jitter_can_be_disabled(monkeypatch):
    monkeypatch.setattr("agentix.adapter.random.uniform", lambda *_: pytest.fail("Jitter disabled"))
    with AgentixAdapter("https://agentix.example", "key", backoff_jitter=False) as adapter:
        assert adapter._retry_delay(None, 0) == 0.25
        assert adapter._jitter(4) == 4
    with pytest.raises(ValueError, match="boolean"):
        AgentixAdapter("https://agentix.example", "key", backoff_jitter="false")


def test_idle_jitter_preserves_exponential_ceiling_and_stop(monkeypatch):
    monkeypatch.setattr("agentix.adapter.random.uniform", lambda low, high: low)

    class Stop:
        delays = []

        def is_set(self):
            return False

        def wait(self, delay):
            self.delays.append(delay)
            return len(self.delays) == 4

    stop = Stop()
    with AgentixAdapter(
        "https://agentix.example",
        "key",
        transport=httpx.MockTransport(lambda _: httpx.Response(204)),
    ) as adapter:
        adapter.run_forever(
            lambda _: pytest.fail("No task available"),
            stop=stop,
            poll_seconds=2,
            max_poll_seconds=5,
        )
    assert stop.delays == [1, 2, 2.5, 2.5]


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2"])
def test_session_task_limit_rejects_invalid_values_before_requests(limit):
    requests = []
    with AgentixAdapter(
        "https://agentix.example",
        "key",
        transport=httpx.MockTransport(lambda request: requests.append(request)),
    ) as adapter:
        with pytest.raises(ValueError, match="max_tasks"):
            adapter.run_forever(lambda _: {}, stop=Event(), max_tasks=limit)
    assert requests == []


@pytest.mark.parametrize("time_limited", [False, True])
def test_session_task_limit_leaves_next_assignment_unclaimed(
    client, app, participants, monkeypatch, time_limited
):
    from agentix.models import Agent

    p = participants
    with app.state.sessions.begin() as db:
        db.get(Agent, p["agent"]["id"]).capacity = 2
    task_ids = {reserve(client, p, key=key, price=20).json()["id"] for key in ("one", "two")}
    claims, handled = [], []
    clock = [100.0]
    monkeypatch.setattr("agentix.adapter.time.monotonic", lambda: clock[0])
    limits = {"max_session_seconds": 1} if time_limited else {"max_tasks": 1}

    def transport(request):
        if request.url.path == "/v1/tasks/claim":
            claims.append(request)
            if len(claims) == 1:
                return httpx.Response(204)  # Idle polls must not consume the task budget.
        response = client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        return httpx.Response(response.status_code, content=response.content)

    def handler(task):
        handled.append(task["id"])
        clock[0] += 2  # Active work may finish after the participation window.
        return {"text": "Owner-local work"}

    stop = Event()
    with AgentixAdapter(
        "http://testserver", p["agent"]["api_key"], transport=httpx.MockTransport(transport)
    ) as adapter:
        adapter.run_forever(handler, stop=stop, **limits, poll_seconds=0.001)
        assert len(claims) == 2
        assert len(handled) == 1
        states = [
            client.get(f"/v1/tasks/{t}", headers=p["buyer"]).json()["state"] for t in task_ids
        ]
        assert sorted(states) == ["reserved", "submitted"]
        assert not stop.is_set()  # The caller owns its stop signal; another invocation is allowed.
        adapter.run_forever(handler, stop=stop, **limits)
    assert len(claims) == 3
    assert set(handled) == task_ids


def test_stopped_bounded_session_does_not_claim():
    stop = Event()
    stop.set()
    requests = []
    with AgentixAdapter(
        "https://agentix.example",
        "key",
        transport=httpx.MockTransport(lambda request: requests.append(request)),
    ) as adapter:
        adapter.run_forever(lambda _: {}, stop=stop, max_tasks=1)
    assert requests == []


@pytest.mark.parametrize("seconds", [0, -1, True, "2", float("nan"), float("inf"), 86401])
def test_session_window_rejects_invalid_values_before_requests(seconds):
    requests = []
    with AgentixAdapter(
        "https://agentix.example",
        "key",
        transport=httpx.MockTransport(lambda request: requests.append(request)),
    ) as adapter:
        with pytest.raises(ValueError, match="max_session_seconds"):
            adapter.run_forever(lambda _: {}, stop=Event(), max_session_seconds=seconds)
    assert requests == []


def test_idle_wait_is_clipped_to_session_window(monkeypatch):
    clock = [100.0]
    requests, waits = [], []
    monkeypatch.setattr("agentix.adapter.time.monotonic", lambda: clock[0])

    class Stop:
        def is_set(self):
            return False

        def wait(self, seconds):
            waits.append(seconds)
            clock[0] += seconds
            return False

    def transport(request):
        requests.append(request)
        return httpx.Response(204)

    with AgentixAdapter(
        "https://agentix.example",
        "key",
        backoff_jitter=False,
        transport=httpx.MockTransport(transport),
    ) as adapter:
        adapter.run_forever(lambda _: {}, stop=Stop(), max_session_seconds=3, poll_seconds=2)
    assert waits == [2, 1]
    assert len(requests) == 2


@pytest.mark.parametrize("committed_first", [False, True])
def test_adapter_keeps_renewal_alive_during_delivery_retry(
    client, participants, monkeypatch, committed_first
):
    p = participants
    task_id = reserve(client, p).json()["id"]
    delivering, renewed = Event(), Event()
    renewal_events = []
    calls, submissions, heartbeats = [], [], []

    class DeliveryWait(Event):
        def __init__(self):
            super().__init__()
            renewal_events.append(self)
            self.first = True

        def wait(self, timeout=None):
            if self.first:
                self.first = False
                assert delivering.wait(2), "Submission never began"
                return self.is_set()
            return super().wait(timeout)

    monkeypatch.setattr("agentix.adapter.Event", DeliveryWait)
    # Deterministic synchronization: a retry cannot proceed until renewal finishes.
    monkeypatch.setattr("agentix.adapter.time.sleep", lambda _: renewed.wait(2))

    def transport(request):
        path = request.url.path
        if path.endswith("/submit"):
            submissions.append((request.content, request.headers["X-Execution-Token"]))
            if len(submissions) == 1:
                if committed_first:
                    response = client.request(
                        request.method,
                        str(request.url),
                        headers=dict(request.headers),
                        content=request.content,
                    )
                    assert response.status_code == 200
                delivering.set()
                assert renewed.wait(2), "Lease was not renewed during delivery"
                raise httpx.ReadTimeout("Lost delivery response", request=request)
        response = client.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        if path.endswith("/heartbeat"):
            heartbeats.append(response.status_code)
            renewed.set()
        return httpx.Response(response.status_code, content=response.content)

    with AgentixAdapter(
        "http://testserver", p["agent"]["api_key"], transport=httpx.MockTransport(transport)
    ) as adapter:

        def handler(task):
            calls.append(task["id"])
            return {"text": "one local execution"}

        assert adapter.run_once(handler) == task_id
    assert calls == [task_id]
    assert len(submissions) == 2 and submissions[0] == submissions[1]
    assert heartbeats == ([409] if committed_first else [200])
    assert all(event.is_set() for event in renewal_events)
    history = client.get(f"/v1/tasks/{task_id}/events", headers=p["buyer"]).json()
    assert sum(e["kind"] == "submitted" for e in history) == 1
    assert client.get("/v1/wallet", headers=p["seller"]).json()["earnings"] == 0
    for _ in range(2):
        client.post(f"/v1/tasks/{task_id}/accept", headers=p["buyer"]).raise_for_status()
    assert client.get("/v1/wallet", headers=p["seller"]).json()["earnings"] == 200


@pytest.mark.parametrize("failure", ["handler", "artifact", "lease_rejected", "delivery_exhausted"])
def test_adapter_joins_renewal_worker_on_every_failure(monkeypatch, failure):
    from threading import Thread

    workers = []

    class TrackedThread(Thread):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            workers.append(self)

    monkeypatch.setattr("agentix.adapter.Thread", TrackedThread)
    monkeypatch.setattr("agentix.adapter.time.sleep", lambda _: None)
    requests = []

    def transport(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/claim"):
            return httpx.Response(200, json={"id": "task"})
        return httpx.Response(409 if failure == "lease_rejected" else 503, json={"detail": failure})

    def handler(_):
        if failure == "handler":
            raise RuntimeError("Local runtime failed")
        return {} if failure == "artifact" else {"text": "result"}

    expected = (
        RuntimeError
        if failure == "handler"
        else ValueError
        if failure == "artifact"
        else httpx.HTTPStatusError
    )
    with AgentixAdapter(
        "http://testserver", "key", transport=httpx.MockTransport(transport)
    ) as adapter:
        with pytest.raises(expected):
            adapter.run_once(handler)
    assert len(workers) == 1 and not workers[0].is_alive()
    expected_submits = (
        3 if failure == "delivery_exhausted" else 1 if failure == "lease_rejected" else 0
    )
    assert requests.count("/v1/tasks/task/submit") == expected_submits
