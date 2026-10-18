import asyncio

from app.db.session import engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Таблицы созданы")


if __name__ == "__main__":
    asyncio.run(main())
