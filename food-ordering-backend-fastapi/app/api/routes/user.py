"""
User Profile Module router — structure only. Matches
food-ordering-backend/src/routes/MyUserRoute.ts (3 endpoints).
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_user_service
from app.services.user_service import UserService

router = APIRouter(prefix="/api/my/user", tags=["user"])


@router.get("")
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    service: UserService = Depends(get_user_service),
):
    return await service.get_current_user(user_id)


@router.post("")
async def create_current_user(
    user_id: str = Depends(get_current_user_id),
    service: UserService = Depends(get_user_service),
):
    # NOTE: confirmed as a no-op in the current backend (checks existence,
    # never actually creates) — reproduced as a stub for structural parity,
    # not implemented as "real" creation logic (see CURRENT_STATE.md §3).
    return await service.get_current_user(user_id)


@router.put("")
async def update_current_user(
    updates: dict,
    user_id: str = Depends(get_current_user_id),
    service: UserService = Depends(get_user_service),
):
    return await service.update_current_user(user_id, updates)
