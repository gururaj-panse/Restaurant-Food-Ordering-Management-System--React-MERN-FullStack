# Unit Test Plan — Order Management & Order Lifecycle Module

**Document type:** unit-test design artifact. Enumerates proposed unit tests derived from the actual Phase 3 FastAPI implementation and `docs/testing/test-scenario-matrix.md`. **No test code is implemented and no production code is modified by this document.**

**Basis (re-read directly from the repository for this document, not recalled from memory):**
- `app/services/order_service.py` (`OrderService.get_my_orders`, `populate_order`)
- `app/services/restaurant_service.py` (`RestaurantService.get_my_restaurant_orders`, `RestaurantService.update_order_status`, `OrderOwnershipError`)
- `app/repositories/order_repository.py`, `app/repositories/base.py`
- `app/schemas/common.py` (`mongo_to_jsonable`)
- `app/core/errors.py` (`AppError`, `EmptyBodyAppError`)
- `tests/test_repositories.py`, `tests/conftest.py` (existing baseline + fixture conventions)
- `docs/testing/qa-readiness-notes.md`, `docs/testing/test-scenario-matrix.md`, `docs/testing/test-plan.md`

---

## 1. Scope & Boundaries

**In scope:** unit-level tests (service layer + the two shared/pure helper functions) for the same three endpoints' business logic already enumerated in `docs/testing/test-scenario-matrix.md`:

- `OrderService.get_my_orders` — `GET /api/order`
- `RestaurantService.get_my_restaurant_orders` — `GET /api/my/restaurant/order`
- `RestaurantService.update_order_status` — `PATCH /api/my/restaurant/order/:orderId/status`
- `populate_order()` — shared helper used by both GET paths
- `mongo_to_jsonable()` — shared serialization helper
- `OrderOwnershipError` — error-class contract (Python-level, not HTTP-response-shape level)
- Two small, genuinely uncovered repository-layer gaps discovered while re-reading `base.py`/`order_repository.py` against what the service layer assumes (§6)

**Explicitly out of scope, consistent with the scope already agreed in `docs/testing/test-plan.md` §1–2:**
- `OrderService.create_checkout_session`, `OrderService.handle_stripe_webhook`, `StripeClient` — Stripe/payment logic, out of scope for this module's Phase 4 testing charter
- All stub methods in `RestaurantService` (`get_my_restaurant`, `create_my_restaurant`, etc.) — unimplemented, nothing to unit test yet
- Route-level / `TestClient` / HTTP-status / response-shape tests — those belong to `test-plan.md` §7 (API Testing), not this document
- Repository CRUD already covered by `tests/test_repositories.py` (§6 lists only the specific, real gaps found, not a re-derivation of that whole suite)

**Test ID scheme:**

| Prefix | Target |
|---|---|
| `UT-ORD-GET-##` | `OrderService.get_my_orders` |
| `UT-POP-##` | `populate_order()` |
| `UT-RST-GET-##` | `RestaurantService.get_my_restaurant_orders` |
| `UT-RST-PATCH-##` | `RestaurantService.update_order_status` |
| `UT-COMMON-##` | `mongo_to_jsonable()` |
| `UT-ERR-##` | Error-class contracts |
| `UT-REPO-##` | Repository-layer gaps not already covered by `tests/test_repositories.py` |

**Total proposed: 45 tests.**

---

## 2. Fixture & Mock Conventions

All service-layer tests construct the service directly with mocked repositories — no `TestClient`, no real/mongomock database. This matches the approach already agreed in `test-plan.md` §6.

```python
from unittest.mock import AsyncMock

order_repo = AsyncMock()          # spec=OrderRepository
restaurant_repo = AsyncMock()     # spec=RestaurantRepository
user_repo = AsyncMock()           # spec=UserRepository

service = RestaurantService(restaurant_repo, order_repo, user_repo)
# or: OrderService(order_repo, restaurant_repo, user_repo, stripe_client=AsyncMock(), frontend_url="http://localhost:5173")
```

**Standard sample documents** (reused by reference across the tables below rather than repeated per row):

