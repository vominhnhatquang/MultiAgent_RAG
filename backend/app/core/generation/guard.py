"""Guard to enforce relevance thresholds in strict mode."""
from dataclasses import dataclass
from enum import StrEnum

import structlog

from app.core.retrieval.pipeline import RetrievalResult

logger = structlog.get_logger(__name__)


class GuardFailReason(StrEnum):
    """Reasons why guard check failed."""

    NO_CHUNKS = "no_chunks"
    LOW_RELEVANCE = "low_relevance"


@dataclass
class GuardResult:
    """Result of guard check."""

    passed: bool
    reason: GuardFailReason | None = None
    max_score: float | None = None
    threshold: float | None = None


# Pre-defined responses for guard failures
GUARD_FAIL_MESSAGES = {
    GuardFailReason.NO_CHUNKS: "Tôi không tìm thấy thông tin liên quan trong tài liệu đã upload.",
    GuardFailReason.LOW_RELEVANCE: "Tôi không có đủ thông tin đáng tin cậy để trả lời câu hỏi này.",
}


class StrictGuard:
    """
    Guard for strict mode that blocks responses when relevance is too low.

    In strict mode:
    - If no chunks found → block (NO_CHUNKS)
    - If max rerank score < threshold → block (LOW_RELEVANCE)
    - Otherwise → pass (allow LLM to generate with context)
    """

    def __init__(self, threshold: float = 0.7) -> None:
        """
        Args:
            threshold: Minimum rerank score to pass guard (default 0.7)
        """
        self.threshold = threshold

    def check(self, retrieval_result: RetrievalResult) -> GuardResult:
        """
        Check if retrieval results pass the guard.

        Args:
            retrieval_result: Result from retrieval pipeline

        Returns:
            GuardResult indicating pass/fail and reason
        """
        if not retrieval_result.has_results:
            logger.info("guard.fail", reason="no_chunks")
            return GuardResult(
                passed=False,
                reason=GuardFailReason.NO_CHUNKS,
            )

        max_score = retrieval_result.max_score

        if max_score < self.threshold:
            logger.info(
                "guard.fail",
                reason="low_relevance",
                max_score=max_score,
                threshold=self.threshold,
            )
            return GuardResult(
                passed=False,
                reason=GuardFailReason.LOW_RELEVANCE,
                max_score=max_score,
                threshold=self.threshold,
            )

        logger.debug("guard.pass", max_score=max_score)
        return GuardResult(
            passed=True,
            max_score=max_score,
        )

    def get_fail_message(self, reason: GuardFailReason) -> str:
        """Get the user-facing message for a guard failure."""
        return GUARD_FAIL_MESSAGES.get(
            reason,
            "Tôi không thể trả lời câu hỏi này dựa trên tài liệu hiện có.",
        )
