# Unit Test Execution Results — Order Management & Order Lifecycle Module

**Date executed:** 2026-09-22
**Executed by:** automated run in this session (no results fabricated or estimated — output below is copied directly from the actual pytest run)
**Scope:** implementation of `docs/testing/unit-test-plan.md` (45 planned test IDs) for the Phase 3 FastAPI Order Management module.

---

## 1. Exact Command

Run from `food-ordering-backend-fastapi/`, using the project's existing virtual environment (the one referenced by `requirements.txt`; no new packages were installed):

```
./venv/Scripts/python.exe -m pytest -v
```

**Environment:**
- Python 3.14.2
- pytest 9.1.1
- pytest-asyncio 1.4.0 (mode: `Mode.STRICT` — matches existing `pytest.ini`/test convention; all async tests use explicit `@pytest.mark.asyncio`)
- plugins: `anyio-4.15.1`, `asyncio-1.4.0`
- rootdir: `food-ordering-backend-fastapi/`
- `testpaths = tests` (from `pytest.ini`, unchanged)

---

## 2. Result Summary

```
collected 64 items
================== 63 passed, 1 xfailed, 2 warnings in 4.08s ==================
```

| Metric | Count |
|---|---|
| Total collected | 64 |
| Passed | 63 |
| Failed | 0 |
| Skipped | 0 |
| XFailed (expected failure, pre-existing) | 1 |
| Errors | 0 |

**No failures occurred.** All newly implemented tests, and all pre-existing tests, pass. The one `xfail` (`test_restaurant_search_cuisine_filter_is_and_not_or`) is a pre-existing, documented `mongomock` tooling limitation from Phase 3 (unrelated to this work — see its `xfail(reason=..., strict=True)` in `tests/test_repositories.py`), not a new finding from this test-implementation pass.

---

## 3. New Test Files Added

| File | Test IDs implemented | Count |
|---|---|---|
| `tests/test_order_service.py` | UT-ORD-GET-01…08, UT-POP-01…07 | 15 |
| `tests/test_restaurant_order_lifecycle.py` | UT-RST-GET-01…06, UT-RST-PATCH-01…15 | 21 test defs (UT-RST-PATCH-10 is `@pytest.mark.parametrize`d over 2 cases → 22 collected items) |
| `tests/test_common_schema.py` | UT-COMMON-01…06 | 6 |
| `tests/test_errors.py` | UT-ERR-01 | 1 |
| `tests/test_repositories.py` (appended, existing file) | UT-REPO-01, UT-REPO-02 | 2 |