- `sample_user` — `{"_id": ObjectId(), "email": "jane@example.com", "password": "$2b$08$...hash...", "name": "Jane"}`
- `sample_restaurant` — `{"_id": ObjectId(), "user": "owner-1", "restaurantName": "Pasta Place", "menuItems": [{"_id": ObjectId(), "name": "Spaghetti", "price": 990}]}`
- `sample_order` — `{"_id": ObjectId(), "restaurant": <restaurant._id>, "user": "owner-1", "status": "placed", "cartItems": [{"_id": ObjectId(), "menuItemId": "...", "name": "Spaghetti", "quantity": 2}]}`

Individual rows below note only the **deltas** from these defaults.

---

## 3. `OrderService.get_my_orders` — `GET /api/order`

**Source:** `app/services/order_service.py:100-104`

| ID | Behavior Tested | Expected Result | Fixture/Mock | Test Data | Reason |
|---|---|---|---|---|---|
| UT-ORD-GET-01 | Happy path — multiple orders returned and populated | Returns a list where each order's `restaurant`/`user` fields are replaced by full documents | `order_repo.list_by_user` returns 2 raw orders; `restaurant_repo.get_by_id`/`user_repo.get_by_id` return matching docs | 2 orders, distinct restaurant/user refs each | Confirms the primary read path end-to-end at the service level, not just repository-level |
| UT-ORD-GET-02 | Empty result | Returns `[]`; `populate_order` never invoked (no iteration errors on empty list) | `order_repo.list_by_user` returns `[]` | none | Confirms no exception on the empty-cart-history case, a real first-time-user scenario |
| UT-ORD-GET-03 | Correct repository call contract | `order_repo.list_by_user` called with exactly the `user_id` argument passed to the service method | mock only, no return-value assertions needed beyond call args | `user_id="user-42"` | Confirms the service doesn't accidentally query by restaurant or omit the user scoping — the one thing standing between "my orders" and "everyone's orders" |
| UT-ORD-GET-04 | Recursive ObjectId→string conversion through nested structures | Every `bson.ObjectId` in the returned structure (order `_id`, restaurant `_id`, `menuItems[]._id`, user `_id`, `cartItems[]._id`) is a `str` in the final output | real `sample_order`/`sample_restaurant`/`sample_user` docs with live `ObjectId()` values, 3 levels of nesting | as above | `mongo_to_jsonable` is currently untested (flagged in `qa-readiness-notes.md` §4); this is the one call site where 3-level-deep nesting actually occurs in production data, so a shallow-only test would miss a regression |
| UT-ORD-GET-05 | Regression — password hash preserved in populated user | Returned `order["user"]["password"]` equals the mocked hash unchanged | `sample_user` with a bcrypt-shaped hash string | as above | Pins confirmed finding C1 (`security-review.md`) — this test exists to catch an *accidental* fix, not to validate the leak is acceptable |
| UT-ORD-GET-06 | Per-order independent population, not reused across iterations | Two orders referencing two *different* restaurants/users each end up with their own distinct populated doc, not both showing the last-fetched one | `restaurant_repo.get_by_id`/`user_repo.get_by_id` configured with `side_effect` returning different docs per call | order A → restaurant A/user A; order B → restaurant B/user B | Guards against a classic loop-variable-reuse bug in list-comprehension population code |
| UT-ORD-GET-07 | Mixed batch — one order has a missing `user` ref among otherwise-populated orders | The order with no `user` ref resolves to `order["user"] is None`; sibling orders in the same batch still populate normally | order A has `user: "owner-1"`, order B has `user: None`/missing key | 2 orders in one `list_by_user` result | Confirms a single malformed/legacy document doesn't break population for the rest of the batch — realistic given `Order.user` is not a required ref (`CURRENT_STATE.md`) |
| UT-ORD-GET-08 | Pass-through — service applies no additional filtering beyond what the repository returns | Whatever `order_repo.list_by_user` returns (any status mix) comes back populated 1:1, same count, same order | `order_repo.list_by_user` returns orders with mixed statuses including `"placed"` | 3 orders, 3 different statuses | Confirms status filtering is exclusively the repository's responsibility (already tested there) and the service doesn't silently re-filter or reorder — a regression here would be invisible without this test since the repository-level filter is already a confirmed no-op |

