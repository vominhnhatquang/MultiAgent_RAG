"""Tests for reranker."""
import uuid

from unittest.mock import MagicMock, patch

from app.core.retrieval.bm25_search import ScoredChunk
from app.core.retrieval.reranker import Reranker


class TestReranker:
    """Unit tests for Reranker."""

    def create_chunk(self, content: str, score: float) -> ScoredChunk:
        """Helper to create test chunks."""
        return ScoredChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content=content,
            page_number=1,
            metadata={},
            filename="test.pdf",
            score=score,
            rrf_score=score,
        )

    def test_rerank_empty_input(self):
        """Reranking empty list should return empty list."""
        reranker = Reranker(lazy_load=True)
        # Mock model to avoid loading
        reranker._model = MagicMock()

        result = reranker.rerank("test query", [], top_k=5)

        assert result == []

    def test_rerank_with_mock_model(self):
        """Reranker should improve ranking based on relevance."""
        reranker = Reranker(lazy_load=True)

        # Create mock model
        mock_model = MagicMock()
        # Irrelevant chunk gets low score, relevant chunk gets high score
        mock_model.predict.return_value = [0.2, 0.9]
        reranker._model = mock_model

        chunks = [
            self.create_chunk("thời tiết hôm nay đẹp", 0.9),  # Irrelevant but high initial score
            self.create_chunk("doanh thu Q3 đạt 150 tỷ", 0.5),  # Relevant but low initial score
        ]

        result = reranker.rerank("doanh thu Q3", chunks, top_k=2)

        # Relevant chunk should now be first
        assert result[0].content == "doanh thu Q3 đạt 150 tỷ"
        assert result[0].rerank_score == 0.9

    def test_rerank_sets_rerank_score(self):
        """Reranker should set rerank_score on all chunks."""
        reranker = Reranker(lazy_load=True)

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.5, 0.7, 0.3]
        reranker._model = mock_model

        chunks = [
            self.create_chunk("A", 0.9),
            self.create_chunk("B", 0.8),
            self.create_chunk("C", 0.7),
        ]

        result = reranker.rerank("query", chunks, top_k=3)

        # All chunks should have rerank_score set
        for chunk in result:
            assert chunk.rerank_score is not None

    def test_rerank_respects_top_k(self):
        """Reranker should return at most top_k results."""
        reranker = Reranker(lazy_load=True)

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.8, 0.7, 0.6, 0.5]
        reranker._model = mock_model

        chunks = [self.create_chunk(f"chunk{i}", 0.5) for i in range(5)]

        result = reranker.rerank("query", chunks, top_k=2)

        assert len(result) == 2

    def test_rerank_fallback_when_model_unavailable(self):
        """Should fall back to original scores when model unavailable."""
        reranker = Reranker(lazy_load=True)
        reranker._model = None  # Simulate model not available

        chunks = [
            self.create_chunk("A", 0.9),
            self.create_chunk("B", 0.5),
        ]

        # Patch _get_reranker to return None
        with patch('app.core.retrieval.reranker._get_reranker', return_value=None):
            result = reranker.rerank("query", chunks, top_k=2)

        # Should use original scores
        assert result[0].rerank_score == 0.9
        assert result[1].rerank_score == 0.5

    def test_rerank_handles_predict_exception(self):
        """Should handle exceptions from model.predict gracefully."""
        reranker = Reranker(lazy_load=True)

        mock_model = MagicMock()
        mock_model.predict.side_effect = Exception("Model error")
        reranker._model = mock_model

        chunks = [
            self.create_chunk("A", 0.9),
            self.create_chunk("B", 0.5),
        ]

        result = reranker.rerank("query", chunks, top_k=2)

        # Should fall back to original scores without raising
        assert len(result) == 2

    def test_is_available(self):
        """is_available should return True when model is loaded."""
        reranker = Reranker(lazy_load=True)

        # Not loaded yet
        reranker._model = None
        with patch('app.core.retrieval.reranker._get_reranker', return_value=None):
            assert reranker.is_available() is False

        # Loaded
        reranker._model = MagicMock()
        assert reranker.is_available() is True
