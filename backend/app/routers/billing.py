from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.config import settings
from app.deps import CsrfGuard, CurrentUser, DbSession, get_current_user, rate_limited, record_audit
from app.errors import NotFoundError, PermissionDenied
from app.models import Payment, UserPlan
from app.payments import get_provider
from app.routers.webhooks import build_mock_payload, process_webhook, sign_mock_payload
from app.schemas import CheckoutOut, CheckoutRequest, PlanOut

router = APIRouter(prefix="/billing", tags=["billing"])

FEATURES = [
    "Unlimited clients and invoices",
    "Shareable client invoice links",
    "Pro plan with priority support",
]


@router.get("/plan", response_model=PlanOut)
def current_plan(user: CurrentUser) -> PlanOut:
    return PlanOut(
        current_plan=user.plan,
        price_cents=settings.plan_price_cents,
        currency=settings.plan_currency,
        features=FEATURES,
    )


@router.get("/payments")
def list_payments(user: CurrentUser, db: DbSession) -> list[dict]:
    rows = db.execute(
        select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc())
    ).scalars().all()
    return [
        {
            "id": row.id,
            "provider": row.provider,
            "amount_cents": row.amount_cents,
            "currency": row.currency,
            "status": row.status,
            "plan": row.plan,
            "invoice_id": row.invoice_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    dependencies=[Depends(get_current_user), CsrfGuard, Depends(rate_limited("checkout", limit=20, window=60))],
)
def create_checkout(
    payload: CheckoutRequest,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> CheckoutOut:
    provider = get_provider()
    session = provider.create_checkout(
        user_id=user.id,
        user_email=user.email,
        plan=payload.plan,
        amount_cents=settings.plan_price_cents,
        currency=settings.plan_currency,
    )

    db.add(
        Payment(
            user_id=user.id,
            provider=provider.name,
            provider_ref=session.session_id,
            amount_cents=settings.plan_price_cents,
            currency=settings.plan_currency,
            status="pending",
            plan=payload.plan,
        )
    )
    record_audit(db, action="billing.checkout", entity_type="user", entity_id=user.id, actor_id=user.id)
    db.commit()

    return CheckoutOut(session_id=session.session_id, url=session.path)


@router.get("/mock/checkout/{session_id}", response_class=HTMLResponse)
def mock_checkout_page(session_id: str, request: Request, user: CurrentUser, db: DbSession) -> HTMLResponse:
    payment = db.execute(
        select(Payment).where(Payment.provider == "mock", Payment.provider_ref == session_id)
    ).scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Checkout session not found.", code="session_not_found")
    if payment.user_id != user.id:
        raise PermissionDenied("This checkout session belongs to another account.")

    return_to = request.query_params.get("return_to", "/billing")
    amount = payment.amount_cents / 100
    label = "Quotient Pro plan" if payment.plan == UserPlan.PRO else f"Invoice payment {payment.invoice_id or ''}"
    csrf_cookie = settings.csrf_cookie_name

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Checkout · Quotient</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; background:#0b1020; color:#e6e9f5;
         display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; padding:1.25rem; }}
  .card {{ background:#141a2f; border:1px solid #243052; border-radius:16px;
           padding:1.75rem; max-width:26rem; width:100%; }}
  h1 {{ font-size:1.15rem; margin:0 0 .35rem; }}
  p {{ color:#9aa5c4; font-size:.9rem; margin:.25rem 0; }}
  .amount {{ font-size:2rem; font-weight:700; margin:1rem 0 .35rem; }}
  button {{ width:100%; margin-top:1.25rem; padding:.8rem 1rem; border:0; border-radius:10px; font-size:.95rem;
            font-weight:600; background:#5b7cfa; color:#fff; cursor:pointer; }}
  button:disabled {{ opacity:.6; cursor:not-allowed; }}
  .note {{ font-size:.78rem; color:#6d7899; margin-top:1rem; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Quotient sandbox checkout</h1>
    <p>{label}</p>
    <div class="amount">${amount:,.2f}</div>
    <p class="note">No real money moves here. The request is signed and delivered through the same
       webhook verification path used by Stripe.</p>
    <button id="pay">Pay ${amount:,.2f}</button>
    <p class="note" id="status"></p>
  </div>
<script>
  const readCookie = (name) => document.cookie.split('; ')
    .map(part => part.trim())
    .find(part => part.startsWith(name + '='))
    ?.split('=')[1] || '';
  const button = document.getElementById('pay');
  const status = document.getElementById('status');
  button.addEventListener('click', async () => {{
    button.disabled = true;
    status.textContent = 'Processing…';
    try {{
      const response = await fetch('/api/billing/mock/checkout/{session_id}/complete', {{
        method: 'POST',
        credentials: 'include',
        headers: {{ 'X-CSRF-Token': readCookie('{csrf_cookie}') }},
      }});
      if (!response.ok) throw new Error('Payment could not be completed.');
      window.location.href = '{settings.app_url}' + '{return_to}' + '?paid=1';
    }} catch (error) {{
      status.textContent = error.message;
      button.disabled = false;
    }}
  }});
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/mock/checkout/{session_id}/complete", dependencies=[Depends(get_current_user), CsrfGuard])
def complete_mock_checkout(session_id: str, user: CurrentUser, db: DbSession) -> dict:
    payment = db.execute(
        select(Payment).where(Payment.provider == "mock", Payment.provider_ref == session_id)
    ).scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Checkout session not found.", code="session_not_found")
    if payment.user_id != user.id:
        raise PermissionDenied("This checkout session belongs to another account.")

    payload = build_mock_payload(
        event_id=f"evt_mock_{uuid.uuid4().hex[:20]}",
        session_id=session_id,
        user_id=payment.user_id,
        plan=payment.plan,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
    )
    signature = sign_mock_payload(payload)
    result = process_webhook(provider="mock", payload=payload, signature=signature, db=db)
    return {"status": result.get("status"), "completed_at": datetime.now(UTC).isoformat()}
