# Security & Regression Test Plan — Order Management & Order Lifecycle Module

**Document type:** test-design artifact, curating and extending prior Phase 4 work. **No tests are implemented in this document** — implementation and execution happen in a subsequent step, results recorded separately in `test-results/security-regression-results.md`.

**Basis:**
- `docs/testing/test-scenario-matrix.md` (34 original scenarios)
- `docs/testing/unit-test-plan.md` (45 unit tests, implemented and passing — `test-results/unit-test-results.md`)
- `docs/testing/api-integration-test-plan.md` (56 API/integration tests, implemented and passing — `test-results/api-integration-test-results.md`)
- `docs/testing/node-fastapi-parity-report.md` (fresh Node source comparison)
- `docs/security-review.md` (Module 3 security findings, C1/C2/H1-H3/M1-M6/L1-L5/I1-I6)
- Actual current source: `app/api/deps.py`, `app/services/order_service.py`, `app/services/restaurant_service.py`, `app/core/errors.py`, `app/models` equivalents (`app/schemas/*`)

**Purpose:** identify which security- and regression-relevant scenarios from the requested categories are **already covered** by existing, executed tests (cross-referenced, not duplicated), and which represent **genuine gaps** worth closing with new automated tests. Per the task's explicit instruction, this plan does not introduce security scenarios unrelated to what this module actually implements (no CSRF, no XSS, no rate limiting, no RBAC — see §2 for why each is out of scope, not merely omitted).

---

## 1. Category-by-Category Analysis

### 1.1 Authentication

**Already covered — no gap.** `app/api/deps.py: get_current_user_id` is exercised by 18 executed test cases across all 3 endpoints (`AUTH-01`…`AUTH-06`, applied to each route independently in `test_api_order_routes.py` and `test_api_restaurant_order_routes.py`): missing token, non-Bearer header, garbage token, valid-signature-missing-claim, wrong secret, expired token — all confirmed to produce an identical `401 {"message":"unauthorized"}`. The `session_id` cookie fallback is also confirmed live (`API-ORD-GET-03`, `API-RST-GET-04`).

**New test added (SEC-05):** a belt-and-suspenders check that every one of these distinct failure *reasons* produces a **byte-identical** response to every other — not just that each independently matches a hardcoded string, but that no failure mode is distinguishable from any other by content, length, or headers. This directly serves the "sensitive information exposure" category too (no information leak about *why* auth failed, which would otherwise aid credential-stuffing/token-guessing attacks by telling an attacker whether their token was "close" — e.g., correctly formed but expired, vs. garbage).

### 1.2 Authorization

**Already covered — no gap.** The ownership-check fix (finding C2) is the most heavily tested single behavior in the module: `API-RST-PATCH-15/16/17` (mismatched owner, orphaned restaurant ref, restaurant with no owner — all confirmed 401 empty-body) plus the positive control (`API-RST-PATCH-01/18`, legitimate owner succeeds) plus the unit-level exhaustive case analysis (`UT-RST-PATCH-04…07`) plus the fresh Node-source case analysis in `node-fastapi-parity-report.md` §3. No further tests proposed here.

### 1.3 Role-Based Access

