"""Query transformation with HyDE and multi-query expansion."""
import asyncio
from dataclasses import dataclass, field

import httpx
import structlog

from app.config import settings
from app.exceptions import LLMUnavailableError

logger = structlog.get_logger(__name__)


@dataclass
class TransformedQuery:
    """Result of query transformation."""

    original: str
    vector: list[float]
    alt_queries: list[str] = field(default_factory=list)
    hyde_answer: str | None = None


class QueryTransformer:
    """
    Transform queries using HyDE and multi-query expansion.

    HyDE (Hypothetical Document Embedding):
        1. Generate a hypothetical answer using LLM
        2. Embed both original query and hypothetical answer
        3. Combine: final_vec = 0.7 * query_vec + 0.3 * hyde_vec

    Multi-Query:
        Generate 2-3 alternative phrasings of the query for BM25 expansion.
    """

    HYDE_WEIGHT_QUERY = 0.7
    HYDE_WEIGHT_HYDE = 0.3

    def __init__(self, embedder_func) -> None:
        """
        Args:
            embedder_func: Async function that takes str and returns list[float]
        """
        self.embedder = embedder_func

    async def transform(
        self,
        query: str,
        use_hyde: bool = True,
        use_multi_query: bool = True,
    ) -> TransformedQuery:
        """
        Transform query with HyDE and multi-query.

        Args:
            query: Original user query
            use_hyde: Whether to use HyDE expansion
            use_multi_query: Whether to generate alternative queries

        Returns:
            TransformedQuery with combined vector and alternatives
        """
        tasks = []

        # HyDE task
        async def _noop_hyde() -> str | None:
            return None

        async def _noop_multi() -> list[str]:
            return []

        if use_hyde:
            tasks.append(self._generate_hyde(query))
        else:
            tasks.append(_noop_hyde())

        # Multi-query task
        if use_multi_query:
            tasks.append(self._generate_multi_query(query))
        else:
            tasks.append(_noop_multi())

        # Run in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        hyde_answer = results[0] if not isinstance(results[0], Exception) else None
        alt_queries = results[1] if not isinstance(results[1], Exception) else []

        if isinstance(results[0], Exception):
            logger.warning("hyde.failed", error=str(results[0]))
        if isinstance(results[1], Exception):
            logger.warning("multi_query.failed", error=str(results[1]))

        # Embed original query
        query_vec = await self.embedder(query)

        # Combine with HyDE if available
        if hyde_answer and use_hyde:
            hyde_vec = await self.embedder(hyde_answer)
            final_vec = self._weighted_merge(query_vec, hyde_vec)
        else:
            final_vec = query_vec

        return TransformedQuery(
            original=query,
            vector=final_vec,
            alt_queries=alt_queries if isinstance(alt_queries, list) else [],
            hyde_answer=hyde_answer,
        )

    def _weighted_merge(
        self,
        query_vec: list[float],
        hyde_vec: list[float],
    ) -> list[float]:
        """Merge query and HyDE vectors with weights."""
        return [
            self.HYDE_WEIGHT_QUERY * q + self.HYDE_WEIGHT_HYDE * h
            for q, h in zip(query_vec, hyde_vec)
        ]

    async def _generate_hyde(self, query: str) -> str:
        """Generate hypothetical answer using Ollama."""
        prompt = f"""Dựa trên câu hỏi sau, viết một đoạn văn ngắn (~100 từ) 
mô tả câu trả lời giả định có thể có trong tài liệu. 
Chỉ viết nội dung, không giải thích.

Câu hỏi: {query}
Đoạn văn giả định:"""

        response = await self._ollama_generate(prompt)
        # Cap length to avoid overly long responses
        return response[:500] if response else ""

    async def _generate_multi_query(self, query: str) -> list[str]:
        """Generate alternative query phrasings."""
        prompt = f"""Viết 3 cách diễn đạt khác nhau cho câu hỏi sau.
Mỗi cách 1 dòng, không đánh số, không giải thích.

Câu hỏi: {query}"""

        response = await self._ollama_generate(prompt)
        if not response:
            return []

        lines = [line.strip() for line in response.strip().split("\n") if line.strip()]
        # Filter out lines that are too similar to original
        filtered = [
            line for line in lines
            if line.lower() != query.lower() and len(line) > 3
        ]
        return filtered[:3]  # max 3 variants

    async def _ollama_generate(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 200,
    ) -> str:
        """Call Ollama generate API (non-streaming)."""
        model = model or settings.ollama_chat_model

        try:
            async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.3,
                        },
                    },
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(f"Ollama generate failed: {exc}") from exc
        except httpx.RequestError as exc:
            raise LLMUnavailableError(f"Cannot reach Ollama: {exc}") from exc
