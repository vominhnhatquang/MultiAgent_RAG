"""Unit tests for app.core.ingestion.cleaner."""
import pytest

from app.core.ingestion.cleaner import clean, clean_text
from app.core.ingestion.extractor import ExtractedDocument, ExtractedPage


def test_clean_text_removes_control_chars() -> None:
    dirty = "Hello\x00\x07World"
    result = clean_text(dirty)
    assert "\x00" not in result
    assert "\x07" not in result
    assert "HelloWorld" in result


def test_clean_text_collapses_whitespace() -> None:
    text = "foo   bar\t\tbaz"
    result = clean_text(text)
    assert "  " not in result
    assert "foo bar baz" == result


def test_clean_text_collapses_newlines() -> None:
    text = "para1\n\n\n\n\npara2"
    result = clean_text(text)
    assert "\n\n\n" not in result
    assert "para1" in result
    assert "para2" in result


def test_clean_text_strips_lone_page_numbers() -> None:
    text = "Some content\n42\nMore content"
    result = clean_text(text)
    # lone page number line should be removed
    lines = [l.strip() for l in result.split("\n") if l.strip()]
    assert "42" not in lines


def test_clean_text_unicode_normalisation() -> None:
    # NFC: composed form
    text = "caf\u0065\u0301"  # café with combining acute
    result = clean_text(text)
    assert result == "caf\u00e9"  # NFC: é


@pytest.mark.asyncio
async def test_clean_removes_empty_pages() -> None:
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text="Real content here"),
        ExtractedPage(page_number=2, text="   \n  "),  # whitespace only
    ])
    result = await clean(doc)
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1


@pytest.mark.asyncio
async def test_clean_preserves_valid_pages() -> None:
    doc = ExtractedDocument(pages=[
        ExtractedPage(page_number=1, text="Page one\ncontent"),
        ExtractedPage(page_number=2, text="Page two\ncontent"),
    ])
    result = await clean(doc)
    assert len(result.pages) == 2
