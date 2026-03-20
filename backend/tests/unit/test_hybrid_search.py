"""Tests for hybrid search with RRF fusion."""
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.retrieval.bm25_search import ScoredChunk
from app.core.retrieval.hybrid_search import HybridSearch, HybridSearchConfig
from app.core.retrieval.query_transformer import TransformedQuery


class TestHybridSearch:
    """Unit tests for HybridSearch."""

    @pytest.fixture
    def mock_vector_search(self):
        """Create mock vector search."""
        mock = MagicMock()
        mock.search_by_vector = AsyncMock()
        return mock

    @pytest.fixture
    def mock_bm25_search(self):
        """Create mock BM25 search."""
        mock = MagicMock()
        mock.search_multi = AsyncMock()
        return mock

    @pytest.fixture
    def hybrid_search(self, mock_vector_search, mock_bm25_search):
        """Create HybridSearch with mocks."""
        return HybridSearch(
            vector_search=mock_vector_search,
            bm25_search=mock_bm25_search,
            config=HybridSearchConfig(rrf_k=60),
        )

    def create_chunk(self, id_str: str, content: str, score: float) -> ScoredChunk:
        """Helper to create test chunks."""
        return ScoredChunk(
            id=uuid.UUID(id_str),
            document_id=uuid.uuid4(),
            content=content,
            page_number=1,
            metadata={},
            filename="test.pdf",
            score=score,
        )

    @pytest.mark.asyncio
    async def test_rrf_fusion_basic(self, hybrid_search, mock_vector_search, mock_bm25_search):
        """RRF should correctly fuse results from both searches."""
        # Setup: A appears in both, B only in vector, C only in BM25
        chunk_a = self.create_chunk("00000000-0000-0000-0000-000000000001", "A", 0.9)
        chunk_b = self.create_chunk("00000000-0000-0000-0000-000000000002", "B", 0.8)
        chunk_c = self.create_chunk("00000000-0000-0000-0000-000000000003", "C", 0.7)

        # Vector: A (rank 0), B (rank 1)
        mock_vector_search.search_by_vector.return_value = [chunk_a, chunk_b]
        # BM25: C (rank 0), A (rank 1)
        mock_bm25_search.search_multi.return_value = [chunk_c, chunk_a]

        transformed = TransformedQuery(
            original="test",
            vector=[0.1] * 768,
            alt_queries=["test variant"],
        )

        results = await hybrid_search.search(transformed, top_k=3)

        # A should rank highest (appears in both)
        # RRF score A = 1/(60+1) + 1/(60+2) = 0.01639 + 0.01613 = 0.03252
        # RRF score B = 1/(60+2) = 0.01613
        # RRF score C = 1/(60+1) = 0.01639
        # Order: A > C > B
        assert len(results) == 3
        assert results[0].id == chunk_a.id
        assert results[1].id == chunk_c.id
        assert results[2].id == chunk_b.id

    @pytest.mark.asyncio
    async def test_rrf_sets_rrf_score(self, hybrid_search, mock_vector_search, mock_bm25_search):
        """RRF should set rrf_score on chunks."""
        chunk = self.create_chunk("00000000-0000-0000-0000-000000000001", "A", 0.9)

        mock_vector_search.search_by_vector.return_value = [chunk]
        mock_bm25_search.search_multi.return_value = []

        transformed = TransformedQuery(original="test", vector=[0.1] * 768)

        results = await hybrid_search.search(transformed, top_k=5)

        assert len(results) == 1
        assert results[0].rrf_score is not None
        assert results[0].rrf_score == pytest.approx(1 / 61, rel=0.01)  # 1/(60+1)

    @pytest.mark.asyncio
    async def test_search_uses_alt_queries(self, hybrid_search, mock_vector_search, mock_bm25_search):
        """Search should pass original + alt_queries to BM25."""
        mock_vector_search.search_by_vector.return_value = []
        mock_bm25_search.search_multi.return_value = []

        transformed = TransformedQuery(
            original="main query",
            vector=[0.1] * 768,
            alt_queries=["variant 1", "variant 2"],
        )

        await hybrid_search.search(transformed, top_k=5)

        # Check BM25 was called with all queries
        call_args = mock_bm25_search.search_multi.call_args
        queries = call_args[0][0]  # First positional arg
        assert "main query" in queries
        assert "variant 1" in queries
        assert "variant 2" in queries

    @pytest.mark.asyncio
    async def test_empty_results(self, hybrid_search, mock_vector_search, mock_bm25_search):
        """Empty results from both searches should return empty list."""
        mock_vector_search.search_by_vector.return_value = []
        mock_bm25_search.search_multi.return_value = []

        transformed = TransformedQuery(original="test", vector=[0.1] * 768)

        results = await hybrid_search.search(transformed, top_k=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_respects_top_k(self, hybrid_search, mock_vector_search, mock_bm25_search):
        """Should return at most top_k results."""
        chunks = [
            self.create_chunk(f"00000000-0000-0000-0000-00000000000{i}", f"chunk{i}", 0.9 - i * 0.1)
            for i in range(10)
        ]

        mock_vector_search.search_by_vector.return_value = chunks
        mock_bm25_search.search_multi.return_value = []

        transformed = TransformedQuery(original="test", vector=[0.1] * 768)

        results = await hybrid_search.search(transformed, top_k=3)

        assert len(results) == 3
