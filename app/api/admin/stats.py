from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Manager, SessionDep

from app.models.enums import StaffRole
from app.schemas.stats import DashboardOut, StatsFilter
from app.services import StatsService
router=APIRouter(prefix="/admin/stats", tags=["admin: аналитика"])
@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(f: Annotated[StatsFilter, Query()], session: SessionDep, ctx: Manager):
    if ctx.staff.role != StaffRole.OWNER and ctx.staff.location_id:
        f.location_id = ctx.staff.location_id
    return await StatsService(session).dashboard(f)
