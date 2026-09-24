# API & Integration Test Execution Results — Order Management & Order Lifecycle Module

**Date executed:** 2026-09-22
**Executed by:** automated run in this session (no results fabricated or estimated — every table row below reflects the actual pytest output captured in this run)
**Scope:** implementation of `docs/testing/api-integration-test-plan.md` for the 3 migrated Order Management endpoints, run against the **real FastAPI application** with a real in-memory database and real JWT verification.

---

## 1. Exact Command

Run from `food-ordering-backend-fastapi/`, using the project's existing virtual environment (no new packages installed):

```
./venv/Scripts/python.exe -m pytest -v
```

**Full suite (includes the unit tests from the prior task plus this task's new API/integration tests):**

```
collected 120 items
=========== 118 passed, 1 skipped, 1 xfailed, 88 warnings in 8.50s ===========
```

**New API/integration files only, run in isolation to confirm they carry their own weight:**

```
./venv/Scripts/python.exe -m pytest tests/test_api_order_routes.py tests/test_api_restaurant_order_routes.py -v
collected 56 items
================= 55 passed, 1 skipped, 88 warnings in 1.95s ==================
```

**Environment:**
- Python 3.14.2, pytest 9.1.1, pytest-asyncio 1.4.0 (`Mode.STRICT`)
- Real `app.main:app` FastAPI application (not a stripped-down test app)
- Real JWT verification (`app.api.deps.get_current_user_id`) — tokens signed with the project's actual `JWT_SECRET_KEY` (read live from `app.config.get_settings()`, not hardcoded in the test suite)
- **In-memory `mongomock-motor` database**, swapped into the `mongodb` singleton for the duration of each test — **zero real network calls were made** to the live MongoDB Atlas cluster configured in this project's `.env` (see §6, Safety Notes)

---

## 2. Result Summary

| Metric | Full suite | New API/integration tests only |
|---|---|---|
| Total collected | 120 | 56 |
| Passed | 118 | 55 |
| Failed | 0 | 0 |
| Skipped | 1 | 1 |
| XFailed (pre-existing, unrelated) | 1 | 0 |
| Errors | 0 | 0 |

**No failures occurred.** Every implemented scenario passed against the real application. The one skip is intentional and documented (§5, API-RST-PATCH-30 — a true-concurrency race condition, explicitly deferred in the approved plan as not reproducible via a single-threaded `TestClient`, not silently dropped).

---

## 3. New Test Infrastructure Added

| File | Purpose |
|---|---|
| `tests/conftest.py` (extended, not replaced) | Added `api_client` fixture (real in-memory DB wired into the app's DI chain, `mongodb.connect` monkeypatched to a no-op for safety) and `make_token` fixture (signs real JWTs with the app's actual secret/algorithm) |
| `tests/test_api_order_routes.py` | `GET /api/order` — 13 scenarios |
| `tests/test_api_restaurant_order_routes.py` | `GET /api/my/restaurant/order` (14 scenarios) + `PATCH /api/my/restaurant/order/:orderId/status` (28 executed + 1 skipped) |

The pre-existing `client` fixture (used by `tests/test_health.py`) was left completely untouched.

---

## 4. Scenario-by-Scenario Results

Every row reflects an actual executed assertion against the real app, not a description of intended behavior. "Evidence reference" is the exact pytest node ID — run it directly to reproduce.

### 4.1 `GET /api/order`

| ID | Scenario | Expected | Actual | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| API-ORD-GET-01 | Happy path, multiple orders populated | 200, both orders present, restaurant/user embedded as full docs | 200, both orders present, populated as expected | PASS | `test_api_order_routes.py::test_api_ord_get_01_happy_path_multiple_orders_populated` |
| API-ORD-GET-02 | Happy path, zero orders | 200, `[]` | 200, `[]` | PASS | `...::test_api_ord_get_02_happy_path_no_orders_returns_empty_array` |
| API-ORD-GET-03 (=AUTH-07) | Cookie-only auth (`session_id`), no `Authorization` header | 200, populated array | 200, order returned | PASS | `...::test_api_ord_get_03_happy_path_via_session_id_cookie_fallback` |
| API-ORD-GET-04 (AUTH-01) | No token at all | 401, `{"message":"unauthorized"}` | 401, exact body match | PASS | `...::test_api_ord_get_04_auth01_no_token_at_all` |
| API-ORD-GET-05 (AUTH-02) | Non-`Bearer` `Authorization` header | 401, same body | 401, same body | PASS | `...::test_api_ord_get_05_auth02_non_bearer_authorization_header` |
| API-ORD-GET-06 (AUTH-03) | Garbage Bearer token | 401, same body | 401, same body | PASS | `...::test_api_ord_get_06_auth03_garbage_bearer_token` |
| API-ORD-GET-07 (AUTH-04) | Valid signature, missing `userId` claim | 401, same body | 401, same body | PASS | `...::test_api_ord_get_07_auth04_valid_signature_missing_userid_claim` |
| API-ORD-GET-08 (AUTH-05) | Wrong signing secret | 401, same body | 401, same body | PASS | `...::test_api_ord_get_08_auth05_wrong_signing_secret` |
| API-ORD-GET-09 (AUTH-06) | Expired token | 401, same body | 401, same body | PASS | `...::test_api_ord_get_09_auth06_expired_token` |
| API-ORD-GET-10 | Cross-user isolation | user A never sees user B's orders | confirmed — only A's order returned | PASS | `...::test_api_ord_get_10_cross_user_isolation` |
| API-ORD-GET-11 | Regression: `"placed"` (unpaid) included | all 5 statuses present, unfiltered | all 5 present | PASS | `...::test_api_ord_get_11_regression_placed_status_included_unfiltered` |
| API-ORD-GET-12 | Regression: password hash present (C1) | `user.password` present, bcrypt-shaped | present, `$2b$`-prefixed, ≠ plaintext | PASS | `...::test_api_ord_get_12_regression_password_hash_present_in_response` |
| API-ORD-GET-13 | Orphaned restaurant/user refs → null, not 500 | 200, both fields `null` | 200, both fields `null` | PASS | `...::test_api_ord_get_13_orphaned_refs_resolve_to_null_not_500` |

### 4.2 `GET /api/my/restaurant/order`

| ID | Scenario | Expected | Actual | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| API-RST-GET-01 | Happy path, multiple orders populated | 200, both orders, populated | 200, both present, populated | PASS | `test_api_restaurant_order_routes.py::test_api_rst_get_01_happy_path_multiple_orders_populated` |
| API-RST-GET-02 | Restaurant owned, zero orders | 200, `[]` | 200, `[]` | PASS | `...::test_api_rst_get_02_restaurant_owned_zero_orders_returns_empty_array` |
| API-RST-GET-03 | No restaurant at all | 200, `[]` — **not 404** | 200, `[]` | PASS | `...::test_api_rst_get_03_no_restaurant_at_all_returns_empty_array_not_404` |
| API-RST-GET-04 (=AUTH-07) | Cookie-only auth | 200, populated | 200, order returned | PASS | `...::test_api_rst_get_04_happy_path_via_session_id_cookie_fallback` |
| API-RST-GET-05…10 (AUTH-01…06) | 6 auth-failure modes | 401, `{"message":"unauthorized"}` (all) | 401, exact match (all 6) | PASS ×6 | `...::test_api_rst_get_05_auth01...` through `...get_10_auth06...` |
| API-RST-GET-11 | Cross-restaurant isolation | owner A never sees owner B's orders | confirmed | PASS | `...::test_api_rst_get_11_cross_restaurant_isolation` |
| API-RST-GET-12 | Regression: `"placed"` included, unfiltered | all seeded statuses present | confirmed | PASS | `...::test_api_rst_get_12_regression_placed_status_included_unfiltered` |
| API-RST-GET-13 | Regression: password hash present (C1) | present, bcrypt-shaped | confirmed | PASS | `...::test_api_rst_get_13_regression_password_hash_present_in_response` |
| API-RST-GET-14 | Orphaned `user` ref → null, not 500 (adapted — see §5 note) | 200, `restaurant` populated, `user` null | 200, exactly that | PASS | `...::test_api_rst_get_14_orphaned_user_ref_resolves_to_null_not_500` |

### 4.3 `PATCH /api/my/restaurant/order/:orderId/status`

| ID | Scenario | Expected | Actual | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| API-RST-PATCH-01 | Success response is **unpopulated** (raw ID refs, unlike both GET endpoints) | 200, `restaurant`/`user` are plain strings | 200, confirmed raw strings, not embedded docs | PASS | `...::test_api_rst_patch_01_success_response_is_unpopulated_raw_refs` |
| API-RST-PATCH-02 | Full forward lifecycle walk (4 hops) | 200 at every hop, status reflects each value | 200 ×4, all values correct | PASS | `...::test_api_rst_patch_02_full_forward_lifecycle_walk` |
| API-RST-PATCH-03 | Regression: backward transition accepted | 200, no rejection | 200 | PASS | `...::test_api_rst_patch_03_regression_backward_transition_accepted` |
| API-RST-PATCH-04 | Regression: skip-ahead transition accepted | 200, no rejection | 200 | PASS | `...::test_api_rst_patch_04_regression_skip_ahead_transition_accepted` |
| API-RST-PATCH-05 | Regression: idempotent resubmission accepted | 200 | 200 | PASS | `...::test_api_rst_patch_05_regression_idempotent_resubmission_accepted` |
| API-RST-PATCH-06 | Malformed JSON body | 400, `{"errors":[...]}` (NOT `{"message":...}`) | 400, `errors` key present, `message` key absent | PASS | `...::test_api_rst_patch_06_malformed_json_body_returns_400_errors_shape` |
| API-RST-PATCH-07 | Non-object JSON body (a list) | 400, `{"errors":[...]}` | 400, confirmed | PASS | `...::test_api_rst_patch_07_non_object_json_body_returns_400_errors_shape` |
| API-RST-PATCH-08 | Empty object body `{}` — distinct failure mode from -06/-07 | 500, `{"message":"unable to update order status"}` (NOT 400) | 500, exact message | PASS | `...::test_api_rst_patch_08_empty_object_body_returns_500_service_layer` |
| API-RST-PATCH-09…14 (AUTH-01…06) | 6 auth-failure modes | 401, `{"message":"unauthorized"}` (all) | 401, exact match (all 6) | PASS ×6 | `...::test_api_rst_patch_09_auth01...` through `...patch_14_auth06...` |
| API-RST-PATCH-15 | **Mismatched owner** (the C2 headline test) | 401, empty body; write NOT persisted | 401, `content == b""`; re-fetch confirms status unchanged | PASS | `...::test_api_rst_patch_15_mismatched_owner_returns_401_empty_body` |
| API-RST-PATCH-16 | Orphaned restaurant ref | 401, empty body (not 404/500) | 401, empty body | PASS | `...::test_api_rst_patch_16_orphaned_restaurant_ref_returns_401_not_404_or_500` |
| API-RST-PATCH-17 | Restaurant with no owner assigned | 401, empty body | 401, empty body | PASS | `...::test_api_rst_patch_17_restaurant_with_no_owner_assigned_returns_401` |
| API-RST-PATCH-18 | Positive control (legitimate owner succeeds) | 200 | Same assertion as -01 — see that row (not duplicated as a separate test, per the plan's own cross-reference) | PASS (via -01) | `...::test_api_rst_patch_01_...` |
| API-RST-PATCH-19 | Order not found | 404, `{"message":"order not found"}` | 404, exact match | PASS | `...::test_api_rst_patch_19_order_not_found_returns_404` |
| API-RST-PATCH-20 | Invalid `order_id` format | 400, `{"message":"Invalid order ID format"}` (NOT `{"errors":...}`) | 400, exact match, `errors` key absent | PASS | `...::test_api_rst_patch_20_invalid_order_id_format_returns_400_message_shape` |
| API-RST-PATCH-21 | **[Resolved]** Empty `order_id` path segment | *(plan: needs verification)* | **404, `{"detail":"Not Found"}`** — confirmed Starlette router-level 404, never reaches auth or service | PASS (asserts the now-confirmed value) | `...::test_api_rst_patch_21_empty_order_id_segment_is_a_framework_404` |
| API-RST-PATCH-22 | **[Resolved]** No auth + malformed body together (precedence) | *(plan: needs verification)* | **400, `{"errors":[...]}`** — confirmed request-body validation is resolved before the auth dependency's exception propagates; validation "wins" | PASS (asserts the now-confirmed value) | `...::test_api_rst_patch_22_precedence_no_auth_and_malformed_body_validation_wins` |
| API-RST-PATCH-23 | `status: null` | 500, same message | 500, confirmed | PASS | `...::test_api_rst_patch_23_null_status_returns_500` |
| API-RST-PATCH-24 | `status: "cancelled"` (non-enum) | 500, same message | 500, confirmed | PASS | `...::test_api_rst_patch_24_non_enum_status_string_returns_500` |
| API-RST-PATCH-25 | `status: "Paid"` (wrong case) | 500, same message | 500, confirmed — no case normalization | PASS | `...::test_api_rst_patch_25_wrong_case_status_returns_500` |
| API-RST-PATCH-26 | `status: 123` (non-string type) | 500, same message | 500, confirmed | PASS | `...::test_api_rst_patch_26_non_string_status_type_returns_500` |
| API-RST-PATCH-27 | DB persistence — independent re-fetch, not trusting the response | stored `status` matches the PATCH | confirmed via direct repository re-read | PASS | `...::test_api_rst_patch_27_db_persistence_verified_via_independent_refetch` |
| API-RST-PATCH-28 | `totalAmount` untouched by this endpoint | unchanged after PATCH | confirmed unchanged (4321 before and after) | PASS | `...::test_api_rst_patch_28_total_amount_untouched_by_this_endpoint` |
| API-RST-PATCH-29 | Only the targeted order is modified | sibling order unaffected | confirmed — target changed, sibling unchanged | PASS | `...::test_api_rst_patch_29_only_targeted_order_is_modified` |
| API-RST-PATCH-30 | Concurrent-delete race condition | *(documented coverage limit, not implemented)* | **SKIPPED** — not silently dropped; skip reason references the mocked-equivalent unit test `UT-RST-PATCH-11` | SKIP (intentional) | `...::test_api_rst_patch_30_concurrent_delete_race_condition` |

---

## 5. Deviations From the Written Plan (disclosed, not hidden)

1. **API-RST-GET-14** was adapted. The plan's abstract description ("orphaned restaurant/user ref") doesn't map cleanly onto this endpoint: the order's `restaurant` ref is load-bearing for `list_by_restaurant`'s own query, so it cannot be orphaned without the order simply never appearing. The implemented test instead orphans the `user` ref only (a realistic, reachable variant for this specific endpoint) and confirms `restaurant` still populates correctly while `user` resolves to `null`.
2. **API-RST-PATCH-18** was not written as a separate test. It is the "positive control" — a restatement that a legitimate owner is NOT rejected — which is exactly what API-RST-PATCH-01 already asserts (200 on a matching-owner PATCH). Writing a byte-identical second test under a different ID would not have added coverage.
3. **API-RST-PATCH-30** (true concurrent-request race) is implemented as an explicit `pytest.mark.skip`, not silently omitted. This matches the approved plan's own §6.9, which flagged this as a documented coverage limit — a genuine race is not reproducible via a single-threaded `TestClient` call without a threading harness, which was judged out of scope. The *handling* of a failed write (repository returns `False`) is already covered by the mocked unit test `UT-RST-PATCH-11`.

---

## 6. Safety Notes

This project's `.env` file contains a **live MongoDB Atlas connection string with real credentials**, and `app/main.py`'s lifespan handler attempts to connect to it whenever `TestClient(app)` enters its context, if `settings.mongodb_uri` is truthy (it is). This was identified during test design as a real risk: running integration tests naively could attempt a live network connection to a credentialed external database.

**Mitigation implemented:** the new `api_client` fixture (`tests/conftest.py`) monkeypatches `mongodb.connect` to a no-op (`AsyncMock()`) for the duration of every test that uses it, then explicitly swaps `mongodb.database` to a fresh in-memory `mongomock-motor` database. No real network call to the Atlas cluster was made by any test in this session — confirmed indirectly by execution speed (56 API/integration tests complete in 1.95s; a single real connection attempt alone is configured with a 3-second timeout in `mongodb.py`, so even one real attempt would have been directly observable as a multi-second stall).

**Pre-existing, unrelated observation (not modified, flagged only):** the existing `client` fixture (used by `tests/test_health.py`, unmodified by this task) does *not* apply this same mitigation — it sets `mongodb.database` to a placeholder *before* entering `TestClient`'s context, but `main.py`'s lifespan can still overwrite that with a real (unconfirmed-reachable) Atlas database handle during startup, since `mongodb.connect()` isn't patched there. This has not caused any observed failure (those tests only exercise 501-stub routes and pure health checks that never touch `mongodb.database`), but it is a latent risk worth the project owner's attention if that fixture is ever reused for a DB-backed route. Not fixed here — outside this task's scope (`tests/test_health.py` and its fixture were not touched) — flagged for awareness only.

**Also confirmed, unrelated to correctness:** `PyJWT`'s `InsecureKeyLengthWarning` fires on every token signed/verified during this run — the project's actual `.env` `JWT_SECRET_KEY` is 31 bytes, one byte below PyJWT's recommended HMAC-SHA256 minimum. This is a pre-existing production configuration characteristic, surfaced naturally by using the app's real secret rather than a test-only stand-in; not a test defect, not fixed here.

---

## 7. Coverage

**Not available**, for the same reason as the prior unit-test report: `pytest-cov` is not installed in this project's environment and is not listed in `requirements.txt`. Not installed as part of this task, consistent with not adding dependencies beyond what was authorized.

---

## 8. Business Behavior, Database, and Auth/Authz Verified (summary against the task's explicit checklist)

| Requirement | How verified | Result |
|---|---|---|
| HTTP status | Every scenario asserts an exact `response.status_code` | All correct — see §4 |
| Response structure | Exact-match `response.json() == {...}` (not partial/`in` checks) for every message-bearing response; empty-body checks via `response.content == b""` for the C2 ownership-failure path; explicit type/shape checks distinguishing populated vs. raw-ref bodies | All correct — see §4, esp. API-RST-PATCH-01, -06/-07/-08, -20 |
| Business behavior | No-op status filters (both GET endpoints), lifecycle non-enforcement (all 5 PATCH transition variants), no-restaurant-→-empty-array rule, case-sensitive enum matching | All confirmed live, matching the service-layer unit tests but now proven through the real HTTP path |
| Database changes | API-RST-PATCH-27/28/29 re-fetch via a **fresh repository read**, independent of the PATCH response body, to confirm writes actually persisted (or didn't, for the rejected-ownership case in -15) | Confirmed — writes land correctly, and rejected requests leave no trace |
| Authentication/authorization behavior | All 6 `AUTH-01…06` failure modes executed per route (18 individual executions across 3 route groups) plus the cookie-fallback success path (×2); the C2 ownership-check fix verified live end-to-end (both the reject path -15/-16/-17 and the accept path -01/-18) | Confirmed — matches the unit-level findings, now proven through real JWT verification and a real (in-memory) database |
| Error handling | All 3 distinct 4xx/5xx body shapes in this module (`{"message":...}`, `{"errors":[...]}`, empty body) individually asserted per triggering condition, never conflated | Confirmed distinct in every case — see §4.3 rows -06/-07 vs. -08 vs. -20 |

No fake or trivially-true assertions were used (e.g., no bare `assert response.status_code in (200, 401)`-style catch-alls) — every assertion pins an exact status code and exact body content, matching the "do not weaken assertions" instruction.
