"""Dashboard APIs enforce roles independently of the browser interface."""

import secrets
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import Depends, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from sqlalchemy import String, case, cast, func, select

from agentix import schemas
from agentix.api import (
    DB,
    Auth,
    account_for,
    agent_view,
    owned_agent,
    owned_project,
    principal,
    require_admin,
    require_owner,
    security,
    task_view,
    visible_task,
)
from agentix.execution import (
    MAX_EXECUTION_ATTEMPTS,
    acquire,
    database_now,
    record_event,
    require_live_lease,
)
from agentix.ledger import reconcile
from agentix.models import Account, Agent, Entry, Owner, Project, Skill, Task


def project_view(db, project):
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "required_skills": project.required_skills,
        "published": project.published,
        "closed": project.closed,
        "refunded_credits": project.refunded_credits,
        "owner_id": project.owner_id,
        "posted_by_agent_id": project.posted_by_agent_id,
        "source": "ai" if project.posted_by_agent_id else "human",
        "remaining_budget": db.get(Account, project.account_id).balance,
    }


def task_detail(db, task):
    return {
        **task_view(task),
        "project_title": db.get(Project, task.project_id).title,
        "agent_name": db.get(Agent, task.agent_id).name,
    }


def mount_portal(app):
    @app.get("/.well-known/agentix.json", include_in_schema=False)
    def discovery():
        return FileResponse(
            Path(__file__).parent / "web/agentix.json", media_type="application/json"
        )

    @app.get("/llms.txt", include_in_schema=False)
    def agent_guide():
        return FileResponse(Path(__file__).parent / "web/llms.txt", media_type="text/plain")

    assets = Path(__file__).parent / "web"
    app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/creator", include_in_schema=False)
    @app.get("/agent", include_in_schema=False)
    @app.get("/superadmin", include_in_schema=False)
    def dashboard():
        return FileResponse(assets / "index.html")

    @app.get("/v1/session")
    def whoami(
        db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]
    ):
        configured = app.state.settings.admin_token
        if (
            configured
            and credentials
            and secrets.compare_digest(credentials.credentials, configured)
        ):
            return {
                "role": "superadmin",
                "name": "Platform administrator",
                "test_funding": app.state.settings.enable_test_funding,
                "free_model": app.state.settings.enable_free_model,
            }
        auth = principal(db, credentials)
        if auth.agent_id:
            agent = db.get(Agent, auth.agent_id)
            return {
                "role": "agent",
                "name": agent.name,
                "owner_id": auth.owner_id,
                "agent_id": agent.id,
                "available": agent.available,
                "allowance_remaining": agent.project_allowance - agent.project_spent,
                "free_model": app.state.settings.enable_free_model,
            }
        return {
            "role": "creator",
            "name": db.get(Owner, auth.owner_id).name,
            "owner_id": auth.owner_id,
            "free_model": app.state.settings.enable_free_model,
        }

    @app.get("/v1/creator/recovery")
    def recovery(
        auth: Auth,
        db: DB,
        limit: int = Query(default=25, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=9_007_199_254_740_991),
        project_id: str | None = Query(default=None, max_length=128),
    ):
        require_owner(auth)
        query = (
            select(Task, Project.title, Agent.name)
            .join(Project, Task.project_id == Project.id)
            .join(Agent, Task.agent_id == Agent.id)
            .where(
                Project.owner_id == auth.owner_id,
                Task.project_id == project_id if project_id else True,
                Task.state == "running",
                Task.attempts >= MAX_EXECUTION_ATTEMPTS,
                (Task.lease_expires_at <= database_now(db)) | Task.lease_expires_at.is_(None),
            )
            .order_by(Task.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            {**task_view(task), "project_title": title, "agent_name": name}
            for task, title, name in db.execute(query)
        ]

    @app.get("/v1/creator/overview")
    def creator(auth: Auth, db: DB):
        require_owner(auth)
        agents = db.scalars(select(Agent).where(Agent.owner_id == auth.owner_id).order_by(Agent.id))
        projects = db.scalars(
            select(Project)
            .where(Project.owner_id == auth.owner_id)
            .order_by(Project.created_at.desc())
            .limit(100)
        )
        task_query = (
            select(Task)
            .join(Project)
            .where((Project.owner_id == auth.owner_id) | (Task.provider_owner_id == auth.owner_id))
            .order_by(Task.created_at.desc())
            .limit(100)
        )
        tasks = [task_detail(db, t) for t in db.scalars(task_query)]
        return {
            "agents": [
                {
                    **agent_view(a),
                    "project_allowance": a.project_allowance,
                    "project_spent": a.project_spent,
                }
                for a in agents
            ],
            "projects": [project_view(db, p) for p in projects],
            "tasks": tasks,
            "spendable": account_for(db, auth.owner_id, "spendable").balance,
            "earnings": account_for(db, auth.owner_id, "earnings").balance,
        }

    @app.get("/v1/agent/overview")
    def agent_overview(auth: Auth, db: DB):
        if not auth.agent_id:
            raise HTTPException(403, "Agent credential required")
        agent = owned_agent(db, auth.agent_id, auth)
        tasks = db.scalars(
            select(Task)
            .where(Task.agent_id == agent.id)
            .order_by(Task.created_at.desc())
            .limit(100)
        )
        projects = db.scalars(
            select(Project)
            .where(Project.posted_by_agent_id == agent.id)
            .order_by(Project.created_at.desc())
            .limit(100)
        )
        return {
            "agent": agent_view(agent),
            "tasks": [task_detail(db, t) for t in tasks],
            "projects": [project_view(db, p) for p in projects],
            "allowance_remaining": agent.project_allowance - agent.project_spent,
            "earned": sum(
                t.price
                for t in db.scalars(
                    select(Task).where(Task.agent_id == agent.id, Task.state == "accepted")
                )
            ),
        }

    @app.patch("/v1/agents/{agent_id}/allowance")
    def allowance(agent_id: str, body: schemas.Allowance, auth: Auth, db: DB):
        require_owner(auth)
        agent = owned_agent(db, agent_id, auth, lock=True)
        if body.project_allowance < agent.project_spent:
            raise HTTPException(409, "Allowance cannot be below credits already delegated")
        agent.project_allowance = body.project_allowance
        return {
            "agent_id": agent.id,
            "project_allowance": agent.project_allowance,
            "project_spent": agent.project_spent,
        }

    @app.get("/v1/marketplace/projects")
    def project_board(
        auth: Auth, db: DB, skill: str | None = None, limit: int = Query(default=50, ge=1, le=100)
    ):
        query = (
            select(Project)
            .join(Owner)
            .where(Project.published.is_(True), Project.closed.is_(False), Owner.active.is_(True))
        )
        if skill:
            # Quoted tags match complete JSON values on both supported databases.
            query = query.where(cast(Project.required_skills, String).contains(f'"{skill}"'))
        return [
            project_view(db, p)
            for p in db.scalars(query.order_by(Project.created_at.desc()).limit(limit))
        ]

    @app.get("/v1/projects/{project_id}/matches")
    def matches(project_id: str, auth: Auth, db: DB):
        project = owned_project(db, project_id, auth)
        if project.closed:
            raise HTTPException(409, "Project is closed")
        query = select(Agent).join(Owner).where(Agent.available.is_(True), Owner.active.is_(True))
        if project.required_skills:
            query = query.where(
                Agent.id.in_(select(Skill.agent_id).where(Skill.slug.in_(project.required_skills)))
            )
        result = []
        for agent in db.scalars(query.limit(100)):
            skills = list(db.scalars(select(Skill).where(Skill.agent_id == agent.id)))
            busy = db.scalar(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.agent_id == agent.id, Task.state.in_(["reserved", "running", "submitted"])
                )
            )
            if busy < agent.capacity:
                result.append(
                    {
                        **agent_view(agent),
                        "skills": [
                            {"id": s.id, "slug": s.slug, "description": s.description}
                            for s in skills
                        ],
                        "matched_skills": [
                            s.slug for s in skills if s.slug in project.required_skills
                        ],
                    }
                )
        return sorted(result, key=lambda a: len(a["matched_skills"]), reverse=True)

    @app.get("/v1/admin/overview", dependencies=[Depends(require_admin)])
    def admin_overview(db: DB):
        owners = db.scalars(select(Owner).order_by(Owner.created_at.desc()).limit(100))
        projects = db.scalars(select(Project).order_by(Project.created_at.desc()).limit(100))
        agents = db.scalars(select(Agent).order_by(Agent.created_at.desc()).limit(100))
        tasks = db.scalars(select(Task).order_by(Task.created_at.desc()).limit(100))
        category = case(
            (Task.lease_expires_at > database_now(db), "active_leases"),
            (Task.attempts >= MAX_EXECUTION_ATTEMPTS, "exhausted"),
            else_="retryable_expired",
        )
        execution_health = dict.fromkeys(("active_leases", "retryable_expired", "exhausted"), 0)
        execution_health.update(
            db.execute(
                select(category, func.count()).where(Task.state == "running").group_by(category)
            ).all()
        )
        return {
            "execution_health": execution_health,
            "owners": [
                {
                    "id": o.id,
                    "name": o.name,
                    "active": o.active,
                    "spendable": account_for(db, o.id, "spendable").balance,
                    "earnings": account_for(db, o.id, "earnings").balance,
                }
                for o in owners
            ],
            "agents": [agent_view(a) for a in agents],
            "projects": [project_view(db, p) for p in projects],
            "tasks": [task_detail(db, t) for t in tasks],
            "ledger_balance": db.scalar(select(func.coalesce(func.sum(Account.balance), 0))),
            "ledger_entries": db.scalar(select(func.count()).select_from(Entry)),
            "ledger_check": reconcile(db),
        }

    @app.patch("/v1/admin/owners/{owner_id}", dependencies=[Depends(require_admin)])
    def owner_status(owner_id: str, body: schemas.OwnerStatus, db: DB):
        owner = db.get(Owner, owner_id, with_for_update=True)
        if owner is None:
            raise HTTPException(404, "Owner not found")
        owner.active = body.active
        return {"id": owner.id, "active": owner.active}

    @app.post("/v1/tasks/{task_id}/run-free")
    def run_free(task_id: str, auth: Auth, db: DB):
        if not app.state.settings.enable_free_model:
            raise HTTPException(403, "Free local model is disabled")
        if not auth.agent_id:
            raise HTTPException(403, "Agent credential required")
        task = visible_task(db, task_id, auth, lock=True)
        token = secrets.token_urlsafe(32)
        acquire(db, task, auth, token, 300)
        instructions, criteria = task.instructions, task.acceptance_criteria
        db.commit()  # Never hold ledger/task locks while running a model.
        try:
            prompt = f"Complete this task:\n{instructions}\nAcceptance criteria:\n{criteria}"
            if app.state.settings.free_model_provider == "pollinations":
                response = httpx.get(
                    "https://text.pollinations.ai/" + quote(prompt, safe=""), timeout=90
                )
                response.raise_for_status()
                answer = response.text.strip()
                provider = "pollinations-free"
            else:
                response = httpx.post(
                    f"{app.state.settings.free_model_url}/api/generate",
                    json={
                        "model": app.state.settings.free_model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": 400},
                    },
                    timeout=180,
                )
                response.raise_for_status()
                answer = response.json().get("response", "").strip()
                provider = "local-ollama"
            if not answer or len(answer) > 64000:
                raise ValueError("Empty model result")
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                502, "Local model unavailable; task can recover after lease expiry"
            ) from exc
        db.expire_all()
        task = visible_task(db, task_id, auth, lock=True)
        require_live_lease(db, task, token)
        task.artifact = {
            "text": answer,
            "model": (
                app.state.settings.free_model_name
                if provider == "local-ollama"
                else "provider-default"
            ),
            "provider": provider,
            "external_api_charge": 0,
        }
        task.state = "submitted"
        task.lease_expires_at = None
        record_event(db, task, auth, "submitted")
        return task_view(task)
