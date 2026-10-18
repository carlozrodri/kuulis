import uuid

from fastapi import APIRouter, Request, status

from apps.audit.services import audit, note, snapshot
from apps.staff import services
from apps.staff.permissions import PERMISSIONS
from apps.staff.schemas import (
    InviteAccept,
    PermissionGroup,
    RolesOverview,
    ServiceTokenCreate,
    ServiceTokenCreated,
    ServiceTokenRead,
    StaffInvite,
    StaffMember,
    StaffRoleCreate,
    StaffRoleRead,
    StaffRoleUpdate,
    StaffUpdate,
)
from apps.users import services as users
from apps.users.dependencies import AdminUser, DBSession, VerifiedAdminUser
from kuulis.core.rate_limit import limiter

router = APIRouter(prefix="/admin", tags=["staff"])
public_router = APIRouter(prefix="/auth", tags=["staff"])

ROLE_FIELDS = ("label", "permissions")
MEMBER_FIELDS = ("role", "staff_role_id", "is_active")


async def _role_read(session: DBSession, role) -> StaffRoleRead:
    counts = await services.member_counts(session)
    return StaffRoleRead(
        id=role.id,
        name=role.name,
        label=role.label,
        permissions=sorted(role.permissions),
        members=counts.get(role.id, 0),
    )


@router.get("/roles", response_model=RolesOverview)
async def roles(_: AdminUser, session: DBSession) -> RolesOverview:
    counts = await services.member_counts(session)
    return RolesOverview(
        catalog=[PermissionGroup(group=g, permissions=list(p)) for g, p in PERMISSIONS.items()],
        roles=[
            StaffRoleRead(
                id=r.id,
                name=r.name,
                label=r.label,
                permissions=sorted(r.permissions),
                members=counts.get(r.id, 0),
            )
            for r in await services.list_roles(session)
        ],
    )


@router.post(
    "/roles",
    dependencies=[audit("role.create", "staff_role")],
    response_model=StaffRoleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_role(
    data: StaffRoleCreate, _: VerifiedAdminUser, session: DBSession
) -> StaffRoleRead:
    role = await services.create_role(session, data)
    note(entity_id=role.id)
    return await _role_read(session, role)


@router.put(
    "/roles/{role_id}",
    dependencies=[audit("role.update", "staff_role", "role_id")],
    response_model=StaffRoleRead,
)
async def update_role(
    role_id: uuid.UUID, data: StaffRoleUpdate, _: VerifiedAdminUser, session: DBSession
) -> StaffRoleRead:
    role = await services.get_role(session, role_id)
    before = snapshot(role, ROLE_FIELDS)
    role = await services.update_role(session, role, data)
    note(before=before, after=snapshot(role, ROLE_FIELDS))
    return await _role_read(session, role)


@router.get("/staff", response_model=list[StaffMember])
async def team(_: AdminUser, session: DBSession) -> list[StaffMember]:
    return await services.team(session)


@router.post(
    "/staff/invite",
    dependencies=[audit("staff.invite", "user")],
    response_model=StaffMember,
    status_code=status.HTTP_201_CREATED,
)
async def invite(data: StaffInvite, _: VerifiedAdminUser, session: DBSession) -> StaffMember:
    user = await services.invite(session, data)
    note(entity_id=user.id)
    return await services.member_of(session, user)


@router.patch(
    "/staff/{user_id}",
    dependencies=[audit("staff.update", "user", "user_id")],
    response_model=StaffMember,
)
async def update_member(
    user_id: uuid.UUID, data: StaffUpdate, admin: VerifiedAdminUser, session: DBSession
) -> StaffMember:
    user = await users.get_or_404(session, user_id)
    before = snapshot(user, MEMBER_FIELDS)
    user = await services.update_member(session, admin, user, data)
    note(before=before, after=snapshot(user, MEMBER_FIELDS))
    return await services.member_of(session, user)


@router.get("/service-tokens", response_model=list[ServiceTokenRead])
async def service_tokens(_: AdminUser, session: DBSession) -> list[ServiceTokenRead]:
    return await services.list_service_tokens(session)


@router.post(
    "/service-tokens",
    dependencies=[audit("service_token.create", "service_token")],
    response_model=ServiceTokenCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_token(
    data: ServiceTokenCreate, admin: VerifiedAdminUser, session: DBSession
) -> ServiceTokenCreated:
    token, plain = await services.create_service_token(session, admin, data)
    note(entity_id=token.id)
    return ServiceTokenCreated(**token.model_dump(), token=plain)


@router.post(
    "/service-tokens/{token_id}/revoke",
    dependencies=[audit("service_token.revoke", "service_token", "token_id")],
    response_model=ServiceTokenRead,
)
async def revoke_service_token(
    token_id: uuid.UUID, _: VerifiedAdminUser, session: DBSession
) -> ServiceTokenRead:
    return await services.revoke_service_token(session, token_id)


@public_router.post("/invite/accept", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/hour")
async def accept_invite(request: Request, data: InviteAccept, session: DBSession) -> None:
    """Sets the password of an invited team member (the admin asks for 2FA at first sign-in)."""
    await services.accept_invite(session, data.token, data.password)
