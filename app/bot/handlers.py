from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from redis.asyncio import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories import ReviewRepository, StaffRepository
from app.services import AuthService, LoyaltyService

from .keyboards import app_url, button, keyboard
from .reviews import PAGE, render

router = Router()
redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def upsert(message: Message, session):
    tg = message.from_user
    user = await AuthService(session, redis)._upsert_telegram({"id": tg.id, "first_name": tg.first_name, "last_name": tg.last_name, "username": tg.username})
    await session.commit()
    return user


MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def day_month(dt) -> str:
    local = dt.astimezone(ZoneInfo("Europe/Moscow"))
    return f"{local.day} {MONTHS[local.month - 1]}"


def expire_rules(card) -> str:
    lines = []
    if card.stamps_expire_days:
        line = f"⏳ Штампы сгорают, если не заказывать {card.stamps_expire_days} дн."
        if card.stamps_expire_at:
            line += f" Ваши сгорят {day_month(card.stamps_expire_at)}."
        lines.append(line)
    if card.gift_expire_days:
        line = f"🎁 Подарок сгорает, если не заказывать {card.gift_expire_days} дн."
        if card.gifts_expire_at:
            line += f" Ваш сгорит {day_month(card.gifts_expire_at)}."
        lines.append(line)
    if lines:
        lines.append("Любой заказ продлевает срок.")
    return "\n".join(lines)


def stamps_line(stamps: int, per_gift: int) -> str:
    return "☕" * stamps + "◯" * max(per_gift - stamps, 0)


async def send_card(message: Message, session, user_id: int) -> None:
    card = await LoyaltyService(session).read(user_id)
    text = f"Ваша карта «{settings.app_name}»\n\n{stamps_line(card.stamps, card.stamps_per_gift)}  {card.stamps} из {card.stamps_per_gift}\n"
    if card.gifts_available:
        text += f"\n🎁 Подарков на карте: {card.gifts_available}. Скажите бариста, что хотите напиток в подарок."
    else:
        text += f"\nДо подарка осталось: {card.stamps_left}"
    rules = expire_rules(card)
    if rules:
        text += f"\n\n{rules}"
    await message.answer(text, reply_markup=keyboard(button("Показать код на кассе", app_url("/card"))))


@router.message(CommandStart())
async def start(message: Message, command: CommandObject):
    async with SessionLocal() as session:
        user = await upsert(message, session)
        if command.args == "card":
            await send_card(message, session, user.id)
            return
    text = (
        f"Привет, {message.from_user.first_name}! Это «{settings.app_name}» ☕\n\n"
        "Заказывайте заранее и забирайте без очереди.\n"
        "Каждый 6-й напиток — в подарок: штамп ставится за любой напиток.\n\n"
        "/card — моя карта\n/reviews — отзывы гостей\n/help — помощь"
    )
    await message.answer(
        text,
        reply_markup=keyboard(button("☕ Открыть меню", app_url()), InlineKeyboardButton(text="⭐ Отзывы гостей", callback_data="rv:0")),
    )


async def reviews_page(offset: int):
    async with SessionLocal() as session:
        repo = ReviewRepository(session)
        avg, count = await repo.summary()
        rows, total = await repo.public_page(PAGE, offset)
        return render(avg, count, rows, total, offset)


@router.message(Command("reviews"))
async def reviews(message: Message):
    text, markup = await reviews_page(0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("rv:"))
async def reviews_more(call: CallbackQuery):
    raw = call.data.split(":", 1)[1]
    offset = int(raw) if raw.isdigit() else 0
    text, markup = await reviews_page(offset)
    if offset == 0 and call.message and not (call.message.text or "").startswith("⭐"):
        await call.message.answer(text, reply_markup=markup)
    elif call.message:
        try:
            await call.message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            pass
    await call.answer()


@router.message(Command("card"))
async def card(message: Message):
    async with SessionLocal() as session:
        user = await upsert(message, session)
        await send_card(message, session, user.id)


@router.message(Command("admin"))
async def admin(message: Message):
    async with SessionLocal() as session:
        staff = await StaffRepository(session).by_tg_id(message.from_user.id)
        if staff is None or not staff.is_active:
            await message.answer("Эта команда только для команды кофейни.")
            return
        link = await AuthService(session, redis).magic_create(staff.user_id)
    await message.answer(
        "Вход в панель управления.\nСсылка одноразовая и действует 2 минуты — никому её не пересылайте.",
        reply_markup=keyboard(button("Открыть в браузере", link, web_app=False), button("Открыть в Telegram", settings.admin_url)),
    )


@router.message(Command("help"))
async def help_(message: Message):
    await message.answer(
        "Что умеет бот:\n\n"
        "/start — открыть меню и заказать\n"
        "/card — сколько штампов до подарка\n"
        "/reviews — что говорят гости\n\n"
        "Когда заказ примут и когда он будет готов — пришлю сообщение сюда."
    )
