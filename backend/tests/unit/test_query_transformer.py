"""Tests for query transformer (HyDE + multi-query)."""
import pytest
from unittest.mock import AsyncMock, patch

from app.core.retrieval.query_transformer import QueryTransformer, TransformedQuery


class TestQueryTransformer:
    """Unit tests for QueryTransformer."""

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedder function."""
        async def embedder(text: str) -> list[float]:
            # Return a simple 768-dim vector based on text hash
            return [float(hash(text) % 100) / 100] * 768
        return embedder

    @pytest.fixture
    def transformer(self, mock_embedder):
        """Create QueryTransformer with mock embedder."""
        return QueryTransformer(embedder_func=mock_embedder)

    @pytest.mark.asyncio
    async def test_transform_returns_transformed_query(self, transformer):
        """transform should return TransformedQuery object."""
        with patch.object(transformer, '_ollama_generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                "Đây là câu trả lời giả định về lợi nhuận năm 2024...",  # HyDE
                "Kết quả kinh doanh 2024\nThu nhập ròng năm ngoái\nBáo cáo tài chính",  # Multi-query
            ]

            result = await transformer.transform("lợi nhuận năm 2024")

            assert isinstance(result, TransformedQuery)
            assert result.original == "lợi nhuận năm 2024"
            assert len(result.vector) == 768
            assert result.hyde_answer is not None

    @pytest.mark.asyncio
    async def test_hyde_answer_length_cap(self, transformer):
        """HyDE answer should be capped at 500 chars."""
        with patch.object(transformer, '_ollama_generate', new_callable=AsyncMock) as mock_gen:
            long_answer = "A" * 1000
            mock_gen.side_effect = [long_answer, "alt1\nalt2"]

            result = await transformer.transform("test query")

            assert len(result.hyde_answer) <= 500

    @pytest.mark.asyncio
    async def test_multi_query_filters_original(self, transformer):
        """Multi-query should filter out variants identical to original."""
        with patch.object(transformer, '_ollama_generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                "HyDE answer",
                "test query\nDifferent phrasing\nAnother way",
            ]

            result = await transformer.transform("test query")

            # "test query" should be filtered out
            assert "test query" not in result.alt_queries
            assert len(result.alt_queries) <= 3

    @pytest.mark.asyncio
    async def test_transform_without_hyde(self, transformer):
        """transform with use_hyde=False should skip HyDE."""
        with patch.object(transformer, '_ollama_generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "alt1\nalt2\nalt3"

            result = await transformer.transform(
                "test",
                use_hyde=False,
                use_multi_query=True,
            )

            assert result.hyde_answer is None
            # Vector should be pure query embedding (not weighted)
            assert len(result.vector) == 768

    @pytest.mark.asyncio
    async def test_weighted_merge(self, transformer):
        """_weighted_merge should correctly combine vectors."""
        query_vec = [1.0] * 768
        hyde_vec = [0.0] * 768

        merged = transformer._weighted_merge(query_vec, hyde_vec)

        # 0.7 * 1.0 + 0.3 * 0.0 = 0.7
        assert all(v == pytest.approx(0.7) for v in merged)

    @pytest.mark.asyncio
    async def test_transform_handles_llm_failure(self, transformer):
        """transform should gracefully handle LLM failures."""
        with patch.object(transformer, '_ollama_generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = Exception("LLM unavailable")

            # Should not raise, should return with fallbacks
            result = await transformer.transform("test query")

            assert result.original == "test query"
            assert len(result.vector) == 768  # Still has embedding
            assert result.hyde_answer is None  # HyDE failed
            assert result.alt_queries == []  # Multi-query failed

    @pytest.mark.asyncio
    async def test_multi_query_max_three_variants(self, transformer):
        """Multi-query should return max 3 variants."""
        with patch.object(transformer, '_ollama_generate', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                "HyDE",
                "var1\nvar2\nvar3\nvar4\nvar5",  # 5 variants
            ]

            result = await transformer.transform("test")

            assert len(result.alt_queries) <= 3
