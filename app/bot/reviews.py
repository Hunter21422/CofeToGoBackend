from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.models import Review

from .keyboards import app_url, button

PAGE = 5
HOW = "✍️ Как оставить отзыв: заберите заказ, откройте его в приложении («Профиль» → «Мои заказы») и поставьте оценку. Отзыв можно оставить на каждый полученный заказ."
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def stars(rating: int) -> str:
    return "★" * rating + "☆" * (5 - rating)


def short(text: str, limit: int = 400) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def review_block(r: Review) -> str:
    name = (r.user.first_name if r.user and r.user.first_name else "") or "Гость"
    head = f"{stars(r.rating)}  {name}"
    if r.location is not None:
        head += f" · {r.location.name}"
    local = r.created_at.astimezone(ZoneInfo(r.location.timezone if r.location is not None else "Europe/Moscow"))
    head += f" · {local.day} {MONTHS[local.month - 1]}"
    text = f"{head}\n«{short(r.comment or '')}»"
    if r.reply:
        text += f"\n↳ Ответ кофейни: {short(r.reply, 300)}"
    return text


def render(avg: float | None, count: int, rows: list[Review], total: int, offset: int) -> tuple[str, InlineKeyboardMarkup]:
    title = f"⭐ Отзывы гостей «{settings.app_name}»"
    if count:
        score = f"{avg:.1f}".replace(".", ",")
        title += f"\nСредняя оценка {score} из 5 · {count} {plural(count, 'оценка', 'оценки', 'оценок')}"
    if rows:
        body = "\n\n".join(review_block(r) for r in rows)
        pages = (total + PAGE - 1) // PAGE
        footer = f"\n\nСтраница {offset // PAGE + 1} из {pages}" if pages > 1 else ""
        text = f"{title}\n\n{body}{footer}\n\n{HOW}"
    else:
        text = f"{title}\n\nПока отзывов нет — ваш может стать первым.\n\n{HOW}"
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="← Новее", callback_data=f"rv:{max(offset - PAGE, 0)}"))
    if offset + PAGE < total:
        nav.append(InlineKeyboardButton(text="Старее →", callback_data=f"rv:{offset + PAGE}"))
    rows_kb = [nav] if nav else []
    leave = button("✍️ Оставить отзыв", app_url("/orders"))
    if leave is not None:
        rows_kb.append([leave])
    return text, InlineKeyboardMarkup(inline_keyboard=rows_kb)
