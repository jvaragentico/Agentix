import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentix import schemas
from agentix.config import Settings
from agentix.db import make_engine, make_sessions
from agentix.execution import (
    acquire,
    database_now,
    digest,
    record_event,
    require_live_lease,
    require_token,
)
from agentix.idempotency import execute_once
from agentix.ledger import transfer
from agentix.models import Account, Agent, Entry, Owner, Project, Skill, Task, TaskEvent, new_id

security = HTTPBearer(auto_error=False)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Principal:
    owner_id: str
    agent_id: str | None = None


def session(request: Request):
    with request.app.state.sessions() as db:
        try:
            yield db
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Conflicting record") from exc
        except Exception:
            db.rollback()
            raise


# Complete the transaction before sending a successful response. Request-scoped
# cleanup can otherwise race the client's next request or hide commit failures.
DB = Annotated[Session, Depends(session, scope="function")]


def principal(
    db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]
):
    if credentials is None:
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    digest = token_hash(credentials.credentials)
    owner = db.scalar(select(Owner).where(Owner.token_hash == digest, Owner.active.is_(True)))
    if owner:
        return Principal(owner_id=owner.id)
    agent = db.scalar(select(Agent).where(Agent.token_hash == digest))
    if agent and db.get(Owner, agent.owner_id).active:
        return Principal(owner_id=agent.owner_id, agent_id=agent.id)
    raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})


Auth = Annotated[Principal, Depends(principal)]
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)]
ExecutionToken = Annotated[str, Header(alias="X-Execution-Token", min_length=32, max_length=128)]


def require_owner(auth: Principal):
    if auth.agent_id is not None:
        raise HTTPException(403, "Owner credential required")


def require_admin(request: Request, credentials=Depends(security)):
    configured = request.app.state.settings.admin_token
    if not configured:
        raise HTTPException(503, "Administrative provisioning is disabled")
    if credentials is None or not secrets.compare_digest(credentials.credentials, configured):
        raise HTTPException(403, "Administrator credential required")


def owned_agent(db: Session, agent_id: str, auth: Principal, lock: bool = False):
    agent = db.get(Agent, agent_id, with_for_update=lock)
    if agent is None or agent.owner_id != auth.owner_id:
        raise HTTPException(404, "Agent not found")
    if auth.agent_id is not None and auth.agent_id != agent_id:
        raise HTTPException(404, "Agent not found")
    return agent


def owned_project(db: Session, project_id: str, auth: Principal, lock: bool = False):
    project = db.get(Project, project_id, with_for_update=lock)
    if project is None or project.owner_id != auth.owner_id:
        raise HTTPException(404, "Project not found")
    if auth.agent_id is not None and project.posted_by_agent_id != auth.agent_id:
        raise HTTPException(404, "Project not found")
    return project


def account_for(db: Session, owner_id: str, kind: str):
    return db.scalar(select(Account).where(Account.owner_id == owner_id, Account.kind == kind))


def agent_view(agent: Agent):
    return {
        key: getattr(agent, key)
        for key in ("id", "owner_id", "name", "framework", "endpoint", "available", "capacity")
    }


def task_view(task: Task):
    result = {
        key: getattr(task, key)
        for key in (
            "id",
            "project_id",
            "agent_id",
            "skill_id",
            "provider_owner_id",
            "instructions",
            "acceptance_criteria",
            "price",
            "state",
            "artifact",
            "attempts",
        )
    }
    expiry = task.lease_expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    result["lease_expires_at"] = expiry.isoformat() if expiry is not None else None
    return result


def visible_task(db: Session, task_id: str, auth: Principal, lock: bool = False):
    task = db.get(Task, task_id, with_for_update=lock)
    if task:
        project = db.get(Project, task.project_id)
        if auth.agent_id is not None:
            if task.agent_id == auth.agent_id:
                return task
        elif auth.owner_id in (project.owner_id, task.provider_owner_id):
            return task
    raise HTTPException(404, "Task not found")


