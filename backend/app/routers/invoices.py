from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import Client, Invoice, InvoiceStatus
from app.schemas import (
    DashboardStats,
    InvoiceCreate,
    InvoiceOut,
    InvoiceSummary,
    InvoiceUpdate,
    Page,
    PageMeta,
    ShareLinkOut,
    StatusChangeOut,
)
from app.security import generate_share_token
from app.services.invoices import apply_line_items, next_invoice_number
from app.services.serializers import (
    collected_cents,
    invoice_out,
    invoice_summary,
    outstanding_cents,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

SHARE_LINK_TTL_DAYS = 30


def _owned_invoice(invoice_id: str, user_id: str, db) -> Invoice:
    invoice = db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == user_id)
    ).scalar_one_or_none()
    if invoice is None:
        raise NotFoundError("Invoice not found.", code="invoice_not_found")
    return invoice


def _resolve_client(client_id: str, user_id: str, db) -> Client:
    client = db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == user_id)
    ).scalar_one_or_none()
    if client is None:
        raise NotFoundError("Client not found.", code="client_not_found")
    return client


def _recalculate(invoice: Invoice, payload: InvoiceCreate | InvoiceUpdate) -> None:
    if payload.items is not None:
        apply_line_items(
            invoice,
            [(item.description, item.quantity_milli, item.unit_price_cents) for item in payload.items],
        )
    else:
        apply_line_items(
            invoice,
            [(item.description, item.quantity_milli, item.unit_price_cents) for item in invoice.items],
        )


@router.get("/stats/summary", response_model=DashboardStats)
def summary(user: CurrentUser, db: DbSession) -> DashboardStats:
    rows = db.execute(
        select(Invoice.status, func.count(), func.coalesce(func.sum(Invoice.total_cents), 0))
        .where(Invoice.owner_id == user.id)
        .group_by(Invoice.status)
    ).all()

    counts = dict.fromkeys(InvoiceStatus.ALL, 0)
    for status, count, _total in rows:
        counts[status] = int(count)

    client_count = int(
        db.execute(
            select(func.count())
            .select_from(Client)
            .where(Client.owner_id == user.id, Client.archived.is_(False))
        ).scalar_one()
    )

    return DashboardStats(
        total_invoices=sum(counts.values()),
        draft_count=counts[InvoiceStatus.DRAFT],
        sent_count=counts[InvoiceStatus.SENT],
        paid_count=counts[InvoiceStatus.PAID],
        void_count=counts[InvoiceStatus.VOID],
        outstanding_cents=outstanding_cents(db, user.id),
        collected_cents=collected_cents(db, user.id),
        client_count=client_count,
        currency="usd",
    )


