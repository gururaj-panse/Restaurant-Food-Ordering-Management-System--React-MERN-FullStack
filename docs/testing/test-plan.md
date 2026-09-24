# Phase 4 Test Plan — Order Management & Order Lifecycle Module

**Document type:** QA governance and test-execution strategy. Does not report test results or claim tests have passed.

**Basis:** `docs/testing/qa-readiness-notes.md` (QA assessment) and `docs/testing/test-scenario-matrix.md` (34 enumerated scenarios).

---

## 1. Scope

**In scope for Phase 4:**
- Three migrated endpoints: `GET /api/order`, `GET /api/my/restaurant/order`, `PATCH /api/my/restaurant/order/:orderId/status`
- All 34 scenarios enumerated in `docs/testing/test-scenario-matrix.md`
- Order Management & Order Lifecycle module only (Jira Batch 6: RFOMS-11/12/13 stories)
- Business-logic behavior preservation and known regressions
- Database-access layer (repositories) — already passing, referenced for coverage only

**Explicitly not in scope for Phase 4:**
- Stripe/payment logic (`create_checkout_session`, `handle_stripe_webhook`)
- Auth/User/Restaurant-CRUD/Analytics modules (still 501 stubs, not part of this module)
- Frontend testing or changes
- Performance/load/scale testing
- Standing up a Node.js test suite (none exists today; confirmed via direct inspection)
- CI/CD pipeline setup (none exists repo-wide; confirmed)
- LLM evaluation, prompt injection, AI safety testing (not applicable to this module)

---

## 2. Out-of-Scope Items

The following are explicitly **not** tested in Phase 4:

| Item | Reason |
|---|---|
| Stripe API integration | Payment/checkout is out of scope per RFOMS-11/12/13 boundaries |
| JWT/Bearer authentication | RFOMS-7 (Auth Module) not yet migrated; 7 auth scenarios are `Blocked` |
| Google OAuth / Cloudinary / Email | Out of scope; depend on Auth/Restaurant modules not yet migrated |
| Frontend / React testing | No test framework configured in `food-ordering-frontend/` |
| Node.js automated test suite | None exists today; creating one invents scope |
| CI/CD pipeline automation | No CI/CD exists anywhere in the repo |
| Performance characteristics | Latency, throughput, load capacity testing deferred |
| Database schema migration | No migration needed for this module's scope |
| Multi-instance readiness / distributed state | Out of scope for the Order module's current boundaries |

---

## 3. Test Levels

### 3.1 Repository-level (already satisfied)

**Status:** ✅ Baseline established by `tests/test_repositories.py` (17 passing, 1 documented `xfail`).

- `OrderRepository` CRUD + `list_by_user` / `list_by_restaurant`
- `RestaurantRepository.get_by_owner`
- `UserRepository` creation and lookup
- Coverage is comprehensive; no new repository tests proposed in Phase 4

### 3.2 Unit (service layer) — Primary Phase 4 focus

**Approach:** Service methods tested in isolation with mocked repositories.

- **Target:** `OrderService.get_my_orders`, `RestaurantService.get_my_restaurant_orders`, `RestaurantService.update_order_status` + the helper `populate_order()`
- **Framework:** `pytest` + `pytest-asyncio` (strict mode, consistent with existing tests)
- **Mocking:** Repositories instantiated with in-memory `mongomock-motor` collections
- **Environment:** No real MongoDB, no network calls
- **Execution:** `pytest tests/test_order_service.py tests/test_restaurant_order_lifecycle.py -v`

### 3.3 Integration (route-level) — Secondary Phase 4 focus

**Approach:** Full route-to-repository path via `TestClient`, with dependency-injection overrides for auth.

- **Target:** Request/response shapes, HTTP status codes, error-response bodies
- **Framework:** FastAPI `TestClient` (via `tests/conftest.py`)
- **Auth bypass:** `app.dependency_overrides[get_current_user_id] = lambda: <test_user_id>` — allows testing protected routes without RFOMS-7
- **Execution:** Route-level test module (e.g., `tests/test_order_routes.py`)
- **Advantage:** Validates error-handler dispatch (`PlainTextAppError` → plain-text 400, `EmptyBodyAppError` → empty-body 401)

