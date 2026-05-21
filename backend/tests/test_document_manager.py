import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document_manager import DocumentManager


@pytest.mark.asyncio
async def test_pre_fetch_skips_existing_url():
    doc_items = [{"url": "https://sec.gov/doc.htm", "doc_type": "10-Q", "filename": "doc.htm"}]

    mock_db = AsyncMock()
    existing_doc = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_doc
    mock_db.execute = AsyncMock(return_value=mock_result)

    manager = DocumentManager()
    result = await manager.pre_fetch(
        ticker="AAPL",
        asset_id=uuid.uuid4(),
        doc_items=doc_items,
        db=mock_db,
    )

    assert result["skipped"] == 1
    assert result["fetched"] == 0


@pytest.mark.asyncio
async def test_pre_fetch_downloads_new_url():
    doc_items = [{"url": "https://sec.gov/doc.htm", "doc_type": "10-Q", "filename": "doc.htm"}]

    mock_db = AsyncMock()
    mock_db.begin_nested = MagicMock(return_value=AsyncMock())
    no_result = MagicMock()
    no_result.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [no_result, no_result]

    fake_content = b"%PDF-1.4 fake pdf content"

    manager = DocumentManager()
    with patch.object(manager, "_download", new_callable=AsyncMock, return_value=fake_content), \
         patch.object(manager, "_save_file", return_value="/uploads/AAPL/10-Q/doc.htm"), \
         patch.object(manager, "_enqueue_ingest", new_callable=AsyncMock):
        result = await manager.pre_fetch(
            ticker="AAPL",
            asset_id=uuid.uuid4(),
            doc_items=doc_items,
            db=mock_db,
        )

    assert result["fetched"] == 1
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_pre_fetch_skips_duplicate_content_hash():
    """Same content downloaded twice should be skipped on second call."""
    manager = DocumentManager()
    content = b"<html>10-K filing content</html>"
    content_hash = hashlib.sha256(content).hexdigest()

    existing_doc = MagicMock()
    existing_doc.id = uuid.uuid4()

    db = AsyncMock()
    url_check_result = MagicMock()
    url_check_result.scalar_one_or_none.return_value = None
    hash_check_result = MagicMock()
    hash_check_result.scalar_one_or_none.return_value = existing_doc
    db.execute.side_effect = [url_check_result, hash_check_result]

    with patch.object(manager, "_download", new_callable=AsyncMock, return_value=content), \
         patch.object(manager, "_save_file"), \
         patch.object(manager, "_enqueue_ingest", new_callable=AsyncMock):
        result = await manager.pre_fetch(
            ticker="AAPL",
            asset_id=uuid.uuid4(),
            doc_items=[{
                "url": "https://sec.gov/Archives/10-K.htm",
                "doc_type": "10-K",
                "filename": "10-K_001.htm",
            }],
            db=db,
        )

    assert result["skipped"] == 1
    assert result["fetched"] == 0


@pytest.mark.asyncio
async def test_pre_fetch_saves_content_hash_on_new_doc():
    """New document should be saved with content_hash set."""
    manager = DocumentManager()
    content = b"<html>fresh 10-K content</html>"
    expected_hash = hashlib.sha256(content).hexdigest()
    asset_id = uuid.uuid4()

    db = AsyncMock()
    db.begin_nested = MagicMock(return_value=AsyncMock())
    no_result = MagicMock()
    no_result.scalar_one_or_none.return_value = None
    db.execute.side_effect = [no_result, no_result]

    saved_doc = None

    def capture_add(doc):
        nonlocal saved_doc
        saved_doc = doc

    db.add = MagicMock(side_effect=capture_add)

    with patch.object(manager, "_download", new_callable=AsyncMock, return_value=content), \
         patch.object(manager, "_save_file", return_value="/app/uploads/AAPL/10-K/doc.htm"), \
         patch.object(manager, "_enqueue_ingest", new_callable=AsyncMock):
        result = await manager.pre_fetch(
            ticker="AAPL",
            asset_id=asset_id,
            doc_items=[{
                "url": "https://sec.gov/Archives/10-K.htm",
                "doc_type": "10-K",
                "filename": "10-K_001.htm",
            }],
            db=db,
        )

    assert result["fetched"] == 1
    assert saved_doc is not None
    assert saved_doc.content_hash == expected_hash
