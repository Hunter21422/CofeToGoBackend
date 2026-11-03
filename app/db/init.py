import asyncio

from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models import Base
from app.services.push import PushService


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS yandex_reviews_url VARCHAR(512)"))
        await conn.execute(text("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS publish_consent BOOLEAN NOT NULL DEFAULT false"))
        await conn.execute(text("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS channel_message_id BIGINT"))
        await conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
        await conn.execute(text("ALTER TABLE categories ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))
    async with SessionLocal() as session:
        await PushService(session).keys()
        await session.commit()
    await engine.dispose()
    print("Таблицы созданы")


if __name__ == "__main__":
    asyncio.run(main())
