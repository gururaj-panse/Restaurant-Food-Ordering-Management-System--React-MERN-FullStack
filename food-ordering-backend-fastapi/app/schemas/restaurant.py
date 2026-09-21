"""
Restaurant / MenuItem schemas — field-for-field match to CURRENT_STATE.md §4
/ TARGET_ERD.md `RESTAURANT` and embedded `MENU_ITEM`. `deliveryPrice` and
menu item `price` remain integer pence, per the confirmed cross-cutting rule
(CURRENT_STATE.md §8) — no unit conversion happens in these schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import PyObjectId


class MenuItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId | None = None
    name: str
    price: int  # integer pence


class RestaurantBase(BaseModel):
    restaurantName: str
    city: str
    country: str
    deliveryPrice: int  # integer pence
    estimatedDeliveryTime: int  # minutes
    cuisines: list[str]
    menuItems: list[MenuItem] = []
    imageUrl: str
    lastUpdated: datetime


class RestaurantInDB(RestaurantBase):
    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId | None = None
    user: PyObjectId | None = None  # ref User; NOT required at schema level (confirmed)


class RestaurantPublic(RestaurantBase):
    id: PyObjectId
    user: PyObjectId | None = None
