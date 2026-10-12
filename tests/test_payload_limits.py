import asyncio
import json

import pytest
from test_workflow import balance, execution_headers, reserve

from agentix.payload_limits import MAX_REQUEST_BYTES, PayloadLimitMiddleware


@pytest.mark.parametrize("declared_length,expected_reads", [(None, 2), (b"1", 2), (b"100001", 0)])
def test_chunked_requests_stop_at_limit_without_entering_application(
    declared_length, expected_reads
):
    reads, sent = [], []

    async def downstream(*_):
        raise AssertionError("Oversized request reached application")

    async def receive():
        reads.append(1)
        assert len(reads) <= 2, "Read beyond the size limit"
        return {"type": "http.request", "body": b"x" * 60000, "more_body": True}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "POST", "headers": [], "state": {"request_id": "test"}}
    if declared_length:
        scope["headers"] = [(b"content-length", declared_length)]
    asyncio.run(PayloadLimitMiddleware(downstream)(scope, receive, send))
    assert len(reads) == expected_reads
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["error"]["retryable"] is False


def test_exact_boundary_json_is_accepted(client):
    payload = b'{"name":"Boundary account"}'
    payload += b" " * (MAX_REQUEST_BYTES - len(payload))
    result = client.post(
        "/v1/admin/owners",
        content=payload,
        headers={"Authorization": "Bearer test-admin", "Content-Type": "application/json"},
    )
    assert result.status_code == 201


def test_unicode_deliverable_is_bounded_in_bytes_and_can_be_corrected(client, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]
    client.post(
        f"/v1/tasks/{task_id}/start", headers=execution_headers(p["agent_auth"]), json={}
    ).raise_for_status()
    body = json.dumps({"artifact": {"text": "界" * 40000}}, ensure_ascii=False).encode()
    assert len(body) > MAX_REQUEST_BYTES
    result = client.post(
        f"/v1/tasks/{task_id}/submit",
        headers={**execution_headers(p["agent_auth"]), "Content-Type": "application/json"},
        content=body,
    )
    assert result.status_code == 413
    assert result.json()["error"]["request_id"] == result.headers["X-Request-ID"]
    assert result.json()["error"]["retryable"] is False
    task = client.get(f"/v1/tasks/{task_id}", headers=p["buyer"]).json()
    assert task["state"] == "running" and task["artifact"] is None
    assert balance(client, p["buyer"], "task") == 200
    assert balance(client, p["seller"], "earnings") == 0
    assert (
        client.post(
            f"/v1/tasks/{task_id}/submit",
            headers=execution_headers(p["agent_auth"]),
            json={"artifact": {"text": "Shortened result"}},
        ).status_code
        == 200
    )