**Total new test IDs implemented: 45 (matches `docs/testing/unit-test-plan.md` exactly). Total new pytest items collected: 46** (one extra item from `UT-RST-PATCH-10`'s two parametrized cases, `cancelled` and `Paid`).

No existing test was modified, weakened, or deleted. `tests/test_repositories.py` was extended only by appending two new test functions after the existing final test; all prior tests in that file are byte-for-byte unchanged.

---

## 4. Full Verbose Output

```
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-9.1.1, pluggy-1.6.0 -- .../food-ordering-backend-fastapi/venv/Scripts/python.exe
cachedir: .pytest_cache
rootdir: .../food-ordering-backend-fastapi
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 64 items

tests/test_common_schema.py::test_ut_common_01_bare_objectid_converts_to_string PASSED [  1%]
tests/test_common_schema.py::test_ut_common_02_dict_with_objectid_values_converts_selectively PASSED [  3%]
tests/test_common_schema.py::test_ut_common_03_list_of_dicts_each_converted_independently PASSED [  4%]
tests/test_common_schema.py::test_ut_common_04_deeply_nested_structure_recursed_fully PASSED [  6%]
tests/test_common_schema.py::test_ut_common_05_non_convertible_types_pass_through_unchanged_including_datetime PASSED [  7%]
tests/test_common_schema.py::test_ut_common_06_empty_dict_and_empty_list_pass_through PASSED [  9%]
tests/test_errors.py::test_ut_err_01_order_ownership_error_is_an_empty_body_app_error_with_401 PASSED [ 10%]
tests/test_health.py::test_root PASSED                                   [ 12%]
tests/test_health.py::test_health PASSED                                 [ 14%]
tests/test_health.py::test_api_health PASSED                             [ 15%]
tests/test_health.py::test_stub_routes_return_501 PASSED                 [ 17%]
tests/test_order_service.py::test_ut_ord_get_01_happy_path_multiple_orders_populated PASSED [ 18%]
tests/test_order_service.py::test_ut_ord_get_02_empty_result_returns_empty_list PASSED [ 20%]
tests/test_order_service.py::test_ut_ord_get_03_list_by_user_called_with_correct_user_id PASSED [ 21%]
tests/test_order_service.py::test_ut_ord_get_04_objectids_converted_recursively_in_nested_structures PASSED [ 23%]
tests/test_order_service.py::test_ut_ord_get_05_regression_password_hash_preserved_in_populated_user PASSED [ 25%]
tests/test_order_service.py::test_ut_ord_get_06_per_order_independent_population_not_reused PASSED [ 26%]
tests/test_order_service.py::test_ut_ord_get_07_mixed_batch_missing_ref_does_not_break_siblings PASSED [ 28%]
tests/test_order_service.py::test_ut_ord_get_08_service_applies_no_additional_filtering PASSED [ 29%]
tests/test_order_service.py::test_ut_pop_01_input_dict_is_not_mutated PASSED [ 31%]
tests/test_order_service.py::test_ut_pop_02_missing_restaurant_ref_skips_lookup PASSED [ 32%]
tests/test_order_service.py::test_ut_pop_03_orphaned_restaurant_ref_resolves_to_none_without_error PASSED [ 34%]
tests/test_order_service.py::test_ut_pop_04_restaurant_ref_as_objectid_is_stringified_before_lookup PASSED [ 35%]
tests/test_order_service.py::test_ut_pop_05_missing_user_ref_skips_lookup PASSED [ 37%]
tests/test_order_service.py::test_ut_pop_06_orphaned_user_ref_resolves_to_none_without_error PASSED [ 39%]
tests/test_order_service.py::test_ut_pop_07_user_ref_as_objectid_is_stringified_before_lookup PASSED [ 40%]
tests/test_repositories.py::test_user_create_hashes_password_and_is_retrievable PASSED [ 42%]
tests/test_repositories.py::test_user_get_by_email PASSED                [ 43%]
tests/test_repositories.py::test_user_email_unique_index_is_enforced PASSED [ 45%]
tests/test_repositories.py::test_user_update_profile PASSED              [ 46%]
tests/test_repositories.py::test_restaurant_create_generates_menu_item_ids PASSED [ 48%]
tests/test_repositories.py::test_restaurant_get_by_owner_and_distinct_cities PASSED [ 50%]
tests/test_repositories.py::test_restaurant_search_cuisine_filter_is_and_not_or XFAIL [ 51%]
tests/test_repositories.py::test_restaurant_search_city_all_skips_filter PASSED [ 53%]
tests/test_repositories.py::test_restaurant_search_pagination_page_size_is_fixed_ten PASSED [ 54%]
tests/test_repositories.py::test_order_create_generates_cart_item_ids PASSED [ 56%]
tests/test_repositories.py::test_order_list_by_user_status_filter_is_a_confirmed_noop PASSED [ 57%]
tests/test_repositories.py::test_order_list_by_restaurant_includes_unpaid_placed_orders PASSED [ 59%]
tests/test_repositories.py::test_order_update_status_sets_status_and_total_amount PASSED [ 60%]
tests/test_repositories.py::test_order_update_status_without_total_amount_leaves_it_untouched PASSED [ 62%]
tests/test_repositories.py::test_ut_repo_01_order_update_status_on_nonexistent_id_returns_false PASSED [ 64%]
tests/test_repositories.py::test_ut_repo_02_order_get_by_id_with_invalid_objectid_returns_none PASSED [ 65%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_get_01_no_restaurant_returns_empty_list_without_querying_orders PASSED [ 67%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_get_02_restaurant_owned_returns_populated_orders PASSED [ 68%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_get_03_restaurant_owned_with_no_orders_returns_empty_list_after_query PASSED [ 70%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_get_04_list_by_restaurant_called_with_stringified_restaurant_id PASSED [ 71%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_get_05_regression_no_status_filter_includes_unpaid_placed_orders PASSED [ 73%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_get_06_regression_password_hash_preserved_in_populated_user PASSED [ 75%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_01_malformed_order_id_raises_400_before_any_db_call PASSED [ 76%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_02_empty_order_id_raises_400 PASSED [ 78%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_03_order_not_found_raises_404 PASSED [ 79%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_04_legitimate_owner_passes_ownership_check PASSED [ 81%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_05_mismatched_owner_raises_ownership_error PASSED [ 82%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_06_orphaned_restaurant_ref_raises_401_not_404_or_500 PASSED [ 84%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_07_restaurant_with_no_owner_assigned_raises_401 PASSED [ 85%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_08_success_updates_status_and_returns_updated_order PASSED [ 87%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_09_missing_status_raises_500 PASSED [ 89%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_10_non_enum_status_raises_500[cancelled] PASSED [ 90%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_10_non_enum_status_raises_500[Paid] PASSED [ 92%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_11_repository_update_failure_raises_500 PASSED [ 93%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_12_regression_backward_transition_accepted_no_lifecycle_enforcement PASSED [ 95%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_13_regression_unchanged_status_resubmission_accepted PASSED [ 96%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_14_update_status_called_without_total_amount PASSED [ 98%]
tests/test_restaurant_order_lifecycle.py::test_ut_rst_patch_15_restaurant_ref_as_objectid_resolves_ownership_correctly PASSED [100%]

============================== warnings summary ===============================
venv\Lib\site-packages\fastapi\testclient.py:1
  ...: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

venv\Lib\site-packages\starlette\testclient.py:53
  ...: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================== 63 passed, 1 xfailed, 2 warnings in 4.08s ==================
```

Both warnings are pre-existing (present in the Phase 3 baseline run before this work started — see §6) and originate from third-party library code (`starlette`/`fastapi`), not from any test added in this pass.

---

## 5. Coverage

**Not available.** `pytest-cov` is not listed in `requirements.txt` and is not installed in the project's virtual environment:

```
$ ./venv/Scripts/python.exe -c "import pytest_cov"
ModuleNotFoundError: No module named 'pytest_cov'
```

No coverage report was generated. Installing `pytest-cov` was not performed, since it would add a new dependency beyond what this task authorized (implement and run the approved test plan). If a coverage report is required, that is a separate, explicit follow-up (add `pytest-cov` to `requirements.txt` and run `pytest --cov=app.services --cov-report=html`, as anticipated in `docs/testing/test-plan.md` §16).

---

## 6. Baseline Comparison (pre-existing tests, unaffected)

The pre-existing suite was run once before any new test file was added, to confirm environment correctness and establish a baseline:

```
================== 17 passed, 1 xfailed, 2 warnings in 3.86s ==================
```

After adding the 45 new test IDs (46 collected items), the same 17 pre-existing tests and the same 1 `xfail` still pass/xfail identically — confirming no pre-existing test was broken, weakened, or altered by this work.

---

## 7. Failures

**None.** No defect analysis is required from this run — every test passed on the first execution against the current, unmodified production code. No production code was changed to make any test pass.

---

## 8. Traceability

Every test file references `docs/testing/unit-test-plan.md` in its module docstring, and every test function name embeds its plan test ID (e.g., `test_ut_rst_patch_05_...` implements `UT-RST-PATCH-05`), so each of the 45 planned tests can be traced 1:1 to its design entry in the plan (test ID, source function, behavior, expected result, fixture/mock, test data, reason).
