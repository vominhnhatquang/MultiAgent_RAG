"""Tests for BM25 search."""
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.retrieval.bm25_search import BM25Search, ScoredChunk


class TestBM25Search:
    """Unit tests for BM25Search."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def bm25_search(self, mock_session):
        """Create BM25Search instance with mock session."""
        return BM25Search(session=mock_session)

    @pytest.mark.asyncio
    async def test_search_empty_query(self, bm25_search):
        """Empty query should return empty list."""
        results = await bm25_search.search("", limit=20)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_whitespace_query(self, bm25_search):
        """Whitespace-only query should return empty list."""
        results = await bm25_search.search("   ", limit=20)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_scored_chunks(self, bm25_search, mock_session):
        """Search should return ScoredChunk objects."""
        # Setup mock result
        mock_row = MagicMock()
        mock_row.id = uuid.uuid4()
        mock_row.document_id = uuid.uuid4()
        mock_row.content = "doanh thu quý 3 đạt 150 tỷ"
        mock_row.page_number = 1
        mock_row.metadata = {}
        mock_row.filename = "report.pdf"
        mock_row.score = 0.85

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await bm25_search.search("doanh thu quý 3", limit=5)

        assert len(results) == 1
        assert isinstance(results[0], ScoredChunk)
        assert results[0].content == "doanh thu quý 3 đạt 150 tỷ"
        assert results[0].bm25_score == 0.85

    @pytest.mark.asyncio
    async def test_search_no_match(self, bm25_search, mock_session):
        """Query with no matches should return empty list."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        results = await bm25_search.search("xyzabc123gibberish", limit=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_multi_deduplicates(self, bm25_search, mock_session):
        """search_multi should deduplicate results across queries."""
        chunk_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        def create_mock_row(score):
            row = MagicMock()
            row.id = chunk_id  # Same ID
            row.document_id = doc_id
            row.content = "shared content"
            row.page_number = 1
            row.metadata = {}
            row.filename = "doc.pdf"
            row.score = score
            return row

        # First query returns score 0.8, second returns 0.9
        call_count = [0]

        def side_effect(*args, **kwargs):
            result = MagicMock()
            if call_count[0] == 0:
                result.fetchall.return_value = [create_mock_row(0.8)]
            else:
                result.fetchall.return_value = [create_mock_row(0.9)]
            call_count[0] += 1
            return result

        mock_session.execute.side_effect = side_effect

        results = await bm25_search.search_multi(
            ["query1", "query2"],
            limit=10,
        )

        # Should deduplicate to 1 result with the higher score
        assert len(results) == 1
        assert results[0].id == chunk_id
        assert results[0].score == 0.9  # Higher score wins

    @pytest.mark.asyncio
    async def test_search_multi_empty_queries(self, bm25_search, mock_session):
        """search_multi should handle empty query strings."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await bm25_search.search_multi(
            ["", "  ", "valid query"],
            limit=10,
        )

        # Only "valid query" should trigger a search
        assert mock_session.execute.call_count == 1
