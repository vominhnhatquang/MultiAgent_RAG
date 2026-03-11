"""Unit tests for app.core.ingestion.chunker."""
import pytest

from app.core.ingestion.chunker import TextChunk, _count_tokens, chunk
from app.core.ingestion.extractor import ExtractedDocument, ExtractedPage


def test_count_tokens_non_empty() -> None:
    count = _count_tokens("Hello world, this is a test sentence.")
    assert count > 0


def test_count_tokens_empty() -> None:
    count = _count_tokens("")
    assert count >= 1  # fallback returns at least 1


def test_count_tokens_proportional() -> None:
    short = _count_tokens("hello")
    long = _count_tokens("hello " * 100)
    assert long > short


@pytest.mark.asyncio
async def test_chunk_basic() -> None:
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text="This is a sentence. And another one. And a third.")
    ])
    chunks = await chunk(doc)
    assert len(chunks) >= 1
    assert all(isinstance(c, TextChunk) for c in chunks)


@pytest.mark.asyncio
async def test_chunk_indices_sequential() -> None:
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text=". ".join([f"Sentence {i}" for i in range(200)]))
    ])
    chunks = await chunk(doc)
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


@pytest.mark.asyncio
async def test_chunk_page_number_preserved() -> None:
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=5, text="Content on page five. More content here.")
    ])
    chunks = await chunk(doc)
    for c in chunks:
        assert c.page_number == 5


@pytest.mark.asyncio
async def test_chunk_char_count_matches() -> None:
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text="Short content.")
    ])
    chunks = await chunk(doc)
    for c in chunks:
        assert c.char_count == len(c.content)


@pytest.mark.asyncio
async def test_chunk_respects_size_limit() -> None:
    from app.config import settings
    long_text = " ".join(["word"] * 2000)
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text=long_text)
    ])
    chunks = await chunk(doc)
    for c in chunks:
        # Each chunk should be reasonably close to chunk_size (allow 2x for edge cases)
        assert c.token_count <= settings.chunk_size * 2


@pytest.mark.asyncio
async def test_chunk_empty_page_produces_nothing() -> None:
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text="")
    ])
    chunks = await chunk(doc)
    assert len(chunks) == 0
