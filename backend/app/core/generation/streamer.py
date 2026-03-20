"""Build SSE event strings for FastAPI StreamingResponse.

Phase 2: Integrates advanced retrieval pipeline with HyDE, reranking, guard, and mode switch.
"""
import json
import uuid
from collections.abc import AsyncGenerator

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.generation.guard import StrictGuard
from app.core.generation.intent_classifier import Intent, QueryDifficulty, classify_intent, classify_difficulty
from app.core.generation.llm_router import ModelChoice, choose_model, stream_generate
from app.core.generation.mode_switch import ModeSwitch, RouteAction
from app.core.generation.prompt_builder import build_prompt
from app.core.memory.memory_tiers import get_memory_tiers
from app.core.retrieval.pipeline import RetrievalPipeline
from app.db.models.session import Message, Session

logger = structlog.get_logger(__name__)

# Guard threshold for strict mode (cosine similarity range when reranker unavailable)
GUARD_THRESHOLD = 0.4


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_chat(
    session_id: uuid.UUID,
    message: str,
    mode: str,
    db_session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Full SSE stream for a single chat turn.

    Phase 2 Pipeline:
        1. Load session (memory tiers)
        2. Classify intent (chit_chat vs rag_query)
        3. If chit_chat: route via mode switch
        4. If rag_query:
            - Transform query (HyDE + multi-query)
            - Hybrid search (vector + BM25)
            - Rerank (cross-encoder)
            - Guard check
            - Route via mode switch
            - Build prompt
            - LLM generate
            - Stream SSE
        5. Save messages (Hot + Warm)

    Yields SSE-formatted strings.
    """
    log = logger.bind(session_id=str(session_id), mode=mode)

    # Initialize components
    mode_switch = ModeSwitch()
    guard = StrictGuard(threshold=GUARD_THRESHOLD)
    memory_tiers = get_memory_tiers()

    # Step 1: Load recent history
    history = await _load_history(session_id, db_session)

    # Refresh hot tier TTL if active session
    await memory_tiers.refresh_hot_ttl(session_id)

    # Step 2: Classify intent
    intent = classify_intent(message)
    difficulty = classify_difficulty(message, intent)
    model_choice = choose_model(difficulty=difficulty.value)
    log.debug("streamer.intent", intent=intent.value, difficulty=difficulty.value,
              model=model_choice.display_name)

    # SSE: session event (metadata for frontend)
    yield _sse("session", {
        "session_id": str(session_id),
        "model": model_choice.display_name,
        "mode": mode,
        "intent": intent.value,
        "difficulty": difficulty.value,
    })

    # Step 3: Handle chit-chat (no retrieval needed)
    if intent == Intent.CHIT_CHAT:
        async for event in _handle_chit_chat(
            session_id, message, mode, history, mode_switch, model_choice, db_session, log
        ):
            yield event
        return

    # Step 4: RAG query - run retrieval pipeline
    try:
        pipeline = RetrievalPipeline(
            session=db_session,
            use_hyde=True,
            use_reranker=True,
        )
        retrieval_result = await pipeline.run(message, top_k=5)
        log.debug(
            "streamer.retrieval",
            chunks=len(retrieval_result.chunks),
            max_score=retrieval_result.max_score,
        )
    except Exception as exc:
        log.error("streamer.retrieval_failed", error=str(exc))
        yield _sse("error", {"error": "Retrieval failed", "code": "RETRIEVAL_ERROR"})
        return

    # Step 5: Guard check
    guard_result = guard.check(retrieval_result)

    # Step 6: Route decision
    decision = mode_switch.route(mode, "rag_query", guard_result)
    log.debug("streamer.route", action=decision.action.value)

    # Handle routing
    if decision.action == RouteAction.REJECT:
        yield _sse("no_data", {
            "message": decision.message,
            "code": "GUARD_REJECTED",
            "max_score": guard_result.max_score,
        })
        # Still save user message
        await _save_messages(
            session_id, message, decision.message, [], mode,
            model_choice.display_name, difficulty.value, db_session
        )
        return

    if decision.action == RouteAction.LLM_WITHOUT_CONTEXT:
        # General mode fallback - use LLM without context
        async for event in _handle_llm_without_context(
            session_id, message, mode, history, decision, model_choice,
            difficulty, db_session, log
        ):
            yield event
        return

    # Step 7: Build prompt with context
    prompt = build_prompt(
        query=message,
        context_chunks=retrieval_result.chunks,
        history=history,
        mode=mode,
    )

    # Build sources list early to send before streaming
    sources = [
        {
            "chunk_id": str(s.chunk_id),
            "doc_name": s.doc_name,
            "page": s.page,
            "score": s.score,
            "snippet": s.snippet[:100],
        }
        for s in retrieval_result.sources
    ]

    # SSE: send sources before streaming starts (for UI to display)
    if sources:
        yield _sse("sources", {"sources": sources})

    # Step 8: Stream tokens
    full_response: list[str] = []
    try:
        async for token in stream_generate(prompt, mode, model_choice=model_choice):
            full_response.append(token)
            yield _sse("token", {"content": token, "done": False})
    except Exception as exc:
        log.error("streamer.generate_failed", error=str(exc))
        yield _sse("error", {"error": str(exc), "code": "GENERATION_ERROR"})
        return

    total_tokens = sum(len(t.split()) for t in full_response)
    yield _sse("done", {
        "content": "",
        "done": True,
        "sources": sources,
        "model": model_choice.display_name,
        "difficulty": difficulty.value,
        "total_tokens": total_tokens,
        "debug": {
            "hyde_used": retrieval_result.debug.get("hyde_answer") is not None,
            "candidates": retrieval_result.debug.get("candidates_count", 0),
        },
    })

    # Step 9: Save messages + update memory tiers
    assistant_content = "".join(full_response)
    await _save_messages(
        session_id, message, assistant_content, sources, mode,
        model_choice.display_name, difficulty.value, db_session
    )

    # Update hot tier with new messages
    updated_history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": assistant_content},
    ]
    await memory_tiers.save_to_hot(session_id, updated_history[-6:])

    log.info("streamer.done", tokens=total_tokens, sources=len(sources))


async def _load_history(
    session_id: uuid.UUID,
    db_session: AsyncSession,
) -> list[dict]:
    """Load recent message history from database."""
    result = await db_session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(6)
    )
    history_msgs = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in history_msgs]


async def _handle_chit_chat(
    session_id: uuid.UUID,
    message: str,
    mode: str,
    history: list[dict],
    mode_switch: ModeSwitch,
    model_choice: ModelChoice,
    db_session: AsyncSession,
    log,
) -> AsyncGenerator[str, None]:
    """Handle chit-chat intent."""
    decision = mode_switch.route(mode, "chit_chat")

    if decision.action == RouteAction.TEMPLATE:
        # Return template response (no LLM call)
        template_response = mode_switch.get_template(decision.template_key or "default")
        yield _sse("token", {"content": template_response, "done": False})
        yield _sse("done", {
            "content": "",
            "done": True,
            "sources": [],
            "model": "Template",
            "difficulty": "easy",
            "total_tokens": 0,
        })
        await _save_messages(
            session_id, message, template_response, [], mode,
            "Template", "easy", db_session
        )
    else:
        # Use LLM with guided prompt
        from app.core.generation.prompt_builder import BuiltPrompt

        prompt = BuiltPrompt(
            system=decision.system_prompt or "",
            messages=[{"role": "user", "content": message}],
        )

        full_response: list[str] = []
        try:
            async for token in stream_generate(prompt, mode, model_choice=model_choice):
                full_response.append(token)
                yield _sse("token", {"content": token, "done": False})
        except Exception as exc:
            log.error("chit_chat.generate_failed", error=str(exc))
            yield _sse("error", {"error": str(exc), "code": "GENERATION_ERROR"})
            return

        yield _sse("done", {
            "content": "",
            "done": True,
            "sources": [],
            "model": model_choice.display_name,
            "difficulty": "easy",
            "total_tokens": sum(len(t.split()) for t in full_response),
        })
        await _save_messages(
            session_id, message, "".join(full_response), [], mode,
            model_choice.display_name, "easy", db_session
        )


async def _handle_llm_without_context(
    session_id: uuid.UUID,
    message: str,
    mode: str,
    history: list[dict],
    decision,
    model_choice: ModelChoice,
    difficulty: QueryDifficulty,
    db_session: AsyncSession,
    log,
) -> AsyncGenerator[str, None]:
    """Handle LLM response without document context (general mode fallback)."""
    from app.core.generation.prompt_builder import BuiltPrompt

    prompt = BuiltPrompt(
        system=decision.system_prompt or "",
        messages=[{"role": "user", "content": message}],
    )

    full_response: list[str] = []
    try:
        async for token in stream_generate(prompt, mode, model_choice=model_choice):
            full_response.append(token)
            yield _sse("token", {"content": token, "done": False})
    except Exception as exc:
        log.error("llm_no_context.failed", error=str(exc))
        yield _sse("error", {"error": str(exc), "code": "GENERATION_ERROR"})
        return

    yield _sse("done", {
        "content": "",
        "done": True,
        "sources": [],
        "model": model_choice.display_name,
        "difficulty": difficulty.value,
        "total_tokens": sum(len(t.split()) for t in full_response),
        "disclaimer": decision.disclaimer,
    })
    await _save_messages(
        session_id, message, "".join(full_response), [], mode,
        model_choice.display_name, difficulty.value, db_session
    )


async def _save_messages(
    session_id: uuid.UUID,
    user_content: str,
    assistant_content: str,
    sources: list,
    mode: str,
    model_used: str,
    difficulty: str,
    db_session: AsyncSession,
) -> None:
    """Persist user and assistant messages to database."""
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=user_content,
    )
    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        sources=sources if sources else None,
        model_used=model_used,
    )
    db_session.add(user_msg)
    db_session.add(assistant_msg)

    # Update session updated_at and mode
    await db_session.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(mode=mode)
    )
    await db_session.commit()
