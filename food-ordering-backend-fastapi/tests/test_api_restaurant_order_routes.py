"""
API/integration tests for GET /api/my/restaurant/order and
PATCH /api/my/restaurant/order/:orderId/status (Order Management & Order
Lifecycle module). Exercises the REAL FastAPI app end to end against an
in-memory mongomock-motor database, using the `api_client`/`make_token`
fixtures from tests/conftest.py.

Test IDs match docs/testing/api-integration-test-plan.md §3 (shared
AUTH-## matrix), §5 (API-RST-GET-##) and §6 (API-RST-PATCH-##).

Two scenarios in the approved plan were marked [NEEDS VERIFICATION]
because FastAPI/Starlette's internal behavior could not be asserted from
reading the source alone. Both were resolved by direct execution before
writing the corresponding test below (see docs/testing/api-integration-
test-plan.md §6.6 for the original open question; the resolved values are
asserted here, not guessed):
  - API-RST-PATCH-21 (empty order_id path segment): confirmed 404
    {"detail":"Not Found"} — Starlette's own router fails to match the
    path before get_current_user_id or the service ever runs.
  - API-RST-PATCH-22 (no auth token AND a malformed JSON body together):
    confirmed 400 {"errors":[...]} — request-body validation is resolved
    before the auth dependency's exception propagates, so validation
    "wins" over authentication in this specific combination.
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


async def _seed_restaurant(restaurant_repo, owner_user_id=None, **overrides):
    document = {
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
    if owner_user_id is not None:
        document["user"] = owner_user_id
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


# ============================================================================
# GET /api/my/restaurant/order  (API-RST-GET-##)
# ============================================================================


@pytest.mark.asyncio
async def test_api_rst_get_01_happy_path_multiple_orders_populated(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo, email="owner@example.com")
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order1 = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    order2 = await _seed_order(order_repo, restaurant_id, owner_id, status="paid")

    token = make_token(user_id=owner_id)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert {o["_id"] for o in body} == {order1, order2}
    for order in body:
        assert order["restaurant"]["restaurantName"] == "Pasta Place"


@pytest.mark.asyncio
async def test_api_rst_get_02_restaurant_owned_zero_orders_returns_empty_array(api_client, make_token):
    user_repo, restaurant_repo, _ = _repos()
    owner_id = await _seed_user(user_repo)
    await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)

    token = make_token(user_id=owner_id)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_api_rst_get_03_no_restaurant_at_all_returns_empty_array_not_404(api_client, make_token):
    user_repo, _, _ = _repos()
    user_id = await _seed_user(user_repo)  # never assigned a restaurant

    token = make_token(user_id=user_id)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_api_rst_get_04_happy_path_via_session_id_cookie_fallback(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)

    token = make_token(user_id=owner_id)
    response = api_client.get("/api/my/restaurant/order", cookies={"session_id": token})

    assert response.status_code == 200
    assert [o["_id"] for o in response.json()] == [order_id]


def test_api_rst_get_05_auth01_no_token_at_all(api_client):
    response = api_client.get("/api/my/restaurant/order")
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_get_06_auth02_non_bearer_authorization_header(api_client):
    response = api_client.get("/api/my/restaurant/order", headers={"Authorization": "Basic dGVzdDp0ZXN0"})
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_get_07_auth03_garbage_bearer_token(api_client):
    response = api_client.get("/api/my/restaurant/order", headers=_auth("garbage-token"))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_get_08_auth04_valid_signature_missing_userid_claim(api_client, make_token):
    token = make_token(omit_user_id=True)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_get_09_auth05_wrong_signing_secret(api_client, make_token):
    token = make_token(user_id=str(ObjectId()), secret="a-completely-different-secret-value")
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_get_10_auth06_expired_token(api_client, make_token):
    token = make_token(user_id=str(ObjectId()), expired=True)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


@pytest.mark.asyncio
async def test_api_rst_get_11_cross_restaurant_isolation(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_a = await _seed_user(user_repo, email="owner-a@example.com")
    owner_b = await _seed_user(user_repo, email="owner-b@example.com")
    restaurant_a = await _seed_restaurant(restaurant_repo, owner_user_id=owner_a, restaurantName="A's")
    restaurant_b = await _seed_restaurant(restaurant_repo, owner_user_id=owner_b, restaurantName="B's")
    order_a = await _seed_order(order_repo, restaurant_a, owner_a)
    await _seed_order(order_repo, restaurant_b, owner_b)

    token_a = make_token(user_id=owner_a)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token_a))

    assert response.status_code == 200
    assert [o["_id"] for o in response.json()] == [order_a]


@pytest.mark.asyncio
async def test_api_rst_get_12_regression_placed_status_included_unfiltered(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    for status in ("placed", "paid", "delivered"):
        await _seed_order(order_repo, restaurant_id, owner_id, status=status)

    token = make_token(user_id=owner_id)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))

    assert response.status_code == 200
    statuses = {o["status"] for o in response.json()}
    assert statuses == {"placed", "paid", "delivered"}


@pytest.mark.asyncio
async def test_api_rst_get_13_regression_password_hash_present_in_response(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo, email="hashcheck2@example.com", password="hunter22")
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    await _seed_order(order_repo, restaurant_id, owner_id)

    token = make_token(user_id=owner_id)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))

    assert response.status_code == 200
    password_hash = response.json()[0]["user"]["password"]
    assert password_hash != "hunter22"
    assert password_hash.startswith("$2b$")


@pytest.mark.asyncio
async def test_api_rst_get_14_orphaned_user_ref_resolves_to_null_not_500(api_client, make_token):
    """
    Unlike GET /api/order, this endpoint's `restaurant` ref is load-bearing
    for the query itself (list_by_restaurant matches on it) and so cannot
    be orphaned without the order simply not appearing at all. The
    realistic orphan case for this endpoint is the order's `user` ref
    pointing at a user document that no longer exists.
    """
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    orphaned_user_id = str(ObjectId())
    order_id = await _seed_order(order_repo, restaurant_id, orphaned_user_id)

    token = make_token(user_id=owner_id)
    response = api_client.get("/api/my/restaurant/order", headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body[0]["_id"] == order_id
    assert body[0]["restaurant"]["restaurantName"] == "Pasta Place"
    assert body[0]["user"] is None


# ============================================================================
# PATCH /api/my/restaurant/order/:orderId/status  (API-RST-PATCH-##)
# ============================================================================


@pytest.mark.asyncio
async def test_api_rst_patch_01_success_response_is_unpopulated_raw_refs(api_client, make_token):
    """
    Confirms the asymmetry flagged in api-integration-test-plan.md §6:
    unlike both GET endpoints, the PATCH success response is NOT run
    through populate_order() — restaurant/user come back as raw ID
    strings, not embedded documents.
    """
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")

    token = make_token(user_id=owner_id)
    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "paid"}, headers=_auth(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "paid"
    assert body["restaurant"] == restaurant_id  # raw string ref, NOT {"restaurantName": ...}
    assert body["user"] == owner_id  # raw string ref, NOT {"email": ...}
    assert isinstance(body["restaurant"], str)
    assert isinstance(body["user"], str)


@pytest.mark.asyncio
async def test_api_rst_patch_02_full_forward_lifecycle_walk(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    token = make_token(user_id=owner_id)

    for next_status in ("paid", "inProgress", "outForDelivery", "delivered"):
        response = api_client.patch(
            f"/api/my/restaurant/order/{order_id}/status",
            json={"status": next_status},
            headers=_auth(token),
        )
        assert response.status_code == 200
        assert response.json()["status"] == next_status


@pytest.mark.asyncio
async def test_api_rst_patch_03_regression_backward_transition_accepted(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="delivered")
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "placed"}, headers=_auth(token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "placed"


@pytest.mark.asyncio
async def test_api_rst_patch_04_regression_skip_ahead_transition_accepted(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "delivered"}, headers=_auth(token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "delivered"


@pytest.mark.asyncio
async def test_api_rst_patch_05_regression_idempotent_resubmission_accepted(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="paid")
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "paid"}, headers=_auth(token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_api_rst_patch_06_malformed_json_body_returns_400_errors_shape(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status",
        content=b"{not valid json",
        headers={"Content-Type": "application/json", **_auth(token)},
    )

    assert response.status_code == 400
    body = response.json()
    assert "errors" in body
    assert "message" not in body  # distinct shape from the service-layer 400 (API-RST-PATCH-20)


@pytest.mark.asyncio
async def test_api_rst_patch_07_non_object_json_body_returns_400_errors_shape(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json=["a", "list"], headers=_auth(token)
    )

    assert response.status_code == 400
    assert "errors" in response.json()


@pytest.mark.asyncio
async def test_api_rst_patch_08_empty_object_body_returns_500_service_layer(api_client, make_token):
    """
    A well-formed but empty JSON object passes request-body validation
    (any dict is valid), so payload.get("status") is None once it reaches
    the service — a materially different failure mode (500, not 400) from
    API-RST-PATCH-06/07.
    """
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={}, headers=_auth(token)
    )

    assert response.status_code == 500
    assert response.json() == {"message": "unable to update order status"}


def test_api_rst_patch_09_auth01_no_token_at_all(api_client):
    response = api_client.patch(
        f"/api/my/restaurant/order/{ObjectId()}/status", json={"status": "paid"}
    )
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_patch_10_auth02_non_bearer_authorization_header(api_client):
    response = api_client.patch(
        f"/api/my/restaurant/order/{ObjectId()}/status",
        json={"status": "paid"},
        headers={"Authorization": "Basic dGVzdDp0ZXN0"},
    )
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_patch_11_auth03_garbage_bearer_token(api_client):
    response = api_client.patch(
        f"/api/my/restaurant/order/{ObjectId()}/status",
        json={"status": "paid"},
        headers=_auth("garbage-token"),
    )
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_patch_12_auth04_valid_signature_missing_userid_claim(api_client, make_token):
    token = make_token(omit_user_id=True)
    response = api_client.patch(
        f"/api/my/restaurant/order/{ObjectId()}/status", json={"status": "paid"}, headers=_auth(token)
    )
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_patch_13_auth05_wrong_signing_secret(api_client, make_token):
    token = make_token(user_id=str(ObjectId()), secret="a-completely-different-secret-value")
    response = api_client.patch(
        f"/api/my/restaurant/order/{ObjectId()}/status", json={"status": "paid"}, headers=_auth(token)
    )
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


def test_api_rst_patch_14_auth06_expired_token(api_client, make_token):
    token = make_token(user_id=str(ObjectId()), expired=True)
    response = api_client.patch(
        f"/api/my/restaurant/order/{ObjectId()}/status", json={"status": "paid"}, headers=_auth(token)
    )
    assert response.status_code == 401
    assert response.json() == {"message": "unauthorized"}


@pytest.mark.asyncio
async def test_api_rst_patch_15_mismatched_owner_returns_401_empty_body(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    real_owner = await _seed_user(user_repo, email="real-owner@example.com")
    attacker = await _seed_user(user_repo, email="attacker@example.com")
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=real_owner)
    order_id = await _seed_order(order_repo, restaurant_id, real_owner, status="placed")

    token = make_token(user_id=attacker)
    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "paid"}, headers=_auth(token)
    )

    assert response.status_code == 401
    assert response.content == b""

    # Confirm the write did NOT happen despite the request being processed
    stored = await order_repo.get_by_id(order_id)
    assert stored["status"] == "placed"


@pytest.mark.asyncio
async def test_api_rst_patch_16_orphaned_restaurant_ref_returns_401_not_404_or_500(api_client, make_token):
    _, _, order_repo = _repos()
    orphaned_restaurant_id = str(ObjectId())
    order_id = await _seed_order(order_repo, orphaned_restaurant_id, str(ObjectId()), status="placed")

    token = make_token(user_id=str(ObjectId()))
    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "paid"}, headers=_auth(token)
    )

    assert response.status_code == 401
    assert response.content == b""


@pytest.mark.asyncio
async def test_api_rst_patch_17_restaurant_with_no_owner_assigned_returns_401(api_client, make_token):
    _, restaurant_repo, order_repo = _repos()
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=None)  # no "user" field at all
    order_id = await _seed_order(order_repo, restaurant_id, str(ObjectId()), status="placed")

    token = make_token(user_id=str(ObjectId()))
    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "paid"}, headers=_auth(token)
    )

    assert response.status_code == 401
    assert response.content == b""


@pytest.mark.asyncio
async def test_api_rst_patch_19_order_not_found_returns_404(api_client, make_token):
    token = make_token(user_id=str(ObjectId()))
    nonexistent_order_id = str(ObjectId())

    response = api_client.patch(
        f"/api/my/restaurant/order/{nonexistent_order_id}/status",
        json={"status": "paid"},
        headers=_auth(token),
    )

    assert response.status_code == 404
    assert response.json() == {"message": "order not found"}


def test_api_rst_patch_20_invalid_order_id_format_returns_400_message_shape(api_client, make_token):
    token = make_token(user_id=str(ObjectId()))

    response = api_client.patch(
        "/api/my/restaurant/order/not-a-valid-object-id/status",
        json={"status": "paid"},
        headers=_auth(token),
    )

    assert response.status_code == 400
    body = response.json()
    assert body == {"message": "Invalid order ID format"}
    assert "errors" not in body  # distinct shape from the request-validation 400 (API-RST-PATCH-06/07)


def test_api_rst_patch_21_empty_order_id_segment_is_a_framework_404(api_client, make_token):
    """
    Resolved by execution (see module docstring): an empty order_id path
    segment never reaches routing at all — Starlette's router itself
    returns 404 before get_current_user_id or the service run. Confirmed
    with no auth token present; the framework 404 fires regardless.
    """
    response = api_client.patch("/api/my/restaurant/order//status", json={"status": "paid"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_api_rst_patch_22_precedence_no_auth_and_malformed_body_validation_wins(api_client):
    """
    Resolved by execution (see module docstring): with NO auth token and a
    malformed JSON body simultaneously, the request-body validation error
    (400) is returned, not the auth failure (401). Request-body parsing is
    resolved before get_current_user_id's exception is allowed to
    propagate for this endpoint's dependency graph.
    """
    response = api_client.patch(
        "/api/my/restaurant/order/not-a-valid-id/status",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert "errors" in response.json()


@pytest.mark.asyncio
async def test_api_rst_patch_23_null_status_returns_500(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": None}, headers=_auth(token)
    )

    assert response.status_code == 500
    assert response.json() == {"message": "unable to update order status"}


@pytest.mark.asyncio
async def test_api_rst_patch_24_non_enum_status_string_returns_500(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status",
        json={"status": "cancelled"},
        headers=_auth(token),
    )

    assert response.status_code == 500
    assert response.json() == {"message": "unable to update order status"}


@pytest.mark.asyncio
async def test_api_rst_patch_25_wrong_case_status_returns_500(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "Paid"}, headers=_auth(token)
    )

    assert response.status_code == 500
    assert response.json() == {"message": "unable to update order status"}


@pytest.mark.asyncio
async def test_api_rst_patch_26_non_string_status_type_returns_500(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": 123}, headers=_auth(token)
    )

    assert response.status_code == 500
    assert response.json() == {"message": "unable to update order status"}


@pytest.mark.asyncio
async def test_api_rst_patch_27_db_persistence_verified_via_independent_refetch(api_client, make_token):
    """
    Does not trust the PATCH response body — re-fetches the order via a
    fresh repository read to confirm the write actually reached storage.
    """
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "inProgress"}, headers=_auth(token)
    )
    assert response.status_code == 200

    stored = await order_repo.get_by_id(order_id)
    assert stored["status"] == "inProgress"


@pytest.mark.asyncio
async def test_api_rst_patch_28_total_amount_untouched_by_this_endpoint(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed", totalAmount=4321)
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status", json={"status": "paid"}, headers=_auth(token)
    )
    assert response.status_code == 200

    stored = await order_repo.get_by_id(order_id)
    assert stored["totalAmount"] == 4321


@pytest.mark.asyncio
async def test_api_rst_patch_29_only_targeted_order_is_modified(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    target_order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    sibling_order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{target_order_id}/status",
        json={"status": "delivered"},
        headers=_auth(token),
    )
    assert response.status_code == 200

    target_stored = await order_repo.get_by_id(target_order_id)
    sibling_stored = await order_repo.get_by_id(sibling_order_id)
    assert target_stored["status"] == "delivered"
    assert sibling_stored["status"] == "placed"


@pytest.mark.skip(
    reason=(
        "API-RST-PATCH-30 (repository write races with a concurrent delete) is a "
        "documented coverage limit, not a silently dropped scenario — see "
        "docs/testing/api-integration-test-plan.md §6.9. A genuine race is not "
        "reliably reproducible via a single-threaded TestClient call; the "
        "*handling* of a failed write is already covered by the unit-level test "
        "UT-RST-PATCH-11 (tests/test_restaurant_order_lifecycle.py) with a mocked "
        "repository. Forcing a real race here would require a threading harness "
        "beyond this task's scope."
    )
)
def test_api_rst_patch_30_concurrent_delete_race_condition():
    pass