@router.get(
    "",
    response_model=Page[InvoiceSummary],
    dependencies=[Depends(rate_limited("invoices-read", limit=300, window=60))],
)
def list_invoices(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, pattern=r"^(draft|sent|paid|void)$"),
    client_id: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, max_length=120),
) -> Page[InvoiceSummary]:
    filters = [Invoice.owner_id == user.id]
    if status:
        filters.append(Invoice.status == status)
    if client_id:
        filters.append(Invoice.client_id == client_id)
    if q:
        term = f"%{q.lower()}%"
        filters.append(
            or_(
                func.lower(Invoice.number).like(term),
                func.lower(Client.name).like(term),
                func.lower(Client.company).like(term),
            )
        )

    total = int(
        db.execute(
            select(func.count()).select_from(Invoice).join(Client, Invoice.client_id == Client.id).where(*filters)
        ).scalar_one()
    )
    rows = db.execute(
        select(Invoice)
        .join(Client, Invoice.client_id == Client.id)
        .where(*filters)
        .order_by(Invoice.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return Page[InvoiceSummary](
        items=[invoice_summary(row) for row in rows],
        meta=PageMeta(
            page=page,
            page_size=page_size,
            total=total,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


@router.post("", response_model=InvoiceOut, status_code=201, dependencies=[Depends(get_current_user), CsrfGuard])
def create_invoice(
    payload: InvoiceCreate,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> InvoiceOut:
    client = _resolve_client(payload.client_id, user.id, db)
    if payload.due_date and payload.issue_date and payload.due_date < payload.issue_date:
        raise ValidationError("Due date cannot be earlier than the issue date.", code="invalid_dates")

    invoice = Invoice(
        owner_id=user.id,
        client_id=client.id,
        number=next_invoice_number(db, user.id),
        currency=payload.currency.lower(),
        issue_date=payload.issue_date or datetime.now(UTC),
        due_date=payload.due_date,
        notes=payload.notes,
        tax_rate_bp=payload.tax_rate_bp,
        discount_bp=payload.discount_bp,
    )
    db.add(invoice)
    db.flush()

    apply_line_items(
        invoice,
        [(item.description, item.quantity_milli, item.unit_price_cents) for item in payload.items],
    )

    record_audit(
        db,
        action="invoice.create",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(invoice)
    return invoice_out(invoice)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: str, user: CurrentUser, db: DbSession) -> InvoiceOut:
    return invoice_out(_owned_invoice(invoice_id, user.id, db))


@router.patch("/{invoice_id}", response_model=InvoiceOut, dependencies=[Depends(get_current_user), CsrfGuard])
def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    user: CurrentUser,
    db: DbSession,
) -> InvoiceOut:
    invoice = _owned_invoice(invoice_id, user.id, db)
    if invoice.status != InvoiceStatus.DRAFT:
        raise ConflictError("Only draft invoices can be edited.", code="invoice_not_editable")

    data = payload.model_dump(exclude_unset=True)
    if "client_id" in data and data["client_id"]:
        invoice.client_id = _resolve_client(data["client_id"], user.id, db).id
    for field in ("currency", "issue_date", "due_date", "notes", "tax_rate_bp", "discount_bp"):
        if field in data and data[field] is not None:
            setattr(invoice, field, data[field])
    if invoice.currency:
        invoice.currency = invoice.currency.lower()

    _recalculate(invoice, payload)

    db.commit()
    db.refresh(invoice)
    return invoice_out(invoice)


@router.delete("/{invoice_id}", status_code=204, dependencies=[Depends(get_current_user), CsrfGuard])
def delete_invoice(invoice_id: str, user: CurrentUser, db: DbSession) -> None:
    invoice = _owned_invoice(invoice_id, user.id, db)
    if invoice.status == InvoiceStatus.PAID:
        raise ConflictError("Paid invoices cannot be deleted.", code="invoice_not_deletable")
    db.delete(invoice)
    db.commit()


@router.post("/{invoice_id}/send", response_model=StatusChangeOut, dependencies=[Depends(get_current_user), CsrfGuard])
def send_invoice(invoice_id: str, request: Request, user: CurrentUser, db: DbSession) -> StatusChangeOut:
    invoice = _owned_invoice(invoice_id, user.id, db)
    if invoice.status != InvoiceStatus.DRAFT:
        raise ConflictError("Only draft invoices can be sent.", code="invoice_not_sendable")
    if not invoice.share_token:
        invoice.share_token = generate_share_token()
    invoice.share_expires_at = datetime.now(UTC) + timedelta(days=SHARE_LINK_TTL_DAYS)
    invoice.status = InvoiceStatus.SENT
    record_audit(
        db,
        action="invoice.send",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(invoice)
    return StatusChangeOut(id=invoice.id, status=invoice.status, updated_at=invoice.updated_at)


@router.post(
    "/{invoice_id}/mark-paid",
    response_model=StatusChangeOut,
    dependencies=[Depends(get_current_user), CsrfGuard],
)
def mark_paid(invoice_id: str, user: CurrentUser, db: DbSession) -> StatusChangeOut:
    invoice = _owned_invoice(invoice_id, user.id, db)
    if invoice.status == InvoiceStatus.VOID:
        raise ConflictError("Void invoices cannot be marked as paid.", code="invoice_void")
    if invoice.status == InvoiceStatus.PAID:
        raise ConflictError("This invoice is already paid.", code="invoice_already_paid")
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(UTC)
    db.commit()
    db.refresh(invoice)
    return StatusChangeOut(id=invoice.id, status=invoice.status, updated_at=invoice.updated_at)


@router.post("/{invoice_id}/void", response_model=StatusChangeOut, dependencies=[Depends(get_current_user), CsrfGuard])
def void_invoice(invoice_id: str, user: CurrentUser, db: DbSession) -> StatusChangeOut:
    invoice = _owned_invoice(invoice_id, user.id, db)
    if invoice.status == InvoiceStatus.PAID:
        raise ConflictError("Paid invoices cannot be voided.", code="invoice_paid")
    invoice.status = InvoiceStatus.VOID
    db.commit()
    db.refresh(invoice)
    return StatusChangeOut(id=invoice.id, status=invoice.status, updated_at=invoice.updated_at)


@router.post("/{invoice_id}/share", response_model=ShareLinkOut, dependencies=[Depends(get_current_user), CsrfGuard])
def rotate_share_link(invoice_id: str, user: CurrentUser, db: DbSession) -> ShareLinkOut:
    invoice = _owned_invoice(invoice_id, user.id, db)
    invoice.share_token = generate_share_token()
    invoice.share_expires_at = datetime.now(UTC) + timedelta(days=SHARE_LINK_TTL_DAYS)
    if invoice.status == InvoiceStatus.DRAFT:
        invoice.status = InvoiceStatus.SENT
    db.commit()
    db.refresh(invoice)
    return ShareLinkOut(
        token=invoice.share_token or "",
        path=f"/invoice/{invoice.share_token}",
        expires_at=invoice.share_expires_at,
    )


@router.get("/{invoice_id}/share", response_model=ShareLinkOut)
def read_share_link(invoice_id: str, user: CurrentUser, db: DbSession) -> ShareLinkOut:
    invoice = _owned_invoice(invoice_id, user.id, db)
    if not invoice.share_token:
        raise NotFoundError("This invoice has no share link yet.", code="share_link_missing")
    return ShareLinkOut(
        token=invoice.share_token,
        path=f"/invoice/{invoice.share_token}",
        expires_at=invoice.share_expires_at,
    )
