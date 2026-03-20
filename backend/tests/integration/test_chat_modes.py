"""Integration tests for chat modes (strict/general) with full pipeline."""
import uuid

import pytest

from app.core.generation.guard import GuardResult, GuardFailReason, StrictGuard
from app.core.generation.intent_classifier import Intent, classify_intent
from app.core.generation.mode_switch import ModeSwitch, RouteAction
from app.core.generation.prompt_builder import build_prompt
from app.core.retrieval.bm25_search import ScoredChunk
from app.core.retrieval.pipeline import RetrievalResult


class TestStrictModeChatFlow:
    """Tests for strict mode chat behavior."""

    def test_strict_chit_chat_returns_template_no_llm(self):
        """
        Strict mode + chit-chat → template response (no LLM call).
        
        Flow: "xin chào" → classify as chit_chat → route to TEMPLATE
        """
        # Step 1: Intent classification
        intent = classify_intent("xin chào")
        assert intent == Intent.CHIT_CHAT

        # Step 2: Mode switch routing
        switch = ModeSwitch()
        decision = switch.route(mode="strict", intent="chit_chat")

        # Verify: template response, no LLM needed
        assert decision.action == RouteAction.TEMPLATE
        assert decision.template_key is not None

        # Get template content
        template = switch.get_template(decision.template_key)
        assert isinstance(template, str)
        assert len(template) > 0
        # Template should mention "trợ lý tài liệu" or documents
        assert "trợ lý" in template.lower() or "tài liệu" in template.lower()

    def test_strict_irrelevant_query_guard_rejection(self):
        """
        Strict mode + irrelevant query → guard rejection ("Không có thông tin").
        
        Flow: query → retrieve (low scores) → guard fails → REJECT
        """
        # Simulate guard result with low relevance
        guard_result = GuardResult(
            passed=False,
            reason=GuardFailReason.LOW_RELEVANCE,
            max_score=0.35,  # Below 0.7 threshold
        )

        switch = ModeSwitch()
        decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )

        # Verify: rejection with Vietnamese message
        assert decision.action == RouteAction.REJECT
        assert decision.message is not None
        assert "không" in decision.message.lower()

    def test_strict_relevant_query_llm_with_context(self):
        """
        Strict mode + relevant query → LLM with context + sources.
        
        Flow: query → retrieve (high scores) → guard passes → LLM_WITH_CONTEXT
        """
        intent = classify_intent("doanh thu quý 3 năm 2024 là bao nhiêu?")
        assert intent == Intent.RAG_QUERY

        # Simulate good retrieval
        guard_result = GuardResult(passed=True, max_score=0.85)

        switch = ModeSwitch()
        decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )

        # Verify: LLM with context
        assert decision.action == RouteAction.LLM_WITH_CONTEXT
        assert decision.disclaimer is False  # No disclaimer in strict mode with good context

    def test_strict_no_retrieval_results_rejection(self):
        """
        Strict mode + no retrieval results → guard fails → REJECT.
        """
        # Guard fails due to no results
        guard_result = GuardResult(
            passed=False,
            reason=GuardFailReason.NO_CHUNKS,
            max_score=0.0,
        )

        switch = ModeSwitch()
        decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision.action == RouteAction.REJECT


