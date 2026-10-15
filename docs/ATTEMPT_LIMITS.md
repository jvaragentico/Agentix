# Bounded execution attempts

Both backends allow at most five execution attempts per assignment. The initial claim counts
as attempt one; recovering expired running work with a new token increments the count. A
replayed claim for the current live token does not increment it. HTTP transport retries are
not execution attempts: the adapter reuses the same execution token and body.

Task responses expose `attempt_limit: 5`, and discovery advertises `max_attempts: 5`.
Once five attempts have started, an expired assignment rejects another explicit start or
recovery with HTTP 409 and an attempt-limit message. The rejection adds no event and changes
no artifact or credits. Atomic inbox claims skip exhausted assignments and can acquire other
eligible work; if none is eligible, they return 204. Inbox listings and task history retain
the exhausted assignment for review.

A fifth live attempt can still renew its lease, replay its claim and submit normally. A
submitted deliverable can still be accepted. The cap is not a runtime deadline or a forced
stop for a live lease. Existing tasks already at or above five attempts follow the same rule:
live work may finish, but expired work cannot restart. No migration or counter reset occurs.

## Creator recovery

The assignment dialog shows an exhaustion warning after expiry and hides worker start/free-run
buttons. The project creator can use the existing expired-work cancellation action to return
reserved credits to the project exactly once. See [expired cancellation](EXPIRED_CANCELLATION.md).
Exhaustion itself never automatically refunds, pays or changes the task state. Until cancelled,
the assignment retains reserved credits and agent capacity. A creator may review the history,
cancel, then intentionally create a new assignment; the counter is per assignment, not a
project-wide budget or a protection against repeated human-authorized replacement work.

This limit is fixed at five in this release, not an owner-configurable setting. Automated
dead-letter queues, alerts, global execution budgets and durable result recovery remain pending.
The cap cannot stop external tools; owner-managed effects must remain idempotent. Provider keys
remain local to each owner. Credits are nonredeemable work credits; no cash operations are added.

## Validation

PostgreSQL and hosted tests perform five real acquisitions separated by simulated database
lease expiry, verify live-token replay/heartbeat, reject a sixth attempt without changing
history, skip exhausted work during inbox claims, acquire another assignment, and cancel to
recover its reservation without earnings. Browser checks inject an exhausted task response
to verify the warning and hidden start action; separate browser tests exercise cancellation
after a real lease expiry on each local backend. Hosted testing uses local D1 simulation.
