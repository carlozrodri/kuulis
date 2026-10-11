from fastapi import APIRouter, status

from apps.referrals import services
from apps.referrals.schemas import RedeemRequest, ReferralSummary
from apps.users.dependencies import CurrentUser, DBSession

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/me", response_model=ReferralSummary)
async def my_referrals(user: CurrentUser, session: DBSession) -> ReferralSummary:
    return await services.summary(session, user)


@router.post("/redeem", response_model=ReferralSummary, status_code=status.HTTP_200_OK)
async def redeem(data: RedeemRequest, user: CurrentUser, session: DBSession) -> ReferralSummary:
    await services.redeem(session, user, data.code)
    return await services.summary(session, user)
