from fastapi import APIRouter

from app.api.deps import Barista, Manager, RedisDep, SessionDep, check_location
from app.models.enums import LoyaltyTxType
from app.repositories import OrderRepository
from app.schemas.loyalty import CustomerSearchItem, GiftRedeemIn, GuestCodeIn, LoyaltyAdjustIn, LoyaltyOperationOut, QrScanIn, ScanResultOut, StampAddIn
from app.services import LoyaltyService, UserService
router=APIRouter(prefix="/admin/loyalty", tags=["admin: касса"])
async def scan_result(session, user_id: int, visit: str | None = None) -> ScanResultOut:
    user = await UserService(session).get_user(user_id)
    loyalty = await LoyaltyService(session).read(user_id)
    last_orders, _ = await OrderRepository(session).page_for_user(user_id, [], 3, 0)
    return ScanResultOut(user=user, phone=user.phone, loyalty=loyalty, last_orders=last_orders, visit=visit)
async def operation(service: LoyaltyService, user_id: int, gifts_before: int) -> LoyaltyOperationOut:
    loyalty = await service.read(user_id)
    history, _ = await service.history(user_id, [], 5, 0)
    main = next((t for t in history if t.type != LoyaltyTxType.GIFT_UNLOCKED), history[0])
    return LoyaltyOperationOut(loyalty=loyalty, transaction=main, gift_unlocked=loyalty.gifts_available > gifts_before)
@router.post("/scan", response_model=ScanResultOut)
async def scan_qr(data: QrScanIn, session: SessionDep, redis: RedisDep, ctx: Barista):
    check_location(ctx, data.location_id)
    service = LoyaltyService(session, redis)
    user_id = await service.identify_code(data.token)
    return await scan_result(session, user_id, await service.open_visit(user_id, ctx.staff.id, data.location_id))
@router.post("/code", response_model=ScanResultOut)
async def check_code(data: GuestCodeIn, session: SessionDep, redis: RedisDep, ctx: Barista):
    check_location(ctx, data.location_id)
    service = LoyaltyService(session, redis)
    user_id = await service.identify_code(data.code)
    return await scan_result(session, user_id, await service.open_visit(user_id, ctx.staff.id, data.location_id))
@router.get("/search", response_model=list[CustomerSearchItem])
async def search_guest(q: str, session: SessionDep, ctx: Barista):
    service = LoyaltyService(session)
    return [CustomerSearchItem(user=u, phone=u.phone, loyalty=await service.read(u.id)) for u in await UserService(session).search_guests(q)]
@router.post("/stamp", response_model=LoyaltyOperationOut)
async def add_stamps(data: StampAddIn, session: SessionDep, redis: RedisDep, ctx: Barista):
    check_location(ctx, data.location_id)
    service = LoyaltyService(session, redis)
    before = (await service.read(data.user_id)).gifts_available
    await service.stamp_visit(data.visit, data.user_id, data.count, ctx.staff.id, data.location_id)
    return await operation(service, data.user_id, before)
@router.post("/redeem", response_model=LoyaltyOperationOut)
async def redeem_gift(data: GiftRedeemIn, session: SessionDep, redis: RedisDep, ctx: Barista):
    check_location(ctx, data.location_id)
    service = LoyaltyService(session, redis)
    await service.redeem_visit(data.visit, data.user_id, ctx.staff.id, data.location_id)
    return await operation(service, data.user_id, 10**6)
@router.post("/adjust", response_model=LoyaltyOperationOut)
async def adjust(data: LoyaltyAdjustIn, session: SessionDep, ctx: Manager):
    service = LoyaltyService(session)
    before = (await service.read(data.user_id)).gifts_available
    await service.adjust(data.user_id, data.stamps_delta, data.gifts_delta, data.reason, ctx.staff.id, ctx.staff.location_id)
    return await operation(service, data.user_id, before + max(data.gifts_delta, 0))
