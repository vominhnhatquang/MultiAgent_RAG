"""Chat SSE endpoint + session management."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.generation.streamer import stream_chat
from app.db.models.session import Feedback, Message, Session
from app.db.postgres import get_session
from app.exceptions import DuplicateError, NotFoundError, ValidationError

router = APIRouter(tags=["chat"])


# ── Request / Response models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field("strict", pattern="^(strict|general)$")

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v


class SessionItem(BaseModel):
    id: uuid.UUID
    title: str | None
    mode: str
    tier: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class MessageItem(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: list | None = None
    model_used: str | None = None
    created_at: datetime


class SessionDetail(SessionItem):
    messages: list[MessageItem]


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class SessionListResponse(BaseModel):
    sessions: list[SessionItem]
    pagination: Pagination


class DeleteSessionResponse(BaseModel):
    session_id: uuid.UUID
    deleted: bool
    messages_removed: int


class UpdateSessionRequest(BaseModel):
    title: str | None = Field(None, max_length=200)
    mode: str | None = Field(None, pattern="^(strict|general)$")


class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern="^(thumbs_up|thumbs_down)$")
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    rating: str
    created_at: datetime


# ── Chat endpoint ────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    if not req.message.strip():
        raise ValidationError("Message cannot be empty", "EMPTY_MESSAGE").to_http()

    # Resolve or create session
    if req.session_id:
        result = await db.execute(select(Session).where(Session.id == req.session_id))
        session_obj = result.scalars().first()
        if not session_obj:
            raise NotFoundError("Session not found", "SESSION_NOT_FOUND").to_http()
        session_id = req.session_id
    else:
        # Create new session; title will be first ~50 chars of message
        title = req.message[:50].strip()
        session_obj = Session(title=title, mode=req.mode)
        db.add(session_obj)
        await db.flush()
        session_id = session_obj.id

    return StreamingResponse(
        stream_chat(session_id, req.message, req.mode, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Session endpoints ────────────────────────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tier: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
) -> SessionListResponse:
    from sqlalchemy import func
    q = select(Session)
    if tier:
        q = q.where(Session.tier == tier)
    q = q.order_by(Session.updated_at.desc())

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    sessions = result.scalars().all()

    return SessionListResponse(
        sessions=[
            SessionItem(
                id=s.id, title=s.title, mode=s.mode, tier=s.tier,
                message_count=s.message_count,
                created_at=s.created_at, updated_at=s.updated_at,
            )
            for s in sessions
        ],
        pagination=Pagination(
            page=page, per_page=per_page, total=total,
            total_pages=max(1, (total + per_page - 1) // per_page),
        ),
    )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> SessionDetail:
    result = await db.execute(select(Session).where(Session.id == session_id))
    sess = result.scalars().first()
    if not sess:
        raise NotFoundError("Session not found", "SESSION_NOT_FOUND").to_http()

    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return SessionDetail(
        id=sess.id, title=sess.title, mode=sess.mode, tier=sess.tier,
        message_count=sess.message_count,
        created_at=sess.created_at, updated_at=sess.updated_at,
        messages=[
            MessageItem(
                id=m.id, role=m.role, content=m.content,
                sources=m.sources, model_used=m.model_used,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.patch("/sessions/{session_id}", response_model=SessionItem)
async def update_session(
    session_id: uuid.UUID,
    body: UpdateSessionRequest,
    db: AsyncSession = Depends(get_session),
) -> SessionItem:
    """
    Update session title and/or mode.

    Args:
        session_id: Session UUID
        body: Fields to update (title, mode)
        db: Database session

    Returns:
        Updated session
    """
    result = await db.execute(select(Session).where(Session.id == session_id))
    sess = result.scalars().first()
    if not sess:
        raise NotFoundError("Session not found", "SESSION_NOT_FOUND").to_http()

    # Update fields if provided
    if body.title is not None:
        sess.title = body.title
    if body.mode is not None:
        sess.mode = body.mode

    await db.commit()
    await db.refresh(sess)

    return SessionItem(
        id=sess.id,
        title=sess.title,
        mode=sess.mode,
        tier=sess.tier,
        message_count=sess.message_count,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
    )


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> DeleteSessionResponse:
    result = await db.execute(select(Session).where(Session.id == session_id))
    sess = result.scalars().first()
    if not sess:
        raise NotFoundError("Session not found", "SESSION_NOT_FOUND").to_http()

    msg_count = sess.message_count
    await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()

    return DeleteSessionResponse(session_id=session_id, deleted=True, messages_removed=msg_count)


# ── Feedback endpoint ────────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/messages/{message_id}/feedback",
    status_code=201,
    response_model=FeedbackResponse,
)
async def submit_feedback(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_session),
) -> FeedbackResponse:
    # Check message exists
    msg_result = await db.execute(
        select(Message).where(Message.id == message_id, Message.session_id == session_id)
    )
    if not msg_result.scalars().first():
        raise NotFoundError("Message not found").to_http()

    # Check duplicate
    fb_result = await db.execute(select(Feedback).where(Feedback.message_id == message_id))
    if fb_result.scalars().first():
        raise DuplicateError("Already rated this message", "DUPLICATE_FEEDBACK").to_http()

    fb = Feedback(
        message_id=message_id,
        session_id=session_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    return FeedbackResponse(id=fb.id, message_id=message_id, rating=fb.rating, created_at=fb.created_at)
