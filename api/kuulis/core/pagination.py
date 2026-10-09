"""Limit/offset pagination with a stable response shape."""

from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PageParams(BaseModel):
    limit: int = 20
    offset: int = 0


def page_params(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


async def paginate(session: AsyncSession, stmt: Select, params: PageParams) -> tuple[list, int]:
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = await session.scalars(stmt.limit(params.limit).offset(params.offset))
    return list(rows.all()), int(total or 0)
