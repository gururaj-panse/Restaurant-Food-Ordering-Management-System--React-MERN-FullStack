"""
Restaurant & Menu Module router (owner-facing) — structure only. Matches
food-ordering-backend/src/routes/MyRestaurantRoute.ts (5 endpoints).

POST/PUT accept the raw multipart request rather than declared Form(...)
fields: the confirmed contract uses bracket-notation array fields
(`cuisines[0]`, `menuItems[0][name]`, `menuItems[0][price]`) that FastAPI's
Form() does not parse natively. Building that parser is real migration work
(Jira RFOMS-45, the "multipart form parsing" sub-task under Story RFOMS-9),
not structure — so it is deliberately deferred rather than approximated here.
"""

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user_id, get_restaurant_service
from app.services.restaurant_service import RestaurantService

router = APIRouter(prefix="/api/my/restaurant", tags=["my-restaurant"])


@router.get("")
async def get_my_restaurant(
    user_id: str = Depends(get_current_user_id),
    service: RestaurantService = Depends(get_restaurant_service),
):
    return await service.get_my_restaurant(user_id)


@router.post("", status_code=201)
async def create_my_restaurant(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    service: RestaurantService = Depends(get_restaurant_service),
):
    return await service.create_my_restaurant(user_id, request, None)


@router.put("")
async def update_my_restaurant(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    service: RestaurantService = Depends(get_restaurant_service),
):
    return await service.update_my_restaurant(user_id, request, None)


@router.get("/order")
async def get_my_restaurant_orders(
    user_id: str = Depends(get_current_user_id),
    service: RestaurantService = Depends(get_restaurant_service),
):
    return await service.get_my_restaurant_orders(user_id)


@router.patch("/order/{order_id}/status")
async def update_order_status(
    order_id: str,
    payload: dict,
    user_id: str = Depends(get_current_user_id),
    service: RestaurantService = Depends(get_restaurant_service),
):
    return await service.update_order_status(user_id, order_id, payload.get("status"))
