"""Orchestrate the full document ingestion pipeline (Phase 1: sync)."""
import hashlib
import uuid

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion.cleaner import clean
from app.core.ingestion.chunker import chunk
from app.core.ingestion.embedder import embed
from app.core.ingestion.enricher import enrich
from app.core.ingestion.extractor import extract
from app.core.ingestion.indexer import index
from app.db.models.document import Document
from app.exceptions import AppError, DuplicateError

logger = structlog.get_logger(__name__)


async def run_ingestion(
    doc_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    session: AsyncSession,
) -> int:
    """
    Full pipeline: extract → clean → chunk → enrich → embed → index.
    Updates document status in DB. Returns chunk count.
    """
    log = logger.bind(doc_id=str(doc_id), filename=filename)
    try:
        log.info("pipeline.start")

        # 1. Extract
        extracted = await extract(file_bytes, filename)

        # 2. Clean
        cleaned = await clean(extracted)
        if not cleaned.pages:
            raise AppError("Document produced no extractable text", "EMPTY_DOCUMENT", 422)

        # 3. Chunk
        chunks = await chunk(cleaned)

        # 4. Enrich
        enriched = await enrich(chunks)

        # 5. Embed
        chunk_vectors = await embed(enriched)

        # 6. Index
        count = await index(doc_id, filename, chunk_vectors, session)

        # Update document status
        await session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status="indexed", chunk_count=count)
        )
        await session.commit()

        log.info("pipeline.complete", chunks=count)
        return count

    except Exception as exc:
        error_msg = str(exc)
        log.error("pipeline.failed", error=error_msg)
        await session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status="error", error_message=error_msg[:1000])
        )
        await session.commit()
        raise


def compute_file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def check_duplicate(file_hash: str, session: AsyncSession) -> bool:
    """Return True if a non-deleted document with this hash exists."""
    result = await session.execute(
        select(Document).where(
            Document.file_hash == file_hash,
            Document.status != "deleted",
        )
    )
    return result.scalars().first() is not None
