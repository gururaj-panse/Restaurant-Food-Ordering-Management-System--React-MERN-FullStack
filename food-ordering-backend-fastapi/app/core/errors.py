"""
Centralized error handling.

The current Node backend has NO centralized error handler (CURRENT_STATE.md
§9) and two inconsistent validation-error shapes (`{errors:[...]}` vs
`{message:[...]}`) — which shape the target should use is Open Question #6,
gated behind Jira Story RFOMS-2, and is NOT decided here. The shapes below
are a reasonable, clearly-labeled placeholder so the skeleton has *a*
consistent behavior to test against, not the approved final contract.
"""

import logging

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for application-raised HTTP errors."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class PlainTextAppError(AppError):
    """
    An AppError whose current-system equivalent responds with a plain-text
    body rather than the standard `{"message": ...}` JSON shape.

    Used by the Order module's Stripe webhook signature failure, which
    mirrors Node's `res.status(400).send('Webhook error: ' + error.message)`
    — a plain-text body, not JSON (CURRENT_STATE.md-confirmed via
    OrderController.ts's stripeWebhookHandler).
    """


class EmptyBodyAppError(AppError):
    """
    An AppError whose current-system equivalent responds with an empty
    body rather than the standard `{"message": ...}` JSON shape.

    Used by the Order module's restaurant-ownership check, which mirrors
    Node's `res.status(401).send()` in
    MyRestaurantController.updateOrderStatus — an empty body, not JSON.
    """


class NotImplementedFeatureError(AppError):
    """
    Raised by stub service methods during Module 3's structure-only phase.
    Every route currently wired to a stub will surface this until its
    business logic is migrated in a later batch (see docs/module-3-development-plan.md §3).
    """

    def __init__(self, feature: str):
        super().__init__(
            message=f"'{feature}' is not yet migrated — structure-only skeleton (Module 3).",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


def register_exception_handlers(app: FastAPI) -> None:
    # Registered before the generic AppError handler so FastAPI's
    # most-specific-class lookup picks these for their respective
    # subclasses instead of the default JSON `{"message": ...}` shape.
    @app.exception_handler(PlainTextAppError)
    async def plain_text_app_error_handler(_: Request, exc: PlainTextAppError) -> PlainTextResponse:
        return PlainTextResponse(content=exc.message, status_code=exc.status_code)

    @app.exception_handler(EmptyBodyAppError)
    async def empty_body_app_error_handler(_: Request, exc: EmptyBodyAppError) -> Response:
        return Response(status_code=exc.status_code)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # PLACEHOLDER shape — see module docstring. Not the approved contract.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": "Something went wrong"},
        )
