"""Tests for mode switch."""
import pytest

from app.core.generation.guard import GuardResult, GuardFailReason
from app.core.generation.mode_switch import ModeSwitch, RouteAction


class TestModeSwitch:
    """Unit tests for ModeSwitch."""

    @pytest.fixture
    def switch(self):
        """Create ModeSwitch instance."""
        return ModeSwitch()

    # Chit-chat routing tests

    def test_chit_chat_strict_returns_template(self, switch):
        """Chit-chat in strict mode should return template response."""
        decision = switch.route(mode="strict", intent="chit_chat")

        assert decision.action == RouteAction.TEMPLATE
        assert decision.template_key is not None

    def test_chit_chat_general_returns_llm_guided(self, switch):
        """Chit-chat in general mode should use LLM with guided prompt."""
        decision = switch.route(mode="strict", intent="chit_chat")
        decision_general = switch.route(mode="general", intent="chit_chat")

        assert decision.action == RouteAction.TEMPLATE
        assert decision_general.action == RouteAction.LLM_GUIDED
        assert decision_general.system_prompt is not None

    # RAG query routing tests

    def test_rag_guard_passed_returns_llm_with_context(self, switch):
        """RAG query with passed guard should use LLM with context."""
        guard_result = GuardResult(passed=True, max_score=0.8)

        decision_strict = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )
        decision_general = switch.route(
            mode="general",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision_strict.action == RouteAction.LLM_WITH_CONTEXT
        assert decision_general.action == RouteAction.LLM_WITH_CONTEXT

    def test_rag_guard_failed_strict_rejects(self, switch):
        """RAG query with failed guard in strict mode should reject."""
        guard_result = GuardResult(
            passed=False,
            reason=GuardFailReason.LOW_RELEVANCE,
            max_score=0.5,
        )

        decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision.action == RouteAction.REJECT
        assert decision.message is not None

    def test_rag_guard_failed_general_uses_llm_without_context(self, switch):
        """RAG query with failed guard in general mode should use LLM without context."""
        guard_result = GuardResult(
            passed=False,
            reason=GuardFailReason.LOW_RELEVANCE,
            max_score=0.5,
        )

        decision = switch.route(
            mode="general",
            intent="rag_query",
            guard_result=guard_result,
        )

        assert decision.action == RouteAction.LLM_WITHOUT_CONTEXT
        assert decision.disclaimer is True
        assert decision.system_prompt is not None

    def test_rag_no_guard_result_strict_rejects(self, switch):
        """RAG query without guard result in strict mode should reject."""
        decision = switch.route(
            mode="strict",
            intent="rag_query",
            guard_result=None,
        )

        assert decision.action == RouteAction.REJECT

    def test_rag_no_guard_result_general_uses_fallback(self, switch):
        """RAG query without guard result in general mode should use fallback."""
        decision = switch.route(
            mode="general",
            intent="rag_query",
            guard_result=None,
        )

        assert decision.action == RouteAction.LLM_WITHOUT_CONTEXT
        assert decision.disclaimer is True

    # Template tests

    def test_get_template_returns_string(self, switch):
        """get_template should return a string for known keys."""
        greeting = switch.get_template("greeting")
        farewell = switch.get_template("farewell")
        default = switch.get_template("unknown_key")

        assert isinstance(greeting, str)
        assert isinstance(farewell, str)
        assert isinstance(default, str)  # Falls back to default

    def test_get_template_default_fallback(self, switch):
        """get_template should return default for unknown keys."""
        unknown = switch.get_template("xyz_unknown")
        default = switch.get_template("default")

        assert unknown == default
