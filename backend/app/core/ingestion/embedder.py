"""Generate embeddings via Ollama nomic-embed-text (768-dim)."""
import structlog
import httpx

from app.config import settings
from app.core.ingestion.chunker import TextChunk
from app.exceptions import LLMUnavailableError

logger = structlog.get_logger(__name__)

EMBED_BATCH_SIZE = 16  # Ollama handles batches fine for small chunks


async def embed(chunks: list[TextChunk]) -> list[tuple[TextChunk, list[float]]]:
    """Return list of (chunk, embedding_vector) pairs."""
    results: list[tuple[TextChunk, list[float]]] = []
    texts = [c.content for c in chunks]

    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch_texts = texts[i : i + EMBED_BATCH_SIZE]
            batch_chunks = chunks[i : i + EMBED_BATCH_SIZE]
            vectors = await _embed_batch(client, batch_texts)
            results.extend(zip(batch_chunks, vectors))

    logger.info("embedder.done", total=len(results))
    return results


async def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
        vectors = await _embed_batch(client, [text])
    return vectors[0]


async def _embed_batch(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    try:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.ollama_embed_model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"]
    except httpx.HTTPStatusError as exc:
        raise LLMUnavailableError(f"Ollama embed failed: {exc}") from exc
    except httpx.RequestError as exc:
        raise LLMUnavailableError(f"Cannot reach Ollama: {exc}") from exc
