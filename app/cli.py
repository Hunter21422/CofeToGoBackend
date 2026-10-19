import asyncio
import sys

from redis.asyncio import Redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories import StaffRepository, UserRepository
from app.services import AuthService

HELP = """Запасной вход в панель, когда Telegram недоступен.

  python -m app.cli login-link <телефон или telegram id>

Печатает одноразовую ссылку на 2 минуты. Дальше сотрудник вводит свой PIN."""


async def login_link(who: str) -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    async with SessionLocal() as session:
        users = UserRepository(session)
        digits = "".join(ch for ch in who if ch.isdigit())
        user = await users.by_phone("+" + digits) if who.startswith("+") or len(digits) == 11 else await users.by_tg_id(int(digits))
        staff = await StaffRepository(session).by_user_id(user.id) if user else None
        if staff is None or not staff.is_active:
            raise SystemExit("Сотрудник не найден или отключён")
        link = await AuthService(session, redis).magic_create(user.id)
    await redis.aclose()
    print(f"{user.first_name}: {link}")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "login-link":
        asyncio.run(login_link(sys.argv[2]))
    else:
        print(HELP)


if __name__ == "__main__":
    main()
