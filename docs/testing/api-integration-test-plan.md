# API & Integration Test Plan — Order Management & Order Lifecycle Module

**Document type:** test-design artifact. Traces each in-scope request end-to-end through the actual current FastAPI implementation and enumerates the API/integration-level test scenarios that trace derives. **No tests are implemented and no production code is modified by this document.**

**Basis (re-read directly from the repository for this document):**
- `app/api/routes/order.py`, `app/api/routes/my_restaurant.py`
- `app/api/deps.py` (routing + dependency wiring, including `get_current_user_id`)
- `app/services/order_service.py`, `app/services/restaurant_service.py`
- `app/db/mongodb.py`, `app/main.py`
- `app/core/errors.py` (exception-handler dispatch)
- `app/config.py`
- `tests/conftest.py`, `tests/test_health.py`
- `docs/testing/qa-readiness-notes.md`, `docs/testing/test-scenario-matrix.md`, `docs/testing/test-plan.md`, `docs/testing/unit-test-plan.md`

---

## 0. Important Finding — Auth Is No Longer a Stub (changes the premise of prior Phase 4 docs)

Every earlier Phase 4 document (`qa-readiness-notes.md`, `test-scenario-matrix.md`, `test-plan.md`) was written against `get_current_user_id` as a `NotImplementedFeatureError` stub, and treated 7 auth-related scenarios as **Blocked pending RFOMS-7**.

Re-reading `app/api/deps.py` fresh for this document shows that is **no longer true**. The working tree currently has **uncommitted local changes** (confirmed via `git diff` / `git status` — `app/api/deps.py`, `app/db/mongodb.py`, `app/main.py`, `app/services/auth_service.py` are all modified but not committed) that implement real JWT verification:

```python
async def get_current_user_id(
    authorization: str | None = Header(default=None),
    session_id: str | None = Cookie(default=None),
) -> str:
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else session_id
    if not token:
        raise AppError("unauthorized", status_code=401)
    try:
        import jwt
        secret = get_settings().JWT_SECRET_KEY or "fallback_secret_key_12345"
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return str(payload["userId"])
    except Exception:
        raise AppError("unauthorized", status_code=401)
```

