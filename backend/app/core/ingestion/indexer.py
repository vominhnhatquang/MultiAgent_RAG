"""Index embedded chunks into Qdrant and persist chunk records in PostgreSQL."""
import uuid

import structlog
from qdrant_client.models import PointStruct
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ingestion.chunker import TextChunk
from app.db.models.document import Chunk
from app.db.qdrant import get_qdrant

logger = structlog.get_logger(__name__)


async def index(
    doc_id: uuid.UUID,
    filename: str,
    chunk_vectors: list[tuple[TextChunk, list[float]]],
    session: AsyncSession,
) -> int:
    """Store chunks in PostgreSQL + Qdrant. Returns number of chunks indexed."""
    qdrant = get_qdrant()
    points: list[PointStruct] = []
    orm_chunks: list[Chunk] = []

    for chunk, vector in chunk_vectors:
        chunk_id = uuid.uuid4()
        orm_chunks.append(
            Chunk(
                id=chunk_id,
                document_id=doc_id,
                content=chunk.content,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                token_count=chunk.token_count,
                char_count=chunk.char_count,
                metadata_=chunk.metadata,
            )
        )
        points.append(
            PointStruct(
                id=str(chunk_id),
                vector=vector,
                payload={
                    "doc_id": str(doc_id),
                    "filename": filename,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "language": chunk.metadata.get("language", "vi"),
                    "content": chunk.content,
                },
            )
        )

    # Persist to PostgreSQL
    session.add_all(orm_chunks)
    await session.flush()

    # Upsert into Qdrant in batches
    batch_size = 64
    for i in range(0, len(points), batch_size):
        await qdrant.upsert(
            collection_name=settings.qdrant_collection,
            points=points[i : i + batch_size],
        )

    count = len(orm_chunks)
    logger.info("indexer.done", doc_id=str(doc_id), chunks=count)
    return count