class TestGeneralModeChatFlow:
    """Tests for general mode chat behavior."""

    def test_general_chit_chat_llm_guided(self):
        """
        General mode + chit-chat → LLM guided response.
        
        Flow: "hi" → classify as chit_chat → route to LLM_GUIDED
        """
        intent = classify_intent("hi")
        assert intent == Intent.CHIT_CHAT

        switch = ModeSwitch()
        decision = switch.route(mode="general", intent="chit_chat")

        # Verify: LLM guided (not template)
        assert decision.action == RouteAction.LLM_GUIDED
        assert decision.system_prompt is not None

    def test_general_irrelevant_query_llm_without_context(self):
        """
        General mode + irrelevant query → LLM without context + disclaimer.
        
        Flow: query → retrieve (low scores) → guard fails → LLM_WITHOUT_CONTEXT
        """
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

        # Verify: LLM without context + disclaimer
        assert decision.action == RouteAction.LLM_WITHOUT_CONTEXT
        assert decision.disclaimer is True

    def test_general_relevant_query_llm_with_context(self):
        """
        General mode + relevant query → LLM with context.
        """
        guard_result = GuardResult(passed=True, max_score=0.82)

        switch = ModeSwitch()
        decision = switch.route(
            mode="general",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision.action == RouteAction.LLM_WITH_CONTEXT


class TestModeSwitchMidSession:
    """Tests for switching modes during a session."""

    def test_switch_strict_to_general_mid_session(self):
        """
        Test switching from strict to general mode mid-session.
        
        Same query, different mode → different routing decision.
        """
        switch = ModeSwitch()

        # Same guard result (borderline)
        guard_result = GuardResult(
            passed=False,
            reason=GuardFailReason.LOW_RELEVANCE,
            max_score=0.5,
        )

        # In strict mode: REJECT
        strict_decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )
        assert strict_decision.action == RouteAction.REJECT

        # Switch to general mode: LLM_WITHOUT_CONTEXT
        general_decision = switch.route(
            mode="general",
            intent="rag_query",
            guard_result=guard_result,
        )
        assert general_decision.action == RouteAction.LLM_WITHOUT_CONTEXT
        assert general_decision.disclaimer is True

    def test_switch_general_to_strict_mid_session(self):
        """
        Test switching from general to strict mode mid-session.
        
        Chit-chat in both modes shows different behavior.
        """
        switch = ModeSwitch()

        # General mode: LLM guided
        general_decision = switch.route(mode="general", intent="chit_chat")
        assert general_decision.action == RouteAction.LLM_GUIDED

        # Strict mode: template
        strict_decision = switch.route(mode="strict", intent="chit_chat")
        assert strict_decision.action == RouteAction.TEMPLATE

    def test_mode_consistency_within_session(self):
        """
        Test that mode decisions are consistent for same inputs.
        """
        switch = ModeSwitch()
        guard_result = GuardResult(passed=True, max_score=0.75)

        # Multiple calls with same inputs should give same result
        for _ in range(3):
            decision = switch.route(
                mode="strict",
                intent="rag_query",
                guard_result=guard_result,
            )
            assert decision.action == RouteAction.LLM_WITH_CONTEXT


class TestGuardThresholds:
    """Tests for guard threshold behavior."""

    def test_guard_exact_threshold(self):
        """Test behavior at exact 0.7 threshold."""
        guard = StrictGuard(threshold=0.7)

        # Create RetrievalResult with chunk at threshold
        chunks = [
            ScoredChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Test content",
                page_number=1,
                metadata={},
                filename="test.pdf",
                score=0.7,
                rerank_score=0.7,
            )
        ]
        retrieval_result = RetrievalResult(chunks=chunks, sources=[])

        result = guard.check(retrieval_result)
        assert result.passed is True
        assert result.max_score == 0.7

    def test_guard_below_threshold(self):
        """Test guard fails below threshold."""
        guard = StrictGuard(threshold=0.7)

        chunks = [
            ScoredChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Test content",
                page_number=1,
                metadata={},
                filename="test.pdf",
                score=0.69,
                rerank_score=0.69,
            )
        ]
        retrieval_result = RetrievalResult(chunks=chunks, sources=[])

        result = guard.check(retrieval_result)
        assert result.passed is False
        assert result.reason == GuardFailReason.LOW_RELEVANCE

    def test_guard_empty_chunks(self):
        """Test guard with no chunks."""
        guard = StrictGuard()

        retrieval_result = RetrievalResult(chunks=[], sources=[])
        result = guard.check(retrieval_result)
        assert result.passed is False
        assert result.reason == GuardFailReason.NO_CHUNKS