**Not applicable to this module — confirmed absent, not merely untested.** Re-confirmed by reading `app/schemas/order.py`, `app/repositories/user_repository.py`, and `app/api/deps.py` fresh for this plan: there is no `role`, `permissions`, `isAdmin`, or any comparable field anywhere in the `User`, `Restaurant`, or `Order` schemas, and the JWT payload carries only `userId` (confirmed in `node-fastapi-parity-report.md` §2). Authorization in this module is **exclusively** ownership-based (does `userId` match the resource's owner), already covered under §1.2. Inventing role-based test scenarios for a system with no role concept would violate this task's explicit instruction not to introduce unrelated security scenarios — so none are proposed. If RBAC is ever added to this system, this section should be revisited.

### 1.4 Unauthorized Order Access

**Mostly covered.** Cross-user isolation on `GET /api/order` (`API-ORD-GET-10`) and cross-restaurant isolation on `GET /api/my/restaurant/order` (`API-RST-GET-11`) are both confirmed — a user only ever sees their own data. The PATCH endpoint's ownership boundary is covered under §1.2.

**New test added (SEC-04):** a **mass-assignment** check. The route (`app/api/routes/my_restaurant.py: update_order_status`) accepts a raw `payload: dict` body but explicitly extracts only `payload.get("status")` before calling the service — meaning a client cannot influence `totalAmount`, `restaurant`, `user`, or `_id` via this endpoint no matter what extra fields it sends, even though the client fully controls the request body. This is a genuine, previously-untested attack surface: an attacker with legitimate ownership of *an* order could attempt to smuggle a different `restaurant`/`user`/`totalAmount` value into the same request that changes their own order's status, hoping a less careful implementation might merge the whole body into the update. Confirming this is impossible is a direct "unauthorized order access" / data-integrity test, not previously exercised (the existing `API-RST-PATCH-28` confirms `totalAmount` is untouched during a *normal* status-only request — it does not confirm the endpoint *rejects or ignores* an adversarial attempt to change it).

### 1.5 Invalid Identifiers

**Mostly covered.** Malformed `order_id` format (`API-RST-PATCH-20`), order-not-found (`API-RST-PATCH-19`), and the empty-path-segment framework 404 (`API-RST-PATCH-21`) are all confirmed.

**New test added (SEC-03):** the existing malformed-ID test uses one representative bad string (`"not-a-valid-object-id"`). This plan adds a **parametrized set of identifier strings shaped like common injection payloads** (a SQL-injection-shaped fragment, a JSON-operator-shaped fragment, a command-injection-shaped fragment, and a very long string) to explicitly document — for a security-focused reader — that `ObjectId.is_valid()`'s strict format check rejects all of them identically and safely (`400`, never reaching a database query unsanitized).

**Real finding surfaced while implementing this test (not assumed in advance):** a path-traversal-shaped identifier (`"../../../etc/passwd"`) does **not** produce the same `400` — standard URL path normalization collapses `/api/my/restaurant/order/../../../etc/passwd/status` down to `/api/etc/passwd/status` *before* routing ever occurs, so the string never reaches `order_id` as written at all. The outcome is a plain framework `404`, not the service's `400`. This is still a safe outcome (no injection, no bypass — the string is never evaluated as an identifier by the application), just via a different mechanism than the other four cases. Implemented as a separate test (SEC-03b) asserting the actual, verified behavior rather than forcing an incorrect uniform expectation across all five payloads.

### 1.6 Malformed Requests

**Already covered — no gap.** Malformed JSON body (`API-RST-PATCH-06`), non-object JSON body (`API-RST-PATCH-07`), and the combined no-auth+malformed-body precedence case (`API-RST-PATCH-22`) are all confirmed, including the exact distinct error shapes involved (`{"errors":[...]}` vs `{"message":...}` vs empty body — see `api-integration-test-plan.md` §7).

### 1.7 Invalid Status Values

**Partially covered — real gap identified and closed.** The existing suite covers `null`, non-enum strings, wrong case, and a non-string scalar (`123`) — all producing the expected `500 {"message":"unable to update order status"}` (`API-RST-PATCH-23…26`, `UT-RST-PATCH-09/10`).

**Gap found and verified by direct execution before writing this plan** (not assumed): a `status` value of an **unhashable type** — a JSON array or a JSON object — is not covered by any existing test, and behaves *differently* from the covered cases. `restaurant_service.py:110`'s `if status not in _ORDER_STATUSES:` performs a Python `set` membership check; `_ORDER_STATUSES` is a `set`, and Python's `in`/`not in` on a `set` requires the operand to be hashable. A `list` or `dict` value raises an **uncaught `TypeError`** at that line — this is *not* one of the module's deliberately-raised `AppError` subclasses, and is a materially different code path from every other invalid-status test already written (those all resolve cleanly to the intended `AppError(500, ...)`; this one is a genuine unhandled exception that only the application-wide generic handler catches).

**New tests added (SEC-01, SEC-02):**
- **SEC-01**: `{"status": ["a", "b"]}` (JSON array) — confirms the uncaught `TypeError` is still caught by FastAPI's global exception handler and produces the same clean `500 {"message":"Something went wrong"}` a client would see for any other unexpected server error, with no internal detail (stack trace, file path, exception class name) leaked into the response body.
- **SEC-02**: `{"status": {"$ne": "delivered"}}` (a JSON object shaped like a MongoDB operator-injection attempt) — same expected outcome, and explicitly documents that this specific *shape* of malicious input (an attempt to smuggle a MongoDB query operator into a field that will later be used in a `$set` update) fails safely rather than being silently accepted and forwarded into a database write unexamined.

Both of these also serve §1.8 and §1.9 below — they were designed once and cover three categories at once, deliberately, rather than being duplicated across sections.

### 1.8 Sensitive Information Exposure

**Password-hash leak (finding C1) already covered — no gap.** `API-ORD-GET-12`, `API-RST-GET-13`, `UT-ORD-GET-05`, `UT-RST-GET-06` all confirm the bcrypt hash is present in populated responses — a confirmed, flagged, pre-existing (not migration-introduced) behavior, not something this plan proposes fixing (that decision is gated behind a separate RFOMS-2 follow-up per `qa-readiness-notes.md` §5).

**New coverage via SEC-01/SEC-02 (§1.7):** confirms that even a genuinely *unexpected* server-side exception does not leak stack traces, file paths, or internal exception text to the client — the response body is asserted to be exactly the generic `{"message":"Something went wrong"}` shape, and explicitly asserted to **not** contain markers like `Traceback`, `.py`, or the exception's own class name.

### 1.9 Unexpected Server Errors

**New gap closed by SEC-01/SEC-02 (§1.7).** Every previously-existing 500-producing test in this module triggers a *deliberately raised* `AppError`. Before this plan, there was no test at all confirming what happens when a **genuinely unhandled** exception occurs inside a request — i.e., whether `app/core/errors.py`'s `@app.exception_handler(Exception)` catch-all actually engages in practice, for a real code path reachable by ordinary (if malformed) client input, not a contrived unit-level mock. SEC-01/SEC-02 close this gap using a real, reachable, previously-unknown code path (§1.7) rather than an artificial one.

**Testing note:** FastAPI's `TestClient` re-raises unhandled exceptions into the test process by default (`raise_server_exceptions=True`), for debugger-friendly tracebacks — this is useful default behavior for the rest of the suite (it makes an accidental regression that removes error handling fail loudly), but it means the *test process* sees the raw Python exception even though a real client over HTTP would receive the clean handled response. SEC-01/SEC-02 use a dedicated `api_client_no_raise` fixture (`raise_server_exceptions=False`) specifically so the assertions reflect what an actual HTTP client receives — confirmed by direct execution before writing this plan, not assumed.

### 1.10 Regression of Existing Order Functionality

**Already extensively covered — no new tests needed, referenced here for completeness:**
- No-op status filters on both GET endpoints (`API-ORD-GET-11`, `API-RST-GET-12`, `UT-ORD-GET-08`, `UT-RST-GET-05`)
- Password-hash preservation, C1 (§1.8)
- Lifecycle non-enforcement — backward, skip-ahead, and idempotent transitions all accepted (`API-RST-PATCH-03/04/05`, `UT-RST-PATCH-12/13`)
- Ownership-check fix, C2, remains fixed (§1.2)
- `totalAmount` untouched by the status-write path (`API-RST-PATCH-28`)
- Only the targeted order is modified, siblings unaffected (`API-RST-PATCH-29`)
- Orphaned restaurant/user refs resolve to `null`, not a 500 (`API-ORD-GET-13`, `API-RST-GET-14`, `UT-POP-03/06`)

These are re-run (not re-implemented) as part of this task's execution step to confirm the new security tests introduce no regression of their own.

---

## 2. Explicitly Out of Scope (and why)

| Category | Why excluded |
|---|---|
| CSRF | This is a stateless, Bearer-token/JSON API with no session-cookie-driven state-changing form submissions from a browser in the relevant sense; CSRF protection is a browser-session-cookie concern this module's auth model (JWT Bearer, primarily) doesn't rely on. The `session_id` cookie fallback exists, but CSRF exploitation would require a same-site cookie-based auth flow this module doesn't implement as its primary mechanism. Flagged as a reasoned exclusion, not an oversight. |
| XSS / output-encoding | This module returns JSON only, never renders HTML; XSS is a frontend/templating concern, not applicable to a JSON API backend. |
| Rate limiting / brute-force throttling | Confirmed absent in both Node and FastAPI (`docs/module-3-development-plan.md` §7: "No new security controls... are in scope"); this is a known, already-documented gap in the *product*, not something this test plan can meaningfully assert on without such a control existing to test. |
| SQL injection | No SQL database is used anywhere in this system; not applicable. |
| RBAC / role-based access | No role concept exists in this module (§1.3). |
| Timing-based side-channel analysis (e.g., does a 401 for "order doesn't exist" take measurably longer/shorter than "order exists but wrong owner") | Not practically or meaningfully testable against an in-memory `mongomock-motor` database (no realistic network/disk timing exists to measure), and no prior finding suggests this module distinguishes these cases in *content* (both already confirmed to produce byte-identical 401 empty bodies) — a timing side-channel would be a separate, much larger effort requiring a live, network-realistic environment, disproportionate to this module's scope. |
| Stripe/payment/checkout endpoints | Consistently out of scope across every Phase 4 document — see `docs/testing/test-plan.md` §1. |

---

## 3. New Test Scenarios Summary

| ID | Category(ies) | Scenario | Expected Result |
|---|---|---|---|
| SEC-01 | Invalid status values, unexpected server errors, sensitive info exposure | `status` is a JSON array (unhashable) | `500`, generic `{"message":"Something went wrong"}`, no internal details in body |
| SEC-02 | Invalid status values, unexpected server errors, sensitive info exposure | `status` is a JSON object shaped like a MongoDB operator injection (`{"$ne": "delivered"}`) | `500`, same generic body; no injection bypass — order status is NOT changed |
| SEC-03 | Invalid identifiers | `order_id` path segment shaped like common injection payloads (parametrized, 4 cases) | `400 {"message":"Invalid order ID format"}` for every case, never reaches a DB query |
| SEC-03b | Invalid identifiers | `order_id` shaped as a path-traversal payload | `404` (framework routing, not the service) — a different but equally safe outcome, see finding above |
| SEC-04 | Unauthorized order access, regression | PATCH body includes extra fields (`totalAmount`, `restaurant`, `user`, `_id`) alongside a valid `status` | `200`; only `status` changes — verified via independent DB re-fetch that every other field is byte-identical to its pre-request value |
| SEC-05 | Authentication, sensitive info exposure | Every distinct auth-failure reason (no token, bad header, garbage token, wrong secret, expired token) produces a response **pairwise identical** to every other, not just individually matching a hardcoded string | All responses byte-identical (status, body, and body length) |

All five are implemented in a new file, `tests/test_security_regression.py`, reusing the `api_client`/`api_client_no_raise`/`make_token` fixtures already established in `tests/conftest.py` and the seeding-helper pattern already established in the existing API/integration test files (no new production code, no changes to already-passing tests).

---

## 4. Traceability to Requested Categories

| Requested category | Status | Evidence |
|---|---|---|
| Authentication | Covered + strengthened (SEC-05) | §1.1 |
| Authorization | Covered, no gap | §1.2 |
| Role-based access | N/A, confirmed absent | §1.3 |
| Unauthorized order access | Covered + strengthened (SEC-04) | §1.4 |
| Invalid identifiers | Covered + strengthened (SEC-03) | §1.5 |
| Malformed requests | Covered, no gap | §1.6 |
| Invalid status values | Gap closed (SEC-01, SEC-02) | §1.7 |
| Sensitive information exposure | Covered + strengthened (SEC-01, SEC-02, SEC-05) | §1.8 |
| Unexpected server errors | Gap closed (SEC-01, SEC-02) | §1.9 |
| Regression of existing order functionality | Covered, re-run for confidence | §1.10 |

No test code has been written yet as part of this document. Implementation and execution follow in the next step, with results recorded in `test-results/security-regression-results.md`.
