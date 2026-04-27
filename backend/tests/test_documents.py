import io
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_documents_empty(auth_client: AsyncClient):
    resp = await auth_client.get("/api/v1/documents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_upload_document(auth_client: AsyncClient):
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    resp = await auth_client.post(
        "/api/v1/documents/upload",
        files={"file": ("test_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "annual_report"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "document_id" in body
    assert body["status"] == "pending"


@pytest.mark.anyio
async def test_list_documents_after_upload(auth_client: AsyncClient):
    pdf_bytes = b"%PDF-1.4 fake pdf"
    await auth_client.post(
        "/api/v1/documents/upload",
        files={"file": ("report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "earnings"},
    )
    resp = await auth_client.get("/api/v1/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1
    assert docs[0]["filename"] == "report.pdf"
    assert docs[0]["status"] == "pending"


@pytest.mark.anyio
async def test_delete_document(auth_client: AsyncClient):
    pdf_bytes = b"%PDF-1.4 fake pdf"
    upload = await auth_client.post(
        "/api/v1/documents/upload",
        files={"file": ("del_me.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        data={"doc_type": "research"},
    )
    doc_id = upload.json()["document_id"]
    del_resp = await auth_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    list_resp = await auth_client.get("/api/v1/documents")
    assert list_resp.json() == []
