from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.services.errors import ServiceError


def make_bot() -> Bot:
    session = None
    if settings.bot_proxy or settings.bot_api_url:
        session = AiohttpSession(proxy=settings.bot_proxy or None)
        if settings.bot_api_url:
            session.api = TelegramAPIServer.from_base(settings.bot_api_url.rstrip("/"))
    return Bot(settings.bot_token, session=session)


async def post_to_channel(chat: str, text: str) -> int:
    try:
        bot = make_bot()
    except Exception as e:
        raise ServiceError("Бот не настроен: проверьте BOT_TOKEN на сервере") from e
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="☕ Заказать без очереди", url=f"https://t.me/{settings.bot_username}")]])
    try:
        msg = await bot.send_message(chat, text, reply_markup=markup, disable_web_page_preview=True)
        return msg.message_id
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        raise ServiceError(f"Бот не может написать в канал {chat}. Добавьте @{settings.bot_username} в канал администратором с правом публиковать сообщения. ({e.message})") from e
    except Exception as e:
        raise ServiceError("Не получилось связаться с Telegram, попробуйте через минуту") from e
    finally:
        await bot.session.close()
