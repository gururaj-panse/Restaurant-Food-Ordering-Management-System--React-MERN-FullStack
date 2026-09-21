"""
Restaurant & Menu Module router (public discovery) — structure only. Matches
food-ordering-backend/src/routes/RestaurantRoute.ts (3 endpoints).
"""

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_restaurant_service
from app.services.restaurant_service import RestaurantService

router = APIRouter(prefix="/api/restaurant", tags=["restaurant"])


@router.get("/cities/all")
async def get_all_cities(service: RestaurantService = Depends(get_restaurant_service)):
    return await service.get_all_cities()


@router.get("/search/{city}")
async def search_restaurants(
    city: str,
    request: Request,
    service: RestaurantService = Depends(get_restaurant_service),
):
    return await service.search_restaurants(city, dict(request.query_params))


@router.get("/{restaurant_id}")
async def get_restaurant(
    restaurant_id: str, service: RestaurantService = Depends(get_restaurant_service)
):
    return await service.get_restaurant(restaurant_id)
