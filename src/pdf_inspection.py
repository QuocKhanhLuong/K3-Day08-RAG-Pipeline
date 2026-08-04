"""PDF text-layer inspection for legal source files.

Determines page count, character count, text-layer presence, and whether
OCR is required.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class PdfInspectionError(RuntimeError):
    """PDF inspection failed or file is invalid."""


@dataclass(frozen=True)
class PdfInspection:
    total_pages: int
    native_text_pages: int
    low_text_pages: int
    total_characters: int
    scanned_ratio: float
    pdf_type: str
    requires_ocr: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fitz_module():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise PdfInspectionError("PyMuPDF is required for PDF inspection. Install requirements.txt.") from exc
    return fitz


def inspect_pdf(
    pdf_path: Path | str,
    min_chars_per_page: int = 50,
    scanned_ratio_threshold: float = 0.30,
) -> PdfInspection:
    """Classify a PDF from text extracted on every page."""
    path = Path(pdf_path)
    if not path.is_file():
        raise PdfInspectionError(f"PDF does not exist: {path}")
    if not path.read_bytes().startswith(b"%PDF-"):
        raise PdfInspectionError(f"Not a valid PDF file: {path}")

    fitz = _fitz_module()
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise PdfInspectionError(f"Cannot open PDF {path}: {exc}") from exc

    total_pages = len(document)
    if total_pages == 0:
        document.close()
        return PdfInspection(
            total_pages=0,
            native_text_pages=0,
            low_text_pages=0,
            total_characters=0,
            scanned_ratio=0.0,
            pdf_type="empty",
            requires_ocr=False,
        )

    native_text_pages = 0
    low_text_pages = 0
    total_characters = 0
    pages_with_images = 0

    try:
        for page in document:
            text = page.get_text("text").strip()
            count = len(text)
            total_characters += count
            if count >= min_chars_per_page:
                native_text_pages += 1
            else:
                low_text_pages += 1
            if page.get_images(full=True):
                pages_with_images += 1
    finally:
        document.close()

    scanned_ratio = low_text_pages / total_pages
    if total_characters == 0 and pages_with_images == 0:
        pdf_type = "empty"
    elif native_text_pages == 0 and scanned_ratio >= scanned_ratio_threshold:
        pdf_type = "scanned"
    elif low_text_pages > 0 and native_text_pages > 0:
        pdf_type = "mixed"
    elif scanned_ratio >= scanned_ratio_threshold:
        pdf_type = "scanned"
    else:
        pdf_type = "born_digital"

    return PdfInspection(
        total_pages=total_pages,
        native_text_pages=native_text_pages,
        low_text_pages=low_text_pages,
        total_characters=total_characters,
        scanned_ratio=scanned_ratio,
        pdf_type=pdf_type,
        requires_ocr=pdf_type in {"scanned", "mixed"},
    )