---

## 4. `populate_order()` — shared helper

**Source:** `app/services/order_service.py:62-80`

| ID | Behavior Tested | Expected Result | Fixture/Mock | Test Data | Reason |
|---|---|---|---|---|---|
| UT-POP-01 | Input non-mutation | The original `order` dict passed in is unchanged after the call (`order["restaurant"]` still the original ref) | plain dict input, no repositories needed for the ref value itself | `{"restaurant": "r1", "user": "u1", ...}` | The function does `order = dict(order)` — a shallow copy — but both call sites (`get_my_orders`, `get_my_restaurant_orders`) call it inside a list comprehension; a future edit that mutates in place instead would silently corrupt the original documents across iterations |
| UT-POP-02 | Missing/falsy `restaurant` ref | `restaurant_repo.get_by_id` is **never called**; `order["restaurant"] is None` | `order = {"restaurant": None, "user": "u1"}` | as above | Confirms the falsy-guard short-circuits rather than calling `get_by_id(None)` (which would raise inside `ObjectId.is_valid`/string handling) |
| UT-POP-03 | `restaurant` ref present but repository returns `None` (deleted/orphaned restaurant) | No exception raised; `order["restaurant"] is None` in the result | `restaurant_repo.get_by_id` returns `None` | `order = {"restaurant": "<deleted-id>", ...}` | This is the exact root state that later produces the documented 401-not-404 edge case on the PATCH endpoint (`RST-ORD-PATCH-05` in the scenario matrix) — confirming *this* helper degrades gracefully (not an exception) is the precondition that makes that downstream behavior reachable at all |
| UT-POP-04 | `restaurant` ref is a real `bson.ObjectId`, not a string | `restaurant_repo.get_by_id` is called with `str(the_objectid)`, a string | `order["restaurant"] = ObjectId(...)` | live `ObjectId()` | Production writes via `create_checkout_session` store `restaurant["_id"]` — a raw `ObjectId` — while test-seeded fixtures elsewhere use plain strings; this confirms population is correct regardless of which shape the ref happens to be in, since both occur in real data |
| UT-POP-05 | Missing/falsy `user` ref | `user_repo.get_by_id` never called; `order["user"] is None` | `order = {"restaurant": "r1", "user": None}` | as above | Mirrors UT-POP-02 for the `user` side — a distinct branch in the same function, not implied by testing the restaurant side alone |
| UT-POP-06 | `user` ref present but repository returns `None` | No exception; `order["user"] is None` | `user_repo.get_by_id` returns `None` | as above | `Order.user` is not a required ref (confirmed gap) — an order with a deleted/never-set user must still populate without crashing the whole list |
| UT-POP-07 | `user` ref is a real `bson.ObjectId` | `user_repo.get_by_id` called with a string form | `order["user"] = ObjectId(...)` | live `ObjectId()` | Mirrors UT-POP-04 for the `user` side |

---

## 5. `RestaurantService.get_my_restaurant_orders` — `GET /api/my/restaurant/order`

**Source:** `app/services/restaurant_service.py:58-66`

