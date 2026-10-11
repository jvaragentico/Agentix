import hashlib
import json
from collections.abc import Callable

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from agentix.models import Operation


def execute_once(db: Session, scope: str, payload: dict, action: Callable[[], dict]) -> dict:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    if db.bind.dialect.name == "postgresql":
        # Serialize the same key even before its operation row exists.
        lock_id = int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], signed=True)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
    previous = db.get(Operation, scope)
    if previous:
        if previous.request_hash != digest:
            raise HTTPException(409, "Idempotency key was already used with different input")
        return previous.response
    response = action()
    db.add(Operation(scope=scope, request_hash=digest, response=response))
    db.flush()
    return response
