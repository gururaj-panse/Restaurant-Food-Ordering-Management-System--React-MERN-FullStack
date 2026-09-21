"""
User Profile Module — service stub.

Current source: food-ordering-backend/src/controllers/MyUserController.ts.
"""

from app.core.errors import NotImplementedFeatureError
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def get_current_user(self, user_id: str):
        raise NotImplementedFeatureError("GET /api/my/user")

    async def update_current_user(self, user_id: str, updates: dict):
        raise NotImplementedFeatureError("PUT /api/my/user")
