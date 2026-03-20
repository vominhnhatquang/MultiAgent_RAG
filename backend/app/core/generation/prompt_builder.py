"""Build LLM prompts from retrieved context + chat history.

Phase 2: "Lost in the Middle" aware — top chunks at beginning and end.
"""
from dataclasses import dataclass

import structlog

from app.core.retrieval.bm25_search import ScoredChunk

logger = structlog.get_logger(__name__)

# System prompts for different modes
SYSTEM_STRICT = """Bạn là trợ lý tài liệu. CHỈ trả lời dựa trên tài liệu được cung cấp. 
Nếu không có thông tin trong tài liệu, trả lời 'Không có thông tin trong tài liệu'.
Ghi rõ nguồn (tên file, trang số) khi trích dẫn.
Trả lời bằng ngôn ngữ mà người dùng sử dụng."""

SYSTEM_GENERAL = """Bạn là trợ lý tài liệu thông minh. 
Ưu tiên trả lời dựa trên tài liệu. Có thể bổ sung kiến thức chung nhưng phải ghi rõ.
Ghi rõ nguồn (tên file, trang số) khi trích dẫn từ tài liệu.
Trả lời bằng ngôn ngữ mà người dùng sử dụng."""

MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_TURNS = 3


@dataclass
class BuiltPrompt:
    """Result of prompt building."""

    system: str
    messages: list[dict]  # [{role, content}]


class PromptBuilder:
    """
    Build prompts with "Lost in the Middle" awareness.

    LLMs pay more attention to content at the BEGINNING and END of the context.
    Strategy:
        - Put most relevant chunk (top-1) at the beginning
        - Put query at the very end
        - History in between
    """

    def build(
        self,
        query: str,
        chunks: list[ScoredChunk],
        history: list[dict],
        mode: str = "strict",
    ) -> BuiltPrompt:
        """
        Build a prompt from query, chunks, and history.

        Args:
            query: User query
            chunks: Retrieved chunks (already ranked by relevance)
            history: Chat history [{role, content}]
            mode: "strict" or "general"

        Returns:
            BuiltPrompt with system and messages
        """
        system = self._build_system(mode)
        context = self._build_context(chunks)
        history_text = self._build_history(history)

        # Construct the user message with context
        user_content = f"""## Tài liệu tham khảo:
{context}

## Lịch sử hội thoại:
{history_text}

## Câu hỏi hiện tại:
{query}

## Hướng dẫn trả lời:
- Trả lời DỰA TRÊN tài liệu tham khảo ở trên
- Ghi rõ nguồn (tên file, trang số) khi trích dẫn
- Nếu thông tin không có trong tài liệu, nói rõ"""

        messages = [{"role": "user", "content": user_content}]

        logger.debug(
            "prompt_builder.built",
            context_chunks=len(chunks),
            history_turns=len(history) // 2,
            mode=mode,
        )

        return BuiltPrompt(system=system, messages=messages)

    def _build_system(self, mode: str) -> str:
        """Get system prompt for mode."""
        return SYSTEM_STRICT if mode == "strict" else SYSTEM_GENERAL

    def _build_context(self, chunks: list[ScoredChunk]) -> str:
        """
        Build context from chunks.

        "Lost in the Middle" optimization: top-1 (most relevant) at the start.
        """
        if not chunks:
            return "(Không có tài liệu tham khảo)"

        parts = []
        total_chars = 0

        for i, chunk in enumerate(chunks):
            source = f"[Nguồn: {chunk.filename or 'unknown'}, trang {chunk.page_number or '?'}]"
            snippet = f"--- Đoạn {i + 1} {source} ---\n{chunk.content}"

            if total_chars + len(snippet) > MAX_CONTEXT_CHARS:
                break

            parts.append(snippet)
            total_chars += len(snippet)

        return "\n\n".join(parts)

    def _build_history(self, history: list[dict], max_turns: int = MAX_HISTORY_TURNS) -> str:
        """Build history text from recent turns."""
        if not history:
            return "(Không có lịch sử)"

        # Get last N turns (user + assistant pairs)
        recent = history[-(max_turns * 2) :]

        lines = []
        for msg in recent:
            role = "Người dùng" if msg["role"] == "user" else "Trợ lý"
            content = msg["content"][:300]  # Truncate long messages
            lines.append(f"{role}: {content}")

        return "\n".join(lines)


# Singleton instance
_builder: PromptBuilder | None = None


def get_prompt_builder() -> PromptBuilder:
    """Get the global prompt builder instance."""
    global _builder
    if _builder is None:
        _builder = PromptBuilder()
    return _builder


def build_prompt(
    query: str,
    context_chunks: list[dict] | list[ScoredChunk],
    history: list[dict],
    mode: str = "strict",
) -> BuiltPrompt:
    """
    Build prompt (convenience function, backward compatible).

    Args:
        query: User query
        context_chunks: Retrieved chunks (dict or ScoredChunk format)
        history: Chat history [{role, content}]
        mode: "strict" or "general"

    Returns:
        BuiltPrompt
    """
    builder = get_prompt_builder()

    # Convert dict chunks to ScoredChunk if needed (backward compatibility)
    if context_chunks and isinstance(context_chunks[0], dict):
        from uuid import uuid4
        chunks = [
            ScoredChunk(
                id=uuid4(),
                document_id=uuid4(),
                content=c.get("content", ""),
                page_number=c.get("page"),
                metadata={},
                filename=c.get("filename"),
                score=c.get("score", 0),
            )
            for c in context_chunks
        ]
    else:
        chunks = context_chunks

    return builder.build(query, chunks, history, mode)
