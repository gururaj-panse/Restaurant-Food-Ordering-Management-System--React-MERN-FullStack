import re
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.repositories.base import BaseRepository


def _with_menu_item_ids(menu_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Motor has no equivalent of Mongoose's auto/declared sub-document `_id`
    generation — that is a Mongoose-only convenience. The current schema
    (restaurant.ts) explicitly declares a generated ObjectId per menu item,
    so it must be generated explicitly here or menu items would silently
    end up with no `_id` at all (see the mismatch noted before implementing).
    """
    result = []
    for item in menu_items:
        item = dict(item)
        item.setdefault("_id", ObjectId())
        result.append(item)
    return result


class RestaurantRepository(BaseRepository):
    def __init__(self, collection: AsyncIOMotorCollection):
        super().__init__(collection)

    async def get_by_owner(self, user_id: str) -> dict[str, Any] | None:
        """Mirrors Restaurant.findOne({ user: req.userId })."""
        return await self._collection.find_one({"user": user_id})

    async def distinct_cities(self) -> list[str]:
        """Mirrors Restaurant.distinct("city")."""
        return await self._collection.distinct("city")

    async def create(self, document: dict[str, Any]) -> str:
        document = dict(document)
        document["menuItems"] = _with_menu_item_ids(document.get("menuItems", []))
        return await self.insert(document)

    async def update_menu_and_profile(self, restaurant_id: str, updates: dict[str, Any]) -> bool:
        updates = dict(updates)
        if "menuItems" in updates:
            updates["menuItems"] = _with_menu_item_ids(updates["menuItems"])
        return await self.update_by_id(restaurant_id, updates)

    async def search(
        self,
        city: str,
        search_query: str = "",
        selected_cuisines: str = "",
        sort_option: str = "lastUpdated",
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Mirrors RestaurantController.searchRestaurant exactly, including its
        confirmed quirks:
          - city "all" or empty skips the city filter
          - selectedCuisines uses $all (AND), not $in (OR)
          - sort is ALWAYS ascending regardless of field (even for the
            non-existent "bestMatch" field the frontend defaults to —
            not "fixed" here, reproduced as-is per Open Question #4)
          - page size is a fixed 10, not configurable
        """
        # NOTE: metacharacters in city/cuisines/searchQuery are NOT escaped
        # below — this reproduces the current Node backend's behavior
        # exactly (new RegExp(input, "i"), unescaped — a confirmed gap,
        # CURRENT_STATE.md §9). Escaping would change matching behavior for
        # inputs containing regex metacharacters; that's a fix, not a
        # preservation, and stays gated behind RFOMS-2 like every other
        # confirmed gap in this project. Not decided here.
        query: dict[str, Any] = {}

        if city and city.lower() != "all":
            query["city"] = re.compile(city, re.IGNORECASE)

        if selected_cuisines:
            cuisine_patterns = [
                re.compile(c, re.IGNORECASE) for c in selected_cuisines.split(",")
            ]
            query["cuisines"] = {"$all": cuisine_patterns}

        if search_query:
            search_pattern = re.compile(search_query, re.IGNORECASE)
            query["$or"] = [
                {"restaurantName": search_pattern},
                {"cuisines": {"$in": [search_pattern]}},
            ]

        page_size = 10
        skip = (page - 1) * page_size

        cursor = (
            self._collection.find(query)
            .sort(sort_option, 1)  # always ascending — confirmed, preserved as-is
            .skip(skip)
            .limit(page_size)
        )
        results = await cursor.to_list(length=page_size)
        total = await self._collection.count_documents(query)
        return results, total
