"""PDF extraction helpers for uploaded study material.

The extractor intentionally starts with the cheapest path: read the PDF text
layer with pypdf. Pages that look image-only or text-poor are flagged for OCR
instead of running OCR for every page.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MIN_TEXT_CHARS_FOR_TEXT_LAYER = 40
MAX_IMAGE_CONTEXT_CHARS = 500


@dataclass
class ImageExtraction:
    image_index: int
    filename: str
    content_type: str
    bytes_size: int
    location: str | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {
            "image_index": self.image_index,
            "filename": self.filename,
            "content_type": self.content_type,
            "bytes_size": self.bytes_size,
            "location": self.location,
        }


@dataclass
class PageExtraction:
    page_number: int
    text: str
    extraction_method: str
    content_types: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    image_count: int = 0
    images: list[ImageExtraction] = field(default_factory=list)
    table_like_line_count: int = 0

    def as_metadata(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "extraction_method": self.extraction_method,
            "content_types": self.content_types,
            "warnings": self.warnings,
            "chars": len(self.text),
            "image_count": self.image_count,
            "images": [image.as_metadata() for image in self.images],
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


def _safe_image_name(raw_name: str | None, page_number: int, image_index: int) -> str:
    raw_name = raw_name or f"image_{image_index}.bin"
    suffix = Path(raw_name).suffix or ".bin"
    suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix) or ".bin"
    return f"page_{page_number:03d}_image_{image_index:03d}{suffix.lower()}"


def _content_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".jp2": "image/jp2",
    }.get(suffix, "application/octet-stream")


def _extract_images(page: Any, page_number: int, output_dir: Path | None = None) -> list[ImageExtraction]:
    images: list[ImageExtraction] = []
    try:
        page_images = list(page.images)
    except Exception:
        return images

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    for image_index, image in enumerate(page_images, start=1):
        filename = _safe_image_name(getattr(image, "name", None), page_number, image_index)
        data = getattr(image, "data", b"") or b""
        location = None
        if output_dir and data:
            path = output_dir / filename
            path.write_bytes(data)
            location = str(path.resolve())
        images.append(
            ImageExtraction(
                image_index=image_index,
                filename=filename,
                content_type=_content_type_for_filename(filename),
                bytes_size=len(data),
                location=location,
            )
        )
    return images


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


def _visual_context(page_number: int, text: str, images: list[ImageExtraction]) -> str:
    if not images:
        return ""
    refs = ", ".join(image.location or image.filename for image in images)
    context = " ".join(text.split())[:MAX_IMAGE_CONTEXT_CHARS] or "No reliable text layer was extracted from this page."
    return (
        f"[page {page_number} visual_assets]\n"
        f"Images/charts extracted: {refs}\n"
        f"Surrounding slide text for retrieval: {context}"
    )


def extract_pdf(data: bytes, image_output_dir: str | Path | None = None) -> DocumentExtraction:
    """Extract text and page-level metadata from a PDF.

    This function saves embedded images when image_output_dir is provided. It
    does not run OCR directly; instead it marks pages that need OCR/Textract or
    Vision so the production pipeline spends money only on those pages.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF extraction") from exc

    reader = PdfReader(io.BytesIO(data))
    image_dir = Path(image_output_dir) if image_output_dir else None
    pages: list[PageExtraction] = []
    body_parts: list[str] = []

    for idx, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        text = _clean_text(raw_text)
        extracted_images = _extract_images(page, idx, image_dir)
        images = len(extracted_images) if extracted_images else _image_count(page)
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
            images=extracted_images,
            table_like_line_count=table_lines,
        )
        pages.append(page_result)

        if text:
            body_parts.append(f"[page {idx}]\n{text}")
        visual_context = _visual_context(idx, text, extracted_images)
        if visual_context:
            body_parts.append(visual_context)

    metadata = {
        "page_count": len(pages),
        "chars_extracted": sum(len(page.text) for page in pages),
        "images_extracted": sum(len(page.images) for page in pages),
        "pages_requiring_ocr": [page.page_number for page in pages if page.extraction_method == "needs_ocr_or_textract"],
        "pages_with_images_or_charts": [page.page_number for page in pages if page.image_count > 0],
        "pages_with_table_like_content": [page.page_number for page in pages if page.table_like_line_count >= 2],
        "strategy": "hybrid_text_layer_plus_image_assets_then_page_level_ocr",
        "page_details": [page.as_metadata() for page in pages],
    }
    return DocumentExtraction(text="\n\n".join(body_parts), pages=pages, metadata=metadata)
