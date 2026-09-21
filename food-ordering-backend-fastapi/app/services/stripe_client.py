"""
Thin wrapper around the `stripe` SDK.

Isolates the Order module's two Stripe touchpoints — matches
food-ordering-backend/src/controllers/OrderController.ts's `STRIPE` usage —
so OrderService can be unit tested against a fake/mock client instead of
importing the `stripe` SDK (and making real network calls) directly.
"""

from typing import Any

import stripe

StripeError = stripe.error.StripeError


class StripeClient:
    def __init__(self, api_key: str | None, webhook_secret: str | None):
        self._api_key = api_key
        self._webhook_secret = webhook_secret

    def create_checkout_session(
        self,
        line_items: list[dict[str, Any]],
        delivery_price: int,
        order_id: str,
        restaurant_id: str,
        frontend_url: str,
    ) -> dict[str, Any]:
        """Mirrors OrderController.ts's createSession()."""
        stripe.api_key = self._api_key
        return stripe.checkout.Session.create(
            line_items=line_items,
            shipping_options=[
                {
                    "shipping_rate_data": {
                        "display_name": "Delivery",
                        "type": "fixed_amount",
                        "fixed_amount": {
                            "amount": delivery_price,  # already integer pence
                            "currency": "gbp",
                        },
                    }
                }
            ],
            mode="payment",
            metadata={"orderId": order_id, "restaurantId": restaurant_id},
            success_url=f"{frontend_url}/order-status?success=true",
            cancel_url=f"{frontend_url}/detail/{restaurant_id}?cancelled=true",
        )

    def construct_event(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        """Mirrors STRIPE.webhooks.constructEvent(req.body, sig, secret)."""
        stripe.api_key = self._api_key
        return stripe.Webhook.construct_event(payload, signature, self._webhook_secret)
