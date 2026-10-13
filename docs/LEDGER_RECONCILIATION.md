# Work-credit ledger reconciliation

The superadmin overview now includes a read-only reconciliation panel. Its data is returned
by the existing admin-only `GET /v1/admin/overview` endpoint on both backends:

```json
{"ledger_check": {"healthy": true, "mismatched_accounts": 0, "invalid_journals": 0}}
```

`mismatched_accounts` counts stored account balances that differ from the sum of their
journal entries. Accounts without entries are compared with zero. `invalid_journals` counts
journals whose entries do not sum to zero or do not contain exactly two entries, as required
by the current transfer implementation. PostgreSQL also detects empty journal records;
the hosted schema represents a journal through its entries and has no independent journal row.
`healthy` means both counts are zero. This is an accounting consistency check, not a financial
audit or proof that each underlying business operation was authorized correctly.

The existing `ledger_balance` and `ledger_entries` fields remain available. A zero global
balance alone does not establish consistency: offsetting errors in two accounts can cancel
out. The new diagnostics use a single SQL statement so both counts observe one committed
database snapshot. Other overview fields are fetched separately and may reflect later or
earlier concurrent activity. Results can change immediately after a check completes.

## Responding to a warning

The dashboard shows **Review required** with mismatch counts. Review server/database access,
journal history and the relevant work-credit operations. Preserve evidence and investigate
before changing balances. This endpoint performs no repair, reversal, funding, acceptance,
refund or cash operation. Refresh reruns the check; the platform does not automatically stop
work or settlement when a warning is present. Creator and agent credentials cannot access it.

If connected to an older server without this field, the dashboard reports reconciliation
unavailable instead of reporting a healthy result. The existing owner-private Site is not
upgraded by this branch; its identity and sharing remain unchanged.

## Validation and remaining work

PostgreSQL and hosted integration tests deliberately introduce offsetting balance drift and
an unbalanced journal in disposable fixtures, verify detection, verify repeated reads do not
repair drift, and check creator/agent isolation. Normal funding, reservations, acceptance and
refund flows remain covered by the existing suites.

The browser workflow verifies a healthy result after real local operations on each backend.
It separately injects an inconsistent API response to test the warning display; this UI check
does not corrupt the running database. Hosted execution uses the local D1 simulation, not a
production deployment. No external financial or model API is needed.

The query aggregates the journal on each admin overview request. It is not an incremental
or scheduled audit; large-ledger performance, alerting, detailed discrepancy pagination,
repair procedures, backup restoration and external payment reconciliation remain pending.
Credits remain nonredeemable work credits. No cash deposits, payouts or provider keys are added.
