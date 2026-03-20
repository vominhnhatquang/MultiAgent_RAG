"""Reranker using cross-encoder for improved ranking accuracy."""
import structlog

from app.core.retrieval.bm25_search import ScoredChunk

logger = structlog.get_logger(__name__)

# Lazy-loaded model to avoid loading at import time
_reranker_model = None


def _get_reranker():
    """Lazy-load the cross-encoder model."""
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder

            logger.info("reranker.loading_model")
            _reranker_model = CrossEncoder(
                "BAAI/bge-reranker-v2-m3",
                max_length=512,
                device="cpu",  # No GPU
            )
            logger.info("reranker.model_loaded")
        except ImportError:
            logger.warning("reranker.sentence_transformers_not_installed")
            return None
        except Exception as e:
            logger.error("reranker.load_failed", error=str(e))
            return None
    return _reranker_model


class Reranker:
    """
    Cross-encoder reranker for improved ranking accuracy.

    Uses BAAI/bge-reranker-v2-m3 which looks at query + document together
    (unlike bi-encoders which embed separately).

    This provides more accurate relevance scores but is slower,
    so we only rerank the top-K candidates from hybrid search.
    """

    def __init__(self, lazy_load: bool = True) -> None:
        """
        Args:
            lazy_load: If True, load model on first use. If False, load immediately.
        """
        self._model = None
        if not lazy_load:
            self._model = _get_reranker()

    @property
    def model(self):
        """Get the cross-encoder model (lazy loaded)."""
        if self._model is None:
            self._model = _get_reranker()
        return self._model

    def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
        top_k: int = 5,
    ) -> list[ScoredChunk]:
        """
        Rerank chunks using cross-encoder.

        Args:
            query: Original user query
            chunks: Candidate chunks from hybrid search
            top_k: Number of top results to return

        Returns:
            Reranked chunks with rerank_score set
        """
        if not chunks:
            return []

        model = self.model
        if model is None:
            # Fallback: return chunks as-is with score as rerank_score
            logger.warning("reranker.model_unavailable_fallback")
            for chunk in chunks:
                chunk.rerank_score = chunk.score
            return chunks[:top_k]

        # Create query-document pairs
        pairs = [[query, chunk.content] for chunk in chunks]

        # Score all pairs
        try:
            scores = model.predict(pairs)
        except Exception as e:
            logger.error("reranker.predict_failed", error=str(e))
            # Fallback
            for chunk in chunks:
                chunk.rerank_score = chunk.score
            return chunks[:top_k]

        # Attach scores
        for chunk, score in zip(chunks, scores):
            chunk.rerank_score = float(score)

        # Sort by rerank score descending
        ranked = sorted(chunks, key=lambda c: c.rerank_score or 0, reverse=True)

        logger.info(
            "reranker.done",
            input_count=len(chunks),
            output_count=min(len(ranked), top_k),
            top_score=ranked[0].rerank_score if ranked else None,
        )

        return ranked[:top_k]

    def is_available(self) -> bool:
        """Check if the reranker model is available."""
        return self.model is not None


# Singleton for optional preloading during startup
_global_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """Get the global reranker instance."""
    global _global_reranker
    if _global_reranker is None:
        _global_reranker = Reranker(lazy_load=True)
    return _global_reranker


async def preload_reranker() -> None:
    """Preload the reranker model (call during startup for faster first request)."""
    reranker = get_reranker()
    _ = reranker.model  # Trigger lazy load
    logger.info("reranker.preloaded", available=reranker.is_available())
