from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from agentix.models import Owner


def test_commit_failure_returns_conflict_instead_of_success(app, client):
    class CommitFailure(Session):
        def commit(self):
            raise IntegrityError("COMMIT", {}, RuntimeError("commit rejected"))

    app.state.sessions = sessionmaker(bind=app.state.engine, class_=CommitFailure)
    response = client.post(
        "/v1/admin/owners",
        headers={"Authorization": "Bearer test-admin"},
        json={"name": "Must not appear successful"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Conflicting record"}
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(Owner)) == 0
