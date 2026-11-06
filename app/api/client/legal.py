from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.services.settings import SettingsService

router = APIRouter(prefix="/legal", tags=["клиент: документы"])


class LegalOut(BaseModel):
    ready: bool
    operator: str
    email: str | None
    docs_date: str | None
    per_gift: int
    stamps_expire_days: int | None
    gift_expire_days: int | None
    gift_with_modifiers: bool
    birthday_gift: bool
    pickup_minutes: int
    deal_soda: bool


@router.get("", response_model=LegalOut)
async def legal(session: SessionDep):
    s = await SettingsService(session).get_all()
    lg, lo = s.legal, s.loyalty
    parts = [f"ОГРНИП {lg.ogrnip}" if lg.ogrnip else None, f"ИНН {lg.inn}" if lg.inn else None, f"адрес: {lg.address}" if lg.address else None, f"e-mail: {lg.email}" if lg.email else None]
    details = ", ".join(p for p in parts if p)
    name = lg.operator_name or "Индивидуальный предприниматель (реквизиты уточняются)"
    return LegalOut(
        ready=bool(lg.operator_name and lg.inn and lg.email),
        operator=f"{name} ({details})" if details else name,
        email=lg.email,
        docs_date=lg.docs_date,
        per_gift=lo.stamps_per_gift,
        stamps_expire_days=lo.stamps_expire_days,
        gift_expire_days=lo.gift_expire_days,
        gift_with_modifiers=lo.gift_with_modifiers,
        birthday_gift=lo.birthday_gift,
        pickup_minutes=lg.pickup_minutes,
        deal_soda=s.deal.soda_enabled,
    )