**Consequences for this plan:**
- All three endpoints' authentication behavior is now **directly testable end-to-end**, not blocked. This document treats auth as in-scope and fully testable, superseding the "Blocked" status assigned in `test-plan.md` §9.1 for this module.
- The `session_id` cookie fallback (previously flagged in `docs/module-3-development-plan.md` §7 as an open decision — "whether to retain or drop the dead `session_id` cookie fallback, RFOMS-41") has been **implemented, not dropped**, and is now live, testable behavior — not dead code.
- **Environment gap found:** `PyJWT` (imported as `jwt`, version 2.14.0 confirmed installed in the project's venv) is used by both `deps.py` and `auth_service.py` but is **not listed in `requirements.txt`**. This is a real dependency-tracking gap — flagged here, not silently fixed, consistent with this project's "never silently fix a confirmed gap" rule. Any test environment rebuilt from `requirements.txt` alone would fail to run these routes at all.
- The docstring at the top of `deps.py` still says `get_current_user_id` is "intentionally a STUB" that "will surface a clear 501 until Jira Story RFOMS-7 ... is implemented" — this comment is now **stale** and contradicts the code beneath it. Not corrected here (out of scope: "do not modify production code"), but flagged so it isn't mistaken for current fact.
- Since these changes are uncommitted, they represent **in-progress local work**, not a merged/approved state. This plan tests the code **as it currently exists on disk**, per the instruction to trace actual behavior — but the reader should treat RFOMS-7's completion as unconfirmed/in-progress until committed and reviewed, not as an already-approved architectural decision.

---

## 1. Scope

**In scope — the 3 endpoints named in this task, with actual paths confirmed against the router source:**

| Requested (as written in this task) | Actual path (verified in `app/api/routes/*.py`) | Route function |
|---|---|---|
| `GET /api/my/order` | **`GET /api/order`** (no `/my/` segment — same discrepancy already documented in `qa-readiness-notes.md` §1; restated here, not silently corrected) | `order.py: get_my_orders` |
| `GET /api/my/restaurant/order` | matches | `my_restaurant.py: get_my_restaurant_orders` |
| `PATCH /api/my/restaurant/order/:orderId/status` | matches (`/order/{order_id}/status`) | `my_restaurant.py: update_order_status` |

**Out of scope**, consistent with every prior Phase 4 document: Stripe/payment endpoints (`create-checkout-session`, `webhook`), all other modules' routes, frontend, performance/load testing, and — per this task's own instruction — actual test **implementation**.

**Test ID scheme:** `API-ORD-GET-##` / `API-RST-GET-##` / `API-RST-PATCH-##`, plus a shared `AUTH-##` matrix (§3) referenced by all three endpoints to avoid tripling up 6 identical dependency-layer scenarios.

---

## 2. Generic Request Trace (applies to all 3 endpoints)

```
Request
  │
  ▼
FastAPI routing (path/method match — Starlette router)
  │  • order_id path param (PATCH only): bound as a raw string, NO format
  │    validation at this layer — any string routes through.
  │  • no query params on any of the 3 endpoints.
  ▼
Request-body validation (PATCH only: `payload: dict`)
  │  • body must parse as a JSON object; anything else → RequestValidationError
  │    → registered handler → 400 {"errors": [...]}  (app/core/errors.py)
  │  • GET endpoints have no body — this stage does not apply to them.
  ▼
Dependency resolution: get_current_user_id(authorization, session_id)
  │  • Bearer header → strip "Bearer "; else session_id cookie fallback.
  │  • No token at all → AppError(401, "unauthorized")
  │  • jwt.decode(token, secret, algorithms=["HS256"]) — any exception
  │    (bad signature, malformed token, expired, wrong claim shape) is
  │    caught by a single broad `except Exception` → AppError(401,
  │    "unauthorized"). No distinction is surfaced between failure reasons.
  │  • On success: user_id = str(payload["userId"])
  ▼
Dependency resolution: get_order_service / get_restaurant_service
  │  • Constructs repositories from `mongodb.<collection>` — requires
  │    `mongodb.database` to be a real, queryable database for these routes
  │    to do anything beyond raise RuntimeError("MongoDB is not connected").
  ▼
Service / business logic (see docs/testing/unit-test-plan.md for the
  exhaustive unit-level trace of each service method's branches)
  │  • GET /api/order            → OrderService.get_my_orders
  │  • GET .../restaurant/order  → RestaurantService.get_my_restaurant_orders
  │  • PATCH .../order/{id}/status → RestaurantService.update_order_status
  ▼
Database (Motor / MongoDB — real DB in production, in-memory
  mongomock-motor recommended for these tests, see §9)
  │  • orders / restaurants / users collections, queried and (PATCH only)
  │    written via the repository layer.
  ▼
Response
  • 2xx: JSON body (or empty body for PATCH's own 201/204 — N/A here, all
    3 routes return implicit 200) via FastAPI's default JSON encoder.
  • Non-2xx: dispatched through app/core/errors.py's exception handlers —
    THREE DIFFERENT response shapes are possible for the same nominal
    "error" depending on which AppError subclass was raised:
      - AppError            → JSON {"message": "..."}
      - EmptyBodyAppError   → empty body, no JSON at all
      - RequestValidationError → JSON {"errors": [...]}  (different shape
        from AppError's {"message": ...})
    Every test in this plan must assert on the EXACT shape for its status
    code, not just the status code, since two 400s or two 401s in this
    module can have genuinely different bodies (see §3, §6).
```

---

## 3. Shared Authentication Failure Matrix (`AUTH-##`)

Applies identically to all three routes (all three depend on the same `get_current_user_id`), so listed once here and referenced by ID from each endpoint's table rather than repeated three times.

| ID | Scenario | Request shape | Expected status | Expected body | Node-comparable |
|---|---|---|---|---|---|
| AUTH-01 | No `Authorization` header, no `session_id` cookie | no auth material at all | 401 | `{"message": "unauthorized"}` | Yes — needs a fresh read of `food-ordering-backend/src/middleware/auth.ts` to confirm exact message/shape parity (not re-read in this pass; flagged, not assumed) |
| AUTH-02 | `Authorization` header present but doesn't start with `"Bearer "`, no cookie | e.g. `Authorization: Basic xyz` | 401 | `{"message": "unauthorized"}` | Yes, same caveat as AUTH-01 |
| AUTH-03 | `Authorization: Bearer <garbage>` — not a well-formed JWT at all | malformed token string | 401 | `{"message": "unauthorized"}` | Yes |
| AUTH-04 | Syntactically valid JWT, correct signature, but payload has no `userId` claim | crafted token, signed with the real secret, missing claim | 401 | `{"message": "unauthorized"}` | Partial — this exact "valid signature, wrong claim shape" case is FastAPI-specific plumbing (a bare `except Exception` around a dict-key access); worth confirming Node's equivalent JWT-verify path has an analogous guard, but not assumed identical |
| AUTH-05 | Bearer token signed with the WRONG secret (signature mismatch) | token signed with a different key | 401 | `{"message": "unauthorized"}` | Yes |
| AUTH-06 | Bearer token expired (`exp` claim in the past) | token with `exp` < now | 401 | `{"message": "unauthorized"}` | Yes, assuming Node's JWT verification also honors `exp` (standard `jsonwebtoken` behavior — plausible but not re-confirmed this pass) |
| AUTH-07 | **Success case**, not a failure: no `Authorization` header, valid JWT supplied only via `session_id` cookie | cookie-only auth | 200 (route-appropriate happy-path body) | route-specific | Needs fresh Node source read — `docs/module-3-development-plan.md` flagged this cookie fallback as previously "dead" in Node; confirming whether Node's version is actually exercised is a prerequisite before claiming 1:1 parity here |

**Note on precedence:** if BOTH the auth dependency and the request body would independently fail (PATCH only — e.g., no token AND a malformed JSON body), FastAPI's internal dependency-resolution order between calling `get_current_user_id` (which raises immediately, uncaught, inside dependency resolution) and accumulating body-validation errors (only raised at the end of the same resolution pass) is **not something this plan asserts confidently** — reasoning about FastAPI/Starlette internals without executing the code would risk stating an invented fact. This is called out explicitly as **[NEEDS VERIFICATION]** — see API-RST-PATCH-19.

---

## 4. Endpoint 1 — `GET /api/order`

**Route:** `order.py: get_my_orders` → `OrderService.get_my_orders(user_id)`.

**Applicability of the 8 requested categories to this endpoint:**

| Category | Applies? | Why |
|---|---|---|
| Happy path | Yes | primary read path |
| Validation failures | **N/A** | no request body, path params, or query params on this route — nothing to validate beyond auth |
| Authentication failures | Yes | via `AUTH-01…07` |
| Authorization failures | **N/A** | no ownership/ACL check beyond "must be authenticated" — the query is inherently scoped to the caller's own `user_id`; see cross-user isolation under Regression instead |
| Missing records | **N/A as an error** | a user with zero orders gets `200 []`, not `404` — stated explicitly since it's easy to wrongly expect a 404 here |
| Invalid status values | **N/A** | read-only; no status is submitted |
| Lifecycle transition cases | **N/A** | read-only; no transitions occur (but see the no-op-filter regression test) |
| DB persistence verification | **N/A** | read-only; nothing is written |

### Scenario table

| ID | Category | Scenario | Expected Status | Expected Response Body | Node-Comparable |
|---|---|---|---|---|---|
| API-ORD-GET-01 | Happy path | Authenticated user with orders in every status (`placed`, `paid`, `inProgress`, `outForDelivery`, `delivered`) | 200 | JSON array, one entry per order, each with `restaurant`/`user` fully populated (embedded documents, not refs) and `_id` fields as strings | Yes |
| API-ORD-GET-02 | Happy path | Authenticated user with zero orders | 200 | `[]` | Yes |
| API-ORD-GET-03 | Happy path (= AUTH-07 applied here) | Valid JWT supplied only via `session_id` cookie, no `Authorization` header | 200 | same shape as API-ORD-GET-01 | See AUTH-07 caveat |
| API-ORD-GET-04…09 | Auth failure | `AUTH-01` through `AUTH-06` applied to this route | 401 (all) | `{"message": "unauthorized"}` (all) | See §3 |
| API-ORD-GET-10 | Regression / security | Two users, each with their own orders — user A's authenticated request never includes user B's orders | 200 | array scoped strictly to the caller | Yes — this is the real "authorization" mechanism for this endpoint; a regression here is a cross-tenant data leak |
| API-ORD-GET-11 | Regression | An order in `"placed"` (unpaid) status appears in the response | 200 | included, unfiltered | Yes — pins the confirmed no-op status filter (`ORD-GET-05` in the earlier scenario matrix) at the actual HTTP layer, not just the repository/service layer |
| API-ORD-GET-12 | Regression / security | Response's embedded `user` object includes the bcrypt `password` hash field | 200 | `order.user.password` present, unredacted | Yes — confirms finding C1 is reachable via the real HTTP response body, the most security-relevant single assertion in this endpoint's test set |
| API-ORD-GET-13 | Regression | Order whose `restaurant` or `user` ref no longer resolves to an existing document | 200 | the corresponding field is `null`, not a 500 | Needs Node source re-read — confirms `populate_order()`'s graceful-null behavior end-to-end, matching Mongoose's `.populate()` on a dangling ref (assumed analogous, not reconfirmed this pass) |

---

## 5. Endpoint 2 — `GET /api/my/restaurant/order`

**Route:** `my_restaurant.py: get_my_restaurant_orders` → `RestaurantService.get_my_restaurant_orders(user_id)`.

**Applicability:** same as Endpoint 1 for validation/invalid-status/lifecycle/persistence (all N/A, same reasoning). Two differences worth calling out explicitly:
- **"Missing records" is genuinely distinctive here**, not just a footnote: "user owns no restaurant at all" is a first-class, confirmed business rule (200 + `[]`, not 404) that deserves its own dedicated test, separate from "owns a restaurant with zero orders."
- **Authorization** is still N/A in the sense of "no explicit reject path" — but the implicit scoping mechanism (`get_by_owner(user_id)`) is the whole security model for this endpoint and is exercised under Regression below.

### Scenario table

| ID | Category | Scenario | Expected Status | Expected Response Body | Node-Comparable |
|---|---|---|---|---|---|
| API-RST-GET-01 | Happy path | Authenticated restaurant owner with orders in multiple statuses (incl. `placed`) | 200 | JSON array, populated orders | Yes |
| API-RST-GET-02 | Happy path | Owner's restaurant exists, has zero orders | 200 | `[]` | Yes |
| API-RST-GET-03 | Missing records (distinctive to this endpoint) | Authenticated user owns **no restaurant at all** | 200 | `[]` — NOT 404 | Yes — counter-intuitive confirmed behavior, worth its own explicit test rather than assuming it's covered by API-RST-GET-02 |
| API-RST-GET-04 | Happy path (= AUTH-07) | Valid JWT via `session_id` cookie only | 200 | populated array | See AUTH-07 caveat |
| API-RST-GET-05…10 | Auth failure | `AUTH-01`…`AUTH-06` applied to this route | 401 (all) | `{"message": "unauthorized"}` | See §3 |
| API-RST-GET-11 | Regression / security | Restaurant owner A never sees restaurant B's orders, even with two restaurants in the same DB | 200 | scoped strictly to the caller's own restaurant | Yes — this endpoint's actual authorization boundary |
| API-RST-GET-12 | Regression | `"placed"` (unpaid) orders included, unfiltered | 200 | included | Yes — pins `RST-ORD-GET-04`; distinct code path from API-ORD-GET-11 (`list_by_restaurant` has NO filter at all, vs. `list_by_user`'s no-op `$in` filter — worth its own test since a regression could land in either repository method independently) |
| API-RST-GET-13 | Regression / security | Password hash present in populated `user` sub-document | 200 | `password` field present | Yes — same C1 finding, independent call site from Endpoint 1 |
| API-RST-GET-14 | Regression | Order's `restaurant` or `user` ref orphaned | 200 | field is `null`, not 500 | Needs Node source re-read |

---

## 6. Endpoint 3 — `PATCH /api/my/restaurant/order/:orderId/status`

**Route:** `my_restaurant.py: update_order_status(order_id: str, payload: dict, ...)` → `RestaurantService.update_order_status(user_id, order_id, payload.get("status"))`.

The richest endpoint in the module — it is the sole location of the deliberate, flagged C2 fix (ownership-check bug in Node) and the only endpoint that writes to the database. Every category the task asks for genuinely applies here.

**One response-structure fact worth flagging up front, confirmed by re-reading `restaurant_service.py` fresh for this document:** unlike both GET endpoints, `update_order_status`'s success response is **NOT** run through `populate_order()` — it returns `mongo_to_jsonable(updated_order)` directly. This means the PATCH response's `restaurant` and `user` fields are **plain ID strings**, not full embedded documents, in contrast to both GET endpoints. This asymmetry must be asserted explicitly (API-RST-PATCH-01), not assumed to match the GET endpoints' shape by analogy — and whether Node's equivalent response is populated or raw is **[NEEDS VERIFICATION AGAINST NODE SOURCE]**, not re-confirmed in this pass.

### 6.1 Happy path & lifecycle transitions

| ID | Scenario | Expected Status | Expected Response Body | Node-Comparable |
|---|---|---|---|---|
| API-RST-PATCH-01 | Legitimate owner sets a valid new status | 200 | updated order, **`restaurant`/`user` as raw ID strings, NOT populated** (see callout above) | Needs Node source re-read for the populate-vs-raw distinction specifically |
| API-RST-PATCH-02 | Full forward lifecycle walk: `placed → paid → inProgress → outForDelivery → delivered`, one PATCH per hop against the same order | 200 at every hop | status reflects each intermediate value | Yes for each individual 200; the *absence* of any rejection at any hop is FastAPI-specific (no state machine) — see API-RST-PATCH-16 |
| API-RST-PATCH-03 | Regression — backward transition (`delivered → placed`) accepted | 200 | status updated to `placed` | No — deliberately unenforced in both backends per prior analysis, but worth an explicit Node-side confirmation rather than assuming symmetry |
| API-RST-PATCH-04 | Regression — skip-ahead transition (`placed → delivered`, skipping intermediates) accepted | 200 | status updated to `delivered` | Same caveat as API-RST-PATCH-03 |
| API-RST-PATCH-05 | Regression — idempotent resubmission of the current status | 200 | status unchanged, write still occurs | Same caveat |

### 6.2 Request validation (request-body layer, before the service is ever reached)

| ID | Scenario | Expected Status | Expected Response Body | Node-Comparable |
|---|---|---|---|---|
| API-RST-PATCH-06 | Request body is not valid JSON at all | 400 | `{"errors": [...]}` — Pydantic/FastAPI validation-error shape, **different from** the service-layer `{"message": "Invalid order ID format"}` 400 (API-RST-PATCH-11) | No — this specific error SHAPE is a FastAPI/Pydantic artifact (`errors.py`'s placeholder validation-error handler is explicitly documented as not-yet-approved, per `errors.py`'s own module docstring); Node's equivalent is almost certainly a different shape given Node has no centralized error handler (confirmed in `qa-readiness-notes.md`) |
| API-RST-PATCH-07 | Request body is valid JSON but not an object (e.g. a JSON array `[]` or a bare string) | 400 | `{"errors": [...]}` | No, same reasoning as above |
| API-RST-PATCH-08 | Request body is a valid, empty JSON object `{}` (no `status` key at all) | 500 | `{"message": "unable to update order status"}` — this is **service-layer**, not request-validation — `payload.get("status")` silently yields `None`, which fails the enum check downstream. Worth its own test distinguishing this from API-RST-PATCH-06/07 since it's a materially different failure mode (500, not 400) for what a naive tester might lump together as "bad body" | Yes — mirrors Mongoose's save()-time enum validation failure per the service's own docstring |

### 6.3 Authentication failures

| ID | Scenario | Expected Status | Expected Response Body |
|---|---|---|---|
| API-RST-PATCH-09…14 | `AUTH-01`…`AUTH-06` applied to this route | 401 (all) | `{"message": "unauthorized"}` (all) |

(See §3 for the shared matrix and Node-comparability notes — identical caveats apply per-route since each route's dependency wiring is independently testable, per `unit-test-plan.md`'s reasoning for why a shared helper still needs per-call-site tests.)

### 6.4 Authorization failures — the module's highest-priority test set

| ID | Scenario | Expected Status | Expected Response Body | Node-Comparable |
|---|---|---|---|---|
| API-RST-PATCH-15 | Authenticated caller is NOT the owner of the restaurant tied to the order | 401 | **empty body** (`Content-Length: 0`, no JSON at all — `EmptyBodyAppError` dispatch, confirmed via `errors.py`) | **No — deliberate, flagged divergence (finding C2).** Node's equivalent check throws a `TypeError` for any restaurant with a `user` set (i.e. almost always), caught by a generic catch, producing a **500** in Node — meaning this exact scenario is EXPECTED to differ: FastAPI 401 vs. Node 500. Any Node-comparison test for this scenario must assert the difference is present, not treat a mismatch as a defect |
| API-RST-PATCH-16 | Order's `restaurant` ref resolves to a deleted/non-existent restaurant (orphaned ref) | 401 | empty body | Needs Node source re-read — this is the specific edge case traced through `populate_order`'s graceful-null handling combined with the ownership check's `if restaurant and restaurant.get("user")` guard; whether Node's (crashing) code path even reaches a comparable state for this input is itself uncertain without a fresh trace |
| API-RST-PATCH-17 | Order's restaurant exists but has no `user` field assigned (never-claimed restaurant) | 401 | empty body | Same caveat as API-RST-PATCH-16 |
| API-RST-PATCH-18 | **Positive control** — legitimate owner is NOT rejected (already covered as API-RST-PATCH-01, cross-referenced here because it is the one path Node's bug makes unreachable in production; without this passing, the ownership check would silently reject everyone) | 200 | — | **No — this is the single most important divergence test in the whole module.** Node's production behavior today: legitimate owners get a 500, not a 200. FastAPI is expected to differ here by design |

### 6.5 Missing records

| ID | Scenario | Expected Status | Expected Response Body | Node-Comparable |
|---|---|---|---|---|
| API-RST-PATCH-19 | `order_id` is a well-formed ObjectId (24 hex chars) but no matching order exists | 404 | `{"message": "order not found"}` | Yes |

### 6.6 Request-layer `order_id` format validation

| ID | Scenario | Expected Status | Expected Response Body | Node-Comparable | Notes |
|---|---|---|---|---|---|
| API-RST-PATCH-20 | `order_id` path segment is not a valid ObjectId format (e.g. `"abc123"`) | 400 | `{"message": "Invalid order ID format"}` — **service-layer** shape, distinct from the request-validation `{"errors":[...]}` shape in §6.2 | Yes |
| API-RST-PATCH-21 | `order_id` path segment is empty (e.g. requesting `/order//status`) | **[NEEDS VERIFICATION]** — likely a framework-level 404 from Starlette's router failing to match `{order_id}` against an empty path segment at all, never reaching `get_current_user_id` or the service. This differs from the unit-level test (`UT-RST-PATCH-02` in `unit-test-plan.md`), which exercises the service method directly with `order_id=""` and correctly gets the service's own 400 — that unit test remains valid for the service's *internal* contract, but this specific HTTP-level scenario may be unreachable via a real request at all | (likely) FastAPI/Starlette default 404 `{"detail": "Not Found"}` — a DIFFERENT shape from every other 404 in this module | No — framework routing behavior, not application logic | Must be executed, not reasoned about, before this row's expected status is treated as fact |
| API-RST-PATCH-22 | Combined precedence case: no auth token AND a malformed request body in the same request | **[NEEDS VERIFICATION]** — see §3's precedence note; do not assume "auth wins" or "validation wins" without executing this against the real app | one of 401 / 400, TBD | N/A | Exists specifically to resolve the open question raised in §3, not to assert an answer here |

### 6.7 Invalid status values

| ID | Scenario | Expected Status | Expected Response Body | Node-Comparable |
|---|---|---|---|---|
| API-RST-PATCH-23 | `status` key present but `null` (`{"status": null}`) | 500 | `{"message": "unable to update order status"}` | Yes |
| API-RST-PATCH-24 | `status` is a non-enum string (e.g. `"cancelled"`) | 500 | same | Yes |
| API-RST-PATCH-25 | `status` has correct spelling, wrong case (e.g. `"Paid"`) | 500 | same | Yes — no normalization in either backend, per prior analysis |
| API-RST-PATCH-26 | `status` is a non-string JSON type (e.g. `{"status": 123}` or `{"status": true}`) | 500 | same | Yes — confirms the enum-membership check handles non-string input without crashing before reaching its own check |

### 6.8 Database persistence verification

| ID | Scenario | Expected Status | Verification | Node-Comparable |
|---|---|---|---|---|
| API-RST-PATCH-27 | After a successful PATCH, independently re-fetch the order (via a second `GET`-equivalent repository read, not by trusting the PATCH response body) | 200 (the PATCH itself) | stored `status` in the database matches the PATCH request, not merely the HTTP response claim | Yes — closes the loop between "the endpoint said 200" and "the write actually happened," the one thing a pure unit test (with a mocked repository) structurally cannot verify |
| API-RST-PATCH-28 | `totalAmount` is untouched by this endpoint | 200 | seed a known `totalAmount` before the PATCH; confirm it is byte-identical after | Yes — distinguishes this call site from the (out-of-scope) Stripe webhook's `status="paid"` + `totalAmount` write, which shares the same repository method |
| API-RST-PATCH-29 | Only the targeted order is modified | 200 | sibling orders for the same restaurant, seeded alongside the target, are unchanged after the PATCH | Yes — guards against an accidental multi-document update |

### 6.9 Race condition (documented limit, not fully testable live)

| ID | Scenario | Expected Status | Notes |
|---|---|---|---|
| API-RST-PATCH-30 | Order is deleted between the initial existence check and the write (true concurrent-request race) | 500 (per `unit-test-plan.md` UT-RST-PATCH-11's mocked equivalent) | **Blocked / Needs-verification at the true-integration level** — a genuine race is not reliably reproducible via a single-threaded `TestClient` call; the *handling* of a failed write is already covered at the unit level (mocked repository returning `False`). Attempting to force this via two overlapping real requests would require either a threading harness or an injected delay, both beyond this plan's "design, don't implement" charter — noted as a known coverage limit, not silently dropped |

---

## 7. HTTP Status Code Reference (all 3 endpoints, combined)

A single request-level bug can produce the wrong status OR the right status with the wrong body shape — both are failures. This table exists so every test asserts the full contract, not just the numeric code.

| Status | Endpoint(s) | Trigger | Body shape |
|---|---|---|---|
| 200 | all 3 | success | GET endpoints: JSON array of populated orders. PATCH: JSON object, **unpopulated** (raw refs) |
| 400 | PATCH only | malformed/non-object JSON request body | `{"errors": [...]}` |
| 400 | PATCH only | `order_id` fails `ObjectId.is_valid` | `{"message": "Invalid order ID format"}` |
| 401 | all 3 | any of `AUTH-01`…`AUTH-06` | `{"message": "unauthorized"}` |
| 401 | PATCH only | ownership check fails (C2 path), including orphaned-restaurant and no-owner-assigned sub-cases | **empty body**, no JSON |
| 404 | PATCH only | `order_id` well-formed but no matching document | `{"message": "order not found"}` |
| 500 | PATCH only | `status` missing/`null`/non-enum/wrong-case, or repository write fails | `{"message": "unable to update order status"}` |

**Two distinct 400 shapes and two distinct 401 shapes exist in this module** — a test asserting only `response.status_code == 400` (or `401`) without checking the body would pass even if the wrong branch were hit. Every scenario table above specifies the exact body, not just the code, for this reason.

---

## 8. Node.js Comparison Summary

| Comparable without qualification | Comparable, but needs a fresh Node source re-read first | Deliberately NOT expected to match (documented divergence) | Not comparable (FastAPI/tooling-specific) |
|---|---|---|---|
| Happy-path response data (order fields, counts, empty-list behavior) | Exact auth-failure message/shape (`auth.ts` not re-read this session) | Ownership-check outcome for a legitimate owner: FastAPI 200 vs. Node 500 (C2) | Request-validation-layer 400 shape (`{"errors":[...]}`) — a FastAPI/Pydantic artifact, `errors.py` explicitly flags this shape as an unapproved placeholder |
| No-op status filter / unfiltered restaurant-order listing | `session_id` cookie fallback's actual Node behavior (previously flagged as "dead code" in Node) | Ownership-check outcome for a wrong owner: FastAPI 401 vs. Node 500 (same C2 finding, opposite framing) | The malformed-`order_id`-empty-path-segment 404 (framework routing, not app logic) |
| Password-hash-in-response (C1) | Whether Node's `updateOrderStatus` success response is populated or raw | Orphaned-restaurant-ref outcome: FastAPI 401 (via the ownership-check's None-coalescing), Node's actual crash path for this specific input is untraced | Auth precedence vs. body-validation precedence (FastAPI/Starlette internal dependency-resolution order) |
| Invalid-status → 500 with exact message | | | |
| 404 on missing order | | | |

**Recommendation carried forward from `test-plan.md` §10.2:** all "needs a fresh Node source re-read" items require running the actual Node server (or re-reading `middleware/auth.ts` and `MyRestaurantController.ts` directly) before a parity test can assert a specific expected Node value — this plan intentionally stops short of asserting those values from memory of an earlier session's summary, since that summary predates this session's discovery that the auth layer has materially changed.

---

## 9. Test Environment & Fixture Requirements

The existing `tests/conftest.py` `client` fixture is **insufficient** for this plan's scenarios as written — it stands `mongodb.database` up as a `defaultdict(lambda: None)`, which was only ever meant to let dependency injection construct repository objects for routes that 501 before touching the database (per that fixture's own docstring). Since all three routes in this plan now reach real query/write logic, running these scenarios requires:

1. **A real in-memory database fixture**, extending (not replacing) the existing pattern already proven in `tests/test_repositories.py`:
   ```python
   from mongomock_motor import AsyncMongoMockClient
   mongodb.database = AsyncMongoMockClient().get_database("test_food_ordering")
   ```
   swapped in for the duration of each test, matching how `tests/test_repositories.py`'s `db` fixture already works — but wired through `mongodb.database` (a module-level singleton) rather than passed directly to a repository constructor, since the route layer resolves repositories via `app.api.deps` functions that read `mongodb.<collection>` directly.

2. **A JWT-issuing test helper**, matching `get_current_user_id`'s exact secret-resolution and encoding logic:
   ```python
   import jwt
   def make_token(user_id: str, secret: str = "fallback_secret_key_12345", **claims):
       return jwt.encode({"userId": user_id, **claims}, secret, algorithm="HS256")
   ```
   Tests should set `JWT_SECRET_KEY` explicitly (e.g. via `monkeypatch.setenv`) rather than relying on the hardcoded fallback secret, so the test suite doesn't silently depend on a value that exists in production code as a fallback for missing configuration — a real secret should be used in tests to also implicitly verify `JWT_SECRET_KEY` is actually being read from settings, not just the fallback path.

3. **`PyJWT` added to `requirements.txt`** (currently missing — see §0) — a prerequisite for any CI environment to run these tests at all, not just this developer's local venv where it happens to already be installed.

4. **Seed-data builders** reusing the same shape conventions already established in `tests/test_repositories.py`'s `_seed_restaurant`/`_seed_order` helpers and this session's own `tests/test_order_service.py` / `tests/test_restaurant_order_lifecycle.py` sample-document helpers, inserted via the real repository `create()` methods against the mongomock database (not raw dict literals), so sub-document `_id` generation (`_with_cart_item_ids`/`_with_menu_item_ids`) is exercised the same way it would be in production.

None of the above is implemented by this document — it is the recommended environment design for whoever implements this plan next.

---

## 10. Explicitly Out of Scope

- `POST /api/order/checkout/create-checkout-session`, `POST /api/order/checkout/webhook` — Stripe/payment, excluded consistently with every prior Phase 4 document.
- Every other module's routes (auth's own endpoints, user, restaurant CRUD/discovery, analytics) — not part of the Order Management & Order Lifecycle module.
- True concurrent-request race-condition reproduction (§6.9) — documented as a coverage limit, not silently dropped.
- Resolving the FastAPI dependency-resolution precedence question in §3/API-RST-PATCH-22 by reasoning alone — flagged as something only execution can answer.
- Modifying `requirements.txt` to add `PyJWT`, or correcting the stale docstring in `deps.py` — both flagged as findings in §0, left for a separate, explicit change.

---

## Summary

| Section | Scenario count |
|---|---|
| §3 Shared auth matrix | 7 (`AUTH-01`…`07`) |
| §4 `GET /api/order` | 13 |
| §5 `GET /api/my/restaurant/order` | 14 |
| §6 `PATCH .../order/:orderId/status` | 30 |
| **Total distinct scenario IDs** | **64** (auth matrix counted once, referenced 3×) |

No test code has been written and no production code has been modified. This plan is ready for implementation under the environment design in §9, using the same `pytest` + `pytest-asyncio` + `TestClient` conventions already established in `tests/conftest.py` and this module's existing test files.
