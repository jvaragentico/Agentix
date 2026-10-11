import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agentix.models import Task, TaskEvent


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def database_now(db: Session) -> datetime:
    function = (
        func.clock_timestamp() if db.bind.dialect.name == "postgresql" else func.current_timestamp()
    )
    value = db.scalar(select(function))
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def expired(task: Task, now: datetime) -> bool:
    if task.lease_expires_at is None:
        return True
    expiry = task.lease_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return expiry <= now


def record_event(db: Session, task: Task, auth, kind: str):
    db.add(
        TaskEvent(
            task_id=task.id,
            actor_owner_id=auth.owner_id,
            actor_agent_id=auth.agent_id,
            kind=kind,
            attempt=task.attempts,
        )
    )


def require_token(task: Task, token: str):
    if not task.lease_token_hash or not secrets.compare_digest(
        task.lease_token_hash, digest(token)
    ):
        raise HTTPException(409, "Execution claim does not own this task")


def require_live_lease(db: Session, task: Task, token: str):
    require_token(task, token)
    if task.state != "running" or expired(task, database_now(db)):
        raise HTTPException(409, "Execution lease expired or task is not running")


def acquire(db: Session, task: Task, auth, token: str, lease_seconds: int):
    now = database_now(db)
    if task.state == "running" and not expired(task, now):
        require_token(task, token)
        return
    if task.state not in ("reserved", "running"):
        raise HTTPException(409, "Task cannot be claimed")
    if task.state == "running":
        # Fence the original attempt, even if it finishes after the new worker starts.
        if task.lease_token_hash == digest(token):
            raise HTTPException(409, "Recovery requires a new execution token")
        record_event(db, task, auth, "lease_expired")
    task.state = "running"
    task.attempts += 1
    task.lease_token_hash = digest(token)
    task.lease_expires_at = now + timedelta(seconds=lease_seconds)
    record_event(db, task, auth, "claimed")
