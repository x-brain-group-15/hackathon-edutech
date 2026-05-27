"""PDF extraction helpers for uploaded study material.

The extractor intentionally starts with the cheapest path: read the PDF text
layer with pypdf. Pages that look image-only or text-poor are flagged for OCR
instead of running OCR for every page.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any


MIN_TEXT_CHARS_FOR_TEXT_LAYER = 40


@dataclass
class PageExtraction:
    page_number: int
    text: str
    extraction_method: str
    content_types: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    image_count: int = 0
    table_like_line_count: int = 0

    def as_metadata(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "extraction_method": self.extraction_method,
            "content_types": self.content_types,
            "warnings": self.warnings,
            "chars": len(self.text),
            "image_count": self.image_count,
            "table_like_line_count": self.table_like_line_count,
        }


@dataclass
class DocumentExtraction:
    text: str
    pages: list[PageExtraction]
    metadata: dict[str, Any]


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _image_count(page: Any) -> int:
    try:
        return len(page.images)
    except Exception:
        return 0


def _table_like_line_count(text: str) -> int:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    count = 0
    for line in lines:
        has_many_columns = len(re.split(r"\s{2,}|\t|\|", line)) >= 3
        has_number = bool(re.search(r"\d", line))
        if has_many_columns and has_number:
            count += 1
    return count


def _content_types(text: str, images: int, table_lines: int) -> list[str]:
    types = []
    if text.strip():
        types.append("text")
    if table_lines >= 2:
        types.append("table_like")
    if images:
        types.append("image_or_chart")
    if not types:
        types.append("unknown")
    return types


def extract_pdf(data: bytes) -> DocumentExtraction:
    """Extract text and page-level metadata from a PDF.

    This function does not run OCR directly. Instead, it marks pages that need
    OCR/Textract/Vision so the production pipeline can spend money only on those
    pages.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF extraction") from exc

    reader = PdfReader(io.BytesIO(data))
    pages: list[PageExtraction] = []
    body_parts: list[str] = []

    for idx, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        text = _clean_text(raw_text)
        images = _image_count(page)
        table_lines = _table_like_line_count(text)
        warnings: list[str] = []

        if len(text) >= MIN_TEXT_CHARS_FOR_TEXT_LAYER:
            method = "pdf_text_layer"
        elif images:
            method = "needs_ocr_or_textract"
            warnings.append("Page has little extractable text and contains images; run OCR/Textract only for this page.")
        else:
            method = "pdf_text_layer_low_confidence"
            warnings.append("Page has very little extractable text; verify manually or run OCR if this page is important.")

        page_result = PageExtraction(
            page_number=idx,
            text=text,
            extraction_method=method,
            content_types=_content_types(text, images, table_lines),
            warnings=warnings,
            image_count=images,
            table_like_line_count=table_lines,
        )
        pages.append(page_result)

        if text:
            body_parts.append(f"[page {idx}]\n{text}")

    metadata = {
        "page_count": len(pages),
        "chars_extracted": sum(len(page.text) for page in pages),
        "pages_requiring_ocr": [page.page_number for page in pages if page.extraction_method == "needs_ocr_or_textract"],
        "pages_with_images_or_charts": [page.page_number for page in pages if page.image_count > 0],
        "pages_with_table_like_content": [page.page_number for page in pages if page.table_like_line_count >= 2],
        "strategy": "hybrid_pdf_text_layer_first_then_page_level_ocr",
        "page_details": [page.as_metadata() for page in pages],
    }
    return DocumentExtraction(text="\n\n".join(body_parts), pages=pages, metadata=metadata)

