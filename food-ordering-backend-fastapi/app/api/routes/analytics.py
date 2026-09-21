"""
Analytics Module router — structure only. Matches
food-ordering-backend/src/routes/AnalyticsRoute.ts's ONE authenticated +
ONE public endpoint.

The four unauthenticated debug/test endpoints (/test, /db-test,
/debug-orders, /debug-restaurants) are intentionally NOT reproduced here —
their disposition is Open Question #3, gated behind Jira RFOMS-2. Porting
them by default would silently resolve an undecided question.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_analytics_service, get_current_user_id
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/business-insights", tags=["analytics"])


@router.get("")
async def get_analytics(
    time_range: str = "30d",
    user_id: str = Depends(get_current_user_id),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return await service.get_analytics(time_range)


@router.get("/public")
async def get_analytics_public(
    time_range: str = "30d",
    service: AnalyticsService = Depends(get_analytics_service),
):
    return await service.get_analytics(time_range)
