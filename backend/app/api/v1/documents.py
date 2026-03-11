"""Document upload, list, detail, delete endpoints."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ingestion.pipeline import check_duplicate, compute_file_hash, run_ingestion
from app.db.models.document import Document
from app.db.postgres import get_session
from app.db.qdrant import get_qdrant
from app.exceptions import (
    DuplicateError,
    FileTooLargeError,
    NotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_SIZE = settings.max_upload_size_mb * 1024 * 1024


# ── Response models ──────────────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    doc_id: uuid.UUID
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    created_at: datetime


class DocumentItem(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    created_at: datetime


class DocumentDetail(DocumentItem):
    error_message: str | None
    updated_at: datetime


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]
    pagination: Pagination


class DeleteResponse(BaseModel):
    doc_id: uuid.UUID
    status: str
    chunks_removed: int


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=202, response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadResponse:
    if not file.filename:
        raise ValidationError("No file provided", "MISSING_FILE").to_http()

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in settings.allowed_file_types:
        raise UnsupportedFileTypeError(ext).to_http()

    file_bytes = await file.read()
    if len(file_bytes) > MAX_SIZE:
        raise FileTooLargeError().to_http()

    file_hash = compute_file_hash(file_bytes)
    if await check_duplicate(file_hash, session):
        raise DuplicateError("A document with the same content already exists", "DUPLICATE_FILE").to_http()

    doc = Document(
        filename=file.filename,
        file_type=ext,
        file_size_bytes=len(file_bytes),
        file_hash=file_hash,
        status="processing",
    )
    session.add(doc)
    await session.flush()
    doc_id = doc.id
    created_at = doc.created_at

    # Phase 1: sync ingestion (no Celery)
    await run_ingestion(doc_id, file_bytes, file.filename, session)

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        file_type=ext,
        file_size_bytes=len(file_bytes),
        status="processing",
        created_at=created_at,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    session: AsyncSession = Depends(get_session),
) -> DocumentListResponse:
    q = select(Document).where(Document.status != "deleted")
    if status:
        q = q.where(Document.status == status)

    sort_col = getattr(Document, sort, Document.created_at)
    if order == "desc":
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col.asc())

    total_result = await session.execute(
        select(func.count()).select_from(
            q.subquery()
        )
    )
    total = total_result.scalar_one()

    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(q)
    docs = result.scalars().all()

    return DocumentListResponse(
        documents=[
            DocumentItem(
                id=d.id,
                filename=d.filename,
                file_type=d.file_type,
                file_size_bytes=d.file_size_bytes,
                status=d.status,
                chunk_count=d.chunk_count,
                created_at=d.created_at,
            )
            for d in docs
        ],
        pagination=Pagination(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=max(1, (total + per_page - 1) // per_page),
        ),
    )


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DocumentDetail:
    result = await session.execute(
        select(Document).where(Document.id == doc_id, Document.status != "deleted")
    )
    doc = result.scalars().first()
    if not doc:
        raise NotFoundError("Document not found").to_http()

    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document(
    doc_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> DeleteResponse:
    result = await session.execute(
        select(Document).where(Document.id == doc_id, Document.status != "deleted")
    )
    doc = result.scalars().first()
    if not doc:
        raise NotFoundError("Document not found").to_http()

    chunks_removed = doc.chunk_count

    # Soft-delete in PostgreSQL
    await session.execute(
        update(Document).where(Document.id == doc_id).values(status="deleted")
    )

    # Remove vectors from Qdrant
    try:
        qdrant = get_qdrant()
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        await qdrant.delete(
            collection_name=settings.qdrant_collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
            ),
        )
    except Exception:
        pass  # Non-fatal: Qdrant cleanup can be retried later

    await session.commit()
    return DeleteResponse(doc_id=doc_id, status="deleted", chunks_removed=chunks_removed)
