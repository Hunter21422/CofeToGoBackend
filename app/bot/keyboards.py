from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.core.config import settings


def app_url(path: str = "") -> str:
    base = settings.webapp_url.rstrip("/")
    return f"{base}/#{path}" if path else f"{base}/"


def button(text: str, url: str, web_app: bool = True) -> InlineKeyboardButton | None:
    if not url.startswith("https://"):
        return None
    if web_app:
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    return InlineKeyboardButton(text=text, url=url)


def keyboard(*buttons: InlineKeyboardButton | None) -> InlineKeyboardMarkup | None:
    rows = [[b] for b in buttons if b is not None]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
