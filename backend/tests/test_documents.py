"""Tests for document upload and management endpoints."""
import io
import pytest
from unittest.mock import patch, MagicMock


SAMPLE_PDF_BYTES = b"%PDF-1.4 1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"


def _mock_minio():
    """Return a context manager that mocks MinIO upload/download."""
    mock_svc = MagicMock()
    mock_svc.upload_file.return_value = None
    mock_svc.download_file.return_value = SAMPLE_PDF_BYTES
    return patch("app.api.documents.minio_service", mock_svc)


def test_upload_pdf(client):
    with _mock_minio():
        resp = client.post(
            "/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["filename"] == "test.pdf"
    assert data["status"] == "uploaded"


def test_upload_invalid_extension(client):
    with _mock_minio():
        resp = client.post(
            "/documents/upload",
            files={"file": ("test.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
        )
    assert resp.status_code == 400


def test_list_documents_empty(client):
    resp = client.get("/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert "documents" in data
    assert "total" in data
    assert isinstance(data["documents"], list)


def test_list_documents_after_upload(client):
    with _mock_minio():
        client.post(
            "/documents/upload",
            files={"file": ("list_test.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
        )
    resp = client.get("/documents")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_get_document_not_found(client):
    import uuid
    resp = client.get(f"/documents/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_document_by_id(client):
    with _mock_minio():
        upload = client.post(
            "/documents/upload",
            files={"file": ("byid.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
        )
    doc_id = upload.json()["id"]
    resp = client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id


def test_get_processing_status(client):
    with _mock_minio():
        upload = client.post(
            "/documents/upload",
            files={"file": ("status.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
        )
    doc_id = upload.json()["id"]
    resp = client.get(f"/documents/{doc_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "document_id" in data
    assert "status" in data


def test_get_pages_no_processing(client):
    with _mock_minio():
        upload = client.post(
            "/documents/upload",
            files={"file": ("pages.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
        )
    doc_id = upload.json()["id"]
    resp = client.get(f"/documents/{doc_id}/pages")
    assert resp.status_code == 200
    data = resp.json()
    assert "pages" in data
    assert "total" in data


def test_get_chunks_no_processing(client):
    with _mock_minio():
        upload = client.post(
            "/documents/upload",
            files={"file": ("chunks.pdf", io.BytesIO(SAMPLE_PDF_BYTES), "application/pdf")},
        )
    doc_id = upload.json()["id"]
    resp = client.get(f"/documents/{doc_id}/chunks")
    assert resp.status_code == 200
    data = resp.json()
    assert "chunks" in data
