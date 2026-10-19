import asyncio

from app.db.session import SessionLocal, engine
from app.models import Base
from app.services.push import PushService


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await PushService(session).keys()
        await session.commit()
    await engine.dispose()
    print("Таблицы созданы")


if __name__ == "__main__":
    asyncio.run(main())
