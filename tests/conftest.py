import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from agentix.api import create_app
from agentix.config import Settings
from agentix.db import make_engine
from agentix.models import Base


@pytest.fixture
def app(tmp_path):
    url = os.getenv("AGENTIX_TEST_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    engine = make_engine(url)
    # PostgreSQL integration tests must target a disposable database.
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.create_all(engine)
    application = create_app(
        Settings(database_url=url, admin_token="test-admin", enable_test_funding=True),
        engine=engine,
    )
    yield application
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def participants(client):
    def owner(name):
        result = client.post(
            "/v1/admin/owners", json={"name": name}, headers={"Authorization": "Bearer test-admin"}
        )
        assert result.status_code == 201
        data = result.json()
        return data["id"], {"Authorization": f"Bearer {data['api_key']}"}

    buyer_id, buyer = owner("Buyer")
    seller_id, seller = owner("Expert")
    _, outsider = owner("Unrelated owner")
    funding = client.post(
        f"/v1/admin/owners/{buyer_id}/test-funding",
        json={"amount": 1000},
        headers={"Authorization": "Bearer test-admin", "Idempotency-Key": "seed"},
    )
    assert funding.status_code == 200
    response = client.post(
        "/v1/agents",
        headers=seller,
        json={
            "name": "Expert agent",
            "framework": "hermes",
            "endpoint": "https://agent.example/api",
        },
    )
    assert response.status_code == 201
    agent = response.json()
    agent_auth = {"Authorization": f"Bearer {agent['api_key']}"}
    assert (
        client.patch(
            f"/v1/agents/{agent['id']}/availability", headers=agent_auth, json={"available": True}
        ).status_code
        == 200
    )
    skill = client.post(
        f"/v1/agents/{agent['id']}/skills",
        headers=seller,
        json={"slug": "code-review", "version": "1", "description": "Review code with evidence"},
    ).json()
    project = client.post(
        "/v1/projects",
        headers={**buyer, "Idempotency-Key": "project"},
        json={"title": "Build API", "budget": 700},
    ).json()
    return {
        "buyer_id": buyer_id,
        "buyer": buyer,
        "seller_id": seller_id,
        "seller": seller,
        "outsider": outsider,
        "agent": agent,
        "agent_auth": agent_auth,
        "skill": skill,
        "project": project,
    }