### 3.4 Manual comparison (Node/FastAPI parity)

**Approach:** Side-by-side comparison of actual Node and FastAPI response outputs.

- **Requirements:** Running Node server on `localhost:5000` with equivalent seed data
- **Methods:** curl / Postman to both servers, capture JSON responses, diff field-for-field
- **Scenarios:** 8 scenarios in the matrix marked `Manual` (response shape comparisons)
- **Execution:** Not automated in CI; documented as optional additional verification for human review
- **Evidence:** Screenshots or curl transcripts saved to `docs/testing/parity-evidence/` (optional)

### 3.5 Blocked (auth-dependent)

**Status:** 7 scenarios require RFOMS-7 (JWT auth dependency) before they can be executed live.

| Scenario ID | Endpoint | Reason |
|---|---|---|
| ORD-GET-03 | GET /api/order | Needs real 401 on invalid token (currently 501) |
| RST-ORD-GET-03 | GET /api/my/restaurant/order | Needs real 401 (currently 501) |
| RST-ORD-PATCH-15 | PATCH .../status | Needs real 401 (currently 501) |
| ORD-GET-09 | GET /api/order | Error-handling (needs controlled exception injection) |
| RST-ORD-PATCH-08 | PATCH .../status | Invalid request data (500 path — may be unit-testable with mocks) |
| RST-ORD-PATCH-16 | PATCH .../status | Repository race-condition (needs mock behavior) |

**Test marking:** `@pytest.mark.skip(reason="RFOMS-7 not implemented — see scenario RST-ORD-PATCH-15 for re-enable instructions")`

---

## 4. Environment

**Baseline (confirmed from `tests/test_repositories.py` and project config):**
- Python 3.10 or later (project default)
- FastAPI 0.115+
- Motor 3.5+ (async MongoDB driver)
- pytest 8.0+
- pytest-asyncio 0.23+ (strict mode)
- mongomock-motor 0.0.30+ (in-memory Motor-compatible fake)
- httpx 0.27+ (used by TestClient)

**No additional infrastructure required:**
- No real MongoDB instance needed (mongomock-motor in-memory throughout)
- No Stripe API access needed (payment out of scope)
- No Google OAuth / Cloudinary credentials needed (auth modules stubbed)
- No CI/CD environment needed for Phase 4 (CI setup is out of scope)

**Optional infrastructure for extended verification:**
- Node.js server running `food-ordering-backend/src/index.ts` on `localhost:5000` for manual parity checks
- curl or Postman for side-by-side response capture (not automated)

---

## 5. Test Data

**Sourcing:** Reuse seed-data patterns from `tests/test_repositories.py` (already proven working with `mongomock-motor`).

**Essential fixtures (to be centralized in `tests/conftest.py` or a shared `tests/factories.py`):**

1. **User documents:**
   - `user_id_1`: email=`alice@example.com`, password hashed at cost factor 8, name=`Alice`
   - `user_id_2`: email=`bob@example.com`, password hashed, name=`Bob`
   - Null password for edge cases (if needed)

2. **Restaurant documents:**
   - `restaurant_id_1`: owner=`user_id_1`, restaurantName=`Alice's Diner`, city=`London`, menuItems=[...], status=`active`
   - `restaurant_id_2`: owner=`user_id_2`, restaurantName=`Bob's Bistro`, city=`Manchester`, menuItems=[...], status=`active`
   - `orphaned_restaurant_id`: owner refs a non-existent user, for edge-case testing
   - Null/missing owner for edge cases

3. **Menu items (embedded in restaurants):**
   - Always include `_id` (generated `ObjectId`)
   - name, price in integer pence (e.g., 990 = £9.90)
   - Used to validate cart-item price lookups in checkout flow (out of scope, but referenced by order tests)

4. **Order documents:**
   - **Always seed all 5 statuses:** `placed`, `paid`, `inProgress`, `outForDelivery`, `delivered`
   - Include `placed` (unpaid) orders — critical for regression testing
   - Multiple orders per user/restaurant for filter validation tests
   - Null/missing `restaurant` and `user` refs for edge cases (order.restaurant=null, order.user=null)

