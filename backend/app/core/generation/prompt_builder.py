"""Build LLM prompts from retrieved context + chat history."""
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

_SYSTEM_STRICT = (
    "Bạn là trợ lý AI. Chỉ trả lời dựa trên ngữ cảnh tài liệu được cung cấp. "
    "Nếu câu trả lời không có trong tài liệu, hãy nói rõ điều đó. "
    "Trả lời bằng ngôn ngữ mà người dùng sử dụng."
)
_SYSTEM_GENERAL = (
    "Bạn là trợ lý AI hữu ích. "
    "Ưu tiên sử dụng ngữ cảnh tài liệu khi có, nhưng có thể dùng kiến thức chung nếu cần. "
    "Trả lời bằng ngôn ngữ mà người dùng sử dụng."
)

MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_TURNS = 3


@dataclass
class BuiltPrompt:
    system: str
    messages: list[dict]   # [{role, content}]


def build_prompt(
    query: str,
    context_chunks: list[dict],   # [{"content": ..., "score": ..., "filename": ..., "page": ...}]
    history: list[dict],          # [{role, content}] most recent last
    mode: str = "strict",
) -> BuiltPrompt:
    system = _SYSTEM_STRICT if mode == "strict" else _SYSTEM_GENERAL

    # Build context block
    context_parts: list[str] = []
    total_chars = 0
    for i, c in enumerate(context_chunks, 1):
        snippet = f"[{i}] (from {c.get('filename','?')}, page {c.get('page','?')}):\n{c['content']}"
        if total_chars + len(snippet) > MAX_CONTEXT_CHARS:
            break
        context_parts.append(snippet)
        total_chars += len(snippet)

    context_str = "\n\n".join(context_parts)
    if context_str:
        context_block = f"=== TÀI LIỆU THAM KHẢO ===\n{context_str}\n=========================\n\n"
    else:
        context_block = ""

    # Build messages list
    msgs: list[dict] = []

    # Recent history
    recent = history[-(MAX_HISTORY_TURNS * 2):]
    for turn in recent:
        msgs.append({"role": turn["role"], "content": turn["content"]})

    # Final user message with context prepended
    user_content = f"{context_block}Câu hỏi: {query}"
    msgs.append({"role": "user", "content": user_content})

    logger.debug("prompt_builder.built", context_chunks=len(context_parts), history_turns=len(recent) // 2)
    return BuiltPrompt(system=system, messages=msgs)
