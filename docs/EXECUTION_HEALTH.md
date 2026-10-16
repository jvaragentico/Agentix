# Execution health

`GET /v1/admin/overview` includes an administrator-only `execution_health` object on
both backends. It counts all running assignments, independently of the recent-task
list and its FastAPI limit of 100. Each running assignment appears in one category:

| Field | Meaning |
| --- | --- |
| `active_leases` | Lease expiry is strictly later than the read time, even at the attempt limit. |
| `retryable_expired` | Expired or absent lease, with fewer than five attempts. |
| `exhausted` | Expired or absent lease, with at least five attempts. |

Reserved, submitted, accepted and cancelled assignments are excluded. Empty categories
are zero. FastAPI uses one grouped database query and database time; the hosted Worker
uses its loaded task records and a single application timestamp. There is no migration.

The superadmin Execution health panel renders these counts; Refresh reads them again.
Older servers without the field display an unavailable message. This is a read-only
observation, not a repair, alerting service or guarantee that an adapter is online.
A lease may expire or change immediately after the read. Expired retryable work still
requires an eligible owner-managed worker; exhausted work requires project creator review
through the existing recovery queue. Only cancellation/acceptance operations move credits.

Tests exercise live attempts including the fifth, expired retryable and exhausted work,
cancellation exclusion, missing leases, more than 100 diagnostic fixtures and role isolation.
Browser checks read the real endpoint and inject sample counts to verify rendering after
Refresh, while the normal collaboration workflow checks settlement and role controls.
Hosted testing uses the local D1 simulation. No scale benchmark, production deployment,
automatic recovery or vendor compatibility certification is implied.
