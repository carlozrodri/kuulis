"""Saved places: home and work (one each, saving again replaces it) plus up to MAX_OTHER others."""

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.places.models import PlaceKind, SavedPlace
from apps.places.schemas import PlaceUpdate, PlaceWrite
from kuulis.core.exceptions import ConflictError, NotFoundError

MAX_OTHER = 10


class PlaceNotFoundError(NotFoundError):
    code = "place_not_found"
    message = "Place not found"


class TooManyPlacesError(ConflictError):
    code = "too_many_places"
    message = "You reached the maximum number of saved places"


async def list_places(session: AsyncSession, user_id: uuid.UUID) -> list[SavedPlace]:
    order = case(
        (SavedPlace.kind == PlaceKind.HOME, 0), (SavedPlace.kind == PlaceKind.WORK, 1), else_=2
    )
    rows = await session.scalars(
        select(SavedPlace)
        .where(SavedPlace.user_id == user_id)
        .order_by(order, SavedPlace.created_at)
    )
    return list(rows)


async def save(session: AsyncSession, user_id: uuid.UUID, data: PlaceWrite) -> SavedPlace:
    values = data.model_dump()
    values["label"] = values["label"].strip()
    if data.kind != PlaceKind.OTHER:
        existing = await session.scalar(
            select(SavedPlace)
            .where(SavedPlace.user_id == user_id, SavedPlace.kind == data.kind)
            .with_for_update()
        )
        if existing is not None:
            for field, value in values.items():
                setattr(existing, field, value)
            await session.flush()
            await session.refresh(existing)
            return existing
    else:
        count = await session.scalar(
            select(func.count()).where(
                SavedPlace.user_id == user_id, SavedPlace.kind == PlaceKind.OTHER
            )
        )
        if (count or 0) >= MAX_OTHER:
            raise TooManyPlacesError(details={"max": MAX_OTHER})
    place = SavedPlace(user_id=user_id, **values)
    session.add(place)
    await session.flush()
    await session.refresh(place)
    return place


async def _own(session: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID) -> SavedPlace:
    place = await session.get(SavedPlace, place_id)
    if place is None or place.user_id != user_id:
        raise PlaceNotFoundError()
    return place


async def update(
    session: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID, data: PlaceUpdate
) -> SavedPlace:
    place = await _own(session, user_id, place_id)
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(place, field, value.strip() if field == "label" else value)
    await session.flush()
    await session.refresh(place)
    return place


async def delete(session: AsyncSession, user_id: uuid.UUID, place_id: uuid.UUID) -> None:
    await session.delete(await _own(session, user_id, place_id))
