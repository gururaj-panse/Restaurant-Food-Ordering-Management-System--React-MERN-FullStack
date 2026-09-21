"""
Order / CartItem / DeliveryDetails schemas — field-for-field match to
CURRENT_STATE.md §4 / TARGET_ERD.md `ORDER`, embedded `ORDER_ITEM`, embedded
`DELIVERY_DETAILS`.

Two confirmed gaps are preserved AS-IS, not silently fixed:
  - DeliveryDetails has no `country` field, though the frontend collects one
    (Open Question #5).
  - CartItem has no `price` field — only the order-level `totalAmount`
    aggregate survives (confirmed gap, CURRENT_STATE.md §4).
Resolving either is gated behind Jira Story RFOMS-2 and is NOT done here.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import PyObjectId

OrderStatus = Literal["placed", "paid", "inProgress", "outForDelivery", "delivered"]


class DeliveryDetails(BaseModel):
    email: str
    name: str
    addressLine1: str
    city: str
    # NOTE: no `country` — confirmed gap, preserved intentionally.


class CartItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId | None = None
    menuItemId: str  # plain string, NOT a Mongo ref (confirmed — no referential integrity)
    name: str
    quantity: int
    # NOTE: no `price` — confirmed gap, preserved intentionally.


class OrderBase(BaseModel):
    deliveryDetails: DeliveryDetails
    cartItems: list[CartItem]
    totalAmount: int | None = None  # integer pence
    status: OrderStatus
    createdAt: datetime


class OrderInDB(OrderBase):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId | None = None
    restaurant: PyObjectId | None = None  # ref Restaurant; NOT required at schema level
    user: PyObjectId | None = None  # ref User; NOT required at schema level


class OrderPublic(OrderBase):
    id: PyObjectId
    restaurant: PyObjectId | None = None
    user: PyObjectId | None = None


class CartItemRequest(BaseModel):
    """Client-submitted cart item — `quantity` arrives as a string, matching
    the current frontend/Node contract (CheckoutSessionRequest in
    OrderController.ts); cast to int at the point it's persisted/priced."""

    menuItemId: str
    name: str
    quantity: str


class DeliveryDetailsRequest(BaseModel):
    email: str
    name: str
    addressLine1: str
    city: str


class CheckoutSessionRequest(BaseModel):
    """
    Mirrors OrderController.ts's `CheckoutSessionRequest` type exactly.

    NOTE: this type exists in Node only as a TypeScript compile-time
    annotation — it is never actually validated at runtime (no
    express-validator chain is wired to this route, confirmed). Declaring
    it as a Pydantic model here is a deliberate, FLAGGED strengthening: the
    route still accepts a raw dict (see app/api/routes/order.py) rather than
    using this as the route's request body model, so malformed input is NOT
    newly rejected — preserving the current "accepts anything" contract.
    This schema exists for documentation and for optional use in tests.
    """

    cartItems: list[CartItemRequest]
    deliveryDetails: DeliveryDetailsRequest
    restaurantId: str


class CheckoutSessionResponse(BaseModel):
    url: str
