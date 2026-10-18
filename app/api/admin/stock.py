from fastapi import APIRouter

from app.api.deps import Barista, SessionDep, check_location
from app.schemas.stock import StockItemCreate, StockItemRead
from app.services import StockService
router=APIRouter(prefix="/admin/locations/{location_id}/stock", tags=["admin: стоп-лист"])
@router.get("", response_model=list[StockItemRead])
async def list_stock(location_id: int, session: SessionDep, ctx: Barista):
    check_location(ctx, location_id)
    return await StockService(session).list_for_location(location_id)
@router.post("", response_model=StockItemRead, status_code=201)
async def stop_item(location_id: int, data: StockItemCreate, session: SessionDep, ctx: Barista):
    check_location(ctx, location_id)
    return await StockService(session).stop(location_id, data, ctx.staff.id)
@router.delete("/{item_id}", status_code=204)
async def resume_item(location_id: int, item_id: int, session: SessionDep, ctx: Barista):
    check_location(ctx, location_id)
    await StockService(session).resume(location_id, item_id)
