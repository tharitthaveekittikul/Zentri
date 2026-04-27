import pytest
from unittest.mock import MagicMock, patch


def _make_mock_collection(count=0):
    col = MagicMock()
    col.count.return_value = count
    col.query.return_value = {"documents": [["chunk about AAPL earnings"]]}
    return col


def test_search_returns_empty_when_collection_empty():
    from app.services.rag_service import search
    col = _make_mock_collection(count=0)
    result = search(col, query="revenue growth")
    assert result == []
    col.query.assert_not_called()


def test_search_returns_chunks_when_collection_has_data():
    from app.services.rag_service import search
    col = _make_mock_collection(count=3)
    result = search(col, query="earnings forecast")
    assert result == ["chunk about AAPL earnings"]


def test_add_chunks_calls_upsert():
    from app.services.rag_service import add_chunks
    col = MagicMock()
    add_chunks(
        col,
        chunks=["text chunk 1", "text chunk 2"],
        metadatas=[{"doc_id": "abc", "chunk_index": 0}, {"doc_id": "abc", "chunk_index": 1}],
        ids=["abc_0", "abc_1"],
    )
    col.upsert.assert_called_once()


def test_get_or_create_collection_uses_global_for_none():
    from app.services.rag_service import get_or_create_collection
    mock_client = MagicMock()
    with patch("app.services.rag_service._get_client", return_value=mock_client):
        get_or_create_collection(None)
    mock_client.get_or_create_collection.assert_called_once_with(name="global")


def test_get_or_create_collection_normalises_symbol():
    from app.services.rag_service import get_or_create_collection
    mock_client = MagicMock()
    with patch("app.services.rag_service._get_client", return_value=mock_client):
        get_or_create_collection("BTC/USDT")
    mock_client.get_or_create_collection.assert_called_once_with(name="btc_usdt")
