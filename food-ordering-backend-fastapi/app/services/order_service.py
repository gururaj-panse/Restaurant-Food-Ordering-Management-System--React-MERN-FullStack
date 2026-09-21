"""
Order & Payment Module — service implementation (Jira RFOMS-11/12/13).

Kept as ONE module, matching the approved architecture decision (order and
payment logic share one controller today — OrderController.ts — and
splitting them was reviewed and rejected as an unjustified structural
change; see MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md §10).

Mirrors food-ordering-backend/src/controllers/OrderController.ts, including
these confirmed behaviors, reproduced deliberately:
  - getMyOrders' status filter is a confirmed no-op — already encoded in
    OrderRepository.list_by_user (unchanged this pass).
  - `.populate("restaurant")`/`.populate("user")` in Node embeds FULL
    documents into the response, including the user's bcrypt password hash
    (User has no `select: false` on `password` — verified against
    models/user.ts). Reproduced here as-is via `populate_order()`; NOT
    filtered out. This is a confirmed, pre-existing security-sensitive
    behavior — flag for a new, higher-priority RFOMS-2 follow-up rather
    than silently fixed during migration.
  - Checkout totals are always computed server-side from the restaurant's
    own menu-item prices, never trusted from the client (preserved).
  - The webhook only reacts to "checkout.session.completed"; every other
    Stripe event type is a silent no-op 200 (confirmed gap, unchanged).

One deliberate, FLAGGED deviation from a literal port: Node's catch-all in
createCheckoutSession does `res.status(500).json({ message: error.raw.message })`.
When the thrown error is not a genuine Stripe error (e.g. "Restaurant not
found"), `error.raw` is undefined and that line itself throws inside the
catch block — an unhandled rejection with no try/catch around it, which
hangs the request (or crashes the process) rather than returning any
response. That is a latent implementation defect, not confirmed business
behavior, and literally reproducing it would mean building an endpoint that
hangs on a bad restaurantId. Instead, non-Stripe errors here raise a clean,
logged AppError (still a 500, still `{"message": ...}` JSON); only genuine
Stripe errors get a Stripe-specific message extracted.
"""

from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from app.core.errors import AppError, PlainTextAppError
from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import mongo_to_jsonable
from app.services.stripe_client import StripeClient, StripeError

logger = logging.getLogger(__name__)


