from fastapi import APIRouter, Request

from app.api.deps import RedisDep, SessionDep, StaffNoPin, client_ip
from app.schemas.auth import PinSetupIn, PinVerifyIn, PinVerifyOut, SmsSendIn, SmsSendOut, TokenPair
from app.schemas.staff import AdminMe
from app.services import AuthService, StaffService
router=APIRouter(prefix="/admin", tags=["admin: вход"])
@router.get("/me", response_model=AdminMe)
async def admin_me(session: SessionDep, ctx: StaffNoPin):
    staff, locations = await StaffService(session).me(ctx.user.id)
    return AdminMe(user=ctx.user, staff=staff, locations=locations, pin_set=staff.pin_set, pin_verified=bool(ctx.payload.get("pin")))
@router.post("/auth/pin/setup", response_model=PinVerifyOut)
async def pin_setup(data: PinSetupIn, session: SessionDep, ctx: StaffNoPin):
    return await StaffService(session).pin_setup(ctx.user.id, ctx.payload["sid"], data.pin)
@router.post("/auth/pin/verify", response_model=PinVerifyOut)
async def pin_verify(data: PinVerifyIn, session: SessionDep, ctx: StaffNoPin):
    return await StaffService(session).pin_verify(ctx.user.id, ctx.payload["sid"], data.pin)
@router.post("/auth/lock", response_model=TokenPair)
async def lock(session: SessionDep, ctx: StaffNoPin):
    return StaffService(session).lock(ctx.staff, ctx.payload["sid"])
@router.post("/auth/logout", status_code=204)
async def logout(session: SessionDep, redis: RedisDep, ctx: StaffNoPin):
    await AuthService(session, redis).logout(ctx.payload["sid"])
@router.post("/auth/phone/send", response_model=SmsSendOut)
async def staff_phone_send(data: SmsSendIn, request: Request, session: SessionDep, redis: RedisDep):
    return await AuthService(session, redis).staff_phone_send(data.phone, client_ip(request))
