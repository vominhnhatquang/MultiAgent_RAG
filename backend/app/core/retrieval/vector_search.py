"""Vector search using Qdrant."""
import uuid

import structlog
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import settings
from app.core.retrieval.bm25_search import ScoredChunk
from app.db.qdrant import get_qdrant

logger = structlog.get_logger(__name__)


class VectorSearch:
    """
    Vector search using Qdrant.

    Supports both text-based search (embed then search) and direct vector search.
    """

    def __init__(self, embedder_func) -> None:
        """
        Args:
            embedder_func: Async function that takes str and returns list[float]
        """
        self.embedder = embedder_func

    async def search(
        self,
        query: str,
        limit: int = 20,
        doc_filter: uuid.UUID | None = None,
    ) -> list[ScoredChunk]:
        """
        Search by query text (will be embedded).

        Args:
            query: Query text to embed and search
            limit: Maximum results
            doc_filter: Optional document ID filter

        Returns:
            List of ScoredChunk ordered by vector similarity
        """
        if not query.strip():
            return []

        vector = await self.embedder(query)
        return await self.search_by_vector(vector, limit=limit, doc_filter=doc_filter)

    async def search_by_vector(
        self,
        vector: list[float],
        limit: int = 20,
        doc_filter: uuid.UUID | None = None,
    ) -> list[ScoredChunk]:
        """
        Search by pre-computed vector.

        Args:
            vector: Query embedding vector (768-dim for nomic-embed-text)
            limit: Maximum results
            doc_filter: Optional document ID filter

        Returns:
            List of ScoredChunk ordered by vector similarity
        """
        qdrant = get_qdrant()

        # Build filter if doc_filter provided
        query_filter = None
        if doc_filter:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=str(doc_filter)),
                    )
                ]
            )

        response = await qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        results = response.points

        chunks = []
        for hit in results:
            payload = hit.payload or {}
            chunks.append(
                ScoredChunk(
                    id=uuid.UUID(hit.id),
                    document_id=uuid.UUID(payload.get("doc_id", "")),
                    content=payload.get("content", ""),
                    page_number=payload.get("page_number"),
                    metadata={
                        "chunk_index": payload.get("chunk_index"),
                        "language": payload.get("language"),
                    },
                    filename=payload.get("filename"),
                    score=hit.score,
                    vector_score=hit.score,
                )
            )

        logger.info("vector_search.done", results=len(chunks))
        return chunks
