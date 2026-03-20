"""Integration tests for retrieval pipeline."""
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRetrievalPipelineIntegration:
    """Integration tests for the full retrieval pipeline."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_qdrant(self):
        """Create mock Qdrant client."""
        mock = AsyncMock()
        mock.search = AsyncMock(return_value=[])
        return mock

    @pytest.mark.asyncio
    async def test_pipeline_end_to_end_with_results(self, mock_session):
        """Test pipeline from query to ranked results."""
        from app.core.retrieval.pipeline import RetrievalPipeline
        from app.core.retrieval.bm25_search import ScoredChunk

        # Create test chunk
        test_chunk = ScoredChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="Doanh thu quý 3 năm 2024 đạt 150 tỷ đồng, tăng 20% so với cùng kỳ.",
            page_number=5,
            metadata={},
            filename="bao_cao_tai_chinh.pdf",
            score=0.85,
            vector_score=0.85,
        )

        with patch('app.core.retrieval.pipeline.embed_query') as mock_embed, \
             patch('app.core.retrieval.vector_search.get_qdrant'), \
             patch.object(RetrievalPipeline, '__init__', lambda self, **kwargs: None):

            # Setup mock embedder
            mock_embed.return_value = [0.1] * 768

            # Create pipeline manually with mocked components
            pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
            pipeline.session = mock_session
            pipeline.use_hyde = False  # Skip for faster test
            pipeline.use_reranker = False

            # Mock transformer
            from app.core.retrieval.query_transformer import TransformedQuery
            mock_transformer = MagicMock()
            mock_transformer.transform = AsyncMock(return_value=TransformedQuery(
                original="doanh thu Q3",
                vector=[0.1] * 768,
                alt_queries=["revenue Q3", "kết quả kinh doanh quý 3"],
            ))
            pipeline.transformer = mock_transformer

            # Mock hybrid search
            mock_hybrid = MagicMock()
            mock_hybrid.search = AsyncMock(return_value=[test_chunk])
            pipeline.hybrid_search = mock_hybrid

            # Mock reranker
            mock_reranker = MagicMock()
            mock_reranker.is_available.return_value = False
            pipeline.reranker = mock_reranker

            # Run pipeline
            result = await pipeline.run("doanh thu Q3", top_k=5)

            # Verify results
            assert result.has_results is True
            assert len(result.chunks) == 1
            assert result.chunks[0].content == test_chunk.content
            assert len(result.sources) == 1
            assert result.sources[0].doc_name == "bao_cao_tai_chinh.pdf"

    @pytest.mark.asyncio
    async def test_pipeline_with_no_results(self, mock_session):
        """Test pipeline handles no results gracefully."""
        from app.core.retrieval.pipeline import RetrievalPipeline

        with patch('app.core.retrieval.pipeline.embed_query') as mock_embed, \
             patch.object(RetrievalPipeline, '__init__', lambda self, **kwargs: None):

            mock_embed.return_value = [0.1] * 768

            # Create pipeline with empty results
            pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
            pipeline.session = mock_session
            pipeline.use_hyde = False
            pipeline.use_reranker = False

            # Mock transformer
            from app.core.retrieval.query_transformer import TransformedQuery
            mock_transformer = MagicMock()
            mock_transformer.transform = AsyncMock(return_value=TransformedQuery(
                original="xyzabc gibberish",
                vector=[0.1] * 768,
            ))
            pipeline.transformer = mock_transformer

            # Mock hybrid search returning empty
            mock_hybrid = MagicMock()
            mock_hybrid.search = AsyncMock(return_value=[])
            pipeline.hybrid_search = mock_hybrid

            # Mock reranker
            mock_reranker = MagicMock()
            mock_reranker.is_available.return_value = False
            pipeline.reranker = mock_reranker

            # Run pipeline
            result = await pipeline.run("xyzabc gibberish", top_k=5)

            # Verify empty results
            assert result.has_results is False
            assert result.chunks == []
            assert result.sources == []

    @pytest.mark.asyncio
    async def test_pipeline_debug_info(self, mock_session):
        """Test pipeline includes debug information."""
        from app.core.retrieval.pipeline import RetrievalPipeline
        from app.core.retrieval.bm25_search import ScoredChunk

        test_chunk = ScoredChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="Test content",
            page_number=1,
            metadata={},
            filename="test.pdf",
            score=0.8,
        )

        with patch('app.core.retrieval.pipeline.embed_query') as mock_embed, \
             patch.object(RetrievalPipeline, '__init__', lambda self, **kwargs: None):

            mock_embed.return_value = [0.1] * 768

            pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
            pipeline.session = mock_session
            pipeline.use_hyde = True
            pipeline.use_reranker = False

            # Mock transformer with HyDE
            from app.core.retrieval.query_transformer import TransformedQuery
            mock_transformer = MagicMock()
            mock_transformer.transform = AsyncMock(return_value=TransformedQuery(
                original="test query",
                vector=[0.1] * 768,
                alt_queries=["alternative 1", "alternative 2"],
                hyde_answer="This is a hypothetical answer about the test query.",
            ))
            pipeline.transformer = mock_transformer

            mock_hybrid = MagicMock()
            mock_hybrid.search = AsyncMock(return_value=[test_chunk])
            pipeline.hybrid_search = mock_hybrid

            mock_reranker = MagicMock()
            mock_reranker.is_available.return_value = False
            pipeline.reranker = mock_reranker

            result = await pipeline.run("test query", top_k=5)

            # Verify debug info
            assert "hyde_answer" in result.debug
            assert result.debug["hyde_answer"] is not None
            assert "alt_queries" in result.debug
            assert len(result.debug["alt_queries"]) == 2
            assert "candidates_count" in result.debug
