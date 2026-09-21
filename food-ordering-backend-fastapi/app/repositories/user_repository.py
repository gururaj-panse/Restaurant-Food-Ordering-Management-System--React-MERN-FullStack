from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.security import hash_password
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, collection: AsyncIOMotorCollection):
        super().__init__(collection)

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Mirrors User.findOne({ email }) — email is the only unique-indexed field."""
        return await self._collection.find_one({"email": email})

    async def create(
        self,
        email: str,
        password: str,
        name: str | None = None,
        image: str | None = None,
    ) -> str:
        """
        Mirrors `new User({...}).save()`. Password is hashed here, matching
        the current Mongoose pre-save hook — hashing is DB-layer behavior,
        not something the (still-stubbed) service layer should redo.

        No confirmed current path ever updates an existing password, so no
        update-password method exists here — adding one would be inventing
        a feature.
        """
        document = {
            "email": email,
            "password": hash_password(password),
            "name": name,
            "addressLine1": None,
            "city": None,
            "country": None,
            "image": image,
        }
        return await self.insert(document)

    async def update_profile(
        self, user_id: str, name: str, address_line1: str, city: str, country: str
    ) -> bool:
        """Mirrors MyUserController.updateCurrentUser — overwrites all four fields."""
        return await self.update_by_id(
            user_id,
            {
                "name": name,
                "addressLine1": address_line1,
                "city": city,
                "country": country,
            },
        )
