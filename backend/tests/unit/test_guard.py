"""Tests for strict guard."""
import uuid

import pytest

from app.core.generation.guard import StrictGuard, GuardFailReason
from app.core.retrieval.bm25_search import ScoredChunk
from app.core.retrieval.pipeline import RetrievalResult


class TestStrictGuard:
    """Unit tests for StrictGuard."""

    @pytest.fixture
    def guard(self):
        """Create guard with default threshold."""
        return StrictGuard(threshold=0.7)

    def create_chunk(self, rerank_score: float) -> ScoredChunk:
        """Helper to create test chunks."""
        return ScoredChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="test content",
            page_number=1,
            metadata={},
            filename="test.pdf",
            score=0.5,
            rerank_score=rerank_score,
        )

    def test_check_passes_when_above_threshold(self, guard):
        """Guard should pass when max score >= threshold."""
        chunks = [
            self.create_chunk(0.8),
            self.create_chunk(0.6),
        ]
        result = RetrievalResult(
            chunks=chunks,
            sources=[],
        )

        guard_result = guard.check(result)

        assert guard_result.passed is True
        assert guard_result.max_score == 0.8

    def test_check_fails_when_below_threshold(self, guard):
        """Guard should fail when max score < threshold."""
        chunks = [
            self.create_chunk(0.5),
            self.create_chunk(0.4),
        ]
        result = RetrievalResult(
            chunks=chunks,
            sources=[],
        )

        guard_result = guard.check(result)

        assert guard_result.passed is False
        assert guard_result.reason == GuardFailReason.LOW_RELEVANCE
        assert guard_result.max_score == 0.5
        assert guard_result.threshold == 0.7

    def test_check_fails_when_no_chunks(self, guard):
        """Guard should fail when no chunks retrieved."""
        result = RetrievalResult(
            chunks=[],
            sources=[],
        )

        guard_result = guard.check(result)

        assert guard_result.passed is False
        assert guard_result.reason == GuardFailReason.NO_CHUNKS

    def test_check_at_exact_threshold(self, guard):
        """Guard should pass when score equals threshold."""
        chunks = [self.create_chunk(0.7)]
        result = RetrievalResult(chunks=chunks, sources=[])

        guard_result = guard.check(result)

        assert guard_result.passed is True

    def test_custom_threshold(self):
        """Guard should respect custom threshold."""
        guard = StrictGuard(threshold=0.9)
        chunks = [self.create_chunk(0.85)]
        result = RetrievalResult(chunks=chunks, sources=[])

        guard_result = guard.check(result)

        assert guard_result.passed is False
        assert guard_result.threshold == 0.9

    def test_get_fail_message(self, guard):
        """Should return appropriate message for each fail reason."""
        no_chunks_msg = guard.get_fail_message(GuardFailReason.NO_CHUNKS)
        low_rel_msg = guard.get_fail_message(GuardFailReason.LOW_RELEVANCE)

        assert "không tìm thấy" in no_chunks_msg.lower()
        assert "không có đủ thông tin" in low_rel_msg.lower()
