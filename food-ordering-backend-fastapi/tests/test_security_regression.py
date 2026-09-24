"""
Security & regression tests for the Order Management & Order Lifecycle
module, implementing docs/testing/security-regression-plan.md §3
(SEC-01..05). These close gaps not covered by the existing unit
(tests/test_order_service.py, tests/test_restaurant_order_lifecycle.py)
and API/integration (tests/test_api_order_routes.py,
tests/test_api_restaurant_order_routes.py) suites — see the plan for why
each scenario is a genuine gap rather than a duplicate.

Uses the same `api_client`/`make_token` fixtures as the existing API
suite, plus the new `api_client_no_raise` fixture (tests/conftest.py) for
the two scenarios that deliberately trigger an unhandled exception and
need to observe the real client-facing response rather than pytest's
re-raised traceback.
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
        "menuItems": [{"name": "Spaghetti", "price": 990}],
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


_LEAK_MARKERS = ("Traceback", ".py", "TypeError", "line ", "File \"")


def _assert_no_internal_leak(body_text: str) -> None:
    for marker in _LEAK_MARKERS:
        assert marker not in body_text, f"response leaked an internal detail: {marker!r} found in {body_text!r}"


# ============================================================================
# SEC-01 / SEC-02 — unhashable status values -> uncaught exception, safe 500
# ============================================================================


@pytest.mark.asyncio
async def test_sec_01_unhashable_list_status_fails_safely_with_no_internal_leak(
    api_client_no_raise, make_token
):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    token = make_token(user_id=owner_id)

    response = api_client_no_raise.patch(
        f"/api/my/restaurant/order/{order_id}/status",
        json={"status": ["a", "b"]},
        headers=_auth(token),
    )

    assert response.status_code == 500
    assert response.json() == {"message": "Something went wrong"}
    _assert_no_internal_leak(response.text)

    # Confirm the order was NOT modified by the failed attempt
    stored = await order_repo.get_by_id(order_id)
    assert stored["status"] == "placed"


@pytest.mark.asyncio
async def test_sec_02_nosql_operator_shaped_status_fails_safely_no_bypass(
    api_client_no_raise, make_token
):
    """
    A status value shaped like a MongoDB operator-injection attempt
    ({"$ne": "delivered"}) must not be silently accepted or forwarded into
    a database write — it should fail exactly the same way as any other
    unhashable-type status value, and the order must remain unmodified.
    """
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(order_repo, restaurant_id, owner_id, status="placed")
    token = make_token(user_id=owner_id)

    response = api_client_no_raise.patch(
        f"/api/my/restaurant/order/{order_id}/status",
        json={"status": {"$ne": "delivered"}},
        headers=_auth(token),
    )

    assert response.status_code == 500
    assert response.json() == {"message": "Something went wrong"}
    _assert_no_internal_leak(response.text)

    stored = await order_repo.get_by_id(order_id)
    assert stored["status"] == "placed"


# ============================================================================
# SEC-03 — injection/traversal-shaped order_id values
# ============================================================================


@pytest.mark.parametrize(
    "malicious_order_id",
    [
        "1' OR '1'='1",
        '{"$ne": null}',
        "000000000000000000000001; DROP TABLE orders",
        "a" * 5000,
    ],
    ids=["sql-shaped", "json-operator-shaped", "command-shaped", "very-long"],
)
def test_sec_03_injection_shaped_order_id_rejected_cleanly(api_client, make_token, malicious_order_id):
    """
    Every one of these strings fails ObjectId.is_valid()'s strict format
    check and is rejected before any database query is constructed.
    """
    token = make_token(user_id=str(ObjectId()))

    response = api_client.patch(
        f"/api/my/restaurant/order/{malicious_order_id}/status",
        json={"status": "paid"},
        headers=_auth(token),
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Invalid order ID format"}


def test_sec_03b_path_traversal_shaped_order_id_never_reaches_the_route(api_client, make_token):
    """
    Unlike the other injection-shaped strings above, a path-traversal
    payload ("../../../etc/passwd") is resolved by standard URL path
    normalization BEFORE routing: "/api/my/restaurant/order/../../../etc/
    passwd/status" collapses to "/api/etc/passwd/status", a path that
    matches no route at all. Confirmed by direct execution (not assumed):
    this produces a plain framework 404, not the service's 400 — a
    DIFFERENT but equally safe outcome, since order_id is never evaluated
    as this literal string by the application at all.
    """
    token = make_token(user_id=str(ObjectId()))

    response = api_client.patch(
        "/api/my/restaurant/order/../../../etc/passwd/status",
        json={"status": "paid"},
        headers=_auth(token),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


# ============================================================================
# SEC-04 — mass-assignment attempt via extra PATCH body fields
# ============================================================================


@pytest.mark.asyncio
async def test_sec_04_mass_assignment_extra_fields_are_ignored(api_client, make_token):
    user_repo, restaurant_repo, order_repo = _repos()
    owner_id = await _seed_user(user_repo)
    other_restaurant_id = str(ObjectId())
    other_user_id = str(ObjectId())
    restaurant_id = await _seed_restaurant(restaurant_repo, owner_user_id=owner_id)
    order_id = await _seed_order(
        order_repo, restaurant_id, owner_id, status="placed", totalAmount=1111
    )
    token = make_token(user_id=owner_id)

    response = api_client.patch(
        f"/api/my/restaurant/order/{order_id}/status",
        json={
            "status": "paid",
            "totalAmount": 999999,
            "restaurant": other_restaurant_id,
            "user": other_user_id,
            "_id": str(ObjectId()),
        },
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paid"

    stored = await order_repo.get_by_id(order_id)
    assert stored["status"] == "paid"  # the one legitimate change
    assert stored["totalAmount"] == 1111  # NOT overwritten by the smuggled 999999
    assert str(stored["restaurant"]) == restaurant_id  # NOT overwritten
    assert str(stored["user"]) == owner_id  # NOT overwritten
    assert str(stored["_id"]) == order_id  # document identity unchanged


# ============================================================================
# SEC-05 — auth-failure responses are pairwise identical (no distinguishing leak)
# ============================================================================


def test_sec_05_all_auth_failure_reasons_produce_identical_responses(api_client, make_token):
    order_id = str(ObjectId())

    conditions = {
        "no_token": {},
        "non_bearer_header": {"headers": {"Authorization": "Basic dGVzdDp0ZXN0"}},
        "garbage_token": {"headers": _auth("garbage-not-a-jwt")},
        "wrong_secret": {"headers": _auth(make_token(user_id=str(ObjectId()), secret="wrong-secret"))},
        "expired_token": {"headers": _auth(make_token(user_id=str(ObjectId()), expired=True))},
        "missing_userid_claim": {"headers": _auth(make_token(omit_user_id=True))},
    }

    responses = {
        name: api_client.patch(
            f"/api/my/restaurant/order/{order_id}/status",
            json={"status": "paid"},
            **kwargs,
        )
        for name, kwargs in conditions.items()
    }

    reference_name, reference_response = next(iter(responses.items()))
    assert reference_response.status_code == 401
    assert reference_response.json() == {"message": "unauthorized"}

    for name, response in responses.items():
        assert response.status_code == reference_response.status_code, f"{name} had a different status code"
        assert response.content == reference_response.content, f"{name} had a different response body"
