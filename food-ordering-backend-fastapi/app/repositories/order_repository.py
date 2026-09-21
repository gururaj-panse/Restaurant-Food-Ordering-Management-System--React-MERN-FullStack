from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.repositories.base import BaseRepository

# Confirmed current filter in OrderController.getMyOrders — matches the
# FULL status enum, which is a confirmed no-op (excludes nothing). Kept
# explicit and literal rather than simplified to "no filter", so the
# no-op-ness stays visible in code, not silently optimized away.
_ACTIVE_STATUSES = ["placed", "paid", "inProgress", "outForDelivery", "delivered"]


def _with_cart_item_ids(cart_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Same Motor-vs-Mongoose gap as menu items: cart-item sub-document `_id`s
    are a Mongoose default-behavior artifact (order.ts does not declare
    `_id: false`), not something Motor provides automatically. Generated
    explicitly here to preserve TARGET_ERD.md's confirmed key structure.
    """
    result = []
    for item in cart_items:
        item = dict(item)
        item.setdefault("_id", ObjectId())
        result.append(item)
    return result


class OrderRepository(BaseRepository):
    def __init__(self, collection: AsyncIOMotorCollection):
        super().__init__(collection)

    async def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Mirrors Order.find({ user: req.userId, status: {$in: [...]} })."""
        return await self._collection.find(
            {"user": user_id, "status": {"$in": _ACTIVE_STATUSES}}
        ).to_list(length=None)

    async def list_by_restaurant(self, restaurant_id: str) -> list[dict[str, Any]]:
        """Mirrors Order.find({ restaurant: restaurant._id }) — includes
        unpaid "placed" orders, unlike list_by_user's (no-op) filter."""
        return await self._collection.find({"restaurant": restaurant_id}).to_list(
            length=None
        )

    async def create(self, document: dict[str, Any]) -> str:
        document = dict(document)
        document["cartItems"] = _with_cart_item_ids(document.get("cartItems", []))
        return await self.insert(document)

    async def update_status(self, order_id: str, status: str, total_amount: int | None = None) -> bool:
        """
        Mirrors both write paths that touch status/totalAmount:
        MyRestaurantController.updateOrderStatus (status only) and the
        Stripe webhook handler (status="paid" + totalAmount together).
        """
        updates: dict[str, Any] = {"status": status}
        if total_amount is not None:
            updates["totalAmount"] = total_amount
        return await self.update_by_id(order_id, updates)
