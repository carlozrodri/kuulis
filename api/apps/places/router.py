import uuid

from fastapi import APIRouter, status

from apps.places import services
from apps.places.schemas import PlaceRead, PlaceUpdate, PlaceWrite
from apps.users.dependencies import CurrentUser, DBSession

router = APIRouter(prefix="/users/me/places", tags=["places"])


@router.get("", response_model=list[PlaceRead])
async def list_places(user: CurrentUser, session: DBSession) -> list[PlaceRead]:
    return [PlaceRead.model_validate(p) for p in await services.list_places(session, user.id)]


@router.post("", response_model=PlaceRead, status_code=status.HTTP_201_CREATED)
async def save_place(data: PlaceWrite, user: CurrentUser, session: DBSession) -> PlaceRead:
    """Saving home or work again replaces it."""
    return PlaceRead.model_validate(await services.save(session, user.id, data))


@router.patch("/{place_id}", response_model=PlaceRead)
async def update_place(
    place_id: uuid.UUID, data: PlaceUpdate, user: CurrentUser, session: DBSession
) -> PlaceRead:
    return PlaceRead.model_validate(await services.update(session, user.id, place_id, data))


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place(place_id: uuid.UUID, user: CurrentUser, session: DBSession) -> None:
    await services.delete(session, user.id, place_id)
