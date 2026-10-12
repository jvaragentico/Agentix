from fastapi.testclient import TestClient


def protected(response, status):
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Request-ID"]


def test_private_success_empty_and_error_responses(client, participants):
    p = participants
    created = client.post(
        "/v1/admin/owners",
        headers={"Authorization": "Bearer test-admin"},
        json={"name": "Cache test"},
    )
    protected(created, 201)
    assert created.json()["api_key"]
    protected(client.get("/v1/wallet", headers=p["seller"]), 200)
    protected(client.get("/v1/tasks", headers=p["agent_auth"]), 200)
    protected(client.get("/v1/tasks"), 401)
    protected(
        client.post("/v1/admin/owners", headers=p["agent_auth"], json={"name": "Denied"}), 403
    )
    protected(client.get("/v1/does-not-exist"), 404)
    protected(client.post("/v1/agents", headers=p["seller"], json={}), 422)
    protected(client.post("/v1/agents", content="x" * 100001), 413)
    protected(client.get("/health/live"), 200)
    protected(client.get("/health/ready"), 503)
    protected(
        client.post(
            "/v1/tasks/claim",
            headers={**p["agent_auth"], "X-Execution-Token": "c" * 32},
            json={"lease_seconds": 300},
        ),
        204,
    )


def test_unhandled_error_is_not_cached_or_exposed(app):
    @app.get("/v1/test-crash")
    def crash():
        raise RuntimeError("private artifact must not escape")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/v1/test-crash")
    protected(response, 500)
    assert response.json()["detail"] == "Internal error"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "private artifact" not in response.text
