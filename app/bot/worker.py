import asyncio
import re
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import func, select, update

from app.db.session import SessionLocal
from app.models import Broadcast, NotificationLog, User
from app.models.enums import BroadcastStatus, NotificationStatus, NotificationType
from app.repositories import BroadcastRepository, NotificationLogRepository
from app.core.config import settings
from app.services import LoyaltyService, OrderService, PushService, StockService
from app.services.auth import LogSender, default_sender

from .keyboards import button, keyboard

log = logging.getLogger("bot.worker")


async def deliver(bot: Bot, n: NotificationLog, user: User) -> int:
    p = n.payload or {}
    markup = keyboard(button(p["button_text"], p["button_url"], p.get("web_app", True))) if p.get("button_text") and p.get("button_url") else None
    parse_mode = "HTML" if n.type == NotificationType.BROADCAST else None
    if p.get("image_url"):
        msg = await bot.send_photo(user.tg_id, p["image_url"], caption=p["text"], reply_markup=markup, parse_mode=parse_mode)
    else:
        msg = await bot.send_message(user.tg_id, p["text"], reply_markup=markup, parse_mode=parse_mode)
    return msg.message_id


async def send_sms(user: User, text: str | None) -> str | None:
    if not text:
        return "Без Telegram, по SMS не отправляем"
    if not user.phone:
        return "У гостя нет Telegram и телефона"
    sender = default_sender()
    if isinstance(sender, LogSender):
        return "SMS не настроены (нет SMS_RU_API_ID)"
    text = re.sub(r"[^\u0000-\uFFFF]", "", text).replace("  ", " ").strip()
    try:
        await sender.send(user.phone, text)
    except Exception as e:
        return f"SMS: {e}"[:500]
    return None


async def send_push(session, n: NotificationLog, user: User) -> int:
    p = n.payload or {}
    body = re.sub(r"<[^>]+>", "", p.get("text") or "").strip()
    try:
        return await PushService(session).send(user.id, settings.app_name, body, p.get("button_url"))
    except Exception as e:
        log.warning("push user %s: %s", user.id, e)
        return 0


async def send_web(session, n: NotificationLog, user: User, sms_text: str | None) -> str | None:
    if await send_push(session, n, user):
        return None
    return await send_sms(user, sms_text)


async def send_pending(bot: Bot) -> int:
    async with SessionLocal() as session:
        items = await NotificationLogRepository(session).pending(25)
        for n in items:
            user = await session.get(User, n.user_id)
            error = None
            sms_text = (n.payload or {}).get("sms")
            if user is None:
                error = "Гость не найден"
            elif n.type == NotificationType.ORDER_STATUS and not user.notifications_enabled:
                error = "Уведомления выключены"
            elif not user.tg_id:
                error = await send_web(session, n, user, sms_text)
            else:
                try:
                    n.tg_message_id = await deliver(bot, n, user)
                except TelegramRetryAfter as e:
                    await session.commit()
                    await asyncio.sleep(e.retry_after)
                    return 0
                except TelegramForbiddenError:
                    error = "Бот заблокирован"
                except TelegramBadRequest as e:
                    error = str(e)[:500]
                if n.type != NotificationType.STAFF_NEW_ORDER and await send_push(session, n, user):
                    error = None
            n.status = NotificationStatus.FAILED if error else NotificationStatus.SENT
            n.error = error
            n.sent_at = None if error else datetime.now(timezone.utc)
            if n.broadcast_id:
                column = Broadcast.failed_count if error else Broadcast.sent_count
                await session.execute(update(Broadcast).where(Broadcast.id == n.broadcast_id).values({column: column + 1}))
            await asyncio.sleep(0.05)
        await session.commit()
        return len(items)


async def start_broadcasts() -> None:
    async with SessionLocal() as session:
        repo = BroadcastRepository(session)
        for b in await repo.due():
            rows = (await session.execute(repo.segment_stmt(b.segment or {}))).all()
            payload = {"text": b.text, "image_url": b.image_url, "button_text": b.button_text, "button_url": b.button_url, "web_app": True}
            for user_id, _ in rows:
                session.add(NotificationLog(user_id=user_id, type=NotificationType.BROADCAST, status=NotificationStatus.PENDING, broadcast_id=b.id, payload=payload))
            b.status = BroadcastStatus.SENDING
            b.started_at = datetime.now(timezone.utc)
            b.total_count = len(rows)
            log.info("Рассылка %s: %s получателей", b.id, len(rows))
        await session.commit()


async def finish_broadcasts() -> None:
    async with SessionLocal() as session:
        pending = (
            select(func.count(NotificationLog.id))
            .where(NotificationLog.broadcast_id == Broadcast.id, NotificationLog.status == NotificationStatus.PENDING)
            .scalar_subquery()
        )
        await session.execute(
            update(Broadcast)
            .where(Broadcast.status == BroadcastStatus.SENDING, pending == 0)
            .values(status=BroadcastStatus.DONE, finished_at=datetime.now(timezone.utc))
        )
        await session.commit()


async def housekeeping() -> None:
    async with SessionLocal() as session:
        expired = await OrderService(session).expire_unpaid()
        cleaned = await StockService(session).cleanup()
        burned = await LoyaltyService(session).expire_old()
        await session.commit()
        if expired or cleaned or burned:
            log.info("Просрочено заказов: %s, снято со стопа: %s, сгорело карт: %s", expired, cleaned, burned)


async def run_worker(bot: Bot) -> None:
    tick = 0
    while True:
        try:
            sent = await send_pending(bot)
            if tick % 15 == 0:
                await start_broadcasts()
                await finish_broadcasts()
            if tick % 30 == 0:
                await housekeeping()
        except Exception:
            log.exception("Ошибка в фоновой задаче")
            sent = 0
        tick += 1
        if not sent:
            await asyncio.sleep(2)
