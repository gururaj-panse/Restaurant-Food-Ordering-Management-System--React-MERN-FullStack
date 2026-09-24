"""
API/integration tests for GET /api/order (Order Management & Order
Lifecycle module). Exercises the REAL FastAPI app end to end — request ->
routing -> auth dependency -> service -> in-memory Motor-compatible DB ->
response — using the `api_client` (real DI-wired TestClient, real
mongomock-motor database) and `make_token` (real JWT signing, same
secret/algorithm as production `get_current_user_id`) fixtures from
tests/conftest.py.

Test IDs match docs/testing/api-integration-test-plan.md §3 (shared
AUTH-## matrix) and §4 (API-ORD-GET-##).
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from app.db.mongodb import mongodb
from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository


def _repos():
    return (
        UserRepository(mongodb.users),
        RestaurantRepository(mongodb.restaurants),
        OrderRepository(mongodb.orders),
    )


async def _seed_user(user_repo, **overrides):
    defaults = {"email": f"user-{ObjectId()}@example.com", "password": "hunter22", "name": "Jane"}
    defaults.update(overrides)
    return await user_repo.create(**defaults)


async def _seed_restaurant(restaurant_repo, owner_user_id, **overrides):
    document = {
        "user": owner_user_id,
        "restaurantName": "Pasta Place",
        "city": "London",
        "country": "UK",
        "deliveryPrice": 250,
        "estimatedDeliveryTime": 30,
        "cuisines": ["Italian"],
        "menuItems": [{"name": "Spaghetti", "price": 990}],
        "imageUrl": "https://example.com/img.jpg",
        "lastUpdated": datetime.now(timezone.utc),
    }
    document.update(overrides)
    return await restaurant_repo.create(document)


async def _seed_order(order_repo, restaurant_id, user_id, status="placed", **overrides):
    document = {
        "restaurant": restaurant_id,
        "user": user_id,
        "deliveryDetails": {
            "email": "jane@example.com",
            "name": "Jane",
            "addressLine1": "1 Main St",
            "city": "London",
        },
        "cartItems": [{"menuItemId": "abc123", "name": "Spaghetti", "quantity": 2}],
        "status": status,
        "createdAt": datetime.now(timezone.utc),
        "totalAmount": 1730,
    }
    document.update(overrides)
    return await order_repo.create(document)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- happy path ----


@pytest.mark.asyncio
async def test_api_ord_get_01_happy_path_multiple_orders_populated(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    user_id = await _seed_user(user_repo, email="alice@example.com")
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=user_id)
    order1_id = await _seed_order(order_repo, restaurant_id, user_id, status="placed")
    order2_id = await _seed_order(order_repo, restaurant_id, user_id, status="delivered")

    token = make_token(user_id=user_id)
    response = api_client.get("/api/order", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert {o["_id"] for o in body} == {order1_id, order2_id}
    for order in body:
        assert order["restaurant"]["restaurantName"] == "Pasta Place"
        assert order["user"]["email"] == "alice@example.com"
        assert isinstance(order["restaurant"]["_id"], str)  # ObjectId -> str conversion


@pytest.mark.asyncio
async def test_api_ord_get_02_happy_path_no_orders_returns_empty_array(api_client, make_token):
    user_repo, _, _ = _repos()
    user_id = await _seed_user(user_repo)

    token = make_token(user_id=user_id)
    response = api_client.get("/api/order", headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_api_ord_get_03_happy_path_via_session_id_cookie_fallback(api_client, make_token):
    """AUTH-07 applied to this route: no Authorization header at all, JWT
    supplied only via the session_id cookie."""
    user_repo, restaurant_repo, order_repo = _repos()
    user_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=user_id)
    order_id = await _seed_order(order_repo, restaurant_id, user_id)

    token = make_token(user_id=user_id)
    response = api_client.get("/api/order", cookies={"session_id": token})

    assert response.status_code == 200
    assert [o["_id"] for o in response.json()] == [order_id]


# --------------------------------------------------------------- auth failures ----


def test_api_ord_get_04_auth01_no_token_at_all(api_client):
    response = api_client.get("/api/order")
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_ord_get_05_auth02_non_bearer_authorization_header(api_client):
    response = api_client.get("/api/order", headers={"Authorization": "Basic dGVzdDp0ZXN0"})
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_ord_get_06_auth03_garbage_bearer_token(api_client):
    response = api_client.get("/api/order", headers=_auth("not-a-valid-jwt-at-all"))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_ord_get_07_auth04_valid_signature_missing_userid_claim(api_client, make_token):
    token = make_token(omit_user_id=True)
    response = api_client.get("/api/order", headers=_auth(token))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_ord_get_08_auth05_wrong_signing_secret(api_client, make_token):
    token = make_token(user_id=str(ObjectId()), secret="a-completely-different-secret-value")
    response = api_client.get("/api/order", headers=_auth(token))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_ord_get_09_auth06_expired_token(api_client, make_token):
    token = make_token(user_id=str(ObjectId()), expired=True)
    response = api_client.get("/api/order", headers=_auth(token))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


# --------------------------------------------------------- regression / security ----


@pytest.mark.asyncio
async def test_api_ord_get_10_cross_user_isolation(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    user_a = await _seed_user(user_repo, email="a@example.com")
    user_b = await _seed_user(user_repo, email="b@example.com")
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=user_a)
    order_a = await _seed_order(order_repo, restaurant_id, user_a)
    await _seed_order(order_repo, restaurant_id, user_b)

    token_a = make_token(user_id=user_a)
    response = api_client.get("/api/order", headers=_auth(token_a))

    assert response.status_code == 200
    body = response.json()
    assert [o["_id"] for o in body] == [order_a]


@pytest.mark.asyncio
async def test_api_ord_get_11_regression_placed_status_included_unfiltered(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    user_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=user_id)
    for status in ("placed", "paid", "inProgress", "outForDelivery", "delivered"):
        await _seed_order(order_repo, restaurant_id, user_id, status=status)

    token = make_token(user_id=user_id)
    response = api_client.get("/api/order", headers=_auth(token))

    assert response.status_code == 200
    statuses = {o["status"] for o in response.json()}
    assert statuses == {"placed", "paid", "inProgress", "outForDelivery", "delivered"}


@pytest.mark.asyncio
async def test_api_ord_get_12_regression_password_hash_present_in_response(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    user_id = await _seed_user(user_repo, email="hashcheck@example.com", password="hunter22")
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=user_id)
    await _seed_order(order_repo, restaurant_id, user_id)

    token = make_token(user_id=user_id)
    response = api_client.get("/api/order", headers=_auth(token))

    assert response.status_code == 200
    password_hash = response.json()[0]["user"]["password"]
    assert password_hash != "hunter22"
    assert password_hash.startswith("$2b$")


@pytest.mark.asyncio
async def test_api_ord_get_13_orphaned_refs_resolve_to_null_not_500(api_client, make_token):
    """
    The order's own `user` ref (== the caller's userId, since that's what
    list_by_user filters on) points at no real user document, and its
    `restaurant` ref points at no real restaurant document either. Both
    must resolve to null in the response, not a 500.
    """
    _, _, order_repo = _repos()
    orphaned_user_id = str(ObjectId())
    orphaned_restaurant_id = str(ObjectId())
    order_id = await _seed_order(order_repo, orphaned_restaurant_id, orphaned_user_id)

    token = make_token(user_id=orphaned_user_id)
    response = api_client.get("/api/order", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["_id"] == order_id
    assert body[0]["restaurant"] is None
    assert body[0]["user"] is None
