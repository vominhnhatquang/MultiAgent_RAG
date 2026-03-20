"""Celery tasks for async document ingestion and maintenance."""
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
from asgiref.sync import async_to_sync
from sqlalchemy import update

from app.celery_app import celery_app
from app.db.models.document import Document

logger = structlog.get_logger(__name__)

# Upload storage directory
UPLOADS_DIR = Path("data/uploads/raw")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@celery_app.task(bind=True, name="app.tasks.health_check")
def health_check(self):
    """Health check task."""
    return {"status": "ok"}


@celery_app.task(
    bind=True,
    name="app.tasks.ingest_document",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def ingest_document(self, doc_id: str, file_path: str) -> dict:
    """
    Async document ingestion task.

    Args:
        doc_id: Document UUID as string
        file_path: Path to the uploaded file on disk

    Returns:
        dict with status and chunk count
    """
    log = logger.bind(doc_id=doc_id, file_path=file_path, task_id=self.request.id)
    log.info("task.ingest_start", attempt=self.request.retries + 1)

    try:
        # Run async pipeline in sync context using asgiref
        result = async_to_sync(_run_ingest_async)(doc_id, file_path)
        log.info("task.ingest_complete", chunks=result["chunk_count"])
        return result

    except Exception as exc:
        log.error("task.ingest_failed", error=str(exc), attempt=self.request.retries + 1)

        # Update document status on final failure
        if self.request.retries >= 2:  # 0-indexed, so 3rd attempt
            async_to_sync(_mark_document_error)(doc_id, str(exc))

        raise


async def _run_ingest_async(doc_id: str, file_path: str) -> dict:
    """Run ingestion pipeline asynchronously."""
    from app.core.ingestion.pipeline import run_ingestion
    from app.db.postgres import AsyncSessionLocal

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Upload file not found: {file_path}")

    file_bytes = file_path.read_bytes()
    filename = file_path.name

    # Extract original filename from stored path (format: {doc_id}_{filename})
    if "_" in filename:
        filename = filename.split("_", 1)[1]

    async with AsyncSessionLocal() as session:
        chunk_count = await run_ingestion(
            doc_id=uuid.UUID(doc_id),
            file_bytes=file_bytes,
            filename=filename,
            session=session,
        )

    # Clean up upload file after successful ingestion
    try:
        file_path.unlink(missing_ok=True)
        logger.debug("task.upload_cleaned", file_path=str(file_path))
    except Exception as e:
        logger.warning("task.upload_cleanup_failed", error=str(e))

    return {"doc_id": doc_id, "status": "indexed", "chunk_count": chunk_count}


async def _mark_document_error(doc_id: str, error_msg: str) -> None:
    """Mark document as error in database."""
    from app.db.postgres import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Document)
            .where(Document.id == uuid.UUID(doc_id))
            .values(status="error", error_message=error_msg[:1000])
        )
        await session.commit()


@celery_app.task(
    bind=True,
    name="app.tasks.cleanup_old_uploads",
)
def cleanup_old_uploads(self, max_age_hours: int = 24) -> dict:
    """
    Periodic task to clean up orphaned upload files.

    Removes upload files older than max_age_hours that were not processed.

    Args:
        max_age_hours: Maximum age of files to keep (default: 24 hours)

    Returns:
        dict with cleanup stats
    """
    log = logger.bind(task="cleanup_old_uploads", max_age_hours=max_age_hours)
    log.info("task.cleanup_start")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    removed = 0
    errors = 0

    try:
        for file_path in UPLOADS_DIR.glob("*"):
            if not file_path.is_file():
                continue

            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    file_path.unlink()
                    removed += 1
                    log.debug("task.file_removed", file=file_path.name)
            except Exception as e:
                errors += 1
                log.warning("task.file_removal_failed", file=file_path.name, error=str(e))

        log.info("task.cleanup_complete", removed=removed, errors=errors)
        return {"removed": removed, "errors": errors}

    except Exception as exc:
        log.error("task.cleanup_failed", error=str(exc))
        raise


def save_upload_file(doc_id: uuid.UUID, filename: str, content: bytes) -> Path:
    """
    Save uploaded file to disk for async processing.

    Args:
        doc_id: Document UUID
        filename: Original filename
        content: File bytes

    Returns:
        Path to saved file
    """
    # Sanitize filename - remove path traversal and dangerous characters
    safe_filename = filename.replace("/", "_").replace("\\", "_").replace("..", "")
    # Also get just the basename to prevent any path injection
    safe_filename = os.path.basename(safe_filename) or "unnamed"
    file_path = UPLOADS_DIR / f"{doc_id}_{safe_filename}"

    file_path.write_bytes(content)
    logger.debug("upload.saved", doc_id=str(doc_id), path=str(file_path), size=len(content))

    return file_path


# Beat schedule is defined in celery_app.py

