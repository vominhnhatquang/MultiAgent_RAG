"""Clean and normalise raw text extracted from documents."""
import re
import unicodedata

import structlog

from app.core.ingestion.extractor import ExtractedDocument, ExtractedPage

logger = structlog.get_logger(__name__)

# Regex patterns
_MULTI_NEWLINE = re.compile(r"\n{3,}")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PAGE_HEADER_FOOTER = re.compile(r"^\s*\d+\s*$", re.MULTILINE)  # lone page numbers


def clean_text(text: str) -> str:
    """Apply normalisation pipeline to a single string."""
    # Unicode NFC normalisation
    text = unicodedata.normalize("NFC", text)
    # Remove control characters
    text = _CONTROL_CHARS.sub("", text)
    # Remove lone page-number lines
    text = _PAGE_HEADER_FOOTER.sub("", text)
    # Collapse excessive whitespace
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


async def clean(doc: ExtractedDocument) -> ExtractedDocument:
    """Clean all pages in the extracted document (in-place replacement)."""
    cleaned_pages: list[ExtractedPage] = []
    for page in doc.pages:
        cleaned = clean_text(page.text)
        if cleaned:
            cleaned_pages.append(ExtractedPage(page_number=page.page_number, text=cleaned))
    doc.pages = cleaned_pages
    logger.info("cleaner.done", pages_kept=len(cleaned_pages))
    return doc
