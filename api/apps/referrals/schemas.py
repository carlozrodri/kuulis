from pydantic import BaseModel, Field


class RedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class ReferralSummary(BaseModel):
    """GET /referrals/me."""

    # Null until the user is an approved driver (only drivers can invite).
    code: str | None
    invited: int  # drivers who joined with the code
    rewarded: int  # of those, the ones who completed their first trip
    # Months of subscription this driver has earned and not used yet.
    free_months: int
    # Who invited this user (first name and initial), if anyone.
    referred_by: str | None
    # True while this user can still enter an invite code (a driver before their first trip).
    can_redeem: bool
