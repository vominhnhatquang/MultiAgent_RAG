"""Mode switch for routing queries based on mode and guard results."""
from dataclasses import dataclass
from enum import StrEnum

import structlog

from app.core.generation.guard import GuardResult, GuardFailReason, GUARD_FAIL_MESSAGES

logger = structlog.get_logger(__name__)


class RouteAction(StrEnum):
    """Actions the router can take."""

    TEMPLATE = "template"  # Return a template response
    LLM_WITH_CONTEXT = "llm_with_context"  # LLM with retrieved context
    LLM_WITHOUT_CONTEXT = "llm_without_context"  # LLM without context (general mode)
    LLM_GUIDED = "llm_guided"  # LLM with special system prompt
    REJECT = "reject"  # Block with message


@dataclass
class RouteDecision:
    """Decision from the mode switch router."""

    action: RouteAction
    template_key: str | None = None  # For TEMPLATE action
    system_prompt: str | None = None  # For LLM_GUIDED action
    message: str | None = None  # For REJECT action
    disclaimer: bool = False  # Whether to add disclaimer


# System prompt for general mode chit-chat
GENERAL_CHITCHAT_PROMPT = """Bạn là trợ lý tài liệu. Bạn có thể trò chuyện ngắn gọn
nhưng luôn nhắc người dùng rằng chức năng chính của bạn là trả lời câu hỏi
dựa trên tài liệu đã upload. Giữ câu trả lời ngắn gọn, chuyên nghiệp."""

# System prompt for general mode when no context
GENERAL_NO_CONTEXT_PROMPT = """Bạn là trợ lý AI. Trả lời câu hỏi một cách hữu ích,
nhưng BẮT BUỘC phải bắt đầu câu trả lời với disclaimer:
"Lưu ý: Câu trả lời này không dựa trên tài liệu đã upload, mà dựa trên kiến thức chung."
Sau đó trả lời câu hỏi."""

# Template responses for chit-chat in strict mode
CHIT_CHAT_TEMPLATES = {
    "greeting": "Xin chào! Tôi là trợ lý tài liệu. Bạn có thể hỏi tôi về nội dung các tài liệu đã upload.",
    "farewell": "Cảm ơn bạn đã sử dụng. Chúc bạn một ngày tốt lành!",
    "thanks": "Không có chi! Nếu bạn cần hỏi thêm về tài liệu, cứ hỏi nhé.",
    "default": "Tôi là trợ lý tài liệu. Hãy hỏi tôi về nội dung trong tài liệu đã upload.",
}


class ModeSwitch:
    """
    Route queries based on mode (strict/general), intent, and guard results.

    Strict Mode:
        - Chit-chat → template response (no LLM)
        - RAG query + guard pass → LLM with context
        - RAG query + guard fail → reject with message

    General Mode:
        - Chit-chat → LLM with guided prompt
        - RAG query + guard pass → LLM with context
        - RAG query + guard fail → LLM without context + disclaimer
    """

    def route(
        self,
        mode: str,
        intent: str,
        guard_result: GuardResult | None = None,
    ) -> RouteDecision:
        """
        Determine how to handle the query.

        Args:
            mode: "strict" or "general"
            intent: "chit_chat" or "rag_query"
            guard_result: Result from guard check (None for chit-chat)

        Returns:
            RouteDecision with action and parameters
        """
        # Chit-chat handling
        if intent == "chit_chat":
            if mode == "strict":
                logger.debug("route.chit_chat_strict")
                return RouteDecision(
                    action=RouteAction.TEMPLATE,
                    template_key="default",
                )
            else:
                logger.debug("route.chit_chat_general")
                return RouteDecision(
                    action=RouteAction.LLM_GUIDED,
                    system_prompt=GENERAL_CHITCHAT_PROMPT,
                )

        # RAG query handling
        if guard_result is None:
            # No guard result means no retrieval was done (shouldn't happen for RAG)
            logger.warning("route.rag_no_guard")
            if mode == "strict":
                return RouteDecision(
                    action=RouteAction.REJECT,
                    message=GUARD_FAIL_MESSAGES[GuardFailReason.NO_CHUNKS],
                )
            return RouteDecision(
                action=RouteAction.LLM_WITHOUT_CONTEXT,
                system_prompt=GENERAL_NO_CONTEXT_PROMPT,
                disclaimer=True,
            )

        if guard_result.passed:
            logger.debug("route.rag_with_context")
            return RouteDecision(action=RouteAction.LLM_WITH_CONTEXT)

        # Guard failed
        if mode == "strict":
            logger.debug("route.rag_reject_strict", reason=guard_result.reason)
            return RouteDecision(
                action=RouteAction.REJECT,
                message=GUARD_FAIL_MESSAGES.get(
                    guard_result.reason,
                    "Tôi không thể trả lời câu hỏi này.",
                ),
            )
        else:
            logger.debug("route.rag_no_context_general", reason=guard_result.reason)
            return RouteDecision(
                action=RouteAction.LLM_WITHOUT_CONTEXT,
                system_prompt=GENERAL_NO_CONTEXT_PROMPT,
                disclaimer=True,
            )

    def get_template(self, key: str) -> str:
        """Get a template response by key."""
        return CHIT_CHAT_TEMPLATES.get(key, CHIT_CHAT_TEMPLATES["default"])
