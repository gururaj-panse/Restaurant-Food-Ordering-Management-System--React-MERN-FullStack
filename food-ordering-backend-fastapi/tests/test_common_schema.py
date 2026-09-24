"""
Unit tests for mongo_to_jsonable() (app/schemas/common.py) — flagged as
untested in docs/testing/qa-readiness-notes.md §4. Pure function, no
mocking required. Test design and rationale: docs/testing/unit-test-plan.md §7.
"""

from datetime import datetime, timezone

from bson import ObjectId

from app.schemas.common import mongo_to_jsonable


def test_ut_common_01_bare_objectid_converts_to_string():
    oid = ObjectId()
    assert mongo_to_jsonable(oid) == str(oid)


def test_ut_common_02_dict_with_objectid_values_converts_selectively():
    oid1, oid2 = ObjectId(), ObjectId()
    value = {"_id": oid1, "restaurant": oid2, "status": "placed"}

    result = mongo_to_jsonable(value)

    assert result == {"_id": str(oid1), "restaurant": str(oid2), "status": "placed"}


def test_ut_common_03_list_of_dicts_each_converted_independently():
    oid1, oid2 = ObjectId(), ObjectId()
    value = [{"_id": oid1}, {"_id": oid2}]

    result = mongo_to_jsonable(value)

    assert result == [{"_id": str(oid1)}, {"_id": str(oid2)}]


def test_ut_common_04_deeply_nested_structure_recursed_fully():
    oid = ObjectId()
    value = {"restaurant": {"menuItems": [{"_id": oid, "name": "Spaghetti"}]}}

    result = mongo_to_jsonable(value)

    assert result == {"restaurant": {"menuItems": [{"_id": str(oid), "name": "Spaghetti"}]}}


def test_ut_common_05_non_convertible_types_pass_through_unchanged_including_datetime():
    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    value = {"name": "Jane", "quantity": 2, "active": True, "note": None, "createdAt": now}

    result = mongo_to_jsonable(value)

    assert result["name"] == "Jane"
    assert result["quantity"] == 2
    assert result["active"] is True
    assert result["note"] is None
    assert result["createdAt"] is now  # left as-is, per the function's own docstring claim


def test_ut_common_06_empty_dict_and_empty_list_pass_through():
    assert mongo_to_jsonable({}) == {}
    assert mongo_to_jsonable([]) == []
