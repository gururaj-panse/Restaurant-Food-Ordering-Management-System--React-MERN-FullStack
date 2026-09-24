"""
Unit tests for OrderService.get_my_orders and the shared populate_order()
helper (Jira RFOMS-11/12/13, Order Management & Order Lifecycle module).

Mocks the repository layer directly with unittest.mock.AsyncMock(spec=...)
— no mongomock-motor, no real DB, no network access. Test design and
rationale for each case: docs/testing/unit-test-plan.md §3-4.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository
from app.services.order_service import OrderService, populate_order


def _order_repo() -> AsyncMock:
    return AsyncMock(spec=OrderRepository)


def _restaurant_repo() -> AsyncMock:
    return AsyncMock(spec=RestaurantRepository)


def _user_repo() -> AsyncMock:
    return AsyncMock(spec=UserRepository)


def _make_service(order_repo=None, restaurant_repo=None, user_repo=None) -> OrderService:
    return OrderService(
        order_repository=order_repo or _order_repo(),
        restaurant_repository=restaurant_repo or _restaurant_repo(),
        user_repository=user_repo or _user_repo(),
        stripe_client=AsyncMock(),
        frontend_url="http://localhost:5173",
    )


def _sample_user(**overrides):
    doc = {
        "_id": ObjectId(),
        "email": "jane@example.com",
        "password": "$2b$08$abcdefghijklmnopqrstuv",  # bcrypt-shaped, never a real secret
        "name": "Jane",
    }
    doc.update(overrides)
    return doc


def _sample_restaurant(**overrides):
    doc = {
        "_id": ObjectId(),
        "user": "owner-1",
        "restaurantName": "Pasta Place",
        "menuItems": [{"_id": ObjectId(), "name": "Spaghetti", "price": 990}],
    }
    doc.update(overrides)
    return doc


def _sample_order(**overrides):
    doc = {
        "_id": ObjectId(),
        "restaurant": ObjectId(),
        "user": "owner-1",
        "status": "placed",
        "cartItems": [{"_id": ObjectId(), "menuItemId": "abc", "name": "Spaghetti", "quantity": 2}],
        "createdAt": datetime.now(timezone.utc),
    }
    doc.update(overrides)
    return doc


# --------------------------------------------- OrderService.get_my_orders ----


@pytest.mark.asyncio
async def test_ut_ord_get_01_happy_path_multiple_orders_populated():
    restaurant1, restaurant2 = _sample_restaurant(), _sample_restaurant()
    user1, user2 = _sample_user(), _sample_user()
    order1 = _sample_order(restaurant=restaurant1["_id"], user=str(user1["_id"]))
    order2 = _sample_order(restaurant=restaurant2["_id"], user=str(user2["_id"]))

    order_repo = _order_repo()
    order_repo.list_by_user.return_value = [order1, order2]
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.side_effect = lambda rid: (
        restaurant1 if rid == str(restaurant1["_id"]) else restaurant2
    )
    user_repo = _user_repo()
    user_repo.get_by_id.side_effect = lambda uid: user1 if uid == str(user1["_id"]) else user2

    service = _make_service(order_repo, restaurant_repo, user_repo)
    result = await service.get_my_orders(user_id="user-1")

    assert len(result) == 2
    assert result[0]["restaurant"]["restaurantName"] == "Pasta Place"
    assert result[0]["user"]["email"] == "jane@example.com"
    assert result[1]["restaurant"]["_id"] == str(restaurant2["_id"])


@pytest.mark.asyncio
async def test_ut_ord_get_02_empty_result_returns_empty_list():
    order_repo = _order_repo()
    order_repo.list_by_user.return_value = []

    service = _make_service(order_repo=order_repo)
    result = await service.get_my_orders(user_id="user-1")

    assert result == []


@pytest.mark.asyncio
async def test_ut_ord_get_03_list_by_user_called_with_correct_user_id():
    order_repo = _order_repo()
    order_repo.list_by_user.return_value = []

    service = _make_service(order_repo=order_repo)
    await service.get_my_orders(user_id="user-42")

    order_repo.list_by_user.assert_awaited_once_with("user-42")


@pytest.mark.asyncio
async def test_ut_ord_get_04_objectids_converted_recursively_in_nested_structures():
    restaurant = _sample_restaurant()
    user = _sample_user()
    order = _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]))

    order_repo = _order_repo()
    order_repo.list_by_user.return_value = [order]
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = user

    service = _make_service(order_repo, restaurant_repo, user_repo)
    result = await service.get_my_orders(user_id="user-1")

    populated = result[0]
    assert isinstance(populated["_id"], str)
    assert isinstance(populated["restaurant"]["_id"], str)
    assert isinstance(populated["restaurant"]["menuItems"][0]["_id"], str)
    assert isinstance(populated["user"]["_id"], str)
    assert isinstance(populated["cartItems"][0]["_id"], str)


@pytest.mark.asyncio
async def test_ut_ord_get_05_regression_password_hash_preserved_in_populated_user():
    user = _sample_user(password="$2b$08$fixedhashvalueforregressiontest")
    restaurant = _sample_restaurant()
    order = _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]))

    order_repo = _order_repo()
    order_repo.list_by_user.return_value = [order]
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = user

    service = _make_service(order_repo, restaurant_repo, user_repo)
    result = await service.get_my_orders(user_id="user-1")

    assert result[0]["user"]["password"] == "$2b$08$fixedhashvalueforregressiontest"


@pytest.mark.asyncio
async def test_ut_ord_get_06_per_order_independent_population_not_reused():
    restaurant_a = _sample_restaurant(restaurantName="A")
    restaurant_b = _sample_restaurant(restaurantName="B")
    user_a = _sample_user(email="a@example.com")
    user_b = _sample_user(email="b@example.com")
    order_a = _sample_order(restaurant=restaurant_a["_id"], user=str(user_a["_id"]))
    order_b = _sample_order(restaurant=restaurant_b["_id"], user=str(user_b["_id"]))

    order_repo = _order_repo()
    order_repo.list_by_user.return_value = [order_a, order_b]
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.side_effect = [restaurant_a, restaurant_b]
    user_repo = _user_repo()
    user_repo.get_by_id.side_effect = [user_a, user_b]

    service = _make_service(order_repo, restaurant_repo, user_repo)
    result = await service.get_my_orders(user_id="user-1")

    assert result[0]["restaurant"]["restaurantName"] == "A"
    assert result[0]["user"]["email"] == "a@example.com"
    assert result[1]["restaurant"]["restaurantName"] == "B"
    assert result[1]["user"]["email"] == "b@example.com"


@pytest.mark.asyncio
async def test_ut_ord_get_07_mixed_batch_missing_ref_does_not_break_siblings():
    restaurant = _sample_restaurant()
    user = _sample_user()
    order_with_user = _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]))
    order_without_user = _sample_order(restaurant=restaurant["_id"], user=None)

    order_repo = _order_repo()
    order_repo.list_by_user.return_value = [order_with_user, order_without_user]
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = user

    service = _make_service(order_repo, restaurant_repo, user_repo)
    result = await service.get_my_orders(user_id="user-1")

    assert result[0]["user"]["email"] == "jane@example.com"
    assert result[1]["user"] is None
    assert user_repo.get_by_id.await_count == 1  # only invoked for the order that has a ref


@pytest.mark.asyncio
async def test_ut_ord_get_08_service_applies_no_additional_filtering():
    restaurant = _sample_restaurant()
    user = _sample_user()
    orders = [
        _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]), status=status)
        for status in ("placed", "paid", "delivered")
    ]

    order_repo = _order_repo()
    order_repo.list_by_user.return_value = orders
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = user

    service = _make_service(order_repo, restaurant_repo, user_repo)
    result = await service.get_my_orders(user_id="user-1")

    assert len(result) == 3
    assert {o["status"] for o in result} == {"placed", "paid", "delivered"}


# ------------------------------------------------------------ populate_order ----


@pytest.mark.asyncio
async def test_ut_pop_01_input_dict_is_not_mutated():
    original = {"restaurant": "r1", "user": "u1", "status": "placed"}
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = {"_id": "r1"}
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = {"_id": "u1"}

    await populate_order(original, restaurant_repo, user_repo)

    assert original["restaurant"] == "r1"
    assert original["user"] == "u1"


@pytest.mark.asyncio
async def test_ut_pop_02_missing_restaurant_ref_skips_lookup():
    restaurant_repo = _restaurant_repo()
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = {"_id": "u1"}

    result = await populate_order({"restaurant": None, "user": "u1"}, restaurant_repo, user_repo)

    restaurant_repo.get_by_id.assert_not_awaited()
    assert result["restaurant"] is None


@pytest.mark.asyncio
async def test_ut_pop_03_orphaned_restaurant_ref_resolves_to_none_without_error():
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = None
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = None

    result = await populate_order(
        {"restaurant": "deleted-id", "user": None}, restaurant_repo, user_repo
    )

    assert result["restaurant"] is None


@pytest.mark.asyncio
async def test_ut_pop_04_restaurant_ref_as_objectid_is_stringified_before_lookup():
    restaurant_id = ObjectId()
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = {"_id": restaurant_id}
    user_repo = _user_repo()

    await populate_order({"restaurant": restaurant_id, "user": None}, restaurant_repo, user_repo)

    restaurant_repo.get_by_id.assert_awaited_once_with(str(restaurant_id))


@pytest.mark.asyncio
async def test_ut_pop_05_missing_user_ref_skips_lookup():
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = {"_id": "r1"}
    user_repo = _user_repo()

    result = await populate_order({"restaurant": "r1", "user": None}, restaurant_repo, user_repo)

    user_repo.get_by_id.assert_not_awaited()
    assert result["user"] is None


@pytest.mark.asyncio
async def test_ut_pop_06_orphaned_user_ref_resolves_to_none_without_error():
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = None
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = None

    result = await populate_order(
        {"restaurant": None, "user": "deleted-user-id"}, restaurant_repo, user_repo
    )

    assert result["user"] is None


@pytest.mark.asyncio
async def test_ut_pop_07_user_ref_as_objectid_is_stringified_before_lookup():
    user_id = ObjectId()
    restaurant_repo = _restaurant_repo()
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = {"_id": user_id}

    await populate_order({"restaurant": None, "user": user_id}, restaurant_repo, user_repo)

    user_repo.get_by_id.assert_awaited_once_with(str(user_id))
