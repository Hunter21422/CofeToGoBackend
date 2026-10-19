from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import NotificationLog, Order
from app.models.enums import NotificationStatus, NotificationType, StaffRole
from app.repositories import StaffRepository

from .settings import SettingsService


def money(kop: int) -> str:
    rub = kop / 100
    return f"{rub:.0f} ₽" if rub == int(rub) else f"{rub:.2f} ₽"


class NotifyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.staff = StaffRepository(session)
        self.config = get_settings()

    def _order_url(self, order: Order) -> str:
        return f"{self.config.webapp_url.rstrip('/')}/#/orders/{order.id}"

    def _add(self, user_id: int, type: NotificationType, text: str, order_id: int | None = None, button_text: str | None = None, button_url: str | None = None, sms: str | None = None) -> None:
        self.session.add(NotificationLog(
            user_id=user_id, type=type, status=NotificationStatus.PENDING, order_id=order_id,
            payload={"text": text, "button_text": button_text, "button_url": button_url, "web_app": True, "sms": sms},
        ))

    async def _texts(self):
        return (await SettingsService(self.session).get_all()).texts

    async def order_status(self, order: Order, kind: str, reason: str | None = None) -> None:
        texts = await self._texts()
        template = {"accepted": texts.order_accepted, "ready": texts.order_ready, "cancelled": texts.order_cancelled}[kind]
        text = template.format(number=order.display_number)
        sms = f"{self.config.app_name}: {text}" if kind in ("ready", "cancelled") else None
        if reason:
            text += f"\nПричина: {reason}"
        self._add(order.user_id, NotificationType.ORDER_STATUS, text, order.id, "Открыть заказ", self._order_url(order), sms=sms)

    async def new_order(self, order: Order) -> None:
        lines = []
        for item in order.items:
            name = item.product_name + (f" {item.variant_name}" if item.variant_name else "")
            mods = ", ".join(m["name"] for m in item.modifiers or [])
            gift = " 🎁" if item.is_gift else ""
            lines.append(f"• {name} ×{item.quantity}{gift}" + (f"\n   {mods}" if mods else ""))
        when = f"\nК {order.pickup_at.astimezone(ZoneInfo(order.location.timezone)).strftime('%H:%M')}" if order.pickup_at else "\nКак можно скорее"
        comment = f"\n💬 {order.comment}" if order.comment else ""
        text = f"🆕 Новый заказ {order.display_number} · {money(order.total)}\n" + "\n".join(lines) + when + comment
        for s in await self.staff.list_team():
            if s.is_active and s.role in (StaffRole.BARISTA, StaffRole.MANAGER, StaffRole.OWNER) and s.location_id in (None, order.location_id):
                self._add(s.user_id, NotificationType.STAFF_NEW_ORDER, text, order.id, "Очередь заказов", self.config.admin_url)

    async def order_cancelled_by_guest(self, order: Order) -> None:
        text = f"❌ Гость отменил заказ {order.display_number}"
        for s in await self.staff.list_team():
            if s.is_active and s.location_id in (None, order.location_id):
                self._add(s.user_id, NotificationType.STAFF_NEW_ORDER, text, order.id)

    async def gift_unlocked(self, user_id: int) -> None:
        texts = await self._texts()
        url = f"{self.config.webapp_url.rstrip('/')}/#/card"
        self._add(user_id, NotificationType.LOYALTY, texts.gift_unlocked, None, "Моя карта", url, sms=f"{self.config.app_name}: {texts.gift_unlocked}")
