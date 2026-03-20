"""End-to-end tests for chat flow."""
import uuid

import pytest

from app.core.generation.guard import GuardResult, GuardFailReason
from app.core.generation.mode_switch import ModeSwitch, RouteAction
from app.core.generation.intent_classifier import Intent, classify_intent


class TestChatE2E:
    """End-to-end tests for the chat flow."""

    def test_chit_chat_strict_flow(self):
        """Test chit-chat in strict mode returns template."""
        # Step 1: Classify intent
        intent = classify_intent("xin chào")
        assert intent == Intent.CHIT_CHAT

        # Step 2: Route decision
        switch = ModeSwitch()
        decision = switch.route(mode="strict", intent="chit_chat")

        assert decision.action == RouteAction.TEMPLATE
        template = switch.get_template(decision.template_key)
        assert len(template) > 0

    def test_chit_chat_general_flow(self):
        """Test chit-chat in general mode uses LLM."""
        intent = classify_intent("hi")
        assert intent == Intent.CHIT_CHAT

        switch = ModeSwitch()
        decision = switch.route(mode="general", intent="chit_chat")

        assert decision.action == RouteAction.LLM_GUIDED
        assert decision.system_prompt is not None

    def test_rag_query_with_context_flow(self):
        """Test RAG query with good context."""
        # Step 1: Classify intent
        intent = classify_intent("doanh thu quý 3 là bao nhiêu?")
        assert intent == Intent.RAG_QUERY

        # Step 2: Simulate retrieval result
        guard_result = GuardResult(passed=True, max_score=0.85)

        # Step 3: Route decision
        switch = ModeSwitch()
        decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision.action == RouteAction.LLM_WITH_CONTEXT

    def test_rag_query_strict_guard_fail(self):
        """Test RAG query in strict mode with low relevance."""
        # "thời tiết hôm nay" might be classified as rag_query due to default behavior
        
        guard_result = GuardResult(
            passed=False,
            reason=GuardFailReason.LOW_RELEVANCE,
            max_score=0.3,
        )

        switch = ModeSwitch()
        decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision.action == RouteAction.REJECT
        assert decision.message is not None
        assert "không" in decision.message.lower()

    def test_rag_query_general_guard_fail(self):
        """Test RAG query in general mode with low relevance."""
        guard_result = GuardResult(
            passed=False,
            reason=GuardFailReason.LOW_RELEVANCE,
            max_score=0.3,
        )

        switch = ModeSwitch()
        decision = switch.route(
            mode="general",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision.action == RouteAction.LLM_WITHOUT_CONTEXT
        assert decision.disclaimer is True

    def test_full_flow_with_retrieval(self):
        """Test complete flow from query to response decision."""
        query = "chi phí nhân sự năm 2024 là bao nhiêu?"

        # 1. Intent classification
        intent = classify_intent(query)
        assert intent == Intent.RAG_QUERY

        # 2. Simulate retrieval (would normally call pipeline.run())
        # Assume we got relevant results
        guard_result = GuardResult(passed=True, max_score=0.78)

        # 3. Mode switch
        switch = ModeSwitch()

        # Strict mode
        strict_decision = switch.route("strict", "rag_query", guard_result)
        assert strict_decision.action == RouteAction.LLM_WITH_CONTEXT

        # General mode (same guard result)
        general_decision = switch.route("general", "rag_query", guard_result)
        assert general_decision.action == RouteAction.LLM_WITH_CONTEXT

    def test_edge_case_borderline_guard(self):
        """Test borderline guard score (exactly at threshold)."""
        guard_result = GuardResult(passed=True, max_score=0.7)  # Exactly at threshold

        switch = ModeSwitch()
        decision = switch.route("strict", "rag_query", guard_result)

        # Should pass (>= threshold)
        assert decision.action == RouteAction.LLM_WITH_CONTEXT

    def test_mixed_language_query(self):
        """Test query with mixed Vietnamese/English."""
        queries = [
            ("revenue quý 3", Intent.RAG_QUERY),
            ("doanh thu Q3 2024", Intent.RAG_QUERY),
            ("what is chi phí", Intent.RAG_QUERY),
        ]

        for query, expected_intent in queries:
            intent = classify_intent(query)
            assert intent == expected_intent, f"Failed for query: {query}"

    @pytest.mark.asyncio
    async def test_prompt_building_with_chunks(self):
        """Test prompt building with retrieved chunks."""
        from app.core.generation.prompt_builder import build_prompt
        from app.core.retrieval.bm25_search import ScoredChunk

        chunks = [
            ScoredChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Doanh thu Q3 2024 đạt 150 tỷ VND",
                page_number=5,
                metadata={},
                filename="bao_cao.pdf",
                score=0.9,
                rerank_score=0.9,
            ),
            ScoredChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="So với Q2, tăng trưởng 15%",
                page_number=6,
                metadata={},
                filename="bao_cao.pdf",
                score=0.8,
                rerank_score=0.8,
            ),
        ]

        history = [
            {"role": "user", "content": "Xin chào"},
            {"role": "assistant", "content": "Xin chào! Tôi có thể giúp gì?"},
        ]

        prompt = build_prompt(
            query="Doanh thu Q3 là bao nhiêu?",
            context_chunks=chunks,
            history=history,
            mode="strict",
        )

        # Verify prompt structure
        assert prompt.system is not None
        assert "CHỈ trả lời dựa trên tài liệu" in prompt.system
        assert len(prompt.messages) == 1
        assert "150 tỷ" in prompt.messages[0]["content"]
        assert "bao_cao.pdf" in prompt.messages[0]["content"]