class WebhookSignatureError(PlainTextAppError):
    """Mirrors Node's 400 `Webhook error: <message>` plain-text response."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)


async def populate_order(
    order: dict[str, Any],
    restaurant_repository: RestaurantRepository,
    user_repository: UserRepository,
) -> dict[str, Any]:
    """
    Mirrors Mongoose's `.populate("restaurant").populate("user")` — replaces
    the `restaurant`/`user` ref fields with the full referenced document.
    Shared by OrderService.get_my_orders and RestaurantService's
    get_my_restaurant_orders (both populate the same way in Node).
    """
    order = dict(order)
    restaurant_ref = order.get("restaurant")
    user_ref = order.get("user")
    order["restaurant"] = (
        await restaurant_repository.get_by_id(str(restaurant_ref)) if restaurant_ref else None
    )
    order["user"] = await user_repository.get_by_id(str(user_ref)) if user_ref else None
    return order


class OrderService:
    def __init__(
        self,
        order_repository: OrderRepository,
        restaurant_repository: RestaurantRepository,
        user_repository: UserRepository,
        stripe_client: StripeClient,
        frontend_url: str,
    ):
        self._orders = order_repository
        self._restaurants = restaurant_repository
        self._users = user_repository
        self._stripe = stripe_client
        self._frontend_url = frontend_url

    # ---- GET /api/order ---------------------------------------------------

    async def get_my_orders(self, user_id: str) -> list[dict[str, Any]]:
        """Mirrors OrderController.getMyOrders."""
        orders = await self._orders.list_by_user(user_id)
        populated = [await populate_order(o, self._restaurants, self._users) for o in orders]
        return mongo_to_jsonable(populated)

    # ---- POST /api/order/checkout/create-checkout-session -----------------

    async def create_checkout_session(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Mirrors OrderController.createCheckoutSession + createLineItems."""
        restaurant_id = payload.get("restaurantId")
        restaurant = await self._restaurants.get_by_id(restaurant_id) if restaurant_id else None
        if not restaurant:
            # See module docstring: Node's equivalent path here is a latent
            # crash bug, not confirmed behavior — this is a deliberate,
            # flagged deviation to a clean, logged 500 instead.
            raise AppError("Restaurant not found", status_code=500)

        cart_items = payload.get("cartItems", [])
        delivery_details = payload.get("deliveryDetails", {})
        menu_items_by_id = {
            str(item.get("_id")): item for item in restaurant.get("menuItems", [])
        }

        line_items: list[dict[str, Any]] = []
        stored_cart_items: list[dict[str, Any]] = []
        subtotal = 0
        for cart_item in cart_items:
            menu_item_id = str(cart_item.get("menuItemId"))
            menu_item = menu_items_by_id.get(menu_item_id)
            if menu_item is None:
                # Mirrors createLineItems' `throw new Error("Menu item not
                # found: ...")`, also caught by the same generic path.
                raise AppError(f"Menu item not found: {menu_item_id}", status_code=500)

            quantity = int(cart_item.get("quantity", 0))
            price = menu_item["price"]
            subtotal += price * quantity

            line_items.append(
                {
                    "price_data": {
                        "currency": "gbp",
                        "unit_amount": price,
                        "product_data": {"name": menu_item["name"]},
                    },
                    "quantity": quantity,
                }
            )
            stored_cart_items.append(
                {
                    "menuItemId": menu_item_id,
                    "name": cart_item.get("name", menu_item["name"]),
                    "quantity": quantity,
                }
            )

        delivery_price = int(restaurant.get("deliveryPrice", 0))
        total_amount = subtotal + delivery_price

        order_document = {
            "restaurant": restaurant["_id"],
            "user": ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id,
            "status": "placed",
            "deliveryDetails": delivery_details,
            "cartItems": stored_cart_items,
            "totalAmount": total_amount,
        }
        order_id = await self._orders.create(order_document)

        try:
            session = self._stripe.create_checkout_session(
                line_items=line_items,
                delivery_price=delivery_price,
                order_id=order_id,
                restaurant_id=str(restaurant["_id"]),
                frontend_url=self._frontend_url,
            )
        except StripeError as exc:
            logger.error("Stripe session creation failed for order %s: %s", order_id, exc)
            raise AppError(getattr(exc, "user_message", None) or str(exc), status_code=500) from exc

        session_url = session.get("url")
        if not session_url:
            raise AppError("Error creating stripe session", status_code=500)

        return {"url": session_url}

    # ---- POST /api/order/checkout/webhook ----------------------------------

    async def handle_stripe_webhook(self, raw_body: bytes, signature: str | None) -> None:
        """Mirrors OrderController.stripeWebhookHandler."""
        try:
            event = self._stripe.construct_event(raw_body, signature)
        except StripeError as exc:
            logger.warning("Stripe webhook signature verification failed: %s", exc)
            raise WebhookSignatureError(f"Webhook error: {exc}") from exc

        if event.get("type") != "checkout.session.completed":
            return  # confirmed no-op for every other event type

        session_object = event.get("data", {}).get("object", {})
        order_id = (session_object.get("metadata") or {}).get("orderId")

        if not order_id or not ObjectId.is_valid(order_id):
            logger.error("Invalid orderId in Stripe webhook: %r", order_id)
            raise AppError("Invalid order ID format in webhook metadata", status_code=400)

        order = await self._orders.get_by_id(order_id)
        if not order:
            logger.error("Order not found for ID: %s", order_id)
            raise AppError("Order not found", status_code=404)

        updated = await self._orders.update_status(
            order_id, status="paid", total_amount=session_object.get("amount_total")
        )
        if not updated:
            raise AppError("Error processing order update", status_code=500)
