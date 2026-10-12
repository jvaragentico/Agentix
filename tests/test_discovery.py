def test_machine_discovery_and_error_correlation(client):
    manifest = client.get("/.well-known/agentix.json")
    assert manifest.status_code == 200
    assert manifest.json()["request_limits"]["max_body_bytes"] == 100000
    assert manifest.json()["execution"]["empty_inbox_status"] == 204
    assert manifest.json()["settlement"]["redeemable"] is False
    assert "X-Execution-Token" in client.get("/llms.txt").text
    denied = client.get("/v1/tasks")
    assert denied.status_code == 401
    assert denied.json()["error"]["request_id"] == denied.headers["X-Request-ID"]
    assert denied.json()["error"]["retryable"] is False
