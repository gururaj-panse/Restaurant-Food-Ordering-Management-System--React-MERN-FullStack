"""
Unit tests for RestaurantService.get_my_restaurant_orders and
update_order_status (Jira RFOMS-11/12/13, Order Management & Order
Lifecycle module).

update_order_status is the highest-priority target in this module: it is
the sole location of the deliberate, flagged fix to Node's ownership-check
bug (finding C2, docs/module-3-code-review.md). Test design and rationale
for each case: docs/testing/unit-test-plan.md §5-6.
"""

from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.core.errors import AppError, EmptyBodyAppError
from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository
from app.services.restaurant_service import OrderOwnershipError, RestaurantService


def _order_repo() -> AsyncMock:
    return AsyncMock(spec=OrderRepository)


def _restaurant_repo() -> AsyncMock:
    return AsyncMock(spec=RestaurantRepository)


def _user_repo() -> AsyncMock:
    return AsyncMock(spec=UserRepository)


def _make_service(restaurant_repo=None, order_repo=None, user_repo=None) -> RestaurantService:
    return RestaurantService(
        restaurant_repository=restaurant_repo or _restaurant_repo(),
        order_repository=order_repo or _order_repo(),
        user_repository=user_repo or _user_repo(),
    )


def _sample_restaurant(**overrides):
    doc = {"_id": ObjectId(), "user": "owner-1", "restaurantName": "Pasta Place"}
    doc.update(overrides)
    return doc


def _sample_user(**overrides):
    doc = {"_id": ObjectId(), "email": "jane@example.com", "password": "$2b$08$hash", "name": "Jane"}
    doc.update(overrides)
    return doc


def _sample_order(**overrides):
    doc = {"_id": ObjectId(), "restaurant": ObjectId(), "user": "owner-1", "status": "placed"}
    doc.update(overrides)
    return doc


# --------------------------------- RestaurantService.get_my_restaurant_orders ----


@pytest.mark.asyncio
async def test_ut_rst_get_01_no_restaurant_returns_empty_list_without_querying_orders():
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_owner.return_value = None
    order_repo = _order_repo()

    service = _make_service(restaurant_repo=restaurant_repo, order_repo=order_repo)
    result = await service.get_my_restaurant_orders(user_id="no-restaurant-user")

    assert result == []
    order_repo.list_by_restaurant.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut_rst_get_02_restaurant_owned_returns_populated_orders():
    restaurant = _sample_restaurant()
    user = _sample_user()
    order1 = _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]))
    order2 = _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]))

    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_owner.return_value = restaurant
    restaurant_repo.get_by_id.return_value = restaurant
    order_repo = _order_repo()
    order_repo.list_by_restaurant.return_value = [order1, order2]
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = user

    service = _make_service(restaurant_repo, order_repo, user_repo)
    result = await service.get_my_restaurant_orders(user_id="owner-1")

    assert len(result) == 2
    assert result[0]["restaurant"]["restaurantName"] == "Pasta Place"
    assert result[0]["user"]["email"] == "jane@example.com"


@pytest.mark.asyncio
async def test_ut_rst_get_03_restaurant_owned_with_no_orders_returns_empty_list_after_query():
    restaurant = _sample_restaurant()
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_owner.return_value = restaurant
    order_repo = _order_repo()
    order_repo.list_by_restaurant.return_value = []

    service = _make_service(restaurant_repo, order_repo)
    result = await service.get_my_restaurant_orders(user_id="owner-1")

    assert result == []
    order_repo.list_by_restaurant.assert_awaited_once()


@pytest.mark.asyncio
async def test_ut_rst_get_04_list_by_restaurant_called_with_stringified_restaurant_id():
    restaurant = _sample_restaurant()
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_owner.return_value = restaurant
    order_repo = _order_repo()
    order_repo.list_by_restaurant.return_value = []

    service = _make_service(restaurant_repo, order_repo)
    await service.get_my_restaurant_orders(user_id="owner-1")

    order_repo.list_by_restaurant.assert_awaited_once_with(str(restaurant["_id"]))


@pytest.mark.asyncio
async def test_ut_rst_get_05_regression_no_status_filter_includes_unpaid_placed_orders():
    restaurant = _sample_restaurant()
    user = _sample_user()
    orders = [
        _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]), status=status)
        for status in ("placed", "paid", "delivered")
    ]

    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_owner.return_value = restaurant
    restaurant_repo.get_by_id.return_value = restaurant
    order_repo = _order_repo()
    order_repo.list_by_restaurant.return_value = orders
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = user

    service = _make_service(restaurant_repo, order_repo, user_repo)
    result = await service.get_my_restaurant_orders(user_id="owner-1")

    statuses = {o["status"] for o in result}
    assert "placed" in statuses
    assert statuses == {"placed", "paid", "delivered"}


