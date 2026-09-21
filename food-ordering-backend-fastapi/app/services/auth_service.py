"""
Authentication Module — service stub.

Target module per TARGET_ARCHITECTURE_C4_DIAGRAM.md (Rev. 2). Current source:
food-ordering-backend/src/routes/auth.ts (logic embedded directly in the
route file — no controller to port from, per MODULE_3_CURRENT_STATE_AND_GAPS.md
gap #1). Operations below match the 6 confirmed endpoints exactly; none are
implemented yet.
"""

from app.core.errors import NotImplementedFeatureError
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def register(self, email: str, password: str, name: str):
        raise NotImplementedFeatureError("POST /api/auth/register")

    async def login(self, email: str, password: str):
        raise NotImplementedFeatureError("POST /api/auth/login")

    async def google_authorize_url(self) -> str:
        raise NotImplementedFeatureError("GET /api/auth/google")

    async def google_callback(self, code: str):
        raise NotImplementedFeatureError("GET /api/auth/callback/google")

    async def validate_token(self, user_id: str):
        raise NotImplementedFeatureError("GET /api/auth/validate-token")

    async def logout(self):
        raise NotImplementedFeatureError("POST /api/auth/logout")
