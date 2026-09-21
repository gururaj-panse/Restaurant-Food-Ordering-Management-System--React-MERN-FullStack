"""
Basic tests for the data-access layer (Jira RFOMS-4 scope): repositories +
the DB-layer behaviors they're responsible for preserving (password
hashing, sub-document ObjectId generation, unique email index, search/sort
/paginate semantics, the confirmed no-op order-status filter).

Uses mongomock-motor — an in-memory, Motor-compatible fake. No real
MongoDB connection, no network access, no production data touched.
"""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

from app.core.security import verify_password
from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository


@pytest_asyncio.fixture()
async def db():
    client = AsyncMongoMockClient()
    return client.get_database("test_food_ordering")


# ---------------------------------------------------------------- User ----


@pytest.mark.asyncio
async def test_user_create_hashes_password_and_is_retrievable(db):
    repo = UserRepository(db["users"])
    user_id = await repo.create(email="jane@example.com", password="hunter22", name="Jane")

    stored = await repo.get_by_id(user_id)
    assert stored is not None
    assert stored["email"] == "jane@example.com"
    assert stored["password"] != "hunter22"  # never stored in plaintext
    assert verify_password("hunter22", stored["password"]) is True
    assert verify_password("wrong-password", stored["password"]) is False


@pytest.mark.asyncio
async def test_user_get_by_email(db):
    repo = UserRepository(db["users"])
    await repo.create(email="jane@example.com", password="hunter22", name="Jane")

    found = await repo.get_by_email("jane@example.com")
    assert found is not None
    assert found["name"] == "Jane"

    assert await repo.get_by_email("nobody@example.com") is None


@pytest.mark.asyncio
async def test_user_email_unique_index_is_enforced(db):
    """Confirms the one real index in the current system is reproduced."""
    await db["users"].create_index("email", unique=True)
    repo = UserRepository(db["users"])
    await repo.create(email="dup@example.com", password="hunter22", name="A")

    with pytest.raises(Exception):  # DuplicateKeyError from the driver
        await repo.create(email="dup@example.com", password="hunter22", name="B")


@pytest.mark.asyncio
async def test_user_update_profile(db):
    repo = UserRepository(db["users"])
    user_id = await repo.create(email="jane@example.com", password="hunter22", name="Jane")

    updated = await repo.update_profile(
        user_id, name="Jane Doe", address_line1="1 Main St", city="London", country="UK"
    )
    assert updated is True

    stored = await repo.get_by_id(user_id)
    assert stored["name"] == "Jane Doe"
    assert stored["city"] == "London"


# ---------------------------------------------------------- Restaurant ----


async def _seed_restaurant(repo: RestaurantRepository, **overrides):
    document = {
        "user": str(ObjectId()),
        "restaurantName": "Pasta Place",
        "city": "London",
        "country": "UK",
        "deliveryPrice": 250,
        "estimatedDeliveryTime": 30,
        "cuisines": ["Italian", "Pasta"],
        "menuItems": [{"name": "Spaghetti", "price": 990}],
        "imageUrl": "https://example.com/img.jpg",
        "lastUpdated": datetime.now(timezone.utc),
    }
    document.update(overrides)
    return await repo.create(document)


@pytest.mark.asyncio
async def test_restaurant_create_generates_menu_item_ids(db):
    """The core mismatch this pass exists to fix: Motor does not auto-generate
    sub-document _id the way Mongoose does — it must happen explicitly."""
    repo = RestaurantRepository(db["restaurants"])
    restaurant_id = await _seed_restaurant(repo)

    stored = await repo.get_by_id(restaurant_id)
    assert len(stored["menuItems"]) == 1
    assert isinstance(stored["menuItems"][0]["_id"], ObjectId)


@pytest.mark.asyncio
async def test_restaurant_get_by_owner_and_distinct_cities(db):
    repo = RestaurantRepository(db["restaurants"])
    await _seed_restaurant(repo, user="owner-1", city="London")
    await _seed_restaurant(repo, user="owner-2", city="Manchester")

    owned = await repo.get_by_owner("owner-1")
    assert owned["city"] == "London"

    cities = await repo.distinct_cities()
    assert set(cities) == {"London", "Manchester"}


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason=(
        "mongomock does not support $all with regex patterns against array "
        "elements (verified independently: even a single-pattern $all "
        "returns 0 matches against a document that plainly satisfies it). "
        "This is a real MongoDB-documented, supported query — the same one "
        "the current Node backend relies on in production — so this is a "
        "test-tooling limitation, not a repository defect. Re-verify this "
        "specific behavior against a real MongoDB instance before Jira "
        "Story RFOMS-4 is marked complete."
    ),
    strict=True,
)
async def test_restaurant_search_cuisine_filter_is_and_not_or(db):
    """Confirms the $all (AND) semantics — a restaurant must have ALL
    selected cuisines, not just one, per CURRENT_STATE.md §8."""
    repo = RestaurantRepository(db["restaurants"])
    await _seed_restaurant(repo, restaurantName="Italian Only", cuisines=["Italian"])
    await _seed_restaurant(
        repo, restaurantName="Italian and Pizza", cuisines=["Italian", "Pizza"]
    )

    results, total = await repo.search(city="all", selected_cuisines="Italian,Pizza")
    names = {r["restaurantName"] for r in results}

    assert total == 1
    assert names == {"Italian and Pizza"}


