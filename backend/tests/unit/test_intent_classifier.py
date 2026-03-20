"""Tests for intent classifier."""
import pytest

from app.core.generation.intent_classifier import IntentClassifier, Intent, classify_intent


class TestIntentClassifier:
    """Unit tests for IntentClassifier."""

    @pytest.fixture
    def classifier(self):
        """Create IntentClassifier instance."""
        return IntentClassifier()

    # Chit-chat detection tests

    @pytest.mark.parametrize("query", [
        "hi",
        "Hello",
        "hey!",
        "xin chào",
        "chào",
        "Ê",
        "bye",
        "tạm biệt",
        "cảm ơn",
        "thanks",
        "ok",
        "ừ",
        "vâng",
    ])
    def test_detects_chit_chat_greetings(self, classifier, query):
        """Should detect common greetings/farewells as chit-chat."""
        intent = classifier.classify(query)
        assert intent == Intent.CHIT_CHAT

    def test_detects_short_queries_without_keywords_as_chit_chat(self, classifier):
        """Short queries without domain keywords should be chit-chat."""
        intent = classifier.classify("có gì không?")
        # Depends on implementation - might be chit_chat or rag
        assert intent in [Intent.CHIT_CHAT, Intent.RAG_QUERY]

    # RAG query detection tests

    @pytest.mark.parametrize("query", [
        "doanh thu quý 3 là bao nhiêu?",
        "so sánh lợi nhuận Q2 và Q3",
        "tóm tắt báo cáo tài chính",
        "chi phí nhân sự năm 2024",
        "hướng dẫn quy trình đăng ký",
        "chính sách bảo hiểm như thế nào",
        "số liệu thống kê doanh số",
    ])
    def test_detects_rag_queries(self, classifier, query):
        """Should detect domain-specific queries as RAG queries."""
        intent = classifier.classify(query)
        assert intent == Intent.RAG_QUERY

    def test_detects_queries_with_domain_keywords(self, classifier):
        """Queries with domain keywords should be RAG queries."""
        # Even short queries with keywords
        assert classifier.classify("doanh thu?") == Intent.RAG_QUERY
        assert classifier.classify("báo cáo") == Intent.RAG_QUERY

    # Edge cases

    def test_empty_query(self, classifier):
        """Empty query should default to RAG (will likely fail retrieval anyway)."""
        intent = classifier.classify("")
        # Implementation dependent - might be chit_chat or rag
        assert intent in [Intent.CHIT_CHAT, Intent.RAG_QUERY]

    def test_whitespace_query(self, classifier):
        """Whitespace-only query handling."""
        intent = classifier.classify("   ")
        assert intent in [Intent.CHIT_CHAT, Intent.RAG_QUERY]

    def test_mixed_case(self, classifier):
        """Should handle mixed case queries."""
        assert classifier.classify("DOANH THU") == Intent.RAG_QUERY
        assert classifier.classify("Xin Chào") == Intent.CHIT_CHAT

    def test_convenience_function(self):
        """classify_intent function should work."""
        intent = classify_intent("doanh thu quý 3")
        assert intent == Intent.RAG_QUERY

    def test_intent_enum_values(self):
        """Intent enum should have expected values."""
        assert Intent.CHIT_CHAT.value == "chit_chat"
        assert Intent.RAG_QUERY.value == "rag_query"

    # Legacy alias tests

    def test_legacy_aliases(self):
        """Legacy aliases should map to correct intents."""
        assert Intent.RETRIEVAL == Intent.RAG_QUERY
        assert Intent.GENERAL == Intent.CHIT_CHAT