@pytest.mark.asyncio
async def test_ut_rst_get_06_regression_password_hash_preserved_in_populated_user():
    restaurant = _sample_restaurant()
    user = _sample_user(password="$2b$08$fixedhashvalueforregressiontest")
    order = _sample_order(restaurant=restaurant["_id"], user=str(user["_id"]))

    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_owner.return_value = restaurant
    restaurant_repo.get_by_id.return_value = restaurant
    order_repo = _order_repo()
    order_repo.list_by_restaurant.return_value = [order]
    user_repo = _user_repo()
    user_repo.get_by_id.return_value = user

    service = _make_service(restaurant_repo, order_repo, user_repo)
    result = await service.get_my_restaurant_orders(user_id="owner-1")

    assert result[0]["user"]["password"] == "$2b$08$fixedhashvalueforregressiontest"


# ---------------------------------------- RestaurantService.update_order_status ----


@pytest.mark.asyncio
async def test_ut_rst_patch_01_malformed_order_id_raises_400_before_any_db_call():
    order_repo = _order_repo()
    service = _make_service(order_repo=order_repo)

    with pytest.raises(AppError) as exc_info:
        await service.update_order_status(user_id="owner-1", order_id="not-a-valid-id", status="paid")

    assert exc_info.value.status_code == 400
    assert exc_info.value.message == "Invalid order ID format"
    order_repo.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut_rst_patch_02_empty_order_id_raises_400():
    order_repo = _order_repo()
    service = _make_service(order_repo=order_repo)

    with pytest.raises(AppError) as exc_info:
        await service.update_order_status(user_id="owner-1", order_id="", status="paid")

    assert exc_info.value.status_code == 400
    order_repo.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut_rst_patch_03_order_not_found_raises_404():
    order_repo = _order_repo()
    order_repo.get_by_id.return_value = None
    service = _make_service(order_repo=order_repo)

    valid_id = str(ObjectId())
    with pytest.raises(AppError) as exc_info:
        await service.update_order_status(user_id="owner-1", order_id=valid_id, status="paid")

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "order not found"


@pytest.mark.asyncio
async def test_ut_rst_patch_04_legitimate_owner_passes_ownership_check():
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"])
    updated_order = dict(order, status="paid")

    order_repo = _order_repo()
    order_repo.get_by_id.side_effect = [order, updated_order]
    order_repo.update_status.return_value = True
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)
    result = await service.update_order_status(
        user_id="owner-1", order_id=str(order["_id"]), status="paid"
    )

    assert result["status"] == "paid"
    order_repo.update_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_ut_rst_patch_05_mismatched_owner_raises_ownership_error():
    restaurant = _sample_restaurant(user="owner-2")
    order = _sample_order(restaurant=restaurant["_id"])

    order_repo = _order_repo()
    order_repo.get_by_id.return_value = order
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)

    with pytest.raises(OrderOwnershipError) as exc_info:
        await service.update_order_status(
            user_id="owner-1", order_id=str(order["_id"]), status="paid"
        )

    assert exc_info.value.status_code == 401
    assert isinstance(exc_info.value, EmptyBodyAppError)
    order_repo.update_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut_rst_patch_06_orphaned_restaurant_ref_raises_401_not_404_or_500():
    order = _sample_order()

    order_repo = _order_repo()
    order_repo.get_by_id.return_value = order
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = None  # restaurant deleted / orphaned ref

    service = _make_service(restaurant_repo, order_repo)

    with pytest.raises(OrderOwnershipError) as exc_info:
        await service.update_order_status(
            user_id="owner-1", order_id=str(order["_id"]), status="paid"
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_ut_rst_patch_07_restaurant_with_no_owner_assigned_raises_401():
    restaurant = _sample_restaurant()
    del restaurant["user"]
    order = _sample_order(restaurant=restaurant["_id"])

    order_repo = _order_repo()
    order_repo.get_by_id.return_value = order
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)

    with pytest.raises(OrderOwnershipError):
        await service.update_order_status(
            user_id="owner-1", order_id=str(order["_id"]), status="paid"
        )