@pytest.mark.asyncio
async def test_restaurant_search_city_all_skips_filter(db):
    repo = RestaurantRepository(db["restaurants"])
    await _seed_restaurant(repo, city="London")
    await _seed_restaurant(repo, city="Manchester")

    results, total = await repo.search(city="all")
    assert total == 2


@pytest.mark.asyncio
async def test_restaurant_search_pagination_page_size_is_fixed_ten(db):
    repo = RestaurantRepository(db["restaurants"])
    for i in range(12):
        await _seed_restaurant(repo, restaurantName=f"Place {i}", city="all")

    page_1, total = await repo.search(city="all", page=1)
    page_2, _ = await repo.search(city="all", page=2)

    assert total == 12
    assert len(page_1) == 10
    assert len(page_2) == 2


# --------------------------------------------------------------- Order ----


async def _seed_order(repo: OrderRepository, status: str = "placed", **overrides):
    document = {
        "restaurant": str(ObjectId()),
        "user": "user-1",
        "deliveryDetails": {
            "email": "jane@example.com",
            "name": "Jane",
            "addressLine1": "1 Main St",
            "city": "London",
        },
        "cartItems": [{"menuItemId": str(ObjectId()), "name": "Spaghetti", "quantity": 2}],
        "status": status,
        "createdAt": datetime.now(timezone.utc),
    }
    document.update(overrides)
    return await repo.create(document)


@pytest.mark.asyncio
async def test_order_create_generates_cart_item_ids(db):
    repo = OrderRepository(db["orders"])
    order_id = await _seed_order(repo)

    stored = await repo.get_by_id(order_id)
    assert isinstance(stored["cartItems"][0]["_id"], ObjectId)


@pytest.mark.asyncio
async def test_order_list_by_user_status_filter_is_a_confirmed_noop(db):
    """
    getMyOrders filters status IN [all 5 enum values] — every status must
    still be returned, proving the filter excludes nothing today.
    """
    repo = OrderRepository(db["orders"])
    for status in ["placed", "paid", "inProgress", "outForDelivery", "delivered"]:
        await _seed_order(repo, status=status, user="user-1")
    await _seed_order(repo, status="placed", user="someone-else")

    orders = await repo.list_by_user("user-1")
    assert len(orders) == 5


@pytest.mark.asyncio
async def test_order_list_by_restaurant_includes_unpaid_placed_orders(db):
    repo = OrderRepository(db["orders"])
    restaurant_id = str(ObjectId())
    await _seed_order(repo, status="placed", restaurant=restaurant_id)
    await _seed_order(repo, status="paid", restaurant=restaurant_id)

    orders = await repo.list_by_restaurant(restaurant_id)
    statuses = {o["status"] for o in orders}
    assert statuses == {"placed", "paid"}


@pytest.mark.asyncio
async def test_order_update_status_sets_status_and_total_amount(db):
    repo = OrderRepository(db["orders"])
    order_id = await _seed_order(repo, status="placed")

    updated = await repo.update_status(order_id, status="paid", total_amount=1730)
    assert updated is True

    stored = await repo.get_by_id(order_id)
    assert stored["status"] == "paid"
    assert stored["totalAmount"] == 1730


@pytest.mark.asyncio
async def test_order_update_status_without_total_amount_leaves_it_untouched(db):
    """Mirrors MyRestaurantController.updateOrderStatus, which updates
    status only — not every status transition touches totalAmount."""
    repo = OrderRepository(db["orders"])
    order_id = await _seed_order(repo, status="paid", totalAmount=1730)

    await repo.update_status(order_id, status="inProgress")

    stored = await repo.get_by_id(order_id)
    assert stored["status"] == "inProgress"
    assert stored["totalAmount"] == 1730
