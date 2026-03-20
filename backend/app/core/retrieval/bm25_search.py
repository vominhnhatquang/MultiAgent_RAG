"""BM25 search using PostgreSQL full-text search with tsvector + ts_rank_cd."""
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


@dataclass
class ScoredChunk:
    """A chunk with its relevance score."""

    id: uuid.UUID
    document_id: uuid.UUID
    content: str
    page_number: int | None
    metadata: dict
    filename: str | None = None
    score: float = 0.0
    # Scores from different stages (set by downstream processors)
    bm25_score: float | None = None
    vector_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class BM25Search:
    """
    BM25 search using PostgreSQL full-text search.

    Uses:
    - 'simple' config: tách theo whitespace, không stemming (tốt cho tiếng Việt)
    - plainto_tsquery: an toàn với user input
    - ts_rank_cd: BM25-like scoring
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 20,
        doc_filter: uuid.UUID | None = None,
    ) -> list[ScoredChunk]:
        """
        Search chunks using BM25/full-text search.

        Args:
            query: Search query string
            limit: Maximum results to return
            doc_filter: Optional document ID to filter results

        Returns:
            List of ScoredChunk ordered by BM25 score descending
        """
        query = query.strip()
        if not query:
            logger.debug("bm25.empty_query")
            return []

        sql = text("""
            SELECT c.id, c.document_id, c.content, c.page_number, c.metadata,
                   d.filename,
                   ts_rank_cd(to_tsvector('simple', c.content), 
                              plainto_tsquery('simple', :query)) AS score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.status = 'indexed'
              AND to_tsvector('simple', c.content) @@ plainto_tsquery('simple', :query)
              AND (:doc_filter IS NULL OR c.document_id = :doc_filter)
            ORDER BY score DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            sql,
            {"query": query, "limit": limit, "doc_filter": doc_filter},
        )
        rows = result.fetchall()

        chunks = [
            ScoredChunk(
                id=row.id,
                document_id=row.document_id,
                content=row.content,
                page_number=row.page_number,
                metadata=row.metadata or {},
                filename=row.filename,
                score=float(row.score),
                bm25_score=float(row.score),
            )
            for row in rows
        ]

        logger.info("bm25.search", query=query[:50], results=len(chunks))
        return chunks

    async def search_multi(
        self,
        queries: list[str],
        limit: int = 20,
        doc_filter: uuid.UUID | None = None,
    ) -> list[ScoredChunk]:
        """
        Search with multiple query variants, dedupe and merge results.

        Args:
            queries: List of query strings (original + variants)
            limit: Maximum results to return
            doc_filter: Optional document ID filter

        Returns:
            Merged and deduped results, sorted by best score
        """
        all_results: dict[uuid.UUID, ScoredChunk] = {}
        best_score: dict[uuid.UUID, float] = {}

        for query in queries:
            if not query.strip():
                continue
            results = await self.search(query, limit=limit, doc_filter=doc_filter)
            for chunk in results:
                if chunk.id not in best_score or chunk.score > best_score[chunk.id]:
                    best_score[chunk.id] = chunk.score
                    all_results[chunk.id] = chunk

        # Sort by best score
        ranked = sorted(
            all_results.values(),
            key=lambda c: best_score[c.id],
            reverse=True,
        )

        logger.info(
            "bm25.search_multi",
            query_count=len(queries),
            results=len(ranked[:limit]),
        )
        return ranked[:limit]
