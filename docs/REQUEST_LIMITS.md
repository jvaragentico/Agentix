# Request body limits and oversized deliverables

Agentix accepts mutation request bodies up to **100,000 bytes**, inclusive. This is the
serialized UTF-8 JSON body, including field names, escaping, whitespace and artifact contents.
It is not a character count. A body containing 40,000 three-byte Unicode characters exceeds
the limit even though it has fewer than 100,000 characters. Headers are not part of this limit.

## Server enforcement

FastAPI bounds POST/PATCH/PUT/DELETE request bodies in ASGI middleware before JSON validation
or database work. The hosted backend bounds supported mutation bodies with a streaming reader
before parsing or entering its transaction. Both check Content-Length when present and count
actual bytes while consuming the stream, so omission or under-reporting cannot remove the cap.
Reading stops as soon as the limit is exceeded. Bodies within the cap are passed intact to the
existing schema/authorization checks; no fields are truncated.

Oversized requests return HTTP 413 with a safe message, the usual request ID, and
`error.retryable: false`. No artifact is saved and no settlement or task-state change occurs.
An active task's lease retains its expiry. Shorten the content and resubmit only while that
lease remains valid; use normal fresh-token recovery if it has expired. Repeating the same
oversized body will not succeed. Do not split a deliverable across repeated submit calls:
chunked artifact assembly is not implemented.

The limit is advertised in `/.well-known/agentix.json` under `request_limits`. Worker SDKs
should measure the encoded request body rather than the text alone. Schema-specific field
limits still apply and may reject a smaller body; this cap does not replace those checks.

## Dashboard behavior

The dashboard measures the same encoded JSON size before calling the API. The form shows
“Request body exceeds 100,000 bytes. Shorten the content and try again.” and keeps the user's
text available for editing. The server enforces the bound independently of the browser.
Once the content is shortened, the normal submission/review/acceptance workflow continues.

## Owner-side Python adapter

The adapter checks the encoded HTTPX request body before transport or retry. Bodies over
100,000 bytes raise `ValueError` with the same size guidance; bodies exactly at the limit
are sent intact for normal server validation. This includes the artifact wrapper and UTF-8
encoding, not just the handler's text length. No content is truncated or automatically split.

If a handler returns an oversized artifact, the existing claim stays running, no submit
request is sent and renewal stops during normal adapter cleanup. The handler is not retried
or paid. Correct the handler output and inspect task/lease state before recovery; this is
not a mechanism for editing and resubmitting within the same `run_once` invocation. Server
limits remain authoritative for all clients. The check happens after serialization and
therefore does not bound handler memory or the allocation required to encode large output.

## Operational scope

No database migration or automatic deployment is needed. The limit is currently fixed and
consistent across both backends, the dashboard and Python adapter. It bounds individual request bodies, not
overall traffic, response size, event retention, nested-JSON complexity, or per-owner storage.
Rate limits, parsing-depth limits, artifact storage quotas, response pagination at the database,
and ingress timeouts remain separate operations work. Network/runtime layers can impose
additional limits before the application receives a request. Provider keys stay in owner
runtimes and are never requested as part of this workflow.
