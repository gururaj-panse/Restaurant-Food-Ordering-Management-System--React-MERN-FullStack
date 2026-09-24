"""
Authentication Module — service stub.

Target module per TARGET_ARCHITECTURE_C4_DIAGRAM.md (Rev. 2). Current source:
food-ordering-backend/src/routes/auth.ts (logic embedded directly in the
route file — no controller to port from, per MODULE_3_CURRENT_STATE_AND_GAPS.md
gap #1). Operations below match the 6 confirmed endpoints exactly; none are
implemented yet.
"""

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.core.errors import AppError, NotImplementedFeatureError
from app.core.security import verify_password
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository
        self._settings = get_settings()

    def _create_token(self, user_id: str) -> str:
        secret = self._settings.JWT_SECRET_KEY or "fallback_secret_key_12345"
        payload = {
            "userId": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        }
        return jwt.encode(payload, secret, algorithm="HS256")

    async def register(self, email: str, password: str, name: str):
        existing = await self._users.get_by_email(email)
        if existing:
            raise AppError("User already exists", status_code=400)

        user_id = await self._users.create(email=email, password=password, name=name)
        token = self._create_token(user_id)
        return {
            "userId": user_id,
            "token": token,
            "user": {
                "id": user_id,
                "email": email,
                "name": name,
            },
        }

    async def login(self, email: str, password: str):
        user = await self._users.get_by_email(email)
        if not user or not verify_password(password, user.get("password", "")):
            raise AppError("Invalid Credentials", status_code=400)

        user_id = str(user["_id"])
        token = self._create_token(user_id)
        return {
            "userId": user_id,
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user_id,
                "email": user["email"],
                "name": user.get("name") or "",
            },
        }

    async def google_authorize_url(self) -> str:
        raise NotImplementedFeatureError("GET /api/auth/google")

    async def google_callback(self, code: str):
        raise NotImplementedFeatureError("GET /api/auth/callback/google")

    async def validate_token(self, user_id: str):
        return {"userId": user_id}

    async def logout(self):
        return {"message": "Logged out successfully"}

