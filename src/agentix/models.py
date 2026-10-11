from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Owner(Base):
    __tablename__ = "owners"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (CheckConstraint("capacity > 0", name="agent_positive_capacity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    framework: Mapped[str] = mapped_column(String(80))
    endpoint: Mapped[str] = mapped_column(String(2048))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("agent_id", "slug", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("kind = 'test_source' OR balance >= 0", name="nonnegative_account"),
        UniqueConstraint("kind", "reference"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("owners.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    reference: Mapped[str] = mapped_column(String(36))
    balance: Mapped[int] = mapped_column(BigInteger, default=0)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("price > 0", name="positive_task_price"),
        CheckConstraint(
            "state IN ('reserved','running','submitted','accepted','cancelled')",
            name="valid_task_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    provider_owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    instructions: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[str] = mapped_column(Text)
    price: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(20), default="reserved")
    artifact: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Journal(Base):
    __tablename__ = "journals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    operation: Mapped[str] = mapped_column(String(40))
    reference: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (CheckConstraint("amount != 0", name="nonzero_entry"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    journal_id: Mapped[str] = mapped_column(ForeignKey("journals.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)


class Operation(Base):
    __tablename__ = "operations"
    scope: Mapped[str] = mapped_column(String(160), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
