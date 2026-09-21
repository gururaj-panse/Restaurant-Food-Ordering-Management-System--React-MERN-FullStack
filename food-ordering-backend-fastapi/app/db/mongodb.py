"""
MongoDB connection lifecycle (Motor — confirmed choice for this skeleton).

Mirrors the confirmed current collections one-for-one (CURRENT_STATE.md §4,
TARGET_ERD.md): users, restaurants, orders. No schema/document shape is
defined here yet — repositories will map to/from Pydantic schemas once
business logic is migrated. This module only owns connect/close and
collection handles, matching the "async connection lifecycle" gap noted in
MODULE_3_CURRENT_STATE_AND_GAPS.md §12.
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class MongoDB:
    client: AsyncIOMotorClient | None = None
    database: AsyncIOMotorDatabase | None = None

    async def connect(self, uri: str) -> None:
        self.client = AsyncIOMotorClient(uri)
        self.database = self.client.get_default_database()
        # Fail fast on a bad connection string / unreachable server rather
        # than discovering it on the first request.
        await self.client.admin.command("ping")
        logger.info("Connected to MongoDB")
        await self.ensure_indexes()

    async def ensure_indexes(self) -> None:
        """
        Reproduces the ONE confirmed index in the current system
        (Mongoose `unique: true` on User.email — CURRENT_STATE.md §4).
        No other index is confirmed to exist on Restaurant or Order, so
        none is added here — that would be an unapproved schema change.
        """
        await self.users.create_index("email", unique=True)

    async def close(self) -> None:
        if self.client is not None:
            self.client.close()
            logger.info("MongoDB connection closed")

    def _require_database(self) -> AsyncIOMotorDatabase:
        if self.database is None:
            raise RuntimeError(
                "MongoDB is not connected — set MONGODB_URI (or "
                "MONGODB_CONNECTION_STRING) before using a DB-backed route."
            )
        return self.database

    @property
    def users(self):
        return self._require_database()["users"]

    @property
    def restaurants(self):
        return self._require_database()["restaurants"]

    @property
    def orders(self):
        return self._require_database()["orders"]


mongodb = MongoDB()
