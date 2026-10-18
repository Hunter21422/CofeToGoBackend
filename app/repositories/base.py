"""Базовый репозиторий: общий CRUD для любой модели.

Правила слоя:
- только запросы к БД, никакой бизнес-логики и HTTP-ошибок;
- commit не делаем — только flush (транзакцией управляет get_session / сервис);
- связи грузим явно через options=(selectinload(...),): в async ленивая загрузка не работает.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import ColumnElement, Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- чтение ----------
    async def get(self, id_: Any, *, options: Sequence[ORMOption] = (), for_update: bool = False) -> ModelT | None:
        if not options and not for_update:
            return await self.session.get(self.model, id_)
        stmt = select(self.model).where(self.model.id == id_).options(*options)  # type: ignore[attr-defined]
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many(self, ids: Sequence[Any], *, options: Sequence[ORMOption] = ()) -> list[ModelT]:
        if not ids:
            return []
        stmt = select(self.model).where(self.model.id.in_(ids)).options(*options)  # type: ignore[attr-defined]
        return list((await self.session.execute(stmt)).scalars().all())

    async def first(self, *where: ColumnElement[bool], options: Sequence[ORMOption] = ()) -> ModelT | None:
        stmt = select(self.model).where(*where).options(*options).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *where: ColumnElement[bool],
        order_by: Sequence[Any] = (),
        limit: int | None = None,
        offset: int = 0,
        options: Sequence[ORMOption] = (),
    ) -> list[ModelT]:
        stmt = select(self.model).where(*where).options(*options).order_by(*order_by).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self, *where: ColumnElement[bool]) -> int:
        stmt = select(func.count()).select_from(self.model).where(*where)
        return int((await self.session.execute(stmt)).scalar_one())

    async def exists(self, *where: ColumnElement[bool]) -> bool:
        stmt = select(select(self.model).where(*where).exists())
        return bool((await self.session.execute(stmt)).scalar())

    async def page(
        self,
        *where: ColumnElement[bool],
        order_by: Sequence[Any] = (),
        limit: int = 20,
        offset: int = 0,
        options: Sequence[ORMOption] = (),
    ) -> tuple[list[ModelT], int]:
        """Страница + общее количество — под схему Page[T]"""
        items = await self.list(*where, order_by=order_by, limit=limit, offset=offset, options=options)
        return items, await self.count(*where)

    async def paginate_stmt(self, stmt: Select[Any], *, limit: int, offset: int) -> tuple[list[Any], int]:
        """Для сложных запросов с join: считает total по тому же запросу"""
        total = (await self.session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
        rows = (await self.session.execute(stmt.limit(limit).offset(offset))).scalars().all()
        return list(rows), int(total)

    # ---------- запись ----------
    async def create(self, **data: Any) -> ModelT:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: ModelT, **data: Any) -> ModelT:
        """Ставит только переданные поля. Для PATCH: repo.update(obj, **schema.model_dump(exclude_unset=True))"""
        for key, value in data.items():
            setattr(obj, key, value)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def delete_where(self, *where: ColumnElement[bool]) -> int:
        res = await self.session.execute(delete(self.model).where(*where))
        return res.rowcount or 0  # type: ignore[attr-defined]
