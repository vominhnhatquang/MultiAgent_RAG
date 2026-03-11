"""Enrich chunks with metadata: language detection, keyword extraction."""
import re

import structlog

from app.core.ingestion.chunker import TextChunk

logger = structlog.get_logger(__name__)

_VIET_CHARS = re.compile(r"[àáâãèéêìíòóôõùúýăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.IGNORECASE)


def _detect_language(text: str) -> str:
    """Simple heuristic: if Vietnamese diacritics found → 'vi', else 'en'."""
    sample = text[:500]
    return "vi" if _VIET_CHARS.search(sample) else "en"


def _extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """Extract simple high-frequency content words (no stopwords library needed)."""
    _STOP = {
        "the", "and", "is", "in", "at", "of", "a", "to", "for", "on", "that", "it",
        "với", "và", "của", "là", "trong", "có", "được", "cho", "các", "một", "này",
    }
    words = re.findall(r"\b\w{4,}\b", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOP:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:top_n]]


async def enrich(chunks: list[TextChunk]) -> list[TextChunk]:
    """Attach language + keywords to each chunk's metadata."""
    for chunk in chunks:
        lang = _detect_language(chunk.content)
        keywords = _extract_keywords(chunk.content)
        chunk.metadata.update({"language": lang, "keywords": keywords})
    logger.info("enricher.done", chunks=len(chunks))
    return chunks
