from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import InvoiceStatus, UserPlan, UserRole

T = TypeVar("T")

Password = Annotated[str, Field(min_length=10, max_length=128)]
ShortText = Annotated[str, Field(min_length=1, max_length=240)]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --------------------------------------------------------------------------- auth


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=2, max_length=120)]
    email: EmailStr
    password: Password


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class PasswordChangeRequest(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password


class UserOut(ApiModel):
    id: str
    name: str
    email: EmailStr
    role: str
    plan: str
    is_active: bool
    created_at: datetime


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime


class CsrfOut(BaseModel):
    csrf_token: str


class SessionStateOut(BaseModel):
    user: UserOut | None = None


# ------------------------------------------------------------------------- clients


class ClientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr | None = None
    company: Annotated[str, Field(max_length=160)] = ""
    notes: Annotated[str, Field(max_length=2000)] = ""

    @field_validator("email")
    @classmethod
    def _blank_email(cls, value: EmailStr | None) -> EmailStr | None:
        return value or None


class ClientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    email: EmailStr | None = None
    company: Annotated[str, Field(max_length=160)] | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None
    archived: bool | None = None


class ClientOut(ApiModel):
    id: str
    name: str
    email: EmailStr | None
    company: str
    notes: str
    archived: bool
    created_at: datetime


# ----------------------------------------------------------------------- invoices


class LineItemIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    description: ShortText
    quantity: Annotated[Decimal, Field(gt=0, le=Decimal("100000"), max_digits=12, decimal_places=3)]
    unit_price_cents: Annotated[int, Field(ge=0, le=100_000_000)]

    @property
    def quantity_milli(self) -> int:
        return int((self.quantity * 1000).to_integral_value())


class InvoiceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    client_id: Annotated[str, Field(min_length=8, max_length=32)]
    items: Annotated[list[LineItemIn], Field(min_length=1, max_length=100)]
    currency: Annotated[str, Field(pattern=r"^[a-zA-Z]{3}$")] = "usd"
    tax_rate_bp: Annotated[int, Field(ge=0, le=10_000)] = 0
    discount_bp: Annotated[int, Field(ge=0, le=10_000)] = 0
    issue_date: datetime | None = None
    due_date: datetime | None = None
    notes: Annotated[str, Field(max_length=4000)] = ""


class InvoiceUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    client_id: Annotated[str, Field(min_length=8, max_length=32)] | None = None
    items: Annotated[list[LineItemIn], Field(min_length=1, max_length=100)] | None = None
    currency: Annotated[str, Field(pattern=r"^[a-zA-Z]{3}$")] | None = None
    tax_rate_bp: Annotated[int, Field(ge=0, le=10_000)] | None = None
    discount_bp: Annotated[int, Field(ge=0, le=10_000)] | None = None
    issue_date: datetime | None = None
    due_date: datetime | None = None
    notes: Annotated[str, Field(max_length=4000)] | None = None


class LineItemOut(ApiModel):
    id: str
    description: str
    quantity: Decimal
    unit_price_cents: int
    amount_cents: int


class InvoiceOut(ApiModel):
    id: str
    number: str
    status: str
    currency: str
    client: ClientOut
    items: list[LineItemOut]
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int
    notes: str
    issue_date: datetime
    due_date: datetime | None
    paid_at: datetime | None
    share_token: str | None
    share_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InvoiceSummary(ApiModel):
    id: str
    number: str
    status: str
    currency: str
    client_name: str
    client_company: str
    total_cents: int
    issue_date: datetime
    due_date: datetime | None
    created_at: datetime


class ShareLinkOut(BaseModel):
    token: str
    path: str
    expires_at: datetime | None


class StatusChangeOut(BaseModel):
    id: str
    status: str
    updated_at: datetime


class DashboardStats(BaseModel):
    total_invoices: int
    draft_count: int
    sent_count: int
    paid_count: int
    void_count: int
    outstanding_cents: int
    collected_cents: int
    client_count: int
    currency: str


# --------------------------------------------------------------------- pagination


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


# -------------------------------------------------------------------- attachments


class AttachmentOut(ApiModel):
    id: str
    original_name: str
    content_type: str
    size_bytes: int
    invoice_id: str | None
    created_at: datetime
    download_path: str


# ------------------------------------------------------------------------ billing


class PlanOut(BaseModel):
    current_plan: str
    price_cents: int
    currency: str
    features: list[str]


class CheckoutRequest(BaseModel):
    plan: Literal["pro"] = "pro"


class CheckoutOut(BaseModel):
    session_id: str
    url: str


# ------------------------------------------------------------------------- public


class PublicInvoiceOut(BaseModel):
    number: str
    status: str
    currency: str
    studio_name: str
    client_name: str
    client_company: str
    items: list[LineItemOut]
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int
    notes: str
    issue_date: datetime
    due_date: datetime | None


# ------------------------------------------------------------------------- admin


class AdminUserOut(ApiModel):
    id: str
    name: str
    email: EmailStr
    role: str
    plan: str
    is_active: bool
    created_at: datetime
    invoice_count: int


class RoleUpdateRequest(BaseModel):
    role: Literal[UserRole.USER, UserRole.ADMIN]


class AdminStatsOut(BaseModel):
    users: int
    active_users: int
    admins: int
    invoices: int
    clients: int
    paid_invoices: int
    gross_collected_cents: int


class AuditEventOut(ApiModel):
    id: str
    actor_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    ip_address: str | None
    created_at: datetime


InvoiceStatusLiteral = Literal[InvoiceStatus.DRAFT, InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.VOID]
UserPlanLiteral = Literal[UserPlan.FREE, UserPlan.PRO]
