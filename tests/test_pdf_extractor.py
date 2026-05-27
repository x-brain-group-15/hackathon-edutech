import io

from pypdf import PdfWriter

from src.pdf_extractor import extract_pdf


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extract_pdf_returns_page_metadata_for_text_poor_pdf():
    result = extract_pdf(_blank_pdf())

    assert result.metadata["page_count"] == 1
    assert result.metadata["strategy"] == "hybrid_pdf_text_layer_first_then_page_level_ocr"
    assert result.metadata["page_details"][0]["extraction_method"] == "pdf_text_layer_low_confidence"
    assert result.metadata["chars_extracted"] == 0

