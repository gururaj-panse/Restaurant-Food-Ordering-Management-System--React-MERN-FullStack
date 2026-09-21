"""
Order & Payment Module router. Matches food-ordering-backend/src/routes/
OrderRoute.ts (3 endpoints). Business logic implemented in OrderService
(Jira RFOMS-11/12/13) — see that module's docstring for the confirmed
behaviors preserved and the one flagged deviation.

The webhook route reads the raw body via `await request.body()` rather than
a declared Pydantic model — this is what preserves the raw-body requirement
(PRD.md BM-02) for Stripe signature verification; FastAPI has no global
JSON-body-consuming middleware in this skeleton, so no special ordering is
needed the way Express required (see app/core/middleware.py — only CORS
and request logging are registered, neither reads the request body).

`create_checkout_session`'s body stays a raw `dict` (not a declared Pydantic
request model) deliberately: no express-validator chain is wired to this
route in the current Node backend either, so malformed input reaches the
service unvalidated today. A `CheckoutSessionRequest` schema exists in
app/schemas/order.py for documentation/tests but is not used to validate
this route's body, to avoid silently tightening a contract that is
currently unvalidated (see the Module 3 chat-reviewed migration plan for
this module).
"""

from fastapi import APIRouter, Depends, Header, Request, Response

from app.api.deps import get_current_user_id, get_order_service
from app.schemas.order import CheckoutSessionResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/api/order", tags=["order"])


@router.get("")
async def get_my_orders(
    user_id: str = Depends(get_current_user_id),
    service: OrderService = Depends(get_order_service),
):
    return await service.get_my_orders(user_id)


@router.post("/checkout/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    payload: dict,
    user_id: str = Depends(get_current_user_id),
    service: OrderService = Depends(get_order_service),
):
    return await service.create_checkout_session(user_id, payload)


@router.post("/checkout/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    service: OrderService = Depends(get_order_service),
):
    raw_body = await request.body()
    await service.handle_stripe_webhook(raw_body, stripe_signature)
    return Response(status_code=200)  # mirrors Node's res.status(200).send() — empty body
