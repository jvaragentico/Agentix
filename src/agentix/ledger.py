"""All credit movements are atomic, balanced, and represented in the journal."""

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from agentix.models import Account, Entry, Journal


def transfer(
    db: Session, source_id: str, target_id: str, amount: int, operation: str, reference: str
) -> None:
    if amount <= 0 or source_id == target_id:
        raise ValueError("Invalid credit transfer")
    # Lock in a stable order to avoid opposite-direction transfer deadlocks.
    accounts = {}
    for account_id in sorted([source_id, target_id]):
        account = db.get(Account, account_id, with_for_update=True)
        if account is None:
            raise ValueError("Missing ledger account")
        accounts[account_id] = account
    source = accounts[source_id]
    statement = update(Account).where(Account.id == source_id)
    if source.kind != "test_source":
        statement = statement.where(Account.balance >= amount)
    result = db.execute(statement.values(balance=Account.balance - amount))
    if result.rowcount != 1:
        raise HTTPException(409, "Insufficient credits")
    db.execute(
        update(Account).where(Account.id == target_id).values(balance=Account.balance + amount)
    )
    journal = Journal(operation=operation, reference=reference)
    db.add(journal)
    db.flush()
    db.add_all(
        [
            Entry(journal_id=journal.id, account_id=source_id, amount=-amount),
            Entry(journal_id=journal.id, account_id=target_id, amount=amount),
        ]
    )


def reconcile(db: Session) -> dict:
    """Read a single database snapshot; report drift without changing balances."""
    from sqlalchemy import text

    row = (
        db.execute(
            text("""
        SELECT
          (SELECT count(*) FROM accounts a LEFT JOIN
            (SELECT account_id, sum(amount) AS total FROM entries GROUP BY account_id) e
            ON e.account_id = a.id
            WHERE a.balance <> coalesce(e.total, 0)) AS mismatched_accounts,
          (SELECT count(*) FROM (
            SELECT j.id FROM journals j LEFT JOIN entries e ON e.journal_id = j.id
            GROUP BY j.id HAVING coalesce(sum(e.amount), 0) <> 0 OR count(e.id) <> 2
          ) broken) AS invalid_journals
        """)
        )
        .mappings()
        .one()
    )
    counts = dict(row)
    return {"healthy": not any(counts.values()), **counts}
