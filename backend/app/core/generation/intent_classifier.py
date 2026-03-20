"""Classify query intent: chit_chat vs rag_query.

Phase 2: Rule-based first (fast), with domain keyword detection.
"""
import re
from enum import StrEnum

import structlog

logger = structlog.get_logger(__name__)


class Intent(StrEnum):
    CHIT_CHAT = "chit_chat"
    RAG_QUERY = "rag_query"
    # Legacy aliases
    RETRIEVAL = "rag_query"
    GENERAL = "chit_chat"


# Patterns that clearly indicate chit-chat (greetings, farewells, etc.)
CHIT_CHAT_PATTERNS = [
    r"^(hi|hello|hey|xin chào|chào|ê|yo)[\s!?.]*$",
    r"^(bye|tạm biệt|goodbye|cảm ơn|thanks|thank you|cám ơn)[\s!?.]*$",
    r"^(bạn là ai|you are|who are you|tên bạn là gì)[\s?]*$",
    r"^(ok|okay|ừ|vâng|alright|được|rồi)[\s!?.]*$",
    r"^(có gì mới|how are you|khỏe không)[\s?]*$",
]

# Keywords that suggest document-related queries
DOMAIN_KEYWORDS = [
    # Business/Finance
    "doanh thu", "lợi nhuận", "chi phí", "ngân sách", "tài chính",
    "revenue", "profit", "cost", "budget", "financial",
    # Reports/Documents
    "báo cáo", "tài liệu", "file", "trang", "bảng", "biểu đồ",
    "report", "document", "page", "table", "chart",
    # Data/Analysis
    "số liệu", "thống kê", "phân tích", "so sánh", "tóm tắt",
    "data", "statistics", "analysis", "compare", "summary",
    # Instructions/Policies
    "hướng dẫn", "quy trình", "chính sách", "điều kiện", "yêu cầu",
    "guide", "process", "policy", "requirements", "instructions",
    # Questions
    "là gì", "như thế nào", "bao nhiêu", "khi nào", "ở đâu", "tại sao",
    "what is", "how", "how much", "when", "where", "why",
    # Time references
    "quý", "tháng", "năm", "Q1", "Q2", "Q3", "Q4",
    "quarter", "month", "year",
]


class IntentClassifier:
    """
    Classify user intent: chit_chat or rag_query.

    Strategy: Rule-based FIRST (fast, 0 latency), LLM SAU (nếu cần).
    """

    def __init__(self) -> None:
        self._chit_chat_patterns = [re.compile(p, re.IGNORECASE) for p in CHIT_CHAT_PATTERNS]

    def classify(self, query: str) -> Intent:
        """
        Classify query intent.

        Args:
            query: User query string

        Returns:
            Intent.CHIT_CHAT or Intent.RAG_QUERY
        """
        query_stripped = query.strip()
        query_lower = query_stripped.lower()

        # Rule 1: Check chit-chat patterns (fast regex)
        for pattern in self._chit_chat_patterns:
            if pattern.match(query_stripped):
                logger.debug("intent.chit_chat", reason="pattern_match")
                return Intent.CHIT_CHAT

        # Rule 2: Very short query without domain keywords
        words = query_lower.split()
        if len(words) < 3 and not self._has_domain_keyword(query_lower):
            logger.debug("intent.chit_chat", reason="short_no_keyword")
            return Intent.CHIT_CHAT

        # Rule 3: Has domain keyword → RAG query
        if self._has_domain_keyword(query_lower):
            logger.debug("intent.rag_query", reason="domain_keyword")
            return Intent.RAG_QUERY

        # Default: treat as RAG query (better to try retrieval than miss relevant info)
        logger.debug("intent.rag_query", reason="default")
        return Intent.RAG_QUERY

    def _has_domain_keyword(self, text: str) -> bool:
        """Check if text contains any domain-related keywords."""
        return any(kw in text for kw in DOMAIN_KEYWORDS)


# Singleton instance
_classifier: IntentClassifier | None = None


def get_intent_classifier() -> IntentClassifier:
    """Get the global intent classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


def classify_intent(message: str) -> Intent:
    """
    Classify intent (convenience function).

    Args:
        message: User message

    Returns:
        Intent enum value
    """
    return get_intent_classifier().classify(message)
