"""Unit tests for app.core.ingestion.enricher."""
import pytest

from app.core.ingestion.chunker import TextChunk
from app.core.ingestion.enricher import _detect_language, _extract_keywords, enrich


def _make_chunk(content: str, index: int = 0) -> TextChunk:
    return TextChunk(
        content=content,
        chunk_index=index,
        page_number=1,
        token_count=len(content.split()),
        char_count=len(content),
    )


def test_detect_language_vietnamese() -> None:
    text = "Chi phí đào tạo mô hình AI là bao nhiêu?"
    assert _detect_language(text) == "vi"


def test_detect_language_english() -> None:
    text = "The cost of training an AI model is significant."
    assert _detect_language(text) == "en"


def test_extract_keywords_returns_list() -> None:
    text = "machine learning training data model neural network deep learning"
    keywords = _extract_keywords(text, top_n=3)
    assert isinstance(keywords, list)
    assert len(keywords) <= 3


def test_extract_keywords_filters_short_words() -> None:
    text = "the and is in of a to for on machine learning training"
    keywords = _extract_keywords(text)
    # All keywords should be >= 4 chars
    for kw in keywords:
        assert len(kw) >= 4


@pytest.mark.asyncio
async def test_enrich_adds_language_metadata() -> None:
    chunks = [_make_chunk("Chi phí đào tạo mô hình AI là bao nhiêu?")]
    result = await enrich(chunks)
    assert "language" in result[0].metadata
    assert result[0].metadata["language"] == "vi"


@pytest.mark.asyncio
async def test_enrich_adds_keywords_metadata() -> None:
    chunks = [_make_chunk("machine learning training data model")]
    result = await enrich(chunks)
    assert "keywords" in result[0].metadata
    assert isinstance(result[0].metadata["keywords"], list)


@pytest.mark.asyncio
async def test_enrich_multiple_chunks() -> None:
    chunks = [
        _make_chunk("First chunk content about AI training", 0),
        _make_chunk("Second chunk about machine learning models", 1),
    ]
    result = await enrich(chunks)
    assert len(result) == 2
    for c in result:
        assert "language" in c.metadata
        assert "keywords" in c.metadata