5. **CartItems (embedded in orders):**
   - Always include `_id` (generated `ObjectId`)
   - menuItemId, name, quantity
   - No `price` field (confirmed gap, preserved)

---

## 6. Unit Testing

**Framework & tooling (existing):**
```bash
pytest tests/test_order_service.py tests/test_restaurant_order_lifecycle.py -v
```

**Test file structure (proposed):**
- `tests/test_order_service.py` — `OrderService.get_my_orders` and its helper `populate_order()`
- `tests/test_restaurant_order_lifecycle.py` — `RestaurantService.get_my_restaurant_orders` and `update_order_status`

**Test execution approach:**
1. Create service instance with mocked repositories (passed as constructor arguments)
2. Call the service method
3. Assert on the return value (dict shape, fields, values)
4. Optionally, assert on mock-repository call counts/arguments (ensure correct DB queries were made)

**Assertion patterns:**

| Scenario | Assertion target | Example |
|---|---|---|
| Happy path — orders returned | `len(result) > 0` and each order has correct fields | `assert result[0]["status"] in ["placed", "paid", "inProgress", ...]` |
| Empty result | `result == []` | `assert result == []` |
| Response shape | Field presence and type | `assert "user" in result[0]` and `isinstance(result[0]["user"], dict)` |
| Regression — password present | `"password" in result[0]["user"]` | Confirms C1 leak is preserved |
| Regression — no-op filter | All 5 statuses returned | Seed 5 statuses, assert all 5 in result |
| Ownership check (401) | `OrderOwnershipError` raised, caught, returns 401 | `with pytest.raises(OrderOwnershipError): service.update_order_status(...)` |
| Invalid status (500) | `AppError(status_code=500)` raised | `with pytest.raises(AppError, match="unable to update order status"): ...` |

**Mocking pattern for repositories:**
```python
# Mock repositories passed to service
user_repo_mock = Mock(spec=UserRepository)
restaurant_repo_mock = Mock(spec=RestaurantRepository)
order_repo_mock = Mock(spec=OrderRepository)

# Configure mocks to return test data
user_repo_mock.get_by_id.return_value = {"_id": "user1", "email": "test@example.com", "password": "<hash>", ...}
restaurant_repo_mock.get_by_owner.return_value = {"_id": "rest1", "user": "user1", ...}

# Instantiate service with mocks
service = OrderService(
    order_repository=order_repo_mock,
    restaurant_repository=restaurant_repo_mock,
    user_repository=user_repo_mock,
    stripe_client=Mock(),  # Out of scope
    frontend_url="http://localhost:5173"
)

# Execute and assert
result = service.get_my_orders(user_id="user1")
assert len(result) > 0
```

**Expected coverage:**
- Every Happy-path scenario from the matrix
- Every Regression scenario
- Every error-code scenario (400, 401, 404, 500)
- Null/missing reference edge cases

---

## 7. API Testing

**Framework:**
- FastAPI `TestClient` (via `tests/conftest.py`)
- Dependency-injection override for `get_current_user_id` to bypass RFOMS-7 blocker

**Test file (proposed):**
- `tests/test_order_routes.py` — integration tests for all 3 endpoints

**Execution pattern:**
```python
from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_current_user_id

# Override the auth dependency for testing
def override_get_current_user_id():
    return "test_user_id"

app.dependency_overrides[get_current_user_id] = override_get_current_user_id

client = TestClient(app)

# Test GET /api/order
response = client.get("/api/order")
assert response.status_code == 200
assert isinstance(response.json(), list)
```

**Key assertions:**
- HTTP status codes (200, 400, 401, 404, 500)
- Response body structure (JSON object vs. array, required fields)
- Error-response formats:
  - 400 "Invalid order ID format" (JSON, `{"message": "..."}`)
  - 401 empty body for ownership failures (`response.content == b""`)
  - 401 plain-text for webhook signature failures (out of scope)
  - 404 "order not found" (JSON)
  - 500 generic message (JSON, `{"message": "Something went wrong"}`)

