"""Task 3: convert the approved landing corpus to metadata-rich Markdown.

Routes scanned legal PDFs to PaddleOCR, cleans guidance news articles,
enforces strict quality gates on legal document bodies, and generates
a conversion report.

Run with ``python -m src.task3_convert_markdown --rebuild-all``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.legal_markdown_postprocess import count_articles, postprocess_legal_markdown
from src.paddle_ocr_pipeline import PaddleOcrError, ocr_pdf_with_paddle
from src.pdf_inspection import PdfInspectionError, inspect_pdf
from src.task1_collect_legal_docs import collect_legal_documents

ROOT_DIR = Path(__file__).resolve().parent.parent
LANDING_DIR = ROOT_DIR / "data" / "landing"
OUTPUT_DIR = ROOT_DIR / "data" / "standardized"
SUPPORTED_LEGAL_SUFFIXES = {".pdf", ".docx", ".doc", ".html", ".htm", ".txt", ".md"}
MIN_LEGAL_BODY_CHARS = 2000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _front_matter(metadata: dict[str, Any]) -> str:
    """Write stable YAML metadata without modifying source content."""
    ordered = {
        "document_id": metadata.get("document_id"),
        "title": metadata.get("title"),
        "document_number": metadata.get("document_number"),
        "document_type": metadata.get("document_type"),
        "issuing_authority": metadata.get("issuing_authority"),
        "issued_date": metadata.get("issued_date"),
        "effective_date": metadata.get("effective_date"),
        "expiry_date": metadata.get("expiry_date"),
        "legal_status": metadata.get("legal_status"),
        "normative": bool(metadata.get("normative", False)),
        "authoritative": bool(metadata.get("authoritative", False)),
        "authority_level": metadata.get("authority_level"),
        "active_corpus": bool(metadata.get("active_corpus", False)),
        "source_page_url": metadata.get("source_page_url") or metadata.get("source_url"),
        "source_url": metadata.get("source_page_url") or metadata.get("source_url"),
        "resolved_download_url": metadata.get("resolved_download_url"),
        "local_source_file": metadata.get("local_source_file"),
        "source": metadata.get("source"),
        "source_path": metadata.get("source_path"),
        "sha256": metadata.get("sha256"),
        "source_format": metadata.get("source_format"),
        "pdf_type": metadata.get("pdf_type"),
        "pdf_pages": metadata.get("pdf_pages"),
        "processed_pages": metadata.get("processed_pages"),
        "native_text_pages": metadata.get("native_text_pages"),
        "ocr_pages": metadata.get("ocr_pages"),
        "ocr_required": bool(metadata.get("ocr_required", False)),
        "extraction_method": metadata.get("extraction_method"),
        "ocr_quality_status": metadata.get("ocr_quality_status"),
        "body_character_count": metadata.get("body_character_count"),
        "article_count": metadata.get("article_count"),
        "ocr_warnings": list(metadata.get("ocr_warnings") or []),
        "legal_topics": list(metadata.get("legal_topics") or []),
        "audience_roles": list(metadata.get("audience_roles") or []),
    }
    return "---\n" + yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, default_flow_style=False).strip() + "\n---\n\n"


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".md", dir=path.parent, delete=False) as handle:
            handle.write(content)
            temporary = handle.name
        os.replace(temporary, path)
    except OSError:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        raise


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, path)


def _source_path_for_metadata(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _load_legal_manifest() -> dict[str, dict[str, Any]]:
    manifest_path = LANDING_DIR / "legal" / "legal_sources.json"
    if not manifest_path.is_file():
        return {}
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(item.get("local_filename")): item for item in records if isinstance(item, dict) and item.get("local_filename")}


def _convert_with_markitdown(path: Path) -> str:
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        from markitdown import MarkItDown
        return str(MarkItDown().convert(str(path)).text_content)
    except Exception:
        # Fallback to PyMuPDF text extraction
        import fitz
        doc = fitz.open(path)
        text = "\n\n".join(page.get_text("text").strip() for page in doc)
        doc.close()
        return text


def _normalise_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip(" #*-:–—")


def clean_guidance_markdown(raw_text: str, *, title: str = "") -> str:
    """Keep just the official article body, stripping navigation and footer chrome."""
    if not raw_text:
        return ""
    lines = [line.strip() for line in raw_text.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    expected_title = _normalise_for_match(title)
    if expected_title:
        for index, line in enumerate(lines):
            if _normalise_for_match(line) == expected_title:
                # The title is written once by the Markdown formatter below.
                lines = lines[index + 1 :]
                break

    stop_markers = (
        "tham khảo thêm",
        "tin liên quan",
        "bài liên quan",
        "xem thêm",
        "danh sách tỉnh",
        "tin cùng chuyên mục",
        "tin mới",
        "theo dõi",
        "cơ quan chủ quản",
        "tổng biên tập",
        "liên hệ",
        "giấy phép",
        "bản quyền",
    )
    blocked_markers = ("trang chủ", "đăng nhập", "đăng ký", "quảng cáo", "cookie")
    cleaned_lines: list[str] = []
    previous_key = ""
    for stripped in lines:
        lowered = _normalise_for_match(stripped)
        if any(lowered == marker or lowered.startswith(f"{marker}:") for marker in stop_markers):
            break
        if not stripped or any(marker in lowered for marker in blocked_markers):
            continue
        # No navigation/menu list should remain after Task 2; retain only
        # plain article lines here and remove duplicated source chrome.
        if stripped.startswith(("* [", "[")) or lowered == previous_key:
            continue
        cleaned_lines.append(stripped)
        previous_key = lowered
    return "\n\n".join(cleaned_lines).strip()


def _assemble_legal_markdown(metadata: dict[str, Any], raw_body_text: str) -> str:
    processed_body, article_cnt = postprocess_legal_markdown(raw_body_text)
    body_stripped = processed_body.strip()

    # Quality Gate Validation before assembling
    if len(body_stripped) < MIN_LEGAL_BODY_CHARS:
        raise ValueError(f"Legal body too short: {len(body_stripped)} < {MIN_LEGAL_BODY_CHARS} chars")
    if not re.search(r"\bĐiều\s+\d+", body_stripped):
        raise ValueError("Legal body does not contain any 'Điều <number>'")

    non_empty_lines = [line.strip() for line in body_stripped.splitlines() if line.strip()]
    if len(non_empty_lines) <= 1 and (not non_empty_lines or non_empty_lines[0].startswith("#")):
        raise ValueError("Legal body contains title only")

    processed_pages = metadata.get("processed_pages")
    total_pages = metadata.get("pdf_pages")
    if processed_pages is not None and total_pages is not None and processed_pages != total_pages:
        raise ValueError(f"Processed pages ({processed_pages}) != total PDF pages ({total_pages})")

    title = str(metadata.get("title") or "Untitled legal document").strip()
    if not body_stripped.startswith("#"):
        body_content = f"# {title}\n\n{body_stripped}"
    else:
        body_content = body_stripped

    # Count precisely the body written after front matter, not YAML and not a
    # pre-heading intermediate string. The validator independently recomputes it.
    metadata["body_character_count"] = len(body_content.strip())
    metadata["article_count"] = article_cnt

    return _front_matter(metadata) + body_content + "\n"


def _convert_legal_source(source_path: Path, source: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Convert legal file to Markdown, using PaddleOCR for scanned PDFs."""
    metadata = dict(source)
    metadata.update(
        {
            "source": source_path.name,
            "local_source_file": source_path.name,
            "source_path": _source_path_for_metadata(source_path),
            "source_format": source_path.suffix.lower().lstrip("."),
            "source_url": source.get("source_page_url") or source.get("source_url"),
        }
    )
    metadata.setdefault("authoritative", True)
    metadata.setdefault("active_corpus", False)
    metadata.setdefault("legal_topics", [])
    metadata.setdefault("audience_roles", [])

    if source_path.suffix.lower() != ".pdf":
        metadata.update(
            {
                "pdf_type": None,
                "pdf_pages": None,
                "processed_pages": None,
                "ocr_required": False,
                "ocr_quality_status": "not_required",
                "extraction_method": "markitdown_native",
            }
        )
        converted_text = _convert_with_markitdown(source_path)
        markdown = _assemble_legal_markdown(metadata, converted_text)
        return markdown, metadata

    inspection = inspect_pdf(source_path)
    metadata.update(
        {
            "pdf_type": inspection.pdf_type,
            "pdf_pages": inspection.total_pages,
            "ocr_required": inspection.requires_ocr,
        }
    )

    if inspection.requires_ocr:
        ocr_res = ocr_pdf_with_paddle(source_path)
        metadata.update(
            {
                "processed_pages": ocr_res.processed_pages,
                "ocr_quality_status": "automatic_unreviewed" if ocr_res.status == "success" else "failed",
                "ocr_warnings": list(ocr_res.warnings),
                "extraction_method": ocr_res.extraction_method,
                "native_text_pages": ocr_res.native_text_pages,
                "ocr_pages": ocr_res.ocr_pages,
            }
        )
        converted_text = ocr_res.full_text
    else:
        converted_text = _convert_with_markitdown(source_path)
        metadata.update(
            {
                "processed_pages": inspection.total_pages,
                "ocr_quality_status": "not_required",
                "ocr_warnings": [],
                "extraction_method": "markitdown_native",
            }
        )

    markdown = _assemble_legal_markdown(metadata, converted_text)
    return markdown, metadata


