"""Build SSE event strings for FastAPI StreamingResponse."""
import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.generation.intent_classifier import classify_intent
from app.core.generation.llm_router import stream_generate
from app.core.generation.prompt_builder import build_prompt
from app.core.ingestion.embedder import embed_query
from app.db.models.session import Message, Session
from app.db.qdrant import get_qdrant

logger = structlog.get_logger(__name__)

NO_DATA_THRESHOLD = 0.35  # Phase 1: basic threshold; Phase 2 uses strict guard at 0.7


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """Vector search in Qdrant, return list of context dicts."""
    try:
        vector = await embed_query(query)
        qdrant = get_qdrant()
        result = await qdrant.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "content": h.payload.get("content", ""),
                "doc_id": h.payload.get("doc_id"),
                "filename": h.payload.get("filename", ""),
                "page": h.payload.get("page_number"),
                "score": h.score,
            }
            for h in result.points
        ]
    except Exception as exc:
        logger.warning("streamer.retrieve_failed", error=str(exc))
        return []


async def stream_chat(
    session_id: uuid.UUID,
    message: str,
    mode: str,
    db_session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Full SSE stream for a single chat turn.
    Yields SSE-formatted strings.
    """
    log = logger.bind(session_id=str(session_id), mode=mode)

    # Load recent history from DB
    result = await db_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(6)
    )
    history_msgs = list(reversed(result.scalars().all()))
    history = [{"role": m.role, "content": m.content} for m in history_msgs]

    # Classify intent + retrieve context
    _intent = classify_intent(message)
    context_chunks = await _retrieve_context(message)

    # SSE: meta event
    yield _sse("meta", {
        "session_id": str(session_id),
        "model": settings.ollama_chat_model,
        "mode": mode,
    })

    # Check if we have any useful context in strict mode
    if mode == "strict" and context_chunks and context_chunks[0]["score"] < NO_DATA_THRESHOLD:
        log.info("streamer.no_data", top_score=context_chunks[0]["score"])
        yield _sse("no_data", {
            "message": "Không có thông tin liên quan trong tài liệu.",
            "code": "NO_RELEVANT_DATA",
        })
        return

    if mode == "strict" and not context_chunks:
        yield _sse("no_data", {
            "message": "Không có thông tin liên quan trong tài liệu.",
            "code": "NO_RELEVANT_DATA",
        })
        return

    # Build prompt
    prompt = build_prompt(message, context_chunks, history, mode)

    # Stream tokens
    full_response: list[str] = []
    try:
        async for token in stream_generate(prompt, mode):
            full_response.append(token)
            yield _sse("token", {"content": token, "done": False})
    except Exception as exc:
        log.error("streamer.generate_failed", error=str(exc))
        yield _sse("error", {"error": str(exc), "code": "GENERATION_ERROR"})
        return

    # Build sources list
    sources = [
        {
            "doc_id": c["doc_id"],
            "filename": c["filename"],
            "page": c["page"],
            "score": round(c["score"], 4),
        }
        for c in context_chunks
    ]

    total_tokens = sum(len(t.split()) for t in full_response)  # approximate
    yield _sse("done", {
        "content": "",
        "done": True,
        "sources": sources,
        "model": settings.ollama_chat_model,
        "total_tokens": total_tokens,
    })

    # Persist messages
    assistant_content = "".join(full_response)
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=message,
    )
    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        sources=sources,
        model_used=settings.ollama_chat_model,
    )
    db_session.add(user_msg)
    db_session.add(assistant_msg)

    # Update session updated_at
    await db_session.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(mode=mode)
    )
    await db_session.commit()
    log.info("streamer.done", tokens=total_tokens)