**Coverage:**
- Every Integration-level scenario from the matrix
- Response-shape validation (field names, nesting, types)
- Error-handler dispatch (`PlainTextAppError`, `EmptyBodyAppError` → correct response shape)

---

## 8. Integration/Database Testing

**Approach:** Verify that service-layer writes to the database actually persist, not just that the service method returns success.

**Execution pattern (unit-level persistence check):**
```python
# In a unit test, after calling update_order_status:
service.update_order_status(order_id, new_status)

# Re-fetch via the mocked repository to confirm write
order_repo_mock.get_by_id.assert_called_with(order_id)

# Alternatively, if using real mongomock collections (not mocks),
# fetch directly:
persisted = order_repo.get_by_id(order_id)
assert persisted["status"] == new_status
```

**Key scenarios (from `docs/testing/test-scenario-matrix.md`):**
- RST-ORD-PATCH-12: Successful PATCH persists new `status`
- RST-ORD-PATCH-13: `totalAmount` omitted from request, existing value untouched
- ORD-GET-10: Read-only endpoint (no persistence check needed)

**Environment:** mongomock-motor in-memory (consistent with repository tests; no real MongoDB required)

---

## 9. Authentication/Authorization Testing

### 9.1 Authentication Failures (Blocked — RFOMS-7 dependent)

**Scenario:** Missing or invalid Bearer token → 401 `{"message": "unauthorized"}`

**Current status:** All 7 auth-failure scenarios return 501 (stub `get_current_user_id`)

**Blocked scenarios:**
- ORD-GET-03: Missing/invalid token
- RST-ORD-GET-03: Missing/invalid token
- RST-ORD-PATCH-15: Missing/invalid token

**Test marking:** `@pytest.mark.skip(reason="Blocked: RFOMS-7 not implemented")`

**Re-enable instructions (for future):** Once RFOMS-7 lands and `get_current_user_id` is implemented, remove `@pytest.mark.skip` and verify 401 response.

### 9.2 Authorization Failures (Executable today)

**Scenario:** Ownership check on PATCH endpoint — caller is not the owning restaurant's user → 401 empty body

**Test approach (dependency override):**
```python
# Override to return a different user than the owner
def override_get_current_user_id():
    return "wrong_user_id"

app.dependency_overrides[get_current_user_id] = override_get_current_user_id

# Seed order owned by restaurant owned by user1, not wrong_user_id
# PATCH with wrong_user_id should return 401 empty body
response = client.patch("/api/my/restaurant/order/order1/status", json={"status": "paid"})
assert response.status_code == 401
assert response.content == b""
```

**Executable scenarios (3 total):**
- RST-ORD-PATCH-06: Authorization failure — ownership check
- RST-ORD-PATCH-07: Node/FastAPI parity (C2) — FastAPI's fixed 401 vs. Node's 500 crash
- RST-ORD-PATCH-05: Orphaned restaurant — restaurant ref doesn't exist, treated as 401

### 9.3 Authorization Gaps (Documented absence)

**Scenario:** No explicit authorization reject for GET endpoints — a user simply sees only their own restaurant's orders (or `[]` if no restaurant)

**Test approach:**
- Seed multiple restaurants owned by different users
- Override dependency to return user1, request `GET /api/my/restaurant/order`
- Assert result includes only orders for user1's restaurant
- Switch to user2, assert result changes
- This is a regression test (confirms current lack of secondary authz check), not an auth-failure test

---

## 10. Node.js/FastAPI Parity

### 10.1 Documented Deviations

**1. Ownership-check fix (C2) — FastAPI deliberately differs:**
- **Node behavior:** Throws `TypeError` on any real restaurant (dead-code 401 branch) → caught as 500 "unable to update order status"
- **FastAPI behavior:** Fixed; returns real 401 empty body when owner check fails
- **Test approach:** Unit/integration test confirms FastAPI's 401 is returned; document this as a deliberate, flagged fix
- **Node verification:** Manual code inspection only (no Node test suite exists to automate)

**2. Password-hash leak (C1) — both backends the same:**
- **Behavior:** `populate_order()` embeds full `User` doc including `password` hash
- **Test approach:** Both Unit and Integration tests confirm `user.password` field is present
- **Status:** Regression-preserved; flagged as C1 security finding but not "fixed" in this pass

