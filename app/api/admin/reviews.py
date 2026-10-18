from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Manager, SessionDep
from app.models.enums import StaffRole
from app.schemas.common import Page
from app.schemas.profile import ReviewAdminRead, ReviewFilter, ReviewReplyIn
from app.services import ReviewService
router=APIRouter(prefix="/admin/reviews", tags=["admin: отзывы"])
@router.get("", response_model=Page[ReviewAdminRead])
async def list_reviews(f: Annotated[ReviewFilter, Query()], session: SessionDep, ctx: Manager):
    if ctx.staff.role != StaffRole.OWNER and ctx.staff.location_id:
        f.location_id = ctx.staff.location_id
    items, total = await ReviewService(session).admin_list(f)
    return Page(items=items, total=total, limit=f.limit, offset=f.offset)
@router.post("/{review_id}/reply", response_model=ReviewAdminRead)
async def reply_review(review_id: int, data: ReviewReplyIn, session: SessionDep, ctx: Manager):
    return await ReviewService(session).reply(review_id, ctx.user.id, data.reply)
