"""Hybrid search combining Vector + BM25 with RRF fusion."""
import asyncio
import uuid
from dataclasses import dataclass

import structlog

from app.core.retrieval.bm25_search import BM25Search, ScoredChunk
from app.core.retrieval.query_transformer import TransformedQuery
from app.core.retrieval.vector_search import VectorSearch

logger = structlog.get_logger(__name__)


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search."""

    vector_weight: float = 1.0
    bm25_weight: float = 1.0
    rrf_k: int = 60  # RRF constant (standard value from literature)


class HybridSearch:
    """
    Hybrid search combining Vector and BM25 search with RRF fusion.

    Reciprocal Rank Fusion (RRF):
        score(doc) = Σ weight_i / (k + rank_i)

    Where:
        - k = 60 (constant that balances rank importance)
        - rank_i = position in result list i (0-indexed)
        - weight_i = weight for search method i
    """

    def __init__(
        self,
        vector_search: VectorSearch,
        bm25_search: BM25Search,
        config: HybridSearchConfig | None = None,
    ) -> None:
        self.vector_search = vector_search
        self.bm25_search = bm25_search
        self.config = config or HybridSearchConfig()

    async def search(
        self,
        transformed: TransformedQuery,
        top_k: int = 20,
        doc_filter: uuid.UUID | None = None,
    ) -> list[ScoredChunk]:
        """
        Perform hybrid search and fuse results with RRF.

        Args:
            transformed: TransformedQuery with vector and alt_queries
            top_k: Maximum results to return
            doc_filter: Optional document ID filter

        Returns:
            List of ScoredChunk with RRF scores
        """
        # Prepare BM25 queries (original + alternatives)
        bm25_queries = [transformed.original] + transformed.alt_queries

        # Run searches in parallel
        vector_task = self.vector_search.search_by_vector(
            transformed.vector,
            limit=top_k,
            doc_filter=doc_filter,
        )
        bm25_task = self.bm25_search.search_multi(
            bm25_queries,
            limit=top_k,
            doc_filter=doc_filter,
        )

        vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)

        # RRF fusion
        fused = self._rrf_fusion(vector_results, bm25_results)

        logger.info(
            "hybrid_search.done",
            vector_count=len(vector_results),
            bm25_count=len(bm25_results),
            fused_count=len(fused),
        )

        return fused[:top_k]

    def _rrf_fusion(
        self,
        vector_results: list[ScoredChunk],
        bm25_results: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        """
        Fuse results using Reciprocal Rank Fusion.

        RRF score = Σ weight / (k + rank + 1)
        Using rank+1 to make it 1-indexed as per standard RRF
        """
        k = self.config.rrf_k
        scores: dict[uuid.UUID, float] = {}
        chunk_map: dict[uuid.UUID, ScoredChunk] = {}

        # Score vector results
        for rank, chunk in enumerate(vector_results):
            rrf_contrib = self.config.vector_weight / (k + rank + 1)
            scores[chunk.id] = scores.get(chunk.id, 0) + rrf_contrib
            chunk_map[chunk.id] = chunk

        # Score BM25 results
        for rank, chunk in enumerate(bm25_results):
            rrf_contrib = self.config.bm25_weight / (k + rank + 1)
            scores[chunk.id] = scores.get(chunk.id, 0) + rrf_contrib
            # If chunk from BM25 not seen in vector, add it
            if chunk.id not in chunk_map:
                chunk_map[chunk.id] = chunk

        # Sort by RRF score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Build result list with RRF scores
        results = []
        for chunk_id, rrf_score in ranked:
            chunk = chunk_map[chunk_id]
            chunk.rrf_score = rrf_score
            chunk.score = rrf_score  # Update main score to RRF
            results.append(chunk)

        return results
