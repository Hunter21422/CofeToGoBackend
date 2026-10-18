from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=settings.db_echo, pool_pre_ping=True, pool_size=10, max_overflow=20)

# expire_on_commit=False — объекты остаются читаемыми после commit (нужно, чтобы отдать их в схему)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Одна сессия = одна транзакция на запрос. Репозитории делают только flush, commit — здесь."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