**3. No-op status filters — both backends the same:**
- **Behavior:** Both GET endpoints use filters that exclude nothing
- **Test approach:** Seed all 5 statuses, assert all 5 returned
- **Status:** Confirmed preserved, intentional

**4. 500-on-bad-status — both backends the same:**
- **Behavior:** Invalid `status` enum value → 500 (Mongoose's enum-validation-on-save failure caught as generic error)
- **Test approach:** PATCH with invalid status, assert 500 + exact message "unable to update order status"
- **Status:** Node-parity preserved, not a FastAPI native 422

### 10.2 Manual Parity Checks (8 scenarios)

**Approach:** Response shape field-for-field comparison between running Node and FastAPI servers.

**Scenarios requiring manual verification:**
- ORD-GET-08: Response field-for-field shape (GET /api/order)
- RST-ORD-GET-08: Response field-for-field shape (GET /api/my/restaurant/order)
- Plus others in the matrix marked `Manual`

**Method:** 
1. Seed identical test data on both Node and FastAPI servers
2. Make request via curl/Postman to both
3. Compare JSON structure (field names, nesting, data types, array order)
4. Save evidence to `docs/testing/parity-evidence/<scenario-id>.txt`

**Execution:** Manual only; not automated in CI

---

## 11. Regression Testing

**Purpose:** Pin current behavior so accidental "fixes" are caught as test failures, not silent regressions.

### Regression scenarios (from the matrix):

| ID | Behavior | Test assertion |
|---|---|---|
| ORD-GET-05 | No-op status filter (all 5 statuses returned) | Seed 5 statuses, assert all 5 in result |
| ORD-GET-04 | Password hash in populated user | `assert "password" in result[0]["user"]` |
| RST-ORD-GET-04 | No status filter (includes unpaid `placed` orders) | Seed `placed`, assert it's in result |
| RST-ORD-GET-05 | Password hash in populated user | Same assertion as ORD-GET-04 |
| RST-ORD-PATCH-11 | Out-of-order lifecycle accepted (e.g., `delivered` → `placed` succeeds) | PATCH `delivered` → `placed`, assert 200 (not rejected) |
| RST-ORD-PATCH-09 | Invalid status → 500 (not 400/422) | PATCH invalid status, assert `status_code == 500` |

**Test marking:** No special mark needed; these tests always run. If any fail, it indicates an accidental behavior change.

**Integration with CI:** All regression tests run on every CI build; any failure blocks the build unless the regression is intentional and explicitly approved.

---

## 12. Defect Management

**Known issues (already documented, no new defects anticipated):**

| ID | Finding | Status | Jira ticket |
|---|---|---|---|
| C1 | Password-hash leak via populate | Preserved (flagged for later remediation) | Recommend new RFOMS-2 subtask |
| C2 | Ownership-check Node crash (TypeError → 500) | Deliberately fixed in FastAPI | Document as intentional deviation |
| [NEEDS VERIFICATION] ×5 | Scenarios blocked or requiring manual verification | Documented in matrix | Plan cover |

**Defect-discovery flow (for Phase 4):**
1. If a test fails unexpectedly (i.e., not a `@pytest.mark.skip` or `@pytest.mark.xfail`):
   - Pause the test run
   - Investigate: is this a real bug, a test-writing error, or a gap in prior analysis?
   - Log findings to this plan's Defect Management section
   - Escalate to the project team if it's a real bug

2. No defects are anticipated to be found — Phase 4 tests confirm existing, analyzed behavior.

**Escalation path:** If a defect is found, link it to the existing `docs/security-review.md` / `docs/module-3-code-review.md` trail and open a new Jira issue (or subtask under RFOMS-2 if it's a known gap).

---

## 13. Retesting

**Scope:** Retesting is triggered only by:
1. A test failure during Phase 4 execution (retest after fix investigation)
2. Production code change after Phase 4 completion (retest to confirm no regression)
3. RFOMS-7 implementation (retest the 7 blocked auth scenarios)

**Retesting approach:**
- Re-run the full test suite: `pytest tests/test_order_*.py tests/test_restaurant_*.py -v`
- Compare results to Phase 4 baseline (this plan's exit criteria)
- Any new failures = new defects or regressions

**No retesting loop is defined for Phase 4:** Once all tests pass (per exit criteria below), the test suite becomes the CI baseline.

---

## 14. Entry Criteria

Phase 4 testing can begin when:

1. ✅ The 34 scenarios are enumerated in `docs/testing/test-scenario-matrix.md` (completed)
2. ✅ The test environment (pytest + mongomock-motor) is configured and `tests/test_repositories.py` passes (confirmed)
3. ✅ `docs/security-review.md` and `docs/module-3-code-review.md` are finalized (completed)
4. ✅ This test plan is approved (current step)
5. All test files are created in `tests/` directory (to be done during implementation)

---

## 15. Exit Criteria

Phase 4 is considered complete when:

1. **Test coverage:** Every executable scenario from `docs/testing/test-scenario-matrix.md` has a corresponding test
   - Unit tests for service-layer logic
   - Integration tests for routes (with dependency override for auth)
   - Manual comparison notes for Node/FastAPI parity (optional but recommended)

2. **Test execution:**
   - All unit tests pass: `pytest tests/test_order_service.py tests/test_restaurant_order_lifecycle.py -v`
   - All integration tests pass: `pytest tests/test_order_routes.py -v` (or equivalent)
   - All regression tests pass
   - Expected xfail marks are in place for scenarios that will fail (e.g., mongomock `$all` + regex limitation)

3. **Blocked scenarios:** Every auth-blocked scenario (7 total) is marked with `@pytest.mark.skip(reason="RFOMS-7 not implemented")` with clear re-enable instructions

4. **Code coverage:**
   - Target: ≥95% on the three service methods (`OrderService.get_my_orders`, `RestaurantService.get_my_restaurant_orders`, `update_order_status`)
   - Run: `pytest --cov=app.services.order_service --cov=app.services.restaurant_service --cov-report=html`

5. **Documentation:**
   - This test plan is complete and version-controlled
   - Test files contain docstrings explaining each scenario's purpose
   - Any deviations from the matrix are documented (e.g., if a scenario was split into two tests)

6. **No claims of passing:** This plan defines what should be tested, not a final report. Actual test results are reported separately (if at all) in CI logs or a separate test report.

---

## 16. Evidence Requirements

**Deliverables (for Phase 4 completion):**

1. **Test files:**
   - `tests/test_order_service.py` — unit tests for `OrderService`
   - `tests/test_restaurant_order_lifecycle.py` — unit tests for order-lifecycle `RestaurantService` methods
   - `tests/test_order_routes.py` — integration tests via `TestClient`
   - All files version-controlled in the repo

2. **Test execution output:**
   - Command: `pytest tests/test_order_*.py tests/test_restaurant_*.py -v --tb=short`
   - Output shows every test ID, status (PASSED / SKIPPED / XFAILED), and any assertion messages
   - No failures except expected marks

3. **Code coverage report (optional but recommended):**
   - Run: `pytest --cov=app.services --cov-report=html`
   - HTML report shows ≥95% on the three service methods

4. **Manual parity notes (optional):**
   - Directory: `docs/testing/parity-evidence/`
   - Files: `<scenario-id>.txt` containing curl/Postman outputs from Node and FastAPI
   - Example: `ORD-GET-08.txt` contains side-by-side `curl localhost:5000/api/order` vs. `curl localhost:8000/api/order`

5. **This plan (versioned):**
   - `docs/testing/test-plan.md` finalized and committed to version control

---

## Summary

Phase 4 produces a comprehensive test suite that:
- ✅ Covers all 34 scenarios from the matrix (except those blocked by RFOMS-7)
- ✅ Pins regression behavior (no-op filters, password hash, lifecycle-no-enforcement)
- ✅ Validates the deliberate C2 fix (ownership check 401/200 branching)
- ✅ Documents Node/FastAPI parity
- ✅ Allows testing protected routes without RFOMS-7 (via dependency override)
- ✅ Provides clear re-enable instructions for future work

The test suite is ready to execute once this plan is approved.
