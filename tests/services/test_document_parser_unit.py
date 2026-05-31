"""tests/services/test_document_parser_unit.py

Unit tests for Phase 2 multi-modal document parsing (document_parser.py).

Each parser is exercised with a small in-memory document built with the same
library used to read it, so the tests run offline with no fixtures on disk.
Tests also cover the graceful-fallback paths (unknown type, corrupt bytes).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

# Ensure the orchestrator package is importable regardless of test-run ordering.
_SERVICES_ORCHESTRATOR = str(Path(__file__).resolve().parents[2] / "services" / "orchestrator")
if _SERVICES_ORCHESTRATOR not in sys.path:
    sys.path.insert(0, _SERVICES_ORCHESTRATOR)

from orchestrator.document_parser import (  # noqa: E402
    MAX_EXTRACTED_CHARS,
    parse_document,
)

# ---------------------------------------------------------------------------
# Sample-document builders
# ---------------------------------------------------------------------------

def _make_pdf(text: str) -> bytes:
    pypdf = pytest.importorskip("pypdf")
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas", reason="reportlab not installed")
    buf = io.BytesIO()
    c = reportlab.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    buf.seek(0)
    # sanity: the bytes are a valid PDF pypdf can open
    pypdf.PdfReader(io.BytesIO(buf.getvalue()))
    return buf.getvalue()


def _make_docx(paragraphs: list[str]) -> bytes:
    docx = pytest.importorskip("docx")
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pptx(slide_texts: list[str]) -> bytes:
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation()
    blank = prs.slide_layouts[6]
    for text in slide_texts:
        slide = prs.slides.add_slide(blank)
        box = slide.shapes.add_textbox(0, 0, prs.slide_width, prs.slide_height)
        box.text_frame.text = text
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Plain-text / Markdown
# ---------------------------------------------------------------------------

class TestTextParsing:
    def test_markdown_by_content_type(self):
        result = parse_document(b"# Title\n\nbody text", "text/markdown", "x.md")
        assert result is not None
        assert "Title" in result

    def test_plain_text_by_extension(self):
        result = parse_document(b"hello world", "application/octet-stream", "notes.txt")
        assert result == "hello world"

    def test_text_truncated_to_cap(self):
        big = b"a" * (MAX_EXTRACTED_CHARS + 100)
        result = parse_document(big, "text/plain", "big.txt")
        assert result is not None
        assert len(result) == MAX_EXTRACTED_CHARS

    def test_invalid_utf8_replaced_not_raised(self):
        result = parse_document(b"\xff\xfe bad bytes", "text/plain", "x.txt")
        assert result is not None  # decode errors are replaced, never raised


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

class TestPdfParsing:
    def test_extracts_text_by_content_type(self):
        pdf = _make_pdf("Mission requirements PDF content")
        result = parse_document(pdf, "application/pdf", "spec.pdf")
        assert result is not None
        assert "Mission requirements" in result

    def test_extracts_by_extension_when_type_generic(self):
        pdf = _make_pdf("Routed by extension")
        result = parse_document(pdf, "application/octet-stream", "spec.pdf")
        assert result is not None
        assert "Routed by extension" in result

    def test_corrupt_pdf_returns_none(self):
        result = parse_document(b"%PDF-1.4 not really a pdf", "application/pdf", "broken.pdf")
        assert result is None


# ---------------------------------------------------------------------------
# Word (.docx)
# ---------------------------------------------------------------------------

class TestDocxParsing:
    _DOCX_TYPE = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    def test_extracts_paragraphs(self):
        data = _make_docx(["First paragraph", "Second paragraph"])
        result = parse_document(data, self._DOCX_TYPE, "doc.docx")
        assert result is not None
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_extracts_by_extension(self):
        data = _make_docx(["Routed by extension"])
        result = parse_document(data, "application/octet-stream", "doc.docx")
        assert result is not None
        assert "Routed by extension" in result

    def test_corrupt_docx_returns_none(self):
        result = parse_document(b"not a zip", self._DOCX_TYPE, "broken.docx")
        assert result is None


# ---------------------------------------------------------------------------
# PowerPoint (.pptx)
# ---------------------------------------------------------------------------

class TestPptxParsing:
    _PPTX_TYPE = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

    def test_extracts_slide_text(self):
        data = _make_pptx(["Slide one bullet", "Slide two bullet"])
        result = parse_document(data, self._PPTX_TYPE, "deck.pptx")
        assert result is not None
        assert "Slide one bullet" in result
        assert "Slide two bullet" in result

    def test_extracts_by_extension(self):
        data = _make_pptx(["Routed by extension"])
        result = parse_document(data, "application/octet-stream", "deck.pptx")
        assert result is not None
        assert "Routed by extension" in result

    def test_corrupt_pptx_returns_none(self):
        result = parse_document(b"not a zip", self._PPTX_TYPE, "broken.pptx")
        assert result is None


# ---------------------------------------------------------------------------
# Routing / fallback
# ---------------------------------------------------------------------------

class TestRoutingAndFallback:
    def test_unknown_type_returns_none(self):
        result = parse_document(b"\x00\x01\x02", "image/png", "logo.png")
        assert result is None

    def test_empty_content_type_and_unknown_extension_returns_none(self):
        result = parse_document(b"data", "", "archive.zip")
        assert result is None

    def test_content_type_with_charset_param_is_handled(self):
        result = parse_document(b"plain body", "text/plain; charset=utf-8", "x.txt")
        assert result == "plain body"
