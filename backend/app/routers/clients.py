from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select

from app.deps import (
    CsrfGuard,
    CurrentUser,
    DbSession,
    get_client_ip,
    get_current_user,
    rate_limited,
    record_audit,
)
from app.errors import NotFoundError
from app.models import Client
from app.schemas import ClientCreate, ClientOut, ClientUpdate, Page, PageMeta

router = APIRouter(prefix="/clients", tags=["clients"])


def _owned_client(client_id: str, user_id: str, db) -> Client:
    client = db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == user_id)
    ).scalar_one_or_none()
    if client is None:
        raise NotFoundError("Client not found.", code="client_not_found")
    return client


@router.get(
    "",
    response_model=Page[ClientOut],
    dependencies=[Depends(rate_limited("clients-read", limit=300, window=60))],
)
def list_clients(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=120),
) -> Page[ClientOut]:
    filters = [Client.owner_id == user.id, Client.archived.is_(False)]
    if q:
        term = f"%{q.lower()}%"
        filters.append(or_(func.lower(Client.name).like(term), func.lower(Client.company).like(term)))

    total = int(
        db.execute(select(func.count()).select_from(Client).where(*filters)).scalar_one()
    )
    rows = db.execute(
        select(Client)
        .where(*filters)
        .order_by(Client.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return Page[ClientOut](
        items=[ClientOut.model_validate(row) for row in rows],
        meta=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


@router.post("", response_model=ClientOut, status_code=201, dependencies=[Depends(get_current_user), CsrfGuard])
def create_client(
    payload: ClientCreate,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> ClientOut:
    client = Client(
        owner_id=user.id,
        name=payload.name,
        email=payload.email or None,
        company=payload.company,
        notes=payload.notes,
    )
    db.add(client)
    db.flush()
    record_audit(
        db,
        action="client.create",
        entity_type="client",
        entity_id=client.id,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, user: CurrentUser, db: DbSession) -> ClientOut:
    return ClientOut.model_validate(_owned_client(client_id, user.id, db))


@router.patch("/{client_id}", response_model=ClientOut, dependencies=[Depends(get_current_user), CsrfGuard])
def update_client(
    client_id: str,
    payload: ClientUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ClientOut:
    client = _owned_client(client_id, user.id, db)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data:
        data["email"] = str(data["email"]) if data["email"] else None
    for field, value in data.items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.delete("/{client_id}", status_code=204, dependencies=[Depends(get_current_user), CsrfGuard])
def archive_client(client_id: str, user: CurrentUser, db: DbSession) -> None:
    client = _owned_client(client_id, user.id, db)
    client.archived = True
    db.commit()
