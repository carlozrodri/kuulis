from typing import Annotated

from fastapi import Depends, Header

from apps.releases import services
from apps.users.dependencies import DBSession


async def _up_to_date(
    session: DBSession,
    x_app_platform: Annotated[str | None, Header()] = None,
    x_app_build: Annotated[str | None, Header()] = None,
    x_app_channel: Annotated[str | None, Header()] = None,
) -> None:
    await services.ensure_up_to_date(session, x_app_platform, x_app_build, x_app_channel)


# Ride actions (request, accept, go online) answer 426 app_update_required when the app's build is
# below the newest mandatory release; everything else (history, wallet, support) keeps working.
AppUpToDate = Depends(_up_to_date)
