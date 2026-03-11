"""Classify query intent for Phase 1 (simple rule-based; Phase 2 adds LLM-based)."""
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)

# Patterns that signal document-domain queries (Vietnamese + English)
_RETRIEVAL_KEYWORDS = [
    "chi phí", "cost", "giá", "price", "quy trình", "process",
    "hướng dẫn", "guide", "policy", "chính sách", "điều kiện",
    "deadline", "hạn chót", "requirements", "yêu cầu", "lợi ích",
    "benefit", "how", "what", "when", "where", "who", "why",
    "là gì", "như thế nào", "bao nhiêu", "khi nào", "ở đâu",
]


class Intent(StrEnum):
    RETRIEVAL = "retrieval"
    GENERAL = "general"


def classify_intent(message: str) -> Intent:
    """
    Phase 1: keyword heuristic.
    Returns RETRIEVAL if message likely needs document context, else GENERAL.
    """
    lower = message.lower()
    for kw in _RETRIEVAL_KEYWORDS:
        if kw in lower:
            logger.debug("intent.retrieval", keyword=kw)
            return Intent.RETRIEVAL
    # Default to RETRIEVAL so we always try to ground answers
    return Intent.RETRIEVAL
