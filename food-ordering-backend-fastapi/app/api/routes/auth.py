"""
Authentication Module router — structure only. Every handler delegates to
AuthService, whose methods currently raise NotImplementedFeatureError (see
app/services/auth_service.py). Paths/methods match the confirmed 6 endpoints
in food-ordering-backend/src/routes/auth.ts exactly.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_current_user_id
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/google")
async def google_login(service: AuthService = Depends(get_auth_service)):
    return await service.google_authorize_url()


@router.get("/callback/google")
async def google_callback(
    code: str | None = None, service: AuthService = Depends(get_auth_service)
):
    return await service.google_callback(code)


@router.post("/register", status_code=201)
async def register(
    payload: RegisterRequest, service: AuthService = Depends(get_auth_service)
):
    return await service.register(payload.email, payload.password, payload.name)


@router.post("/login")
async def login(
    payload: LoginRequest, service: AuthService = Depends(get_auth_service)
):
    return await service.login(payload.email, payload.password)


@router.get("/validate-token")
async def validate_token(
    user_id: str = Depends(get_current_user_id),
    service: AuthService = Depends(get_auth_service),
):
    return await service.validate_token(user_id)


@router.post("/logout")
async def logout(service: AuthService = Depends(get_auth_service)):
    return await service.logout()