| ID | Behavior Tested | Expected Result | Fixture/Mock | Test Data | Reason |
|---|---|---|---|---|---|
| UT-RST-GET-01 | No restaurant owned by the caller | Returns `[]`; `order_repo.list_by_restaurant` is **never called** | `restaurant_repo.get_by_owner` returns `None` | `user_id="no-restaurant-user"` | Confirmed business rule: 200 + empty list, not 404 (`restaurant_service.py:62`). The "never called" assertion is the meaningful part — a naive test could pass even if the short-circuit were removed and `list_by_restaurant` happened to also return `[]` for a bad ID |
| UT-RST-GET-02 | Restaurant owned, has orders | Returns populated, jsonable list matching the repository's orders | `restaurant_repo.get_by_owner` returns `sample_restaurant`; `order_repo.list_by_restaurant` returns 2 orders | 2 orders for the owned restaurant | Primary happy path for the restaurant-owner order view |
| UT-RST-GET-03 | Restaurant owned, zero orders | Returns `[]` (repository was queried, unlike UT-RST-GET-01) | `order_repo.list_by_restaurant` returns `[]` | none | Distinguishes "new restaurant, no orders yet" from "no restaurant at all" — both produce `[]` but via different code paths; conflating them in one test would hide a regression in the short-circuit logic |
| UT-RST-GET-04 | Correct ID passed to `list_by_restaurant` | Called with `str(restaurant["_id"])` | `sample_restaurant` with a live `ObjectId` `_id` | as above | `get_by_owner` returns a raw Motor doc — `_id` is an `ObjectId`; confirms the required `str()` conversion happens before querying by restaurant, matching `list_by_restaurant`'s string-keyed usage elsewhere |
| UT-RST-GET-05 | Regression — no status filtering, includes unpaid `"placed"` orders | An order with `status="placed"` seeded among the mocked results is present, unfiltered, in the output | `order_repo.list_by_restaurant` returns orders with `status` in `{"placed","paid","delivered"}` | 3 orders, 3 statuses | Pins `RST-ORD-GET-04` from the scenario matrix at the unit level — restaurant owners seeing unpaid orders is a deliberate current behavior, not a bug to "helpfully" filter out later |
| UT-RST-GET-06 | Regression — password hash preserved in populated user | Same assertion pattern as UT-ORD-GET-05 | `sample_user` with hash | as above | Same rule (C1) applies to this endpoint independently — it uses the same `populate_order` helper but is a separate call site and deserves its own pinning test |

---

## 6. `RestaurantService.update_order_status` — `PATCH /api/my/restaurant/order/:orderId/status`

**Source:** `app/services/restaurant_service.py:68-118`. Highest-priority target per `qa-readiness-notes.md` §5 — the sole location of the deliberate, flagged ownership-check fix (finding C2).

