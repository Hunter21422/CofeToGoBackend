from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, RedisDep, SessionDep
from app.schemas.common import Page
from app.schemas.loyalty import LoyaltyHistoryFilter, LoyaltyQrOut, LoyaltyRead, LoyaltyTransactionRead
from app.services import LoyaltyService
router=APIRouter(prefix="/loyalty", tags=["клиент: лояльность"])
@router.get("", response_model=LoyaltyRead)
async def get_loyalty(session: SessionDep, user: CurrentUser):
    return await LoyaltyService(session).read(user.id)
@router.get("/qr", response_model=LoyaltyQrOut)
async def get_qr(session: SessionDep, redis: RedisDep, user: CurrentUser):
    code, expires_at = await LoyaltyService(session, redis).issue_code(user.id)
    seconds_left = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    return LoyaltyQrOut(token=code, code=code, expires_at=expires_at, refresh_in=max(seconds_left - 30, 10))
@router.get("/history", response_model=Page[LoyaltyTransactionRead])
async def get_history(f: Annotated[LoyaltyHistoryFilter, Query()], session: SessionDep, user: CurrentUser):
    items, total = await LoyaltyService(session).history(user.id, f.type, f.limit, f.offset)
    return Page(items=items, total=total, limit=f.limit, offset=f.offset)