def create_app(settings: Settings | None = None, engine=None):
    app = FastAPI(
        title="Agentix",
        version="0.2.0",
        description="Framework-independent agent work coordination and test-credit accounting.",
    )
    app.state.settings = settings or Settings()
    app.state.engine = engine or make_engine(app.state.settings.database_url)
    app.state.sessions = make_sessions(app.state.engine)

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(db: DB):
        try:
            db.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
        except Exception as exc:
            raise HTTPException(
                503, "Database migrations are required or database unavailable"
            ) from exc
        return {"status": "ready"}

    @app.post("/v1/admin/owners", status_code=201, dependencies=[Depends(require_admin)])
    def provision_owner(body: schemas.OwnerCreate, db: DB):
        token = secrets.token_urlsafe(32)
        owner = Owner(name=body.name, token_hash=token_hash(token))
        db.add(owner)
        db.flush()
        for kind in ("spendable", "earnings"):
            db.add(Account(owner_id=owner.id, kind=kind, reference=owner.id))
        db.flush()
        return {"id": owner.id, "name": owner.name, "api_key": token}

    @app.post("/v1/admin/owners/{owner_id}/test-funding", dependencies=[Depends(require_admin)])
    def test_funding(owner_id: str, body: schemas.Funding, key: Key, db: DB):
        if not app.state.settings.enable_test_funding:
            raise HTTPException(403, "Test funding is disabled")
        owner = db.get(Owner, owner_id, with_for_update=True)
        if owner is None:
            raise HTTPException(404, "Owner not found")

        def fund():
            source = db.scalar(select(Account).where(Account.kind == "test_source"))
            if source is None:
                source = Account(kind="test_source", reference="test_source")
                db.add(source)
                db.flush()
            transfer(
                db,
                source.id,
                account_for(db, owner_id, "spendable").id,
                body.amount,
                "test_funding",
                owner_id,
            )
            return {"owner_id": owner_id, "amount": body.amount, "unit": "TEST_CREDIT"}

        # Serialize creation of the single source account across different owners.
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(714812001)"))
        return execute_once(db, f"fund:{owner_id}:{key}", body.model_dump(), fund)

    @app.get("/v1/me")
    def me(auth: Auth):
        return {"owner_id": auth.owner_id, "agent_id": auth.agent_id}

    @app.post("/v1/agents", status_code=201)
    def register_agent(body: schemas.AgentCreate, auth: Auth, db: DB):
        require_owner(auth)
        token = secrets.token_urlsafe(32)
        values = body.model_dump(mode="json")
        agent = Agent(owner_id=auth.owner_id, token_hash=token_hash(token), **values)
        db.add(agent)
        db.flush()
        return {**agent_view(agent), "api_key": token}

    @app.patch("/v1/agents/{agent_id}/availability")
    def availability(agent_id: str, body: schemas.Availability, auth: Auth, db: DB):
        agent = owned_agent(db, agent_id, auth, lock=True)
        agent.available = body.available
        return agent_view(agent)

    @app.post("/v1/agents/{agent_id}/rotate-key")
    def rotate_key(agent_id: str, auth: Auth, db: DB):
        require_owner(auth)
        agent = owned_agent(db, agent_id, auth, lock=True)
        token = secrets.token_urlsafe(32)
        agent.token_hash = token_hash(token)
        return {"agent_id": agent.id, "api_key": token}

    @app.post("/v1/agents/{agent_id}/skills", status_code=201)
    def publish_skill(agent_id: str, body: schemas.SkillCreate, auth: Auth, db: DB):
        require_owner(auth)
        owned_agent(db, agent_id, auth)
        skill = Skill(agent_id=agent_id, **body.model_dump())
        db.add(skill)
        db.flush()
        return {"id": skill.id, "agent_id": agent_id, **body.model_dump()}

    @app.get("/v1/agents")
    def discover(
        auth: Auth,
        db: DB,
        skill: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        query = select(Agent).join(Owner).where(Agent.available.is_(True), Owner.active.is_(True))
        if skill:
            query = query.where(Agent.id.in_(select(Skill.agent_id).where(Skill.slug == skill)))
        return [
            agent_view(a) for a in db.scalars(query.order_by(Agent.id).limit(limit).offset(offset))
        ]

    @app.get("/v1/agents/{agent_id}/skills")
    def get_skills(agent_id: str, auth: Auth, db: DB):
        agent = db.get(Agent, agent_id)
        if agent is None or (not agent.available and agent.owner_id != auth.owner_id):
            raise HTTPException(404, "Agent not found")
        return [
            {
                key: getattr(s, key)
                for key in (
                    "id",
                    "agent_id",
                    "slug",
                    "version",
                    "description",
                    "input_schema",
                    "output_schema",
                )
            }
            for s in db.scalars(select(Skill).where(Skill.agent_id == agent_id).order_by(Skill.id))
        ]

    @app.post("/v1/projects", status_code=201)
    def create_project(body: schemas.ProjectCreate, key: Key, auth: Auth, db: DB):
        def create():
            if auth.agent_id is not None:
                agent = owned_agent(db, auth.agent_id, auth, lock=True)
                if body.budget > agent.project_allowance - agent.project_spent:
                    raise HTTPException(
                        403, "Project budget exceeds the owner's delegated allowance"
                    )
                agent.project_spent += body.budget
            project_id = new_id()
            account = Account(owner_id=auth.owner_id, kind="project", reference=project_id)
            db.add(account)
            db.flush()
            project = Project(
                id=project_id,
                owner_id=auth.owner_id,
                title=body.title,
                account_id=account.id,
                description=body.description,
                required_skills=body.required_skills,
                published=body.published,
                posted_by_agent_id=auth.agent_id,
            )
            db.add(project)
            transfer(
                db,
                account_for(db, auth.owner_id, "spendable").id,
                account.id,
                body.budget,
                "project_funding",
                project_id,
            )
            return {
                "id": project.id,
                "title": project.title,
                "owner_id": project.owner_id,
                "budget": body.budget,
                "source": "ai" if auth.agent_id else "human",
            }

        actor = auth.agent_id or auth.owner_id
        return execute_once(db, f"project:{actor}:{key}", body.model_dump(), create)

    @app.get("/v1/projects/{project_id}")
    def get_project(project_id: str, auth: Auth, db: DB):
        project = owned_project(db, project_id, auth)
        return {
            "id": project.id,
            "title": project.title,
            "owner_id": project.owner_id,
            "remaining_budget": db.get(Account, project.account_id).balance,
        }

    @app.post("/v1/projects/{project_id}/tasks", status_code=201)
    def create_task(project_id: str, body: schemas.TaskCreate, key: Key, auth: Auth, db: DB):
        def create():
            project = owned_project(db, project_id, auth, lock=True)
            agent = db.get(Agent, body.agent_id, with_for_update=True)
            skill = db.get(Skill, body.skill_id)
            if agent is None or skill is None or skill.agent_id != agent.id:
                raise HTTPException(404, "Agent skill not found")
            owner = db.get(Owner, agent.owner_id)
            if not agent.available or not owner.active:
                raise HTTPException(409, "Agent is unavailable")
            active = db.scalar(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.agent_id == agent.id, Task.state.in_(["reserved", "running", "submitted"])
                )
            )
            if active >= agent.capacity:
                raise HTTPException(409, "Agent has no spare capacity")
            task_id = new_id()
            escrow = Account(owner_id=auth.owner_id, kind="task", reference=task_id)
            db.add(escrow)
            db.flush()
            task = Task(
                id=task_id,
                project_id=project.id,
                account_id=escrow.id,
                provider_owner_id=agent.owner_id,
                **body.model_dump(),
            )
            db.add(task)
            transfer(db, project.account_id, escrow.id, body.price, "task_reservation", task_id)
            db.flush()
            record_event(db, task, auth, "reserved")
            return task_view(task)

        return execute_once(
            db, f"task:{auth.owner_id}:{project_id}:{key}", body.model_dump(), create
        )

    @app.get("/v1/tasks")
    def list_tasks(
        auth: Auth,
        db: DB,
        state: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        # Provider inbox: an agent credential can see only its assigned work.
        query = select(Task).where(Task.provider_owner_id == auth.owner_id)
        if auth.agent_id:
            query = query.where(Task.agent_id == auth.agent_id)
        if state:
            query = query.where(Task.state == state)
        return [
            task_view(t) for t in db.scalars(query.order_by(Task.id).limit(limit).offset(offset))
        ]

    @app.get("/v1/tasks/{task_id}")
    def get_task(task_id: str, auth: Auth, db: DB):
        return task_view(visible_task(db, task_id, auth))

    @app.post("/v1/tasks/claim")
    def claim(body: schemas.Lease, token: ExecutionToken, auth: Auth, db: DB):
        if auth.agent_id is None:
            raise HTTPException(403, "An agent credential is required to claim its inbox")
        # Serialize replay of the same claim token, including before the task is selected.
        if db.bind.dialect.name == "postgresql":
            lock_id = int.from_bytes(bytes.fromhex(digest(token))[:8], signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
        previous = db.scalar(
            select(Task).where(Task.lease_token_hash == digest(token)).with_for_update()
        )
        if previous:
            if previous.agent_id != auth.agent_id:
                raise HTTPException(409, "Execution token was already used")
            acquire(db, previous, auth, token, body.lease_seconds)
            return task_view(previous)
        now = database_now(db)
        query = (
            select(Task)
            .where(
                Task.agent_id == auth.agent_id,
                or_(
                    Task.state == "reserved",
                    (Task.state == "running") & (Task.lease_expires_at <= now),
                ),
            )
            .order_by(Task.created_at, Task.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        task = db.scalar(query)
        if task is None:
            return Response(status_code=204)
        acquire(db, task, auth, token, body.lease_seconds)
        return task_view(task)

    @app.post("/v1/tasks/{task_id}/start")
    def start(task_id: str, body: schemas.Lease, token: ExecutionToken, auth: Auth, db: DB):
        task = visible_task(db, task_id, auth, lock=True)
        if task.provider_owner_id != auth.owner_id:
            raise HTTPException(403, "Only the provider can start work")
        acquire(db, task, auth, token, body.lease_seconds)
        return task_view(task)

    @app.post("/v1/tasks/{task_id}/heartbeat")
    def heartbeat(task_id: str, body: schemas.Lease, token: ExecutionToken, auth: Auth, db: DB):
        task = visible_task(db, task_id, auth, lock=True)
        if task.provider_owner_id != auth.owner_id:
            raise HTTPException(403, "Only the provider can renew execution")
        require_live_lease(db, task, token)
        task.lease_expires_at = database_now(db) + timedelta(seconds=body.lease_seconds)
        record_event(db, task, auth, "heartbeat")
        return task_view(task)

    @app.post("/v1/tasks/{task_id}/submit")
    def submit(task_id: str, body: schemas.Submission, token: ExecutionToken, auth: Auth, db: DB):
        task = visible_task(db, task_id, auth, lock=True)
        if task.provider_owner_id != auth.owner_id:
            raise HTTPException(403, "Only the provider can submit work")
        require_token(task, token)
        if task.state in ("submitted", "accepted") and task.artifact == body.artifact:
            return task_view(task)
        require_live_lease(db, task, token)
        task.artifact = body.artifact
        task.state = "submitted"
        task.lease_expires_at = None
        record_event(db, task, auth, "submitted")
        return task_view(task)

    @app.get("/v1/tasks/{task_id}/events")
    def task_events(
        task_id: str,
        auth: Auth,
        db: DB,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        visible_task(db, task_id, auth)
        query = (
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.created_at, TaskEvent.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            {
                "id": e.id,
                "kind": e.kind,
                "attempt": e.attempt,
                "actor_owner_id": e.actor_owner_id,
                "actor_agent_id": e.actor_agent_id,
                "created_at": e.created_at.isoformat(),
            }
            for e in db.scalars(query)
        ]

    @app.post("/v1/tasks/{task_id}/accept")
    def accept(task_id: str, auth: Auth, db: DB):
        require_owner(auth)
        task = visible_task(db, task_id, auth, lock=True)
        project = db.get(Project, task.project_id)
        if project.owner_id != auth.owner_id:
            raise HTTPException(403, "Only the buyer can accept work")
        if task.state == "accepted":
            return task_view(task)
        if task.state != "submitted":
            raise HTTPException(409, "Task must have a submitted deliverable")
        transfer(
            db,
            task.account_id,
            account_for(db, task.provider_owner_id, "earnings").id,
            task.price,
            "task_acceptance",
            task.id,
        )
        task.state = "accepted"
        record_event(db, task, auth, "accepted")
        return task_view(task)

    @app.post("/v1/tasks/{task_id}/cancel")
    def cancel(task_id: str, auth: Auth, db: DB):
        require_owner(auth)
        task = visible_task(db, task_id, auth, lock=True)
        project = db.get(Project, task.project_id)
        if project.owner_id != auth.owner_id:
            raise HTTPException(403, "Only the buyer can cancel reserved work")
        if task.state == "cancelled":
            return task_view(task)
        if task.state != "reserved":
            raise HTTPException(409, "Only unstarted work can be cancelled")
        transfer(db, task.account_id, project.account_id, task.price, "task_cancellation", task.id)
        task.state = "cancelled"
        record_event(db, task, auth, "cancelled")
        return task_view(task)

    @app.get("/v1/wallet")
    def wallet(auth: Auth, db: DB):
        require_owner(auth)
        accounts = db.scalars(select(Account).where(Account.owner_id == auth.owner_id))
        return {
            "unit": "TEST_CREDIT",
            "redeemable": False,
            "spendable": account_for(db, auth.owner_id, "spendable").balance,
            "earnings": account_for(db, auth.owner_id, "earnings").balance,
            "accounts": [
                {"id": a.id, "kind": a.kind, "reference": a.reference, "balance": a.balance}
                for a in accounts
            ],
        }

    @app.get("/v1/wallet/entries")
    def entries(
        auth: Auth,
        db: DB,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        require_owner(auth)
        query = select(Entry).join(Account).where(Account.owner_id == auth.owner_id)
        return [
            {"id": e.id, "journal_id": e.journal_id, "account_id": e.account_id, "amount": e.amount}
            for e in db.scalars(query.order_by(Entry.id).limit(limit).offset(offset))
        ]

    from agentix.portal import mount_portal

    mount_portal(app)
    return app
