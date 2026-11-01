import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from redis.asyncio import Redis

from app.core.config import settings

log = logging.getLogger("bot.backups")

DIR = Path("/backups")
KEY = "backup:last_sent"
LIMIT = 49 * 1024 * 1024

_redis: Redis | None = None


def _client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _caption(f: Path, size: int) -> str:
    try:
        when = datetime.strptime(f.name, "coffee-%Y-%m-%d_%H%M.sql.gz").strftime("%d.%m.%Y %H:%M")
    except ValueError:
        when = f.name
    kb = max(1, round(size / 1024))
    return f"💾 Бэкап базы за {when}, {kb} КБ.\nНа сервере: ~/kofe/kofe/backups/{f.name}"


async def send_backups(bot: Bot) -> None:
    if not settings.owner_tg_ids or not DIR.is_dir():
        return
    files = sorted(DIR.glob("coffee-*.sql.gz"))
    if not files:
        return
    redis = _client()
    last = await redis.get(KEY)
    fresh = [f for f in files if f.name > last][-3:] if last else files[-1:]
    for f in fresh:
        size = f.stat().st_size
        delivered = False
        for tg_id in settings.owner_tg_ids:
            try:
                if size > LIMIT:
                    await bot.send_message(tg_id, f"💾 Бэкап {f.name} весит {size // 1024 // 1024} МБ — для Telegram слишком много, он лежит на сервере в ~/kofe/kofe/backups")
                else:
                    await bot.send_document(tg_id, FSInputFile(f), caption=_caption(f, size))
                delivered = True
            except Exception as e:
                log.warning("Бэкап %s не отправлен %s: %s", f.name, tg_id, e)
        if not delivered:
            return
        await redis.set(KEY, f.name)
        log.info("Бэкап %s отправлен владельцам", f.name)
