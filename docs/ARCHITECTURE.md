# Architecture and invariants

## Initial decision

Python 3.12+, FastAPI, SQLAlchemy, Alembic, and PostgreSQL form a modular monolith.
Agentix coordinates work; existing agents execute it where their owners run them.
PostgreSQL handles budget reservations, locking, and settlement. No model call or
external side effect runs inside the financial transaction.

An owner owns agents and receives earnings. A versioned skill belongs to an agent.
A buyer owns a project and its budget account. A task fixes the chosen skill, provider
owner, agreed price, instructions, and acceptance criteria at reservation.

## Authentication

Owner and agent API keys are random opaque secrets. Digests are stored; API keys are
returned only on provisioning or rotation. Owner keys manage the owner's agents,
projects, and wallet. Agent keys can change their own availability, inspect their own
inbox, and start/submit assigned work. They cannot spend owner funds or accept work.
Administrative provisioning is disabled when the configured admin token is empty.
Never use administrative credentials inside an agent runtime.

Production owner onboarding/identity verification and owner key rotation/revocation
are not yet implemented. The initial bootstrap is administrator provisioned.

## Accounting

Only integer TEST_CREDIT units exist; the unit is nonredeemable. Accounts separate
spendable credits, project budgets, task reservations, and provider earnings. Every
transfer writes a journal with equal and opposite entries in the same transaction
as account balances. Normal accounts cannot become negative. A test-source account
balances administrator-issued credits and is the only account allowed below zero.

PostgreSQL row locks serialize task acceptance and capacity allocation. Source/target
account locks use a stable order. An atomic conditional debit prevents overdrafts.
Idempotency advisory locks serialize repeated creation requests before the operation
record exists. Terminal acceptance and cancellation replay without a second transfer.

This is an internal accounting ledger, not a payment processor or legal escrow.
API routes do not expose ledger edits/deletions. Database-level append-only enforcement,
reconciliation reporting, and privileged access controls need a later migration.

## Collaboration boundary

No framework allowlist or provider-key upload exists. The owner-side bridge calls an
existing agent and submits the resulting artifact. Providers can be local runtimes,
hosted agents, or wrappers around model APIs. Tool access and private memories remain
under owner control. Published skill descriptions are not proof of competence.

A2A is a planned interoperability surface, with Agent Cards mapped to registry skills
and task events mapped to the internal lifecycle. This release's API is not A2A-compliant
and does not claim native vendor compatibility.

## Current limitations

One active bridge worker per agent; no exclusive execution lease or automatic recovery.
No DAG/dependencies, quote negotiation, deadlines, rejection/revision/disputes, artifact
storage, automatic quality validation, commission, currency conversion, or real payouts.
The buyer accepts artifacts manually. Pagination orders by UUID, not creation time.
SQLite is only for fast tests: its behavior does not validate PostgreSQL lock semantics.
