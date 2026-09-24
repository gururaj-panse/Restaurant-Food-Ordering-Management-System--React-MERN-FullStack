"""
Shared FastAPI dependencies — repository/service factories and the
authenticated-user dependency.

`get_current_user_id` is intentionally a STUB. Wiring a fake or partial JWT
check here would misrepresent security state; every "protected" route in
this skeleton depends on it and will surface a clear 501 until Jira Story
RFOMS-7 (the auth dependency, "Authentication Module") is implemented.
"""

from fastapi import Cookie, Depends, Header

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.db.mongodb import mongodb
from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository
from app.repositories.user_repository import UserRepository
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.order_service import OrderService
from app.services.restaurant_service import RestaurantService
from app.services.stripe_client import StripeClient
from app.services.user_service import UserService


def get_user_repository() -> UserRepository:
    return UserRepository(mongodb.users)


def get_restaurant_repository() -> RestaurantRepository:
    return RestaurantRepository(mongodb.restaurants)


def get_order_repository() -> OrderRepository:
    return OrderRepository(mongodb.orders)


def get_auth_service() -> AuthService:
    return AuthService(get_user_repository())


def get_user_service() -> UserService:
    return UserService(get_user_repository())


def get_restaurant_service() -> RestaurantService:
    return RestaurantService(
        get_restaurant_repository(), get_order_repository(), get_user_repository()
    )


def get_stripe_client(settings: Settings = Depends(get_settings)) -> StripeClient:
    return StripeClient(settings.STRIPE_API_KEY, settings.STRIPE_WEBHOOK_SECRET)


def get_order_service(
    settings: Settings = Depends(get_settings),
    stripe_client: StripeClient = Depends(get_stripe_client),
) -> OrderService:
    return OrderService(
        order_repository=get_order_repository(),
        restaurant_repository=get_restaurant_repository(),
        user_repository=get_user_repository(),
        stripe_client=stripe_client,
        frontend_url=settings.FRONTEND_URL,
    )


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService(get_order_repository(), get_restaurant_repository())


async def get_current_user_id(
    authorization: str | None = Header(default=None),
    session_id: str | None = Cookie(default=None),
) -> str:
    token: str | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif session_id:
        token = session_id

    if not token:
        raise AppError("unauthorized", status_code=401)

    try:
        import jwt
        settings = get_settings()
        secret = settings.JWT_SECRET_KEY or "fallback_secret_key_12345"
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return str(payload["userId"])
    except Exception:
        raise AppError("unauthorized", status_code=401)
