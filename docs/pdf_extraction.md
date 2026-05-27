# PDF Content Extraction

## Scope

This module handles the first AI pipeline step: extracting useful content from uploaded PDF slides before the content is passed to chunking and the Knowledge Base.

Supported PDF content types:

- Text layer content: titles, paragraphs, bullet points.
- Table-like text: rows/columns detected from spacing and numbers.
- Image/chart-heavy pages: detected and flagged for OCR, Textract, or Vision processing.
- Scan/image-only pages: detected as text-poor pages so the system does not silently ingest empty content.

## Chosen Strategy: Hybrid Extraction

The system uses a text-layer-first strategy:

1. Store the original PDF.
2. Read each page with `pypdf`.
3. If the page has enough extractable text, ingest that text directly.
4. If the page has little text but contains images, mark it as `needs_ocr_or_textract`.
5. If table-like lines are found, attach metadata so downstream chunking can treat them carefully.
6. Return normalized text plus page-level metadata.

This keeps the default path cheap because normal text PDFs do not need OCR. More expensive OCR/Textract/Vision processing is reserved only for pages that need it.

## Output Shape

Upload responses now include extraction metadata:

```json
{
  "doc_id": "doc-id",
  "filename": "lecture.pdf",
  "chars_extracted": 1200,
  "extraction": {
    "page_count": 6,
    "chars_extracted": 1200,
    "pages_requiring_ocr": [4],
    "pages_with_images_or_charts": [3, 4],
    "pages_with_table_like_content": [2],
    "strategy": "hybrid_pdf_text_layer_first_then_page_level_ocr",
    "page_details": [
      {
        "page_number": 1,
        "extraction_method": "pdf_text_layer",
        "content_types": ["text"],
        "warnings": [],
        "chars": 350,
        "image_count": 0,
        "table_like_line_count": 0
      }
    ]
  }
}
```

## Alternatives Not Chosen

### OCR every page

This handles scan PDFs, but it is not cost optimal. A slide deck with a valid text layer would still be sent through OCR even though `pypdf` can extract the text locally for no additional AWS cost.

### Text parser only

This is the cheapest option, but it fails silently on scan/image-only pages and misses important visual content in slides. In the current implementation, those weak pages are marked so the production pipeline can route only those pages to OCR/Textract/Vision.

## Files

- `src/pdf_extractor.py`: page-level PDF extraction and metadata.
- `src/handlers.py`: upload flow integration.
- `tests/test_pdf_extractor.py`: verifies metadata for a text-poor PDF.

