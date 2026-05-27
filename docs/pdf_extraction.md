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
3. Extract embedded images/charts into storage under `{user_id}/{doc_id}/extracted-assets/`.
4. If the page has enough extractable text, ingest that text directly.
5. Add image references plus nearby slide text to the retrieval text so the Knowledge Base can cite visual assets.
6. If the page has little text but contains images, mark it as `needs_ocr_or_textract`.
7. If table-like lines are found, attach metadata so downstream chunking can treat them carefully.
8. Return normalized text plus page-level metadata.

This keeps the default path cheap because normal text PDFs do not need OCR. Embedded images are saved through the app storage adapter, so local runs write to disk and production runs write to S3. More expensive OCR/Textract/Vision processing is reserved only for pages that need it.

## Image Filtering

PowerPoint-exported PDFs often split one slide into many small image objects, such as logos, icons, masks, and repeated backgrounds. To avoid storing noisy assets in the Knowledge Base, the extractor filters images before saving them:

- Skip images smaller than `8KB`.
- Deduplicate images by SHA-256 hash across the whole PDF.
- Keep the raw image count in metadata so we still know whether a page was visual-heavy.
- Store only filtered image assets in the `images` list.

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
            "location": "s3://studybot-uploads/user-id/doc-id/extracted-assets/page_001_image_001.png"
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

## Production Storage Flow

The upload handler stores both the original PDF and extracted visual assets through the same storage adapter:

```text
Original PDF:
{user_id}/{doc_id}/{filename}

Filtered image/chart assets:
{user_id}/{doc_id}/extracted-assets/page_001_image_001.png
```

With `STORAGE_BACKEND=local`, locations are returned as `file://...`.
With `STORAGE_BACKEND=s3`, locations are returned as `s3://bucket/...`.

The Knowledge Base should ingest text plus metadata/S3 URIs, not raw image bytes. OCR/Textract can then be run only for pages listed in `pages_requiring_ocr`.

## Test Evidence

Test file: `tests/W6_Operations_Hardening_&_Cost-Aware_Cloud_-_Nhóm_15.pptx.pdf`

Hybrid extraction result:

```text
page_count: 20
chars_extracted: 5671
images_extracted: 27
pages_requiring_ocr: [20]
```

Image filtering comparison:

```text
Without filtering: 83 image objects
After size filtering: 43 image assets
After size filtering + document-level deduplication: 27 image assets
```

Interpretation:

- Pages 1-19 have usable text layers, so they can be ingested without OCR.
- Page 20 has very little text but contains images, so it is routed to OCR/Textract.
- The image filter reduces noisy visual assets by about 67% while keeping useful slide images/charts.

## Files

- `src/pdf_extractor.py`: page-level PDF extraction and metadata.
- `src/handlers.py`: upload flow integration.
- `tests/test_pdf_extractor.py`: verifies metadata for a text-poor PDF.
