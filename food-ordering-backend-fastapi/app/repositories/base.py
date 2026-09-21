"""
Generic Motor-backed repository base.

Deliberately mechanical: no query here encodes a business rule (no cuisine
filtering, no ownership check, no price handling). Those belong in the
service layer once business logic is migrated (see docs/module-3-development-plan.md §3).
"""

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection


class BaseRepository:
    def __init__(self, collection: AsyncIOMotorCollection):
        self._collection = collection

    async def get_by_id(self, doc_id: str) -> dict[str, Any] | None:
        if not ObjectId.is_valid(doc_id):
            return None
        return await self._collection.find_one({"_id": ObjectId(doc_id)})

    async def insert(self, document: dict[str, Any]) -> str:
        result = await self._collection.insert_one(document)
        return str(result.inserted_id)

    async def update_by_id(self, doc_id: str, updates: dict[str, Any]) -> bool:
        if not ObjectId.is_valid(doc_id):
            return False
        result = await self._collection.update_one(
            {"_id": ObjectId(doc_id)}, {"$set": updates}
        )
        return result.matched_count > 0
