# PDF Content Extraction

## Scope

This module handles the first AI pipeline step: extracting useful content from uploaded PDF slides before the content is passed to chunking and the Knowledge Base.

Supported PDF content types:

- Text layer content: titles, paragraphs, bullet points.
- Table-like text: rows/columns detected from spacing and numbers.
- Embedded images/charts: extracted as image assets and referenced in metadata.
- Image/chart-heavy pages: flagged for OCR, Textract, or Vision processing when text extraction is weak.
- Scan/image-only pages: detected as text-poor pages so the system does not silently ingest empty content.

## Chosen Strategy: Hybrid Extraction

The system uses a text-layer-first plus image-asset strategy:

1. Store the original PDF.
2. Read each page with `pypdf`.
3. Extract embedded images/charts into an asset folder.
4. If the page has enough extractable text, ingest that text directly.
5. Add image references plus nearby slide text to the retrieval text so the Knowledge Base can cite visual assets.
6. If the page has little text but contains images, mark it as `needs_ocr_or_textract`.
7. If table-like lines are found, attach metadata so downstream chunking can treat them carefully.
8. Return normalized text plus page-level metadata.

This keeps the default path cheap because normal text PDFs do not need OCR. Embedded images are extracted locally, while more expensive OCR/Textract/Vision processing is reserved only for pages that need it.

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
    "images_extracted": 4,
    "pages_requiring_ocr": [4],
    "pages_with_images_or_charts": [3, 4],
    "pages_with_table_like_content": [2],
    "strategy": "hybrid_text_layer_plus_image_assets_then_page_level_ocr",
    "page_details": [
      {
        "page_number": 1,
        "extraction_method": "pdf_text_layer",
        "content_types": ["text"],
        "warnings": [],
        "chars": 350,
        "image_count": 1,
        "images": [
          {
            "image_index": 1,
            "filename": "page_001_image_001.png",
            "content_type": "image/png",
            "bytes_size": 10240,
            "location": "_data/uploads/extracted_assets/doc-id/page_001_image_001.png"
          }
        ],
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

This is the cheapest option, but it fails silently on scan/image-only pages and misses important visual content in slides. In the current implementation, image assets are extracted and weak pages are marked so the production pipeline can route only those pages to OCR/Textract/Vision.

## Files

- `src/pdf_extractor.py`: page-level PDF extraction and metadata.
- `src/handlers.py`: upload flow integration.
- `tests/test_pdf_extractor.py`: verifies metadata for a text-poor PDF.
