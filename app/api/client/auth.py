from fastapi import APIRouter, Request

from app.api.deps import PayloadDep, RedisDep, SessionDep, client_ip, user_agent
from app.schemas.auth import MagicLoginIn, RefreshIn, SmsSendIn, SmsSendOut, SmsVerifyIn, TelegramAuthIn, TelegramWidgetIn, TokenPair
from app.services import AuthService
router=APIRouter(prefix="/auth", tags=["авторизация"])
@router.post("/telegram", response_model=TokenPair)
async def login_telegram(data: TelegramAuthIn, request: Request, session: SessionDep, redis: RedisDep):
    return await AuthService(session, redis).login_telegram(data.init_data, user_agent(request))
@router.post("/telegram-widget", response_model=TokenPair)
async def login_widget(data: TelegramWidgetIn, request: Request, session: SessionDep, redis: RedisDep):
    return await AuthService(session, redis).login_widget(data, user_agent(request))
@router.post("/sms/send", response_model=SmsSendOut)
async def sms_send(data: SmsSendIn, request: Request, session: SessionDep, redis: RedisDep):
    return await AuthService(session, redis).sms_send(data.phone, client_ip(request))
@router.post("/sms/verify", response_model=TokenPair)
async def sms_verify(data: SmsVerifyIn, request: Request, session: SessionDep, redis: RedisDep):
    return await AuthService(session, redis).sms_verify(data.phone, data.code, user_agent(request))
@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshIn, request: Request, session: SessionDep, redis: RedisDep):
    return await AuthService(session, redis).refresh(data.refresh_token, user_agent(request))
@router.post("/magic", response_model=TokenPair)
async def magic_login(data: MagicLoginIn, request: Request, session: SessionDep, redis: RedisDep):
    return await AuthService(session, redis).magic_login(data.token, user_agent(request))
@router.post("/logout", status_code=204)
async def logout(payload: PayloadDep, session: SessionDep, redis: RedisDep):
    await AuthService(session, redis).logout(payload["sid"])
