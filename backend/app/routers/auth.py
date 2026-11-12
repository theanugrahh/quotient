from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from app.config import settings
from app.deps import CsrfGuard, CurrentUser, DbSession, get_client_ip, rate_limited, record_audit
from app.errors import AuthenticationError, ConflictError, ValidationError
from app.models import User, UserRole
from app.schemas import (
    CsrfOut,
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    SessionOut,
    SessionStateOut,
    UserOut,
)
from app.security import (
    TokenError,
    create_access_token,
    create_csrf_token,
    decode_access_token,
    dummy_verify,
    hash_password,
    password_problems,
    verify_password,
)
from app.session import clear_auth_cookies, ensure_csrf_cookie, set_auth_cookies

router = APIRouter(prefix="/auth", tags=["auth"])

auth_rate_limit = rate_limited("auth")


@router.get("/csrf", response_model=CsrfOut)
def issue_csrf(request: Request, response: Response) -> CsrfOut:
    existing = request.cookies.get(settings.csrf_cookie_name)
    if existing:
        return CsrfOut(csrf_token=existing)
    token = ensure_csrf_cookie(response)
    return CsrfOut(csrf_token=token)



@router.post(
    "/register",
    response_model=SessionOut,
    status_code=201,
    dependencies=[Depends(auth_rate_limit), CsrfGuard],
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> SessionOut:
    email = payload.email.lower()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("An account with this email already exists.", code="email_taken")

    problems = password_problems(payload.password)
    if problems:
        raise ValidationError(problems[0], code="weak_password", details={"problems": problems})

    role = UserRole.ADMIN if email in settings.admin_emails else UserRole.USER
    user = User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    csrf_token = create_csrf_token()
    token, expires_at = create_access_token(user_id=user.id, role=user.role, csrf_token=csrf_token)
    set_auth_cookies(response, token=token, csrf_token=csrf_token, expires_at=expires_at)

    record_audit(
        db,
        action="auth.register",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()

    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf_token, expires_at=expires_at)


@router.post("/login", response_model=SessionOut, dependencies=[Depends(auth_rate_limit), CsrfGuard])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> SessionOut:
    email = payload.email.lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()

    if user is None:
        dummy_verify()
        raise AuthenticationError("Incorrect email or password.", code="invalid_credentials")
    if not verify_password(payload.password, user.password_hash):
        raise AuthenticationError("Incorrect email or password.", code="invalid_credentials")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated.", code="account_disabled")

    user.last_login_at = datetime.now(UTC)
    csrf_token = create_csrf_token()
    token, expires_at = create_access_token(user_id=user.id, role=user.role, csrf_token=csrf_token)
    set_auth_cookies(response, token=token, csrf_token=csrf_token, expires_at=expires_at)

    record_audit(
        db,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()

    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf_token, expires_at=expires_at)


@router.post("/logout", status_code=204, dependencies=[CsrfGuard])
def logout(response: Response) -> Response:
    clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.get("/session", response_model=SessionStateOut)
def session_state(request: Request, db: DbSession) -> SessionStateOut:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return SessionStateOut(user=None)
    try:
        payload = decode_access_token(token)
    except TokenError:
        return SessionStateOut(user=None)
    user = db.get(User, payload.get("sub", ""))
    if user is None or not user.is_active:
        return SessionStateOut(user=None)
    return SessionStateOut(user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/password", status_code=204, dependencies=[CsrfGuard])
def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    if not verify_password(payload.current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect.", code="invalid_credentials")

    problems = password_problems(payload.new_password)
    if problems:
        raise ValidationError(problems[0], code="weak_password", details={"problems": problems})

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=204)
