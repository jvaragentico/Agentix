from sqlalchemy import select

from agentix.models import Account, Entry

ADMIN = {"Authorization": "Bearer test-admin"}


def test_reconciliation_detects_offsetting_drift_without_repair(client, app, participants):
    def check():
        response = client.get("/v1/admin/overview", headers=ADMIN)
        assert response.status_code == 200
        return response.json()

    assert check()["ledger_check"] == {
        "healthy": True,
        "mismatched_accounts": 0,
        "invalid_journals": 0,
    }
    # Offset two balances so the old total-only check still reports zero.
    with app.state.sessions.begin() as db:
        accounts = db.scalars(select(Account).where(Account.kind == "spendable")).all()
        buyer = next(a for a in accounts if a.owner_id == participants["buyer_id"])
        seller = next(a for a in accounts if a.owner_id == participants["seller_id"])
        buyer.balance -= 1
        seller.balance += 1
    first = check()
    assert first["ledger_balance"] == 0
    assert first["ledger_check"] == {
        "healthy": False,
        "mismatched_accounts": 2,
        "invalid_journals": 0,
    }
    assert check()["ledger_check"] == first["ledger_check"]
    for headers in (participants["buyer"], participants["agent_auth"]):
        assert client.get("/v1/admin/overview", headers=headers).status_code == 403


def test_reconciliation_detects_unbalanced_journal(client, app, participants):
    with app.state.sessions.begin() as db:
        entry = db.scalars(select(Entry).where(Entry.amount > 0)).first()
        entry.amount += 1
    response = client.get("/v1/admin/overview", headers=ADMIN).json()
    assert response["ledger_check"] == {
        "healthy": False,
        "mismatched_accounts": 1,
        "invalid_journals": 1,
    }
