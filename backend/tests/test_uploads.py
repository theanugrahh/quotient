from __future__ import annotations

import io

from tests.conftest import BASE_URL, TINY_PNG


def _upload(client, *, name: str = "logo.png", content: bytes = TINY_PNG, content_type: str = "image/png", **extra):
    return client.post(
        f"{BASE_URL}/files/upload",
        files={"file": (name, io.BytesIO(content), content_type)},
        data=extra,
    )


def test_upload_and_download_a_logo(auth_client) -> None:
    response = _upload(auth_client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(TINY_PNG)

    download = auth_client.get(f"{BASE_URL}/files/{body['id']}/content")
    assert download.status_code == 200
    assert download.content == TINY_PNG
    assert download.headers["x-content-type-options"] == "nosniff"


def test_upload_rejects_non_image_content(auth_client) -> None:
    response = _upload(auth_client, name="notes.txt", content=b"just some text", content_type="text/plain")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_content_that_disagrees_with_the_declared_type(auth_client) -> None:
    response = _upload(auth_client, name="logo.jpg", content=TINY_PNG, content_type="image/jpeg")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "file_type_mismatch"


def test_upload_rejects_oversized_files(auth_client) -> None:
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024)
    response = _upload(auth_client, content=oversized)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "file_too_large"


def test_upload_rejects_empty_files(auth_client) -> None:
    response = _upload(auth_client, content=b"")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_file"


def test_upload_strips_path_traversal_from_the_filename(auth_client) -> None:
    response = _upload(auth_client, name="../../etc/passwd.png")
    assert response.status_code == 201
    assert "/" not in response.json()["original_name"]
    assert ".." not in response.json()["original_name"]


def test_upload_can_be_attached_to_an_invoice(auth_client) -> None:
    from tests.conftest import create_client_record, create_invoice

    client_record = create_client_record(auth_client)
    invoice = create_invoice(auth_client, client_record["id"])
    response = _upload(auth_client, invoice_id=invoice["id"])
    assert response.status_code == 201
    assert response.json()["invoice_id"] == invoice["id"]


def test_upload_rejects_an_unknown_invoice(auth_client) -> None:
    response = _upload(auth_client, invoice_id="0" * 32)
    assert response.status_code == 404


def test_files_are_not_shared_between_accounts(auth_client, second_client) -> None:
    created = _upload(auth_client).json()
    assert second_client.get(f"{BASE_URL}/files/{created['id']}/content").status_code == 404
    assert second_client.delete(f"{BASE_URL}/files/{created['id']}").status_code == 404


def test_upload_requires_authentication(client) -> None:
    response = _upload(client)
    assert response.status_code == 401