def convert_legal_docs(*, force_redownload: bool = False) -> list[dict[str, Any]]:
    """Convert legal originals independently. Re-downloads if files missing."""
    legal_dir = LANDING_DIR / "legal"
    legal_dir.mkdir(parents=True, exist_ok=True)
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_legal_manifest()

    # Ensure PDFs are collected if missing or force requested
    existing_pdfs = [p for p in legal_dir.glob("*.pdf") if p.is_file()]
    if not existing_pdfs or force_redownload:
        collect_legal_documents(force=force_redownload)
        manifest = _load_legal_manifest()

    outcomes: list[dict[str, Any]] = []
    
    for filename, source in manifest.items():
        source_path = legal_dir / filename
        if not source_path.is_file():
            # Try to fetch missing file
            collect_legal_documents(force=False)
            if not source_path.is_file():
                outcomes.append({"status": "failed", "source": filename, "reason": f"File {filename} not present locally"})
                continue
        try:
            markdown, metadata = _convert_legal_source(source_path, source)
            output_path = output_dir / f"{source_path.stem}.md"
            _write_text_atomic(output_path, markdown)
            
            outcome = {
                "status": "success",
                "source": filename,
                "output": str(output_path),
                "document_id": metadata.get("document_id"),
                "page count": metadata.get("pdf_pages"),
                "page_count": metadata.get("pdf_pages"),
                "processed pages": metadata.get("processed_pages"),
                "processed_pages": metadata.get("processed_pages"),
                "extraction method": metadata.get("extraction_method"),
                "extraction_method": metadata.get("extraction_method"),
                "body characters": metadata.get("body_character_count"),
                "body_characters": metadata.get("body_character_count"),
                "article count": metadata.get("article_count"),
                "article_count": metadata.get("article_count"),
                "OCR status": metadata.get("ocr_quality_status"),
                "ocr_status": metadata.get("ocr_quality_status"),
                "warnings": metadata.get("ocr_warnings", []),
            }
            outcomes.append(outcome)
        except Exception as exc:
            outcomes.append({"status": "failed", "source": filename, "reason": str(exc)})

    return outcomes


