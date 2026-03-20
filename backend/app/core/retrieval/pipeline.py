"""Retrieval pipeline orchestrating transform → hybrid search → rerank."""
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.embedder import embed_query
from app.core.retrieval.bm25_search import BM25Search, ScoredChunk
from app.core.retrieval.hybrid_search import HybridSearch, HybridSearchConfig
from app.core.retrieval.query_transformer import QueryTransformer
from app.core.retrieval.reranker import get_reranker
from app.core.retrieval.vector_search import VectorSearch

logger = structlog.get_logger(__name__)


@dataclass
class Source:
    """Source information for a retrieved chunk."""

    doc_name: str
    page: int | None
    chunk_id: str
    score: float
    snippet: str


@dataclass
class RetrievalResult:
    """Result from the retrieval pipeline."""

    chunks: list[ScoredChunk]
    sources: list[Source]
    debug: dict[str, Any] = field(default_factory=dict)

    @property
    def has_results(self) -> bool:
        return len(self.chunks) > 0

    @property
    def max_score(self) -> float:
        if not self.chunks:
            return 0.0
        return max(c.rerank_score or c.score for c in self.chunks)


class RetrievalPipeline:
    """
    Orchestrates the full retrieval pipeline.

    Pipeline stages:
    1. Query Transform (HyDE + multi-query) ~200-400ms
    2. Hybrid Search (vector + BM25, parallel) ~50-100ms
    3. Rerank (cross-encoder on top-K) ~100-300ms

    Total latency: ~350-800ms
    """

    def __init__(
        self,
        session: AsyncSession,
        use_hyde: bool = True,
        use_reranker: bool = True,
        hybrid_config: HybridSearchConfig | None = None,
    ) -> None:
        """
        Args:
            session: Database session for BM25 search
            use_hyde: Whether to use HyDE query expansion
            use_reranker: Whether to use cross-encoder reranking
            hybrid_config: Optional config for hybrid search weights
        """
        self.session = session
        self.use_hyde = use_hyde
        self.use_reranker = use_reranker

        # Initialize components
        self.transformer = QueryTransformer(embedder_func=embed_query)
        self.vector_search = VectorSearch(embedder_func=embed_query)
        self.bm25_search = BM25Search(session=session)
        self.hybrid_search = HybridSearch(
            vector_search=self.vector_search,
            bm25_search=self.bm25_search,
            config=hybrid_config,
        )
        self.reranker = get_reranker()

    async def run(
        self,
        query: str,
        top_k: int = 5,
        doc_filter: uuid.UUID | None = None,
    ) -> RetrievalResult:
        """
        Run the full retrieval pipeline.

        Args:
            query: User query
            top_k: Number of final results
            doc_filter: Optional document ID filter

        Returns:
            RetrievalResult with ranked chunks and sources
        """
        # Step 1: Transform query (HyDE + multi-query)
        transformed = await self.transformer.transform(
            query,
            use_hyde=self.use_hyde,
            use_multi_query=True,
        )
        logger.debug(
            "retrieval.transformed",
            alt_queries=len(transformed.alt_queries),
            has_hyde=transformed.hyde_answer is not None,
        )

        # Step 2: Hybrid search (vector + BM25)
        candidates = await self.hybrid_search.search(
            transformed,
            top_k=max(20, top_k * 4),  # Get more candidates for reranking
            doc_filter=doc_filter,
        )

        if not candidates:
            logger.info("retrieval.no_candidates")
            return RetrievalResult(
                chunks=[],
                sources=[],
                debug={
                    "hyde_answer": transformed.hyde_answer,
                    "alt_queries": transformed.alt_queries,
                    "candidates_count": 0,
                },
            )

        # Step 3: Rerank (cross-encoder)
        if self.use_reranker and self.reranker.is_available():
            reranked = self.reranker.rerank(query, candidates, top_k=top_k)
        else:
            # No reranking — use vector cosine similarity score (0-1 range)
            # instead of RRF score (~0.01-0.03) which would always fail the guard
            reranked = candidates[:top_k]
            for chunk in reranked:
                chunk.rerank_score = chunk.vector_score or chunk.rrf_score or chunk.score

        # Format sources
        sources = [
            Source(
                doc_name=c.filename or "unknown",
                page=c.page_number,
                chunk_id=str(c.id),
                score=round(c.rerank_score or c.score, 4),
                snippet=c.content[:200],
            )
            for c in reranked
        ]

        logger.info(
            "retrieval.done",
            candidates=len(candidates),
            results=len(reranked),
            top_score=reranked[0].rerank_score if reranked else None,
        )

        return RetrievalResult(
            chunks=reranked,
            sources=sources,
            debug={
                "hyde_answer": transformed.hyde_answer,
                "alt_queries": transformed.alt_queries,
                "candidates_count": len(candidates),
            },
        )


async def create_pipeline(
    session: AsyncSession,
    use_hyde: bool = True,
    use_reranker: bool = True,
) -> RetrievalPipeline:
    """Factory function to create a retrieval pipeline."""
    return RetrievalPipeline(
        session=session,
        use_hyde=use_hyde,
        use_reranker=use_reranker,
    )
