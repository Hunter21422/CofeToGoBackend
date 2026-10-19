import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from app.core.config import settings

from .handlers import router
from .worker import run_worker


async def setup(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть меню"),
        BotCommand(command="card", description="Моя карта лояльности"),
        BotCommand(command="help", description="Помощь"),
    ])
    if settings.webapp_url.startswith("https://"):
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Меню", web_app=WebAppInfo(url=settings.webapp_url)))


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not settings.bot_token:
        raise SystemExit("Укажите BOT_TOKEN в .env")
    session = None
    if settings.bot_proxy or settings.bot_api_url:
        session = AiohttpSession(proxy=settings.bot_proxy or None)
        if settings.bot_api_url:
            session.api = TelegramAPIServer.from_base(settings.bot_api_url.rstrip("/"))
    bot = Bot(settings.bot_token, session=session)
    dp = Dispatcher()
    dp.include_router(router)
    await setup(bot)
    worker = asyncio.create_task(run_worker(bot))
    try:
        await dp.start_polling(bot)
    finally:
        worker.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
