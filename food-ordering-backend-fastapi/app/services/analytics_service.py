"""
Analytics Module — service stub.

Current source: food-ordering-backend/src/controllers/AnalyticsController.ts.
Scope (global vs. per-restaurant) is Open Question #2 — not decided here.
The four unauthenticated debug/test endpoints are intentionally NOT stubbed
below; their disposition is Open Question #3, gated behind Jira RFOMS-2.
"""

from app.core.errors import NotImplementedFeatureError
from app.repositories.order_repository import OrderRepository
from app.repositories.restaurant_repository import RestaurantRepository


class AnalyticsService:
    def __init__(
        self,
        order_repository: OrderRepository,
        restaurant_repository: RestaurantRepository,
    ):
        self._orders = order_repository
        self._restaurants = restaurant_repository

    async def get_analytics(self, time_range: str):
        raise NotImplementedFeatureError("GET /api/business-insights")
