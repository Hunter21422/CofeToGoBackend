from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from redis.asyncio import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories import StaffRepository
from app.services import AuthService, LoyaltyService

from .keyboards import app_url, button, keyboard

router = Router()
redis = Redis.from_url(settings.redis_url, decode_responses=True)


async def upsert(message: Message, session):
    tg = message.from_user
    user = await AuthService(session, redis)._upsert_telegram({"id": tg.id, "first_name": tg.first_name, "last_name": tg.last_name, "username": tg.username})
    await session.commit()
    return user


def stamps_line(stamps: int, per_gift: int) -> str:
    return "☕" * stamps + "◯" * max(per_gift - stamps, 0)


async def send_card(message: Message, session, user_id: int) -> None:
    card = await LoyaltyService(session).read(user_id)
    text = f"Ваша карта «{settings.app_name}»\n\n{stamps_line(card.stamps, card.stamps_per_gift)}  {card.stamps} из {card.stamps_per_gift}\n"
    if card.gifts_available:
        text += f"\n🎁 Подарков на карте: {card.gifts_available}. Скажите бариста, что хотите напиток в подарок."
    else:
        text += f"\nДо подарка осталось: {card.stamps_left}"
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
        "/card — моя карта\n/help — помощь"
    )
    await message.answer(text, reply_markup=keyboard(button("☕ Открыть меню", app_url())))


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
        "/card — сколько штампов до подарка\n\n"
        "Когда заказ примут и когда он будет готов — пришлю сообщение сюда."
    )
