import hashlib
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
async def setup_db():
    yield

from app.main import app
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.document import Document
from app.models.user import User


def make_mock_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    return user


def make_mock_db():
    return AsyncMock(spec=AsyncSession)


@contextmanager
def client_with_db(mock_db):
    def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = make_mock_user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_upload_returns_409_when_content_already_exists():
    content = b"<html>identical content</html>"
    content_hash = hashlib.sha256(content).hexdigest()

    existing_doc = MagicMock(spec=Document)
    existing_doc.id = uuid.uuid4()
    existing_doc.filename = "already_uploaded.htm"
    existing_doc.content_hash = content_hash

    mock_db = make_mock_db()
    hash_check_result = MagicMock()
    hash_check_result.scalar_one_or_none.return_value = existing_doc
    mock_db.execute.return_value = hash_check_result

    with client_with_db(mock_db) as c:
        response = c.post(
            "/api/v1/documents/upload",
            files={"file": ("new_upload.htm", content, "text/html")},
            data={"doc_type": "general"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["existing_id"] == str(existing_doc.id)
    assert body["existing_filename"] == "already_uploaded.htm"


def test_upload_succeeds_with_replace_id():
    content = b"<html>replacement content</html>"
    replace_id = uuid.uuid4()

    old_doc = MagicMock(spec=Document)
    old_doc.id = replace_id
    old_doc.chroma_collection_id = None
    old_doc.file_path = "/tmp/old_file.htm"

    mock_db = make_mock_db()
    hash_check = MagicMock()
    hash_check.scalar_one_or_none.return_value = None
    old_doc_result = MagicMock()
    old_doc_result.scalar_one_or_none.return_value = old_doc
    asset_result = MagicMock()
    asset_result.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [hash_check, old_doc_result, asset_result]

    with client_with_db(mock_db) as c:
        with patch("pathlib.Path.exists", return_value=False), \
             patch("pathlib.Path.write_bytes"), \
             patch("pathlib.Path.unlink"):
            response = c.post(
                f"/api/v1/documents/upload?replace_id={replace_id}",
                files={"file": ("new.htm", content, "text/html")},
                data={"doc_type": "general"},
            )

    assert response.status_code == 202
    assert "document_id" in response.json()