class TestPromptBuildingIntegration:
    """Tests for prompt building with context."""

    @pytest.mark.asyncio
    async def test_strict_prompt_includes_constraints(self):
        """Test strict mode prompt includes document constraints."""
        chunks = [
            ScoredChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Doanh thu Q3 2024: 150 tỷ VND",
                page_number=5,
                metadata={},
                filename="report.pdf",
                score=0.9,
                rerank_score=0.9,
            ),
        ]

        prompt = build_prompt(
            query="Doanh thu Q3?",
            context_chunks=chunks,
            history=[],
            mode="strict",
        )

        # Strict mode should have constraints
        assert "CHỈ trả lời dựa trên tài liệu" in prompt.system
        assert "150 tỷ" in prompt.messages[0]["content"]

    @pytest.mark.asyncio
    async def test_general_prompt_more_flexible(self):
        """Test general mode prompt is more flexible."""
        chunks = [
            ScoredChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Doanh thu Q3 2024: 150 tỷ VND",
                page_number=5,
                metadata={},
                filename="report.pdf",
                score=0.9,
                rerank_score=0.9,
            ),
        ]

        prompt = build_prompt(
            query="Doanh thu Q3?",
            context_chunks=chunks,
            history=[],
            mode="general",
        )

        # General mode still references documents but less strict
        assert prompt.system is not None
        assert "150 tỷ" in prompt.messages[0]["content"]

    @pytest.mark.asyncio
    async def test_prompt_with_conversation_history(self):
        """Test prompt includes conversation history."""
        chunks = [
            ScoredChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                content="Chi phí nhân sự: 50 tỷ",
                page_number=3,
                metadata={},
                filename="report.pdf",
                score=0.85,
                rerank_score=0.85,
            ),
        ]

        history = [
            {"role": "user", "content": "Xin chào"},
            {"role": "assistant", "content": "Xin chào! Tôi có thể giúp gì?"},
            {"role": "user", "content": "Doanh thu là bao nhiêu?"},
            {"role": "assistant", "content": "Doanh thu Q3 2024 là 150 tỷ VND."},
        ]

        prompt = build_prompt(
            query="Chi phí nhân sự?",
            context_chunks=chunks,
            history=history,
            mode="strict",
        )

        # Should have history context
        assert len(prompt.messages) >= 1


class TestVietnameseQueryClassification:
    """Tests for Vietnamese query classification."""

    @pytest.mark.parametrize("query,expected_intent", [
        # Chit-chat patterns
        ("xin chào", Intent.CHIT_CHAT),
        ("cảm ơn", Intent.CHIT_CHAT),
        ("tạm biệt", Intent.CHIT_CHAT),
        ("ok", Intent.CHIT_CHAT),
        ("ừ", Intent.CHIT_CHAT),
        
        # RAG query patterns
        ("doanh thu quý 3", Intent.RAG_QUERY),
        ("chi phí nhân sự năm 2024", Intent.RAG_QUERY),
        ("báo cáo tài chính", Intent.RAG_QUERY),
        ("so sánh Q2 và Q3", Intent.RAG_QUERY),
        ("tổng hợp thông tin", Intent.RAG_QUERY),
    ])
    def test_vietnamese_intent_classification(self, query: str, expected_intent: Intent):
        """Test Vietnamese query intent classification."""
        result = classify_intent(query)
        assert result == expected_intent, f"Query '{query}' expected {expected_intent}, got {result}"

    def test_mixed_language_queries(self):
        """Test mixed Vietnamese/English queries."""
        mixed_queries = [
            ("revenue Q3 2024", Intent.RAG_QUERY),
            ("doanh thu revenue", Intent.RAG_QUERY),
            ("chi phí cost", Intent.RAG_QUERY),
        ]

        for query, expected in mixed_queries:
            result = classify_intent(query)
            assert result == expected, f"Query '{query}' failed"
