from concurrent.futures import ThreadPoolExecutor

import pytest
from test_workflow import balance, complete, reserve


@pytest.fixture(autouse=True)
def require_postgres(app):
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row and advisory locks")


def test_concurrent_acceptance_pays_once(client, participants):
    p = participants
    task_id = reserve(client, p).json()["id"]
    complete(client, p, task_id)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda _: client.post(f"/v1/tasks/{task_id}/accept", headers=p["buyer"]), range(6)
            )
        )
    assert all(r.status_code == 200 for r in results)
    assert balance(client, p["seller"], "earnings") == 200


def test_concurrent_duplicate_reservation_creates_one_task(client, participants):
    p = participants
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: reserve(client, p), range(6)))
    assert all(r.status_code == 201 for r in results)
    assert len({r.json()["id"] for r in results}) == 1
    assert balance(client, p["buyer"], "project") == 500


def test_concurrent_reservations_obey_agent_capacity(client, participants):
    p = participants
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda i: reserve(client, p, key=f"competing-{i}"), range(6)))
    assert sorted(r.status_code for r in results) == [201, 409, 409, 409, 409, 409]
    assert balance(client, p["buyer"], "project") == 500
