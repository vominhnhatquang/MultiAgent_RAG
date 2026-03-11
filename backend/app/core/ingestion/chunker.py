"""Split cleaned document text into overlapping token-bounded chunks."""
from dataclasses import dataclass, field

import structlog

from app.config import settings
from app.core.ingestion.extractor import ExtractedDocument

logger = structlog.get_logger(__name__)


@dataclass
class TextChunk:
    content: str
    chunk_index: int
    page_number: int | None
    token_count: int
    char_count: int
    metadata: dict = field(default_factory=dict)


def _count_tokens(text: str) -> int:
    """Approximate token count using tiktoken cl100k_base encoding."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        # Fallback: ~4 chars per token
        return max(1, len(text) // 4)


def _split_into_sentences(text: str) -> list[str]:
    """Naive sentence splitter on Vietnamese/English text."""
    import re
    parts = re.split(r"(?<=[.!?।\n])\s+", text)
    return [p.strip() for p in parts if p.strip()]


async def chunk(doc: ExtractedDocument) -> list[TextChunk]:
    """Produce overlapping chunks from all document pages."""
    chunk_size = settings.chunk_size
    overlap = settings.chunk_overlap
    chunks: list[TextChunk] = []
    chunk_index = 0

    for page in doc.pages:
        sentences = _split_into_sentences(page.text)
        buffer: list[str] = []
        buffer_tokens = 0

        for sentence in sentences:
            s_tokens = _count_tokens(sentence)

            # If single sentence exceeds chunk_size, force-split it
            if s_tokens > chunk_size:
                words = sentence.split()
                sub_buf: list[str] = []
                sub_tok = 0
                for word in words:
                    w_tok = _count_tokens(word)
                    if sub_tok + w_tok > chunk_size and sub_buf:
                        content = " ".join(sub_buf)
                        chunks.append(_make_chunk(content, chunk_index, page.page_number))
                        chunk_index += 1
                        # overlap: keep last few words
                        keep = _overlap_words(sub_buf, overlap)
                        sub_buf = keep
                        sub_tok = _count_tokens(" ".join(sub_buf))
                    sub_buf.append(word)
                    sub_tok += w_tok
                if sub_buf:
                    buffer = sub_buf
                    buffer_tokens = sub_tok
                continue

            if buffer_tokens + s_tokens > chunk_size and buffer:
                content = " ".join(buffer)
                chunks.append(_make_chunk(content, chunk_index, page.page_number))
                chunk_index += 1
                # Build overlap from end of buffer
                overlap_buf = _overlap_sentences(buffer, overlap)
                buffer = overlap_buf
                buffer_tokens = _count_tokens(" ".join(buffer))

            buffer.append(sentence)
            buffer_tokens += s_tokens

        if buffer:
            content = " ".join(buffer)
            chunks.append(_make_chunk(content, chunk_index, page.page_number))
            chunk_index += 1

    logger.info("chunker.done", total_chunks=len(chunks))
    return chunks


def _make_chunk(content: str, index: int, page: int | None) -> TextChunk:
    return TextChunk(
        content=content,
        chunk_index=index,
        page_number=page,
        token_count=_count_tokens(content),
        char_count=len(content),
    )


def _overlap_sentences(sentences: list[str], overlap_tokens: int) -> list[str]:
    """Return tail sentences that fit within overlap_tokens."""
    result: list[str] = []
    total = 0
    for s in reversed(sentences):
        t = _count_tokens(s)
        if total + t > overlap_tokens:
            break
        result.insert(0, s)
        total += t
    return result


def _overlap_words(words: list[str], overlap_tokens: int) -> list[str]:
    result: list[str] = []
    total = 0
    for w in reversed(words):
        t = _count_tokens(w)
        if total + t > overlap_tokens:
            break
        result.insert(0, w)
        total += t
    return result
