from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.errors import UnsupportedMediaTypeError, ValidationError
from app.models import Attachment

_MAGIC: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
]

_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str | None) -> str:
    name = Path(filename or "").name
    name = _SAFE_NAME.sub("_", name).strip("._")
    return name[:120] or "upload"


def sniff_content_type(data: bytes) -> str | None:
    for signature, content_type in _MAGIC:
        if data.startswith(signature):
            return content_type
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def extension_for(content_type: str) -> str:
    return _EXTENSIONS.get(content_type, "")


def store_upload(
    db: Session,
    *,
    data: bytes,
    filename: str,
    declared_content_type: str,
    owner_id: str,
    invoice_id: str | None = None,
) -> Attachment:
    if not data:
        raise ValidationError("The uploaded file is empty.", code="empty_file")
    if len(data) > settings.max_upload_bytes:
        raise ValidationError(
            f"Files must be smaller than {settings.max_upload_bytes // (1024 * 1024)}MB.", code="file_too_large"
        )

    detected = sniff_content_type(data)
    if detected is None or detected not in settings.allowed_upload_types:
        raise UnsupportedMediaTypeError(
            "Only PNG, JPEG and WebP images are accepted.", code="unsupported_file_type"
        )
    if declared_content_type and declared_content_type != detected:
        raise UnsupportedMediaTypeError(
            "The file content does not match the declared file type.", code="file_type_mismatch"
        )

    stored_name = f"{uuid.uuid4().hex}{extension_for(detected)}"
    directory = Path(settings.uploads_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / stored_name
    target.write_bytes(data)

    attachment = Attachment(
        owner_id=owner_id,
        invoice_id=invoice_id,
        original_name=sanitize_filename(filename),
        stored_name=stored_name,
        content_type=detected,
        size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(attachment)
    return attachment


def read_upload(stored_name: str) -> bytes | None:
    directory = Path(settings.uploads_dir)
    candidate = (directory / stored_name).resolve()
    if candidate.parent != directory.resolve() or not candidate.is_file():
        return None
    return candidate.read_bytes()


def remove_upload(stored_name: str) -> None:
    directory = Path(settings.uploads_dir)
    candidate = (directory / stored_name).resolve()
    if candidate.parent != directory.resolve():
        return
    candidate.unlink(missing_ok=True)