| ID | Behavior Tested | Expected Result | Fixture/Mock | Test Data | Reason |
|---|---|---|---|---|---|
| UT-RST-PATCH-01 | Malformed `order_id` (fails `ObjectId.is_valid`) | Raises `AppError(status_code=400, message="Invalid order ID format")`; `order_repo.get_by_id` **never called** | none needed beyond the string | `order_id="not-a-valid-id"` | Confirms the format check short-circuits before any DB call — a cheap, deterministic guard worth pinning precisely |
| UT-RST-PATCH-02 | Empty/falsy `order_id` | Same 400 as above, via the `not order_id` branch specifically | none | `order_id=""` | Distinct branch of the same `or` condition (`restaurant_service.py:98`) — an empty string and a malformed string are different inputs that must both be caught; testing only one leaves the other unverified |
| UT-RST-PATCH-03 | Valid ID format, order does not exist | Raises `AppError(404, "order not found")` | `order_repo.get_by_id` returns `None` | valid `ObjectId` string | Confirms the not-found path is reached only after format validation passes, and produces the documented 404 (not the 401 that the orphaned-*restaurant* case produces — an important distinction between "order missing" and "restaurant missing") |
| UT-RST-PATCH-04 | Order found, restaurant resolves, `restaurant.user == user_id` | No exception raised through the ownership check; execution proceeds to the status-enum check | `order.restaurant` valid; `restaurant_repo.get_by_id` returns `sample_restaurant` with `"user": "owner-1"`; caller is `"owner-1"` | matching owner | Confirms the legitimate-owner path actually works — this is the path Node's bug made unreachable in production (see module docstring); it is the single most important "does the fix work at all" test |
| UT-RST-PATCH-05 | Order found, restaurant found, `restaurant.user != user_id` | Raises `OrderOwnershipError` (401, empty body contract — see UT-ERR-01) | caller `"owner-1"`, restaurant owned by `"owner-2"` | mismatched owner | **The single must-test item** per `qa-readiness-notes.md` §5 item 1 and `test-scenario-matrix.md` `RST-ORD-PATCH-06`/`-07` — this is the deliberate C2 fix; a regression here silently reopens either the original Node crash-to-500 bug or a security hole allowing cross-restaurant status edits |
| UT-RST-PATCH-06 | Order found, `order.restaurant` ref resolves to `None` (deleted/orphaned restaurant) | Raises `OrderOwnershipError` (401), not a 404 or 500 | `restaurant_repo.get_by_id` returns `None` | `order.restaurant = "<deleted-id>"` | Confirmed edge case traced directly to `restaurant_service.py:106` (`restaurant_owner = str(...) if restaurant and restaurant.get("user") else None`) — `None != user_id` is always true, so this *always* denies, even for the "rightful" former owner. Documented in the matrix as `[confirmed via code trace]`; this test converts that trace into an executable guarantee |
| UT-RST-PATCH-07 | Order found, restaurant found, but `restaurant.get("user")` is falsy (restaurant exists, never assigned an owner) | Raises `OrderOwnershipError` (401) — same outcome as UT-RST-PATCH-06, different precondition | `restaurant_repo.get_by_id` returns a doc with no `"user"` key | restaurant doc missing `user` field | A distinct, realistic data state (`Restaurant.user` is not a required ref per `CURRENT_STATE.md`) from "restaurant was deleted" — worth its own test since a future refactor could fix one path and not the other |
| UT-RST-PATCH-08 | Ownership passes, `status` is a valid enum member | `order_repo.update_status` called with `(order_id, status=status)`; on success, re-fetches via `get_by_id` and returns `mongo_to_jsonable(updated_order)` | `order_repo.update_status` returns `True`; `get_by_id` (2nd call) returns the updated doc | `status="inProgress"` | Full happy-path success test — the only test in this table that reaches the method's final return statement |
| UT-RST-PATCH-09 | Ownership passes, `status is None` | Raises `AppError(500, "unable to update order status")` | none | `status=None` | `None not in _ORDER_STATUSES` — confirms a missing/omitted status field in the PATCH body produces this specific 500, matching Mongoose's save()-time enum-validation-failure behavior it's designed to mirror |
| UT-RST-PATCH-10 | Ownership passes, `status` is a non-enum string | Same 500 as UT-RST-PATCH-09 | none | `status="cancelled"` and, as a second case, `status="Paid"` (wrong case) | Confirms exact, case-sensitive enum membership with no normalization — "Paid" ≠ "paid" is a realistic client-typo scenario worth its own assertion, not assumed identical to a nonsense value |
| UT-RST-PATCH-11 | Ownership + status valid, but `order_repo.update_status` returns `False` (simulated race: order deleted between the initial lookup and the write) | Raises `AppError(500, "unable to update order status")` | `order_repo.update_status` returns `False` | otherwise-valid inputs | Exercises the race-condition branch flagged as `[NEEDS VERIFICATION]`/`Blocked` in the scenario matrix (`RST-ORD-PATCH-16`) — a real concurrency race can't be reliably reproduced in a test, but the *handling* of a failed update is fully mockable and deserves coverage independent of the race itself |
| UT-RST-PATCH-12 | Regression — no lifecycle state-machine enforcement, "backward" transition accepted | A transition from `status="delivered"` (current, irrelevant to this method since it never reads current status) to a requested `status="placed"` succeeds (200), no rejection | `order_repo.update_status` returns `True` regardless of the "previous" status | requested `status="placed"` | Pins the confirmed absence of a lifecycle state machine — the method never even reads the order's *current* status before writing the new one, so any enum member is accepted from any prior state. A future contributor adding "helpful" transition validation would break this without a test present to catch it |
| UT-RST-PATCH-13 | Regression — idempotent re-set accepted (no no-op guard) | Requesting the same status the order already has still succeeds and still calls `update_status` | order's current status and requested status are both `"paid"` | `status="paid"` | Confirms there is no guard against setting an unchanged value either — completes the "no lifecycle logic at all" picture alongside UT-RST-PATCH-12 |
| UT-RST-PATCH-14 | Contract — `update_status` called without `total_amount` | `order_repo.update_status` is called as `update_status(order_id, status=status)` with no `total_amount` argument (or explicitly `None`) | spy on call args | any valid status | Distinguishes this call site from the Stripe-webhook call site (out of scope), which *does* pass `total_amount`. A regression that starts passing a stray `total_amount` here would silently corrupt `totalAmount` on every manual status change — worth a direct contract test since the two call sites share one repository method |
| UT-RST-PATCH-15 | Robustness — `order.get("restaurant")` stored as a real `ObjectId` (not a string) | Ownership check still resolves correctly; `restaurant_repo.get_by_id` called with a string form | `order["restaurant"] = ObjectId(...)` | live `ObjectId()` | Same rationale as UT-POP-04/07 — production orders created via checkout store a raw `ObjectId` in this field; the `str(order.get("restaurant"))` call at `restaurant_service.py:105` must handle both shapes correctly since the ownership check is the security-critical path in this method |