@pytest.mark.asyncio
async def test_ut_rst_patch_08_success_updates_status_and_returns_updated_order():
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"], status="placed")
    updated_order = dict(order, status="inProgress")

    order_repo = _order_repo()
    order_repo.get_by_id.side_effect = [order, updated_order]
    order_repo.update_status.return_value = True
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)
    result = await service.update_order_status(
        user_id="owner-1", order_id=str(order["_id"]), status="inProgress"
    )

    order_repo.update_status.assert_awaited_once_with(str(order["_id"]), status="inProgress")
    assert result["status"] == "inProgress"
    assert isinstance(result["_id"], str)  # mongo_to_jsonable applied


@pytest.mark.asyncio
async def test_ut_rst_patch_09_missing_status_raises_500():
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"])

    order_repo = _order_repo()
    order_repo.get_by_id.return_value = order
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)

    with pytest.raises(AppError) as exc_info:
        await service.update_order_status(user_id="owner-1", order_id=str(order["_id"]), status=None)

    assert exc_info.value.status_code == 500
    assert exc_info.value.message == "unable to update order status"
    order_repo.update_status.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ["cancelled", "Paid"])
async def test_ut_rst_patch_10_non_enum_status_raises_500(bad_status):
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"])

    order_repo = _order_repo()
    order_repo.get_by_id.return_value = order
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)

    with pytest.raises(AppError) as exc_info:
        await service.update_order_status(
            user_id="owner-1", order_id=str(order["_id"]), status=bad_status
        )

    assert exc_info.value.status_code == 500
    order_repo.update_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut_rst_patch_11_repository_update_failure_raises_500():
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"])

    order_repo = _order_repo()
    order_repo.get_by_id.return_value = order
    order_repo.update_status.return_value = False  # simulated race: matched_count == 0
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)

    with pytest.raises(AppError) as exc_info:
        await service.update_order_status(user_id="owner-1", order_id=str(order["_id"]), status="paid")

    assert exc_info.value.status_code == 500
    assert exc_info.value.message == "unable to update order status"


@pytest.mark.asyncio
async def test_ut_rst_patch_12_regression_backward_transition_accepted_no_lifecycle_enforcement():
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"], status="delivered")
    updated_order = dict(order, status="placed")

    order_repo = _order_repo()
    order_repo.get_by_id.side_effect = [order, updated_order]
    order_repo.update_status.return_value = True
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)
    result = await service.update_order_status(
        user_id="owner-1", order_id=str(order["_id"]), status="placed"
    )

    assert result["status"] == "placed"


@pytest.mark.asyncio
async def test_ut_rst_patch_13_regression_unchanged_status_resubmission_accepted():
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"], status="paid")
    updated_order = dict(order)

    order_repo = _order_repo()
    order_repo.get_by_id.side_effect = [order, updated_order]
    order_repo.update_status.return_value = True
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)
    await service.update_order_status(user_id="owner-1", order_id=str(order["_id"]), status="paid")

    order_repo.update_status.assert_awaited_once_with(str(order["_id"]), status="paid")


@pytest.mark.asyncio
async def test_ut_rst_patch_14_update_status_called_without_total_amount():
    restaurant = _sample_restaurant(user="owner-1")
    order = _sample_order(restaurant=restaurant["_id"])
    updated_order = dict(order, status="paid")

    order_repo = _order_repo()
    order_repo.get_by_id.side_effect = [order, updated_order]
    order_repo.update_status.return_value = True
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)
    await service.update_order_status(user_id="owner-1", order_id=str(order["_id"]), status="paid")

    # Exact-match assertion: proves both the correct positional/keyword shape
    # AND the absence of a stray total_amount argument in one check.
    order_repo.update_status.assert_awaited_once_with(str(order["_id"]), status="paid")


@pytest.mark.asyncio
async def test_ut_rst_patch_15_restaurant_ref_as_objectid_resolves_ownership_correctly():
    restaurant_id = ObjectId()
    restaurant = _sample_restaurant(_id=restaurant_id, user="owner-1")
    order = _sample_order(restaurant=restaurant_id)  # raw ObjectId, not a string
    updated_order = dict(order, status="paid")

    order_repo = _order_repo()
    order_repo.get_by_id.side_effect = [order, updated_order]
    order_repo.update_status.return_value = True
    restaurant_repo = _restaurant_repo()
    restaurant_repo.get_by_id.return_value = restaurant

    service = _make_service(restaurant_repo, order_repo)
    result = await service.update_order_status(
        user_id="owner-1", order_id=str(order["_id"]), status="paid"
    )

    restaurant_repo.get_by_id.assert_awaited_once_with(str(restaurant_id))
    assert result["status"] == "paid"
