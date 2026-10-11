import csv
import io
import json
import uuid
from datetime import date, datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from apps.audit import services
from apps.audit.schemas import AuditEntryRead
from apps.users.dependencies import AdminUser, DBSession
from kuulis.core.calendar import CARACAS_TZ
from kuulis.core.pagination import Page, PageParams, page_params, paginate

router = APIRouter(prefix="/admin/audit", tags=["audit"])

CSV_LIMIT = 50_000


class AuditFilters:
    def __init__(
        self,
        actor_id: uuid.UUID | None = None,
        action: Annotated[str | None, Query(max_length=64)] = None,
        entity_type: Annotated[str | None, Query(max_length=32)] = None,
        entity_id: Annotated[str | None, Query(max_length=64)] = None,
        first: Annotated[date | None, Query(alias="from")] = None,
        last: Annotated[date | None, Query(alias="to")] = None,
    ) -> None:
        def _start(day: date) -> datetime:
            return datetime.combine(day, time.min, tzinfo=CARACAS_TZ)

        self.kwargs = {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "since": _start(first) if first else None,
            "until": _start(last + timedelta(days=1)) if last else None,
        }


@router.get("", response_model=Page[AuditEntryRead])
async def list_entries(
    _: AdminUser,
    session: DBSession,
    filters: Annotated[AuditFilters, Depends()],
    params: Annotated[PageParams, Depends(page_params)],
) -> Page[AuditEntryRead]:
    rows, total = await paginate(session, services.query(**filters.kwargs), params)
    return Page(
        items=[AuditEntryRead.model_validate(r) for r in rows],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get(
    "/export.csv",
    response_class=Response,
    dependencies=[Depends(services.audited("audit.export", "audit"))],
)
async def export_csv(
    _: AdminUser, session: DBSession, filters: Annotated[AuditFilters, Depends()]
) -> Response:
    services.note(after={k: v for k, v in filters.kwargs.items() if v is not None})
    rows = await session.scalars(services.query(**filters.kwargs).limit(CSV_LIMIT))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "fecha",
            "actor",
            "accion",
            "entidad",
            "id",
            "motivo",
            "antes",
            "despues",
            "ip",
            "request_id",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.created_at.astimezone(CARACAS_TZ).isoformat(timespec="seconds"),
                r.actor_email,
                r.action,
                r.entity_type,
                r.entity_id or "",
                r.reason or "",
                json.dumps(r.before, ensure_ascii=False) if r.before else "",
                json.dumps(r.after, ensure_ascii=False) if r.after else "",
                r.ip or "",
                r.request_id or "",
            ]
        )
    return Response(
        content=out.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kuulis-auditoria.csv"'},
    )
