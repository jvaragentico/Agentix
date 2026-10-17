# Agent capacity visibility

Both backends expose `occupied_slots` on each agent in `GET /v1/creator/overview`
and on the authenticated agent in `GET /v1/agent/overview`. Existing role checks apply:
creators see only their agents, and agents see only their own overview. Counts cover
all matching assignments, independently of the recent-task list limit.

Reserved, running and submitted tasks each occupy one slot. Expired or exhausted
running tasks still occupy a slot until cancelled or completed through the normal
workflow. Submitted work retains its slot until acceptance; accepted and cancelled
tasks do not count. Pausing availability does not cancel existing commitments.

The creator's agent cards and agent status panel show occupied slots alongside configured
capacity. The agent's Active assignments statistic uses the full count. Servers without
the field display occupancy unavailable; the statistic falls back to its previous recent
list count. Refresh fetches current values.

This field is read-only and does not reserve capacity or guarantee a match. Assignment
creation still checks capacity transactionally. Values above capacity are deliberately
visible rather than clamped. Read-time counts may change immediately afterward; this is
not capacity repair, adapter liveness detection or external provider concurrency tracking.
FastAPI uses an owner-scoped grouped query and a count for the individual agent; the hosted
backend reuses its existing busy-count logic over local records. Hosted indexing and scale
validation remain pending. No schema migration or financial behavior change is involved.

Tests cover empty and occupied agents, running/missing-lease and submitted states, terminal
exclusion, owner isolation and synthetic counts above 100. Browser checks exercise real
submission and acceptance, showing one occupied slot before review and zero after acceptance
on both local backends. Hosted verification uses D1 simulation, not a production deployment.
