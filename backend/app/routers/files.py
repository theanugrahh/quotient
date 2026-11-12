from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from app.config import settings
from app.deps import CsrfGuard, CurrentUser, DbSession, get_current_user, rate_limited, record_audit
from app.errors import NotFoundError, ValidationError
from app.models import Attachment, Invoice
from app.schemas import AttachmentOut
from app.storage import read_upload, remove_upload, store_upload

router = APIRouter(prefix="/files", tags=["files"])

_CHUNK_SIZE = 64 * 1024


def _owned_attachment(attachment_id: str, user_id: str, db) -> Attachment:
    attachment = db.execute(
        select(Attachment).where(Attachment.id == attachment_id, Attachment.owner_id == user_id)
    ).scalar_one_or_none()
    if attachment is None:
        raise NotFoundError("File not found.", code="file_not_found")
    return attachment


def _to_out(attachment: Attachment) -> AttachmentOut:
    return AttachmentOut(
        id=attachment.id,
        original_name=attachment.original_name,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        invoice_id=attachment.invoice_id,
        created_at=attachment.created_at,
        download_path=f"{settings.api_prefix}/files/{attachment.id}/content",
    )


@router.get("", response_model=list[AttachmentOut])
def list_files(user: CurrentUser, db: DbSession) -> list[AttachmentOut]:
    rows = db.execute(
        select(Attachment).where(Attachment.owner_id == user.id).order_by(Attachment.created_at.desc())
    ).scalars().all()
    return [_to_out(row) for row in rows]


@router.post(
    "/upload",
    response_model=AttachmentOut,
    status_code=201,
    dependencies=[
        Depends(get_current_user),
        CsrfGuard,
        Depends(rate_limited("upload", limit=20, window=60)),
    ],
)
async def upload_file(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    invoice_id: str | None = Form(default=None),
) -> AttachmentOut:
    if invoice_id:
        invoice = db.execute(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.owner_id == user.id)
        ).scalar_one_or_none()
        if invoice is None:
            raise NotFoundError("Invoice not found.", code="invoice_not_found")

    payload = await _read_limited(file)
    attachment = store_upload(
        db,
        data=payload,
        filename=file.filename or "upload",
        declared_content_type=(file.content_type or "").split(";")[0].strip().lower(),
        owner_id=user.id,
        invoice_id=invoice_id,
    )
    record_audit(
        db,
        action="file.upload",
        entity_type="attachment",
        entity_id=attachment.id,
        actor_id=user.id,
    )
    db.commit()
    db.refresh(attachment)
    return _to_out(attachment)


@router.get("/{attachment_id}/content")
def download_file(attachment_id: str, user: CurrentUser, db: DbSession) -> Response:
    attachment = _owned_attachment(attachment_id, user.id, db)
    payload = read_upload(attachment.stored_name)
    if payload is None:
        raise NotFoundError("File not found.", code="file_missing")
    return Response(
        content=payload,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{attachment.original_name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{attachment_id}", status_code=204, dependencies=[Depends(get_current_user), CsrfGuard])
def delete_file(attachment_id: str, user: CurrentUser, db: DbSession) -> None:
    attachment = _owned_attachment(attachment_id, user.id, db)
    remove_upload(attachment.stored_name)
    db.delete(attachment)
    db.commit()


async def _read_limited(file: UploadFile) -> bytes:
    limit = settings.max_upload_bytes
    buffer = bytearray()
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > limit:
            raise ValidationError(
                f"Files must be smaller than {limit // (1024 * 1024)}MB.", code="file_too_large"
            )
    return bytes(buffer)
