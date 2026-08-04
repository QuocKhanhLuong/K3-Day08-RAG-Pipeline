"""Local PaddleOCR 3.x extraction for scanned Vietnamese legal PDFs.

This is a batch-oriented helper, not an OCR service.  The PaddleOCR engine is
created once, all cache/model material is local and ignored by Git, and every
PDF page must be accounted for before a caller may replace a Markdown file.
"""

from __future__ import annotations

import io
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

_PADDLE_ENGINE: Any | None = None
ROOT_DIR = Path(__file__).resolve().parent.parent
PADDLE_CACHE_DIR = ROOT_DIR / ".paddlex"


class PaddleOcrError(RuntimeError):
    """PaddleOCR could not produce a complete, reviewable document result."""


@dataclass(frozen=True)
class PaddleOcrResult:
    input_path: str
    total_pages: int
    processed_pages: int
    native_text_pages: int
    ocr_pages: int
    text_by_page: list[str]
    full_text: str
    extraction_method: str
    status: str
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _configure_cache() -> None:
    """Keep PaddleX/PaddleOCR's local model cache inside the ignored workspace."""
    PADDLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(PADDLE_CACHE_DIR))
    # This only suppresses the preflight probe; it does not bypass TLS or make
    # model fetching optional when a model is not already cached.
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def get_ocr_engine() -> Any:
    """Return one local PaddleOCR 3.x pipeline for the whole conversion batch."""
    global _PADDLE_ENGINE
    if _PADDLE_ENGINE is None:
        _configure_cache()
        try:
            from paddleocr import PaddleOCR

            # PaddleOCR 3.x's ordered OCR pipeline is the supported local
            # equivalent to PPStructureV3 for these single-column legal pages.
            # Disable document-preprocessing models not needed for flat scans,
            # while retaining Vietnamese recognition and the model's line order.
            _PADDLE_ENGINE = PaddleOCR(
                lang="vi",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except Exception as exc:
            raise PaddleOcrError(f"Failed to initialize PaddleOCR 3.x: {exc}") from exc
    return _PADDLE_ENGINE


def _pdf_page_to_image(page: Any, *, dpi: int = 240) -> np.ndarray:
    """Render one PDF page to an in-memory RGB numpy image for local OCR."""
    pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
        return np.array(image.convert("RGB"))


def _result_mapping(result: Any) -> Mapping[str, Any]:
    """Normalise PaddleOCR 3.x result objects without depending on private APIs."""
    if isinstance(result, Mapping):
        return result
    payload = getattr(result, "json", None)
    if isinstance(payload, Mapping):
        nested = payload.get("res")
        return nested if isinstance(nested, Mapping) else payload
    raise PaddleOcrError(f"Unsupported PaddleOCR result type: {type(result).__name__}")


def _box_position(box: Any) -> tuple[float, float]:
    """Return a stable top-left position from a Polygon/rectangle-like box."""
    try:
        array = np.asarray(box, dtype=float)
        if array.ndim >= 2 and array.shape[-1] >= 2:
            return float(array[..., 0].min()), float(array[..., 1].min())
        if array.size >= 2:
            return float(array.flat[0]), float(array.flat[1])
    except (TypeError, ValueError):
        pass
    return 0.0, 0.0


def _ordered_text_from_prediction(predictions: Sequence[Any]) -> str:
    """Extract recognized lines in physical reading order from PaddleOCR 3.x."""
    entries: list[tuple[float, float, str]] = []
    for prediction in predictions:
        result = _result_mapping(prediction)
        texts = list(result.get("rec_texts") or [])
        boxes = list(result.get("rec_polys") or result.get("rec_boxes") or [])
        for index, raw_text in enumerate(texts):
            text = str(raw_text or "").strip()
            if not text:
                continue
            box = boxes[index] if index < len(boxes) else []
            x, y = _box_position(box)
            entries.append((y, x, text))
    entries.sort(key=lambda item: (round(item[0] / 10.0), item[1]))
    return "\n".join(item[2] for item in entries).strip()


def ocr_pdf_with_paddle(
    pdf_path: Path | str,
    *,
    min_native_chars_per_page: int = 50,
    dpi: int = 150,
    batch_size: int = 4,
) -> PaddleOcrResult:
    """Produce a complete page-ordered text result from one PDF.

    Pages with a usable native text layer are copied directly. The remaining
    scan pages use a singleton PaddleOCR engine. A page OCR failure raises so
    the caller cannot atomically replace an older Markdown with a partial file.
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise PaddleOcrError(f"PDF not found: {path}")
    try:
        import fitz
    except ImportError as exc:
        raise PaddleOcrError("PyMuPDF is required to render PDF pages for PaddleOCR.") from exc
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise PaddleOcrError(f"Could not open PDF {path}: {exc}") from exc

    total_pages = len(document)
    if total_pages == 0:
        document.close()
        raise PaddleOcrError(f"PDF has no pages: {path.name}")

    page_texts: list[str] = [""] * total_pages
    native_text_pages = 0
    ocr_pages = 0
    pages_to_ocr: list[tuple[int, np.ndarray]] = []
    try:
        for page_index, page in enumerate(document):
            native_text = page.get_text("text").strip()
            if len(native_text) >= min_native_chars_per_page:
                page_texts[page_index] = native_text
                native_text_pages += 1
            else:
                pages_to_ocr.append((page_index, _pdf_page_to_image(page, dpi=dpi)))
    finally:
        document.close()

    if pages_to_ocr:
        engine = get_ocr_engine()
        for i in range(0, len(pages_to_ocr), batch_size):
            chunk = pages_to_ocr[i : i + batch_size]
            chunk_imgs = [item[1] for item in chunk]
            try:
                preds_list = engine.predict(chunk_imgs)
            except PaddleOcrError:
                raise
            except Exception as exc:
                raise PaddleOcrError(f"PaddleOCR failed on page batch starting at {chunk[0][0] + 1}: {exc}") from exc

            if not isinstance(preds_list, list):
                preds_list = [preds_list]

            for (p_idx, _), pred in zip(chunk, preds_list):
                p_text = _ordered_text_from_prediction([pred] if not isinstance(pred, list) else pred)
                if not p_text:
                    raise PaddleOcrError(f"PaddleOCR produced no text on page {p_idx + 1}/{total_pages}")
                page_texts[p_idx] = p_text
                ocr_pages += 1

    processed_pages = native_text_pages + ocr_pages
    if processed_pages != total_pages:
        raise PaddleOcrError(f"OCR processed {processed_pages}/{total_pages} pages; refusing a partial result")
    full_text = "\n\n".join(page_texts).strip()
    if not full_text:
        raise PaddleOcrError("No usable text was extracted from the PDF")
    method = "paddle_ocr" if native_text_pages == 0 else "native_text_plus_paddle_ocr"
    return PaddleOcrResult(
        input_path=str(path),
        total_pages=total_pages,
        processed_pages=processed_pages,
        native_text_pages=native_text_pages,
        ocr_pages=ocr_pages,
        text_by_page=page_texts,
        full_text=full_text,
        extraction_method=method,
        status="success",
        warnings=[],
    )
