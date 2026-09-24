# Phase 4 — Testing & QA Readiness Notes

**Purpose:** ground the upcoming test-writing work for the migrated Order Management & Order Lifecycle module in verified facts — what exists, what's missing, what's risky, and what a sensible testing strategy looks like — before any test code is written. This document contains **no test code and no production-code changes**.

---

## 1. Phase 4 Scope

The three endpoints named in the Phase 4 request, with their actual current paths confirmed against the code:

| # | Requested path | Actual path (verified) | Node source | FastAPI source |
|---|---|---|---|---|
| 1 | `GET /api/my/order` | **`GET /api/order`** (no `/my/` segment) | `OrderController.getMyOrders` | `order_service.py: OrderService.get_my_orders` |
| 2 | `GET /api/my/restaurant/order` | `GET /api/my/restaurant/order` — matches | `MyRestaurantController.getMyRestaurantOrders` | `restaurant_service.py: RestaurantService.get_my_restaurant_orders` |
| 3 | `PATCH /api/my/restaurant/order/:orderId/status` | matches | `MyRestaurantController.updateOrderStatus` | `restaurant_service.py: RestaurantService.update_order_status` |

**Discrepancy note:** endpoint 1 is listed in the Phase 4 request as `/api/my/order`, but both the Node route (`food-ordering-backend/src/routes/OrderRoute.ts`) and the FastAPI route (`app/api/routes/order.py`) mount it at `/api/order` (prefix `/api/order`, method `GET ""`). This is stated here as an observed fact, not silently corrected or silently used — whoever writes the tests should target `/api/order`.

**Explicitly out of scope for Phase 4** (per the request and independently confirmed against the code):
- `POST /api/order/checkout/create-checkout-session` and `POST /api/order/checkout/webhook` — both live in the same `OrderService`/`order.py` router as endpoint 1, but neither is in the "current migrated scope" list, and Stripe/payment is separately excluded. Unambiguous, not treated as an open question.
- Every other FastAPI module (Auth, User, Restaurant CRUD/discovery, Analytics) — all still `NotImplementedFeatureError` stubs, not part of this module.

---

## 2. Source-of-Truth Files Reviewed

**Node.js (original behavior, system of record for what must be preserved):**
- `food-ordering-backend/src/controllers/OrderController.ts`
- `food-ordering-backend/src/routes/OrderRoute.ts`
- `food-ordering-backend/src/models/order.ts`
- `food-ordering-backend/src/controllers/MyRestaurantController.ts`
- `food-ordering-backend/src/routes/MyRestaurantRoute.ts`
- `food-ordering-backend/src/middleware/auth.ts`
- `food-ordering-backend/src/middleware/validation.ts`
- `food-ordering-backend/src/models/user.ts` (for the password-hash-leak-via-populate finding)
- `food-ordering-backend/package.json` (confirmed no test script/framework)

**FastAPI (migration target, current implementation):**
- `app/services/order_service.py`
- `app/services/restaurant_service.py` (order-lifecycle methods only)
- `app/services/stripe_client.py`
- `app/repositories/order_repository.py`, `restaurant_repository.py`, `user_repository.py`, `base.py`
- `app/schemas/order.py`, `schemas/common.py`
- `app/api/routes/order.py`, `api/routes/my_restaurant.py`
- `app/api/deps.py`
- `app/core/errors.py`, `core/security.py`
- `app/db/mongodb.py`
- `tests/conftest.py`, `tests/test_repositories.py`, `tests/test_health.py`
- `pytest.ini`, `requirements.txt`, `README.md`