---

## 7. `mongo_to_jsonable()` — shared serialization helper

**Source:** `app/schemas/common.py:23-40`. Pure function; flagged as untested in `qa-readiness-notes.md` §4 item "mongo_to_jsonable()".

| ID | Behavior Tested | Expected Result | Fixture/Mock | Test Data | Reason |
|---|---|---|---|---|---|
| UT-COMMON-01 | Bare `ObjectId` input | Returns the equivalent string | none | `ObjectId()` | Base case of the function's core contract |
| UT-COMMON-02 | Dict with `ObjectId` values at multiple keys | All `ObjectId` values converted; non-`ObjectId` values (e.g. plain strings) untouched; dict keys unchanged | none | `{"_id": ObjectId(), "restaurant": ObjectId(), "status": "placed"}` | Confirms selective conversion — the function must not accidentally stringify already-string fields or touch dict keys |
| UT-COMMON-03 | List of dicts, each containing an `ObjectId` | Every element converted independently | none | `[{"_id": ObjectId()}, {"_id": ObjectId()}]` | Matches the shape of `list_by_user`/`list_by_restaurant` results before population |
| UT-COMMON-04 | Deeply nested structure — dict → list → dict → `ObjectId` (3 levels) | All levels correctly recursed; structure/shape preserved | none | `{"restaurant": {"menuItems": [{"_id": ObjectId()}]}}` | This exact shape is what a populated order actually looks like in production (order → restaurant → menuItems[] → `_id`); a shallow-recursion bug would only surface at this depth, not at 1–2 levels |
| UT-COMMON-05 | Non-convertible types pass through unchanged, **including `datetime`** | `str`, `int`, `bool`, `None`, and `datetime` values are returned exactly as given (same object/value, no stringification) | none | `{"name": "Jane", "quantity": 2, "active": True, "note": None, "createdAt": datetime.now()}` | The function's own docstring explicitly claims `datetime` is left as-is for FastAPI's encoder to handle later — this is a specific, falsifiable claim that has never been executed as a test; worth verifying directly rather than trusting the comment |
| UT-COMMON-06 | Empty dict and empty list inputs | Returns `{}`/`[]` respectively, no error | none | `{}`, `[]` | Trivial but real edge case — `get_my_restaurant_orders`'s `[]`-on-no-restaurant path and any order with an empty `cartItems` list both flow through this function |

---

## 8. Error-class contracts

**Source:** `app/services/restaurant_service.py:30-34`, `app/core/errors.py:42-50`

| ID | Behavior Tested | Expected Result | Fixture/Mock | Test Data | Reason |
|---|---|---|---|---|---|
| UT-ERR-01 | `OrderOwnershipError` class contract | Instance is an `EmptyBodyAppError` (and therefore an `AppError`); `status_code == 401`; `message == "unauthorized"` | none, direct instantiation | `OrderOwnershipError()` | The HTTP-level empty-body response shape (tested separately at the API level per `test-plan.md` §7) depends entirely on this class staying a subclass of `EmptyBodyAppError` — a future refactor that changes the base class or hardcodes a different status would break the empty-body dispatch silently unless this contract is pinned directly at the unit level, independent of the HTTP layer |

---

## 9. Repository-layer gaps (supplementary to `tests/test_repositories.py`)

The existing repository suite (`tests/test_repositories.py`, 17 passing + 1 documented `xfail`) already covers `list_by_user`, `list_by_restaurant`, `create`, and the success paths of `update_status` for the Order collection. Re-reading `base.py` and `order_repository.py` against what the service layer in §6 assumes surfaced two real, currently-untested behaviors that the service depends on:

| ID | Source | Behavior Tested | Expected Result | Fixture/Mock | Test Data | Reason |
|---|---|---|---|---|---|---|
| UT-REPO-01 | `app/repositories/base.py:28-34` (`update_by_id`, used by `OrderRepository.update_status`) | Update against a **valid-format but non-existent** `_id` | Returns `False` (`matched_count == 0`), no exception | `mongomock-motor` in-memory collection, real repository instance | seed nothing; call `update_status(str(ObjectId()), status="paid")` on an empty collection | UT-RST-PATCH-11 mocks this return value at the service level to test the *handling* of a failed update; this repository-level test closes the gap by confirming the repository actually produces `False` in exactly this situation rather than raising or silently returning `True` — without it, UT-RST-PATCH-11's mock is an assumption, not a verified contract |
| UT-REPO-02 | `app/repositories/base.py:19-22` (`get_by_id`) | Lookup with a syntactically invalid `ObjectId` string | Returns `None`, no exception (the `ObjectId.is_valid` guard short-circuits before the driver call) | `mongomock-motor` in-memory collection, real repository instance | `get_by_id("not-a-valid-id")` | `update_order_status` performs its own `ObjectId.is_valid` check before ever calling a repository method (UT-RST-PATCH-01), so this guard is currently redundant *for that one call site* — but it is the only thing standing between a malformed ID and a driver-level crash for any *other* current or future caller of `get_by_id`, and it has no direct test today |

---

## 10. Cross-reference to `test-scenario-matrix.md`

This unit-test plan implements the mockable, non-HTTP portion of the following matrix scenarios at the unit level (HTTP status/response-shape verification for the same scenarios remains the job of the integration tests described in `test-plan.md` §7):

| Matrix scenario | Unit tests covering it |
|---|---|
| `RST-ORD-PATCH-06`, `RST-ORD-PATCH-07` (ownership check / C2 fix) | UT-RST-PATCH-04, -05 |
| `RST-ORD-PATCH-05` (orphaned restaurant → 401) | UT-RST-PATCH-06, -07, UT-POP-03 |
| `ORD-GET-04`, `RST-ORD-GET-05` (password hash preserved, C1) | UT-ORD-GET-05, UT-RST-GET-06 |
| `ORD-GET-05` (no-op status filter) | UT-ORD-GET-08 (service pass-through only; filter itself already covered by `tests/test_repositories.py`) |
| `RST-ORD-GET-04` (unfiltered, includes `placed`) | UT-RST-GET-05 |
| `RST-ORD-PATCH-11` (out-of-order transition accepted) | UT-RST-PATCH-12 |
| `RST-ORD-PATCH-09` (invalid status → 500) | UT-RST-PATCH-09, -10 |
| `RST-ORD-PATCH-16` (repository race condition, `Blocked`/`Needs-verification`) | UT-RST-PATCH-11 (handling only; true concurrency remains unverified, as noted in the matrix) |

---

## 11. Explicitly Not Proposed

- Any test of `create_checkout_session` / `handle_stripe_webhook` / `StripeClient` — out of scope per §1.
- Any test asserting HTTP status codes or response bodies directly — that is integration-level, not unit-level; see `test-plan.md` §7.
- A test for the `NotImplementedFeatureError` stub methods on `RestaurantService` — they contain no business logic to test, only a fixed 501 raise, already self-evident from `errors.py`.
- Tests re-deriving what `tests/test_repositories.py` already covers (e.g., cart-item `_id` generation, the no-op status filter's own repository-level mechanics) — referenced, not duplicated.

---

## Summary

| Category | Count |
|---|---|
| `OrderService.get_my_orders` | 8 |
| `populate_order()` | 7 |
| `RestaurantService.get_my_restaurant_orders` | 6 |
| `RestaurantService.update_order_status` | 15 |
| `mongo_to_jsonable()` | 6 |
| Error-class contracts | 1 |
| Repository gaps | 2 |
| **Total** | **45** |

No test code has been written. This plan is ready for implementation under the framework and fixture conventions already agreed in `docs/testing/test-plan.md` §6.
