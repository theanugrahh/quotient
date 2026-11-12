from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from app.deps import AdminUser, CsrfGuard, DbSession, get_client_ip, rate_limited, record_audit, require_admin
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import AuditEvent, Client, Invoice, InvoiceStatus, User, UserRole
from app.schemas import AdminStatsOut, AdminUserOut, AuditEventOut, Page, PageMeta, RoleUpdateRequest

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin), Depends(rate_limited("admin", limit=300, window=60))],
)


def _target_user(user_id: str, db) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", code="user_not_found")
    return user


@router.get("/users", response_model=Page[AdminUserOut])
def list_users(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str | None = Query(default=None, max_length=120),
) -> Page[AdminUserOut]:
    filters = []
    if q:
        term = f"%{q.lower()}%"
        filters.append(func.lower(User.email).like(term))

    total = int(db.execute(select(func.count()).select_from(User).where(*filters)).scalar_one())
    rows = db.execute(
        select(User, func.count(Invoice.id))
        .outerjoin(Invoice, Invoice.owner_id == User.id)
        .where(*filters)
        .group_by(User.id)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        AdminUserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            plan=user.plan,
            is_active=user.is_active,
            created_at=user.created_at,
            invoice_count=int(count),
        )
        for user, count in rows
    ]
    pages = max(1, -(-total // page_size))
    return Page[AdminUserOut](
        items=items,
        meta=PageMeta(page=page, page_size=page_size, total=total, pages=pages),
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserOut, dependencies=[CsrfGuard])
def update_role(
    user_id: str,
    payload: RoleUpdateRequest,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> AdminUserOut:
    target = _target_user(user_id, db)
    if target.id == admin.id and payload.role != UserRole.ADMIN:
        raise ValidationError("You cannot remove your own administrator role.", code="self_role_change")

    target.role = payload.role
    record_audit(
        db,
        action="admin.role_change",
        entity_type="user",
        entity_id=target.id,
        actor_id=admin.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(target)
    return AdminUserOut(
        id=target.id,
        name=target.name,
        email=target.email,
        role=target.role,
        plan=target.plan,
        is_active=target.is_active,
        created_at=target.created_at,
        invoice_count=0,
    )


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut, dependencies=[CsrfGuard])
def deactivate_user(
    user_id: str,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> AdminUserOut:
    target = _target_user(user_id, db)
    if target.id == admin.id:
        raise ConflictError("You cannot deactivate your own account.", code="self_deactivation")

    target.is_active = False
    record_audit(
        db,
        action="admin.deactivate",
        entity_type="user",
        entity_id=target.id,
        actor_id=admin.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(target)
    return AdminUserOut(
        id=target.id,
        name=target.name,
        email=target.email,
        role=target.role,
        plan=target.plan,
        is_active=target.is_active,
        created_at=target.created_at,
        invoice_count=0,
    )


@router.post("/users/{user_id}/activate", response_model=AdminUserOut, dependencies=[CsrfGuard])
def activate_user(user_id: str, admin: AdminUser, db: DbSession) -> AdminUserOut:
    target = _target_user(user_id, db)
    target.is_active = True
    db.commit()
    db.refresh(target)
    return AdminUserOut(
        id=target.id,
        name=target.name,
        email=target.email,
        role=target.role,
        plan=target.plan,
        is_active=target.is_active,
        created_at=target.created_at,
        invoice_count=0,
    )


@router.get("/stats", response_model=AdminStatsOut)
def admin_stats(admin: AdminUser, db: DbSession) -> AdminStatsOut:
    users = int(db.execute(select(func.count()).select_from(User)).scalar_one())
    active = int(db.execute(select(func.count()).select_from(User).where(User.is_active.is_(True))).scalar_one())
    admins = int(db.execute(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)).scalar_one())
    invoices = int(db.execute(select(func.count()).select_from(Invoice)).scalar_one())
    clients = int(db.execute(select(func.count()).select_from(Client)).scalar_one())
    paid = int(
        db.execute(
            select(func.count()).select_from(Invoice).where(Invoice.status == InvoiceStatus.PAID)
        ).scalar_one()
    )
    gross = db.execute(
        select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(Invoice.status == InvoiceStatus.PAID)
    ).scalar_one()
    return AdminStatsOut(
        users=users,
        active_users=active,
        admins=admins,
        invoices=invoices,
        clients=clients,
        paid_invoices=paid,
        gross_collected_cents=int(gross),
    )


@router.get("/audit", response_model=Page[AuditEventOut])
def audit_log(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=50, ge=1, le=200),
) -> Page[AuditEventOut]:
    total = int(db.execute(select(func.count()).select_from(AuditEvent)).scalar_one())
    rows = db.execute(
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    pages = max(1, -(-total // page_size))
    return Page[AuditEventOut](
        items=[AuditEventOut.model_validate(row) for row in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total, pages=pages),
    )