**Phase 1–3 documentation:**
- `CURRENT_STATE.md`, `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md`, `TARGET_ERD.md` (Rev. 2), `TARGET_ARCHITECTURE_C4_DIAGRAM.md` (Rev. 2)
- `MODULE_3_CURRENT_STATE_AND_GAPS.md`, `docs/module-3-development-plan.md`
- `docs/security-review.md`, `docs/module-3-code-review.md` (both produced during Phase 3's own review pass; findings below are cross-referenced to these rather than re-derived)

---

## 3. Current Testing Capabilities

**FastAPI backend (`food-ordering-backend-fastapi/`):**
- Test runner: `pytest` (`pytest.ini`: `testpaths = tests`), with `pytest-asyncio` (strict mode) for async tests.
- `mongomock-motor` provides an in-memory Motor-compatible fake — no real MongoDB connection needed for repository tests.
- `fastapi.testclient.TestClient` (via `httpx`) is wired in `tests/conftest.py`'s `client` fixture, which patches `mongodb.database` to a `defaultdict` so DI can construct repositories without a real DB.
- **Existing tests, confirmed by a fresh run:** 17 passed, 1 `xfail`.
  - `tests/test_health.py` — 4 tests: root, `/health`, `/api/health`, and one 501-stub check (`/api/restaurant/cities/all` — an untouched stub, unrelated to the Order module).
  - `tests/test_repositories.py` — ~18 tests across `UserRepository`, `RestaurantRepository`, `OrderRepository`. One test (`test_restaurant_search_cuisine_filter_is_and_not_or`) is `xfail(strict=True)` — a documented `mongomock` limitation (`$all` + regex against array elements), not a repository defect.

**Node.js backend (`food-ordering-backend/`):**
- **No automated test suite exists.** Confirmed via direct inspection: `package.json` has only `dev`, `dev:no-stripe`, `stripe`, `build`, `start` scripts — no `test` script. No `jest.config.*`, `.mocharc*`, or any test-runner config anywhere in the directory (excluding `node_modules`). No `test`/`tests`/`__tests__` directory. `scripts/create-test-user.ts` exists but is a DB-seeding utility, not a test.
- **No CI/CD pipeline exists anywhere in the repository** — no `.github/workflows/`, no `.gitlab-ci.yml`, no `azure-pipelines.yml`. One `Dockerfile` (build/run only) at `food-ordering-backend/Dockerfile`.

**Implication:** there is no existing Node test suite to run as a baseline, and no CI to compare against. Any Node-vs-FastAPI behavioral comparison for Phase 4 must be done via direct source reading (already completed across Phases 2–3 of this engagement) or by manually running the Node server, not by pointing at an existing automated suite.

---

## 4. Test Gaps

| Area | Coverage today | Gap |
|---|---|---|
| `OrderRepository`, `RestaurantRepository`, `UserRepository` | ✅ Tested | None significant (one `xfail` is a tooling limitation, documented) |
| `OrderService.get_my_orders` | ❌ None | No test verifies the no-op status filter, the populate behavior, or JSON serialization of `ObjectId`/`datetime` fields |
| `RestaurantService.get_my_restaurant_orders` | ❌ None | No test verifies the "no restaurant → `[]`" branch, the unfiltered-by-status listing, or populate behavior |
| `RestaurantService.update_order_status` | ❌ None | **Highest-priority gap** — no test verifies the invalid-ObjectId 400, not-found 404, ownership 401 (empty body), invalid-status 500, or success path. This method contains the one deliberate Node-vs-FastAPI behavioral deviation (see §5). |
| `StripeClient` | ❌ None | Out of scope per §1, noted for completeness only |
| `mongo_to_jsonable()` | ❌ None | Pure function, trivial to test, currently untested |
| `PlainTextAppError` / `EmptyBodyAppError` exception-handler resolution | ❌ None | No test confirms these subclass handlers are actually selected over the generic `AppError` handler (relies on Starlette's most-specific-class dispatch, which is currently unverified by any test) |
| HTTP-level (`TestClient`) tests of any of the 3 in-scope endpoints | ❌ **Structurally blocked** | `get_current_user_id` (`app/api/deps.py`) still raises `NotImplementedFeatureError` — every request to `/api/order`, `/api/my/restaurant/order`, or the PATCH endpoint 501s before reaching real logic. `TestClient` cannot currently exercise these endpoints end-to-end without a dependency override. |
| Node-vs-FastAPI parity/comparison | ❌ None | No test or script exists comparing the two backends' behavior directly (expected — no such tooling has been requested or built) |

---

## 5. Relevant Risks

Ranked by what a test could catch, cross-referenced to prior findings rather than re-derived:

1. **Ownership-check behavioral deviation (highest priority).** Node's `updateOrderStatus` ownership check throws a `TypeError` for any restaurant with a `user` field set (essentially always), which the surrounding `catch` converts into a 500 — the 401 branch is effectively dead code in production Node. The FastAPI implementation deliberately fixes this (a real, working 401-vs-200 branch) — documented in `restaurant_service.py`'s docstring and in `docs/module-3-code-review.md` §6 as finding C2. **This is a real, intentional divergence from "preserve exact behavior," and it currently has zero test coverage.** A regression here (accidentally reintroducing the crash, or accidentally breaking the working check) would be invisible without a test.
2. **Password hash exposure via populate (C1 in `docs/security-review.md`).** `populate_order()` embeds the full `User` document — including the bcrypt hash — into `GET /api/order` and `GET /api/my/restaurant/order` responses, matching Node's `.populate("user")` behavior exactly. This is documented as an intentional, flagged preservation (not a FastAPI-introduced bug), but any future test asserting on response shape should be aware the password field is present today by design, pending a separate remediation decision.
3. **No-op status filters are easy to "fix" by accident.** `getMyOrders`'s status filter matches all 5 enum values (a confirmed no-op); `getMyRestaurantOrders` has no status filter at all (returns unpaid `"placed"` orders too). Both are deliberate preservations of current Node behavior. Without a test pinning this, a future contributor who doesn't know the history could "clean up" the no-op filter or add a status filter to the restaurant-orders query, silently changing behavior.
4. **Sub-document ObjectId generation.** Motor has no equivalent of Mongoose's automatic sub-document `_id` generation; `_with_cart_item_ids()`/`_with_menu_item_ids()` generate these explicitly. Tested at the repository layer (`tests/test_repositories.py`) but not through the service/route path that endpoint 1 and 2 actually serve — a regression in how `get_my_orders`/`get_my_restaurant_orders` handle these fields wouldn't be caught by the existing repository tests alone.
5. **JSON serialization of raw Motor documents.** `get_my_orders`, `get_my_restaurant_orders`, and `update_order_status`'s success response all return dicts containing raw `bson.ObjectId` values, passed through `mongo_to_jsonable()` before returning. This conversion path is currently untested; a missed call site (or a future field holding an untested BSON type) would surface only as a runtime serialization error, not a caught test failure.
6. **Auth-dependency stub blocks realistic end-to-end verification.** Because `get_current_user_id` isn't implemented (RFOMS-7), nothing has yet exercised these 3 endpoints through a real HTTP request with a real or even fake JWT. All verification to date has been at the unit/service level or by direct code reading.

---

## 6. Proposed Testing Levels

Four levels, not all equally available right now:

1. **Repository-level (already satisfied).** `tests/test_repositories.py` already covers the data-access layer these 3 endpoints depend on. No new work proposed here beyond what exists.
2. **Service-level unit tests (available now, no blockers).** Construct `OrderService`/`RestaurantService` directly with `mongomock-motor`-backed repositories (same pattern as `test_repositories.py`), bypassing the route/auth layer entirely. This is the only level that can fully exercise all 3 endpoints' business logic today, including the risks in §5.
3. **Route-level tests via dependency override (available now, with a caveat).** FastAPI supports overriding `get_current_user_id` for a `TestClient` instance (`app.dependency_overrides[...]`) without needing RFOMS-7 to be finished — this can verify request/response shape, status codes, and routing/DI wiring for the 3 endpoints without waiting on real auth. This is a genuine option for Phase 4, presented here as a choice rather than a decision already made, since it affects how "real" the route-level tests are (they'd use a fake user ID, not a real JWT flow).
4. **True end-to-end / integration tests with real auth (not available yet).** Blocked on RFOMS-7 (JWT auth dependency). Out of reach for this phase regardless of approach chosen for level 3.

---

## 7. Assumptions and Limitations

- No real MongoDB instance is assumed available for Phase 4 test-writing — consistent with the existing repository tests, `mongomock-motor` is the expected substitute.
- The auth-dependency stub (`get_current_user_id`) means genuine end-to-end testing of "a real user calls a real protected endpoint" is not achievable until RFOMS-7 lands; §6 level 3 is a partial substitute, not equivalent.
- Stripe/payment code paths are excluded from this phase's testing target even though they share a service class (`OrderService`) with in-scope endpoint 1 — testing `OrderService` in isolation will necessarily touch the class but not its Stripe-dependent methods.
- The documented `mongomock` `$all`+regex limitation (affecting restaurant search) is unrelated to the 3 in-scope endpoints directly, but is noted in case any future test seeds restaurant data with cuisine filters as part of order-related fixtures.
- This document assumes the reader has access to `docs/security-review.md` and `docs/module-3-code-review.md` for full detail on findings referenced here by short name (C1, C2) rather than re-explained in full.

---

## 8. Out-of-Scope Items

- Stripe/payment logic and any tests for it (`create_checkout_session`, `handle_stripe_webhook`, `StripeClient`).
- Auth, User, Restaurant CRUD/discovery, and Analytics modules — all still stubs, not part of this migrated module.
- Frontend testing — confirmed no test framework is configured in `food-ordering-frontend/package.json` (`dev`/`build`/`lint`/`preview` only); not this phase's gap to fill.
- Performance/load testing.
- Building a Node.js test suite — none exists today (confirmed above); creating one was not requested and would be inventing scope beyond this phase's charter.
- Setting up CI/CD — confirmed none exists anywhere in the repository; noted as a fact relevant to "what testing infrastructure already exists," not proposed as a Phase 4 deliverable.

---

## 9. Recommended Phase 4 Testing Strategy

1. **Start with service-level unit tests** (§6, level 2) for the 3 in-scope endpoints' business logic — `OrderService.get_my_orders`, `RestaurantService.get_my_restaurant_orders`, `RestaurantService.update_order_status` — using `mongomock-motor`-backed repositories, no real network or DB. This is the highest-leverage, zero-blocker action and directly closes the risks in §5, items 1–5.
2. **Add route-level tests using a dependency override** for `get_current_user_id` (§6, level 3) to verify request/response shape, status codes, and error-response formats (the plain-text 400 / empty-body 401 shapes from `PlainTextAppError`/`EmptyBodyAppError`) end-to-end through the FastAPI routing layer, without waiting on RFOMS-7.
3. **Explicitly defer true end-to-end auth-flow testing** until RFOMS-7 (JWT authentication) is migrated — do not attempt to simulate real auth before then.
4. **Document, rather than automate, the Node-vs-FastAPI behavioral deviations** as a short named checklist (ownership-check fix, no-op status filters, password-hash-in-response preservation) so that whoever eventually does a Node/FastAPI parity pass — manual or automated — has a concrete list to verify against, since no automated Node baseline exists to diff against directly.
5. **Treat the ownership-check fix (§5, item 1) as the single must-test item** before this module is considered QA-ready — it is the one place where FastAPI's behavior is deliberately, correctly different from Node's, and it is currently the least-covered, highest-consequence code path in the module.