def convert_guidance_docs() -> list[dict[str, Any]]:
    """Standardize guidance JSON files into clean Markdown, removing boilerplate."""
    guidance_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[dict[str, Any]] = []

    if not guidance_dir.exists():
        return outcomes

    for source_path in sorted(guidance_dir.glob("*.json")):
        try:
            data = json.loads(source_path.read_text(encoding="utf-8"))
            raw_content = str(data.get("content_markdown") or "")
            title = str(data.get("title") or "").strip()
            cleaned_content = clean_guidance_markdown(raw_content, title=title)
            if len(cleaned_content) < 350:
                raise ValueError(f"Cleaned guidance article is too short: {len(cleaned_content)} characters")

            metadata = {
                "document_id": data.get("document_id"),
                "title": data.get("title"),
                "document_number": None,
                "document_type": "official_guidance",
                "issuing_authority": data.get("issuing_organization"),
                "issued_date": data.get("date_published"),
                "effective_date": None,
                "expiry_date": None,
                "legal_status": "reference",
                "normative": False,
                "authoritative": False,
                "authority_level": "government_guidance",
                "active_corpus": True,
                "source_page_url": data.get("url"),
                "source_url": data.get("url"),
                "resolved_download_url": None,
                "local_source_file": source_path.name,
                "source": source_path.name,
                "source_path": _source_path_for_metadata(source_path),
                "sha256": None,
                "source_format": "json",
                "pdf_type": None,
                "ocr_required": False,
                "extraction_method": "json_markdown",
                "ocr_quality_status": "not_required",
                "legal_topics": data.get("legal_topics") or [],
                "audience_roles": data.get("audience_roles") or [],
            }

            body_parts = [f"# {title}"]
            if metadata["issued_date"]:
                body_parts.append(f"*Ngày đăng: {metadata['issued_date']}*")
            body_parts.append(cleaned_content)
            body = "\n\n".join(body_parts).strip()

            markdown = _front_matter(metadata) + body + "\n"
            output_path = output_dir / f"{source_path.stem}.md"
            _write_text_atomic(output_path, markdown)
            outcomes.append({"status": "success", "source": source_path.name, "output": str(output_path)})
        except Exception as exc:
            outcomes.append({"status": "failed", "source": source_path.name, "reason": str(exc)})

    return outcomes


