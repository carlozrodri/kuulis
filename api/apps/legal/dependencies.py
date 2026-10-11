from fastapi import Depends

from apps.legal import services
from apps.users.dependencies import CurrentUser, DBSession


async def _accepted(user: CurrentUser, session: DBSession) -> None:
    await services.ensure_accepted(session, user)


# Ride actions (request, accept, go online) answer 409 legal_acceptance_required until the user
# accepted the current terms.
LegalAccepted = Depends(_accepted)
