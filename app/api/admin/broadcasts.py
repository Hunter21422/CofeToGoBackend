from fastapi import APIRouter

from app.api.deps import Owner, SessionDep
from app.schemas.marketing import BroadcastCreate, BroadcastRead, BroadcastSegment, BroadcastUpdate, SegmentPreviewOut
from app.services import MarketingService
router=APIRouter(prefix="/admin/broadcasts", tags=["admin: маркетинг"])
@router.get("", response_model=list[BroadcastRead])
async def list_broadcasts(session: SessionDep, ctx: Owner):
    items, _ = await MarketingService(session).list_broadcasts(100, 0)
    return items
@router.post("", response_model=BroadcastRead, status_code=201)
async def create_broadcast(data: BroadcastCreate, session: SessionDep, ctx: Owner):
    return await MarketingService(session).create_broadcast(data, ctx.user.id)
@router.post("/segment-preview", response_model=SegmentPreviewOut)
async def segment_preview(data: BroadcastSegment, session: SessionDep, ctx: Owner):
    return SegmentPreviewOut(count=await MarketingService(session).segment_count(data))
@router.patch("/{broadcast_id}", response_model=BroadcastRead)
async def update_broadcast(broadcast_id: int, data: BroadcastUpdate, session: SessionDep, ctx: Owner):
    return await MarketingService(session).update_broadcast(broadcast_id, data)
@router.post("/{broadcast_id}/send", response_model=BroadcastRead)
async def send_broadcast(broadcast_id: int, session: SessionDep, ctx: Owner):
    return await MarketingService(session).send_now(broadcast_id)
@router.delete("/{broadcast_id}", status_code=204)
async def delete_broadcast(broadcast_id: int, session: SessionDep, ctx: Owner):
    await MarketingService(session).delete_broadcast(broadcast_id)