def convert_news_articles() -> list[dict[str, Any]]:
    return convert_guidance_docs()


def convert_all(*, rebuild_all: bool = False, clean_binaries_after: bool = True) -> dict[str, Any]:
    """Standardize all legal & guidance docs and generate conversion_report.json."""
    legal_outcomes = convert_legal_docs(force_redownload=rebuild_all)
    guidance_outcomes = convert_guidance_docs()

    successes = [item for item in legal_outcomes if item["status"] == "success"]
    failed = [item for item in legal_outcomes + guidance_outcomes if item["status"] == "failed"]
    
    # A report stays useful after source PDFs are removed: it records enough
    # evidence to validate every replacement Markdown without raw OCR payloads.
    report_file = OUTPUT_DIR / "conversion_report.json"
    successful_legal = [item for item in legal_outcomes if item["status"] == "success"]
    report_data = {
        "generated_at": utc_now(),
        "documents": successful_legal,
        "failed": [item for item in legal_outcomes if item["status"] == "failed"],
        "ocr_processed": [item for item in successful_legal if "paddle_ocr" in str(item.get("extraction_method"))],
        "manual_review_required": [item["document_id"] for item in successful_legal if item.get("ocr_status") == "automatic_unreviewed"],
    }
    _write_json_atomic(report_file, report_data)

    # Clean up local PDF/DOCX binaries after successful standardization per Requirement 5
    if not failed and clean_binaries_after:
        legal_dir = LANDING_DIR / "legal"
        for binary_file in legal_dir.glob("*"):
            if binary_file.is_file() and binary_file.suffix.lower() in {".pdf", ".docx", ".doc"}:
                binary_file.unlink(missing_ok=True)

    return {
        "generated_at": utc_now(),
        "legal": legal_outcomes,
        "guidance": guidance_outcomes,
        "success": [item for item in legal_outcomes + guidance_outcomes if item["status"] == "success"],
        "failed": failed,
        "report_file": str(report_file),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Standardize legal & guidance corpus to Markdown.")
    parser.add_argument("--rebuild-all", action="store_true", help="Force redownloading PDFs and rebuilding all Markdowns.")
    args = parser.parse_args(argv)

    report = convert_all(rebuild_all=args.rebuild_all)
    print("Task 3 — Markdown standardization")
    print(f"success: {len(report['success'])}")
    print(f"failed: {len(report['failed'])}")

    if report["failed"]:
        for item in report["failed"]:
            print(f"  - {item['source']}: {item['reason']}")

    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
