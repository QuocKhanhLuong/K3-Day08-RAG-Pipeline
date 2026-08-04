"""PDF text-layer inspection and safe OCR routing for legal source files.

Original source PDFs are never overwritten.  OCR output is local-only under
``data/processed/ocr`` and is intentionally excluded from Git.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


# These patterns describe legal references that should remain recognisable in
# extracted text. They are recorded for QA; they are never used to rewrite OCR.
LEGAL_REFERENCE_PATTERNS: tuple[str, ...] = (
    r"\bĐiều\s+\d+[A-Za-z]?\b",
    r"\bKhoản\s+\d+\b",
    r"\bĐiểm\s+[a-zđ]\b",
    r"\b\d+(?:[.,]\d+)?\s*%",
    r"\b\d+/\d{4}/[A-ZĐ\-]+\b",
)


class PdfOcrError(RuntimeError):
    """OCR inspection or processing did not complete safely."""


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


@dataclass(frozen=True)
class OcrResult:
    input_path: str
    output_path: str
    command: tuple[str, ...]
    before: PdfInspection
    after: PdfInspection
    quality_warnings: tuple[str, ...]
    manual_review_required: bool

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["command"] = list(self.command)
        result["before"] = self.before.as_dict()
        result["after"] = self.after.as_dict()
        result["quality_warnings"] = list(self.quality_warnings)
        return result


def _fitz_module():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise PdfOcrError("PyMuPDF is required for PDF inspection. Install requirements.txt.") from exc
    return fitz


def inspect_pdf(
    pdf_path: Path,
    min_chars_per_page: int = 50,
    scanned_ratio_threshold: float = 0.30,
) -> PdfInspection:
    """Classify a PDF from text extracted on every page, not global text only."""
    if min_chars_per_page < 1:
        raise ValueError("min_chars_per_page must be positive")
    if not 0 < scanned_ratio_threshold <= 1:
        raise ValueError("scanned_ratio_threshold must be in (0, 1]")
    path = Path(pdf_path)
    if not path.is_file():
        raise PdfOcrError(f"PDF does not exist: {path}")
    if not path.read_bytes().startswith(b"%PDF-"):
        raise PdfOcrError(f"Not a PDF according to magic bytes: {path}")

    fitz = _fitz_module()
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise PdfOcrError(f"Cannot open PDF {path}: {exc}") from exc

    total_pages = len(document)
    if total_pages == 0:
        document.close()
        return PdfInspection(0, 0, 0, 0, 0.0, "empty", False)

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


def extract_native_text(pdf_path: Path) -> str:
    """Fallback text extraction for a born-digital PDF when MarkItDown is short."""
    fitz = _fitz_module()
    document = None
    try:
        document = fitz.open(pdf_path)
        return "\n\n".join(page.get_text("text").strip() for page in document).strip()
    except Exception as exc:
        raise PdfOcrError(f"PyMuPDF text extraction failed for {pdf_path}: {exc}") from exc
    finally:
        if document is not None:
            document.close()


def ensure_ocr_dependencies() -> None:
    """Verify executable OCR dependencies and Vietnamese language data."""
    missing = [tool for tool in ("ocrmypdf", "tesseract") if shutil.which(tool) is None]
    if shutil.which("gs") is None and shutil.which("ghostscript") is None:
        missing.append("ghostscript")
    if missing:
        raise PdfOcrError("Missing OCR system dependencies: " + ", ".join(missing))
    try:
        output = subprocess.run(
            ["tesseract", "--list-langs"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise PdfOcrError(f"Cannot inspect Tesseract languages: {exc}") from exc
    languages = {line.strip() for line in output.splitlines() if line.strip() and "List of available" not in line}
    if "vie" not in languages:
        raise PdfOcrError("Tesseract Vietnamese language pack 'vie' is not installed")


def find_ocr_warnings(text: str) -> list[str]:
    """Report suspicious OCR strings; never auto-correct legal content."""
    checks = {
        "article_number_letter": r"\bĐiều\s+\d+[A-Za-z]\b",
        "clause_roman_confusion": r"\bKhoản\s+[Il]\b",
        "percentage_letter_confusion": r"\b\d+[SOIl]\s*%",
        "day_number_letter_confusion": r"\b\d+[SOIl]\s+ngày\b",
        "year_letter_confusion": r"\b20[Il]\d\b",
        "replacement_character": r"�",
    }
    warnings: list[str] = []
    for label, pattern in checks.items():
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            preview = ", ".join(str(match) for match in matches[:3])
            warnings.append(f"{label}: {preview}")
    return warnings


def ocr_pdf(
    input_pdf: Path,
    output_pdf: Path,
    *,
    timeout_seconds: int = 15 * 60,
    jobs: int = 2,
) -> OcrResult:
    """Create an OCR derivative using safe ``--skip-text`` defaults.

    The source is never modified.  An error leaves the source intact and raises
    :class:`PdfOcrError`; callers decide how to record the failed conversion.
    """
    input_pdf = Path(input_pdf)
    output_pdf = Path(output_pdf)
    if input_pdf.resolve() == output_pdf.resolve():
        raise PdfOcrError("OCR output path must differ from the source PDF")
    if jobs < 1:
        raise ValueError("jobs must be at least 1")
    before = inspect_pdf(input_pdf)
    if not before.requires_ocr:
        raise PdfOcrError(f"OCR not required for {input_pdf.name}: {before.pdf_type}")
    ensure_ocr_dependencies()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    command = (
        "ocrmypdf",
        "--language",
        "vie+eng",
        "--skip-text",
        "--rotate-pages",
        "--deskew",
        "--output-type",
        "pdf",
        "--jobs",
        str(jobs),
        str(input_pdf),
        str(output_pdf),
    )
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PdfOcrError(f"OCR command failed for {input_pdf.name}: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "unknown OCR error").strip()
        raise PdfOcrError(f"OCR failed for {input_pdf.name}: {message[:500]}")
    if not output_pdf.is_file() or output_pdf.stat().st_size <= 1024:
        raise PdfOcrError(f"OCR output is missing or too small: {output_pdf}")
    after = inspect_pdf(output_pdf)
    if after.native_text_pages <= before.native_text_pages and after.low_text_pages >= before.low_text_pages:
        raise PdfOcrError("OCR did not increase pages with usable text")
    warnings = tuple(find_ocr_warnings(extract_native_text(output_pdf)))
    return OcrResult(
        input_path=str(input_pdf),
        output_path=str(output_pdf),
        command=command,
        before=before,
        after=after,
        quality_warnings=warnings,
        manual_review_required=True,
    )
