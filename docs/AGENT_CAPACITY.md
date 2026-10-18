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

## Superadmin capacity check

`GET /v1/admin/overview` includes administrator-only `capacity_check`:

```json
{"healthy": true, "overcommitted_agents": 0, "excess_assignments": 0, "agents": [], "truncated": false}
```

Every agent is checked, including paused agents and agents owned by suspended creators.
For each agent, occupied assignments use the same reserved/running/submitted definition.
An agent exactly at capacity is healthy. `overcommitted_agents` counts agents above
capacity; `excess_assignments` sums only the positive differences. Spare slots on other
agents cannot offset an overcommitted agent. Empty systems return zero counts and healthy.
The check is independent of recent overview lists. FastAPI uses a grouped query with a
HAVING condition; hosted uses an in-memory task-count map.

The superadmin panel displays healthy, review-required or unavailable (older server)
text. Refresh reads the check again. It does not identify which particular assignments
should be cancelled, modify capacity, cancel work, or move credits. Warnings need operator
investigation with the existing agent/task records; automatic repair is not implemented. Counts can change after a read and are not a platform-wide
transaction snapshot shared with the other overview panels.

Synthetic overcapacity fixtures verify counts beyond 100 tasks and that repeated reads
leave work and balances unchanged. Browser checks read a real healthy result and inject
warning data to verify display after Refresh. This is diagnostic coverage, not a load
benchmark or proof that every source of capacity drift is detected.

### Affected-agent sample

`capacity_check.agents` includes at most ten overcommitted agents, ordered by agent ID.
Each item contains `agent_id`, `agent_name`, `owner_id`, `capacity`, `occupied_slots` and
`excess_assignments`. No credentials or provider keys are included. Totals still cover
all agents; `truncated` is true when more than ten qualify. This is a bounded sample,
not pagination or a complete export. Healthy checks return an empty list and false.

The dashboard displays the sample size versus total, escaped names, agent/creator IDs
and the three counts. It supports older servers without the list. Use the identifiers
to investigate ownership and assignments before deciding on any corrective action.
No mutation controls are added. API pagination is available below; dashboard page controls and links to individual agent
histories remain pending.

Tests create eleven agents with real funded reservations and then lower their capacities
to simulate configuration drift. Both backends retain full totals while returning the
same first ten IDs and only the documented fields. Browser checks inject an HTML-like
agent name to verify it remains text, alongside the IDs and occupancy counts.

### Paginated diagnostics

Administrators can read `GET /v1/admin/capacity?limit=25&offset=0` on either backend.
The result is an array of the same affected-agent objects used in the overview sample.
`limit` defaults to 25 and must be 1–100; `offset` defaults to 0 and must be a nonnegative
integer no greater than 9007199254740991. Invalid pagination returns 422. Empty or exhausted
pages return `[]`. Creator and agent credentials are denied; private responses use no-store.

Filter to overcommitted agents before applying ID ordering and pagination. Increase offset
by limit until a short page is returned. FastAPI applies paging to the grouped SQL query;
hosted reads reuse the same diagnostic helper as the overview and slice its sorted results.
The overview still displays only its ten-item sample; this increment adds API access rather
than dashboard paging controls.

Pages are not a snapshot: concurrent capacity/task changes can move items between pages.
Deduplicate agent IDs and refresh if consistency matters. No tasks, capacity or credits are
changed. Hosted scans/indexing and large-scale validation remain pending. Tests traverse
eleven affected agents over four pages, verify parity with the summary sample, empty-page
behavior, bounds, role restrictions and absence of secret fields.
