# Security notes

This document lists the controls in Quotient, the threat each one addresses,
and the test that holds it in place. Every claim below is covered by the test
suite in `backend/tests`.

## Authentication

**Password storage.** Passwords are hashed with Argon2id (memory hard, time
cost 2, parallelism 2) and verified with a constant time comparison. Failed
logins for an unknown address still run a hash verification against a dummy
hash so the response time does not reveal whether an account exists.

*Tests:* `test_auth.py::test_login_for_unknown_account_is_indistinguishable`,
`test_auth.py::test_login_rejects_wrong_password`.

**Session tokens.** A signed HS256 token is issued for sixty minutes and
stored in an `HttpOnly`, `SameSite=Lax` cookie. `Secure` and HSTS are turned
on in production. The token carries the user id, the role and the CSRF value.

*Tests:* `test_hardening.py::test_garbage_session_token_is_rejected`,
`test_hardening.py::test_session_token_cannot_be_forged` (including an
`alg: none` token).

**Password policy.** At least ten characters, at least one letter and one
number, with a small blocklist of common passwords. Changing a password
requires the current one.

## Authorisation

Every query that touches user data is filtered by `owner_id`, and the check
happens in the query rather than after the fetch. A request for another
account's resource returns `404` rather than `403`, so identifiers cannot be
probed by watching the status code change.

The admin surface is protected by a router level dependency, so a
non-administrator is rejected before any handler body runs.

*Tests:* `test_invoices.py::test_invoices_are_scoped_to_the_owner`,
`test_clients.py::test_clients_are_scoped_to_the_owner`,
`test_uploads.py::test_files_are_not_shared_between_accounts`,
`test_permissions.py::test_admin_routes_reject_regular_users`.

## Money

Amounts are stored as integer cents and quantities as thousandths of a unit.
Totals are recomputed from the line items on every write, and any total sent
by the client is ignored. Discount is applied before tax.

*Tests:* `test_money.py` (rounding, discount before tax, rejected ranges),
`test_invoices.py::test_client_supplied_totals_are_ignored`.

## Request integrity

**Validation.** Request bodies are Pydantic models with explicit bounds. The
invoice status filter, the pagination window and every numeric field are
range checked. Unknown fields are ignored rather than assigned, so a payload
cannot smuggle in a role.

*Tests:* `test_hardening.py::test_unknown_fields_are_ignored_on_registration`,
`test_invoices.py::test_invoice_requires_at_least_one_line_item`,
`test_invoices.py::test_invoice_rejects_negative_price`.

**CSRF.** Session cookies are sent automatically by the browser, so every
mutating request must carry an `X-CSRF-Token` header that matches a readable
cookie *and* the claim inside the signed session token. Both comparisons are
constant time.

*Tests:* `test_security.py::test_csrf_token_is_required_for_mutations`,
`test_security.py::test_mismatched_csrf_token_is_rejected`.

**Rate limiting.** A sliding window limiter guards authentication, public
invoice links, uploads and checkout. The limit and the window are resolved
per request, so the limits are configuration rather than code. Exceeding a
limit returns `429` with a `Retry-After` header.

*Tests:* `test_security.py::test_rate_limit_is_enforced_on_authentication`,
`test_security.py::test_sliding_window_limiter_blocks_after_the_limit`.

**Body size.** Requests larger than eight megabytes are rejected before the
server buffers them, and uploads are capped at two megabytes while they are
being read.

*Tests:* `test_security.py::test_oversized_request_bodies_are_rejected`,
`test_uploads.py::test_upload_rejects_oversized_files`.

## Uploads

The declared content type is never trusted. The file is sniffed by magic
bytes and has to match both the allow list and the declared type. Filenames
are sanitised, stored under a generated name and read back through a path
that is checked against the upload directory. Only PNG, JPEG and WebP are
accepted, which rules out SVG and anything that could carry a script.

*Tests:* `test_uploads.py` (type mismatch, php payload, svg payload, empty
file, oversized file, path traversal, cross account access).

## Errors and logging

Every failure returns the same envelope:

```json
{"error": {"code": "validation_error", "message": "...", "request_id": "..."}}
```

Internal exception text, SQL and stack traces never reach the client. The
request id in the response matches the one in the log, so a report can be
traced without exposing anything. Logging is structured and carries the
request id; there are no `print` calls outside the command line entry point.

*Tests:* `test_security.py::test_errors_use_a_consistent_envelope`,
`test_security.py::test_unknown_routes_return_a_json_envelope`.

## Payments

Checkout sessions are created by a provider behind a small interface. The
production implementation verifies the Stripe signature; the development
implementation signs its payloads with an HMAC and pushes them through the
same endpoint, so the verification path is exercised in every environment.

Events are de-duplicated by event id before they are applied, and applying an
event twice is a no-op. A payload without an event id is rejected outright.

*Tests:* `test_billing.py::test_webhook_rejects_a_forged_signature`,
`test_billing.py::test_webhook_processing_is_idempotent`,
`test_billing.py::test_two_different_payments_are_both_applied`.

## Transport and headers

Responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`,
`Cross-Origin-Resource-Policy: same-origin`, a `Permissions-Policy` and a
`Content-Security-Policy`. The CSP allows scripts only from the same origin;
the single inline script on the sandbox checkout page is allowed through a
per-response nonce. HSTS is added in production.

The API is mounted under a single origin behind a reverse proxy, so the
cookie based session needs no cross site relaxation.

*Tests:* `test_security.py::test_security_headers_are_present`.

## Data at rest

The database is accessed through the ORM with parameterised statements. No
SQL is built by string formatting anywhere in the codebase. Foreign keys are
enforced, and SQLite runs with `PRAGMA foreign_keys=ON`. Uploaded files are
kept outside the web root and are only reachable through an authorised route.

*Tests:* `test_hardening.py::test_sql_metacharacters_in_a_search_term_are_treated_as_text`.

## What is not covered

- The rate limiter is per process. A multi node deployment needs Redis behind
  the same interface.
- Uploads are stored on the local disk and are not virus scanned.
- There is no password reset flow, so no email delivery path exists yet.
- The sandbox payment provider is for development only.
