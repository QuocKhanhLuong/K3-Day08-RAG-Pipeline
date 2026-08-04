"""Offline integrity checks for the Task 1–3 labour-law corpus.

The validator performs no network calls.  It checks that the local originals,
provenance manifest and standardized Markdown agree before the corpus is handed
to Task 4.  Run with ``python -m src.validate_corpus``.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from src.schemas import LEGAL_STATUSES, metadata_errors

ROOT_DIR = Path(__file__).resolve().parent.parent
LANDING_DIR = ROOT_DIR / "data" / "landing"
STANDARDIZED_DIR = ROOT_DIR / "data" / "standardized"
MIN_LEGAL_BYTES = 1024
MIN_GUIDANCE_BYTES = 500
MIN_CONTENT_CHARS = 350
MIN_STANDARDIZED_CHARS = 200
PLACEHOLDERS = ("todo", "lorem ipsum", "example content", "chưa có nội dung")


@dataclass
class CorpusValidationReport:
    legal_documents: int = 0
    guidance_documents: int = 0
    standardized_documents: int = 0
    standardized_legal_files: int = 0
    standardized_guidance_files: int = 0
    ocr_processed: int = 0
    manual_review_required: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_readable_legal_file(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            signature = handle.read(8)
        if path.suffix.lower() == ".pdf":
            return signature.startswith(b"%PDF-")
        if path.suffix.lower() == ".docx":
            with zipfile.ZipFile(path) as archive:
                return "[Content_Types].xml" in archive.namelist()
        return path.suffix.lower() == ".doc" and path.stat().st_size > MIN_LEGAL_BYTES
    except (OSError, zipfile.BadZipFile):
        return False


def _is_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def parse_front_matter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Read front matter only when it starts at byte zero."""
    if not content.startswith("---\n"):
        return None, content
    end = content.find("\n---\n", 4)
    if end < 0:
        return None, content
    try:
        data = yaml.safe_load(content[4:end]) or {}
    except yaml.YAMLError:
        return None, content
    return data if isinstance(data, dict) else None, content[end + 5 :]


def _load_manifest(manifest_path: Path, report: CorpusValidationReport) -> list[dict[str, Any]]:
    if not manifest_path.is_file():
        report.errors.append(f"Missing legal manifest: {manifest_path}")
        return []
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"Invalid legal manifest: {exc}")
        return []
    if not isinstance(records, list):
        report.errors.append("Legal manifest must be a JSON list")
        return []
    return [record for record in records if isinstance(record, dict)]


def _validate_legal(report: CorpusValidationReport, legal_dir: Path) -> list[dict[str, Any]]:
    if not legal_dir.is_dir():
        report.errors.append(f"Legal directory does not exist: {legal_dir}")
        return []
    files = sorted(path for path in legal_dir.iterdir() if path.is_file() and path.suffix.lower() in {".pdf", ".docx", ".doc"})
    records = _load_manifest(legal_dir / "legal_sources.json", report)
    if not files and records:
        report.legal_documents = len(records)
    else:
        report.legal_documents = len(files)
        if len(files) < 3 and len(records) < 3:
            report.errors.append(f"Expected at least 3 legal PDF/DOCX/DOC files, found {len(files)}")
    for path in files:
        if path.stat().st_size <= MIN_LEGAL_BYTES:
            report.errors.append(f"Legal file is too small: {path.name}")
        if not _is_readable_legal_file(path):
            report.errors.append(f"Legal file has an invalid signature or cannot be read: {path.name}")

    seen_ids: set[str] = set()
    active_ids: set[str] = set()
    for record in records:
        document_id = record.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            report.errors.append("Legal manifest item is missing document_id")
            continue
        if document_id in seen_ids:
            report.errors.append(f"Duplicate document_id in legal manifest: {document_id}")
        seen_ids.add(document_id)
        source_page_url = record.get("source_page_url") or record.get("source_url")
        if not _is_https_url(source_page_url):
            report.errors.append(f"Manifest source_page_url is missing/invalid for {document_id}")
        if record.get("authoritative") is not True:
            report.errors.append(f"Legal manifest record must set authoritative=true: {document_id}")
        status = record.get("legal_status")
        if status not in LEGAL_STATUSES or status == "reference":
            report.errors.append(f"Manifest legal_status is invalid for {document_id}: {status}")
        if "draft" in f"{record.get('document_type', '')} {record.get('title', '')}".lower() and record.get("active_corpus") is True:
            report.errors.append(f"Draft document cannot be active_corpus: {document_id}")
        if record.get("active_corpus") is True:
            active_ids.add(document_id)
        filename = record.get("local_filename")
        source_path = legal_dir / str(filename or "")
        if record.get("download_status") not in (None, "success"):
            report.errors.append(f"Legal document was not collected successfully: {document_id}")
        if source_path.is_file():
            expected_checksum = record.get("sha256")
            if not isinstance(expected_checksum, str) or _sha256(source_path) != expected_checksum:
                report.errors.append(f"Checksum mismatch for {document_id}")
        for error in metadata_errors(record):
            report.errors.append(f"{document_id}: {error}")
    if {"labor_code_consolidated_18_2026", "labor_code_45_2019"}.issubset(active_ids):
        report.errors.append("The original Labor Code and the consolidated Labor Code cannot both be active_corpus")
    return records


def _validate_guidance(report: CorpusValidationReport, guidance_dir: Path) -> None:
    if not guidance_dir.is_dir():
        report.errors.append(f"Guidance directory does not exist: {guidance_dir}")
        return
    files = sorted(path for path in guidance_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")
    report.guidance_documents = len(files)
    if len(files) < 5:
        report.errors.append(f"Expected at least 5 guidance JSON files, found {len(files)}")
    seen_ids: set[str] = set()
    for path in files:
        if path.stat().st_size <= MIN_GUIDANCE_BYTES:
            report.errors.append(f"Guidance file is too small: {path.name}")
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.errors.append(f"Invalid guidance JSON {path.name}: {exc}")
            continue
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            report.errors.append(f"Guidance item has no document_id: {path.name}")
        elif document_id in seen_ids:
            report.errors.append(f"Duplicate document_id in guidance JSON: {document_id}")
        else:
            seen_ids.add(document_id)
        if not _is_https_url(item.get("url")):
            report.errors.append(f"Guidance item has missing/invalid URL: {path.name}")
        if not str(item.get("title") or "").strip():
            report.errors.append(f"Guidance item has no title: {path.name}")
        if len(str(item.get("content_markdown") or "").strip()) < MIN_CONTENT_CHARS:
            report.errors.append(f"Guidance content is too short: {path.name}")
        if item.get("document_type") != "official_guidance":
            report.errors.append(f"Guidance document_type must be official_guidance: {path.name}")
        if item.get("normative") is not False:
            report.errors.append(f"Guidance must be normative=false: {path.name}")
        if item.get("authoritative") is not False:
            report.errors.append(f"Guidance must be authoritative=false: {path.name}")
        if item.get("authority_level") != "government_guidance":
            report.errors.append(f"Guidance authority_level must be government_guidance: {path.name}")
        if item.get("legal_status") != "reference":
            report.errors.append(f"Guidance must use legal_status=reference: {path.name}")
        if not isinstance(item.get("legal_topics"), list) or not item["legal_topics"]:
            report.errors.append(f"Guidance has no legal_topics: {path.name}")


def _validate_standardized(report: CorpusValidationReport, standardized_dir: Path) -> None:
    if not standardized_dir.is_dir():
        report.errors.append(f"Standardized directory does not exist: {standardized_dir}")
        return
    legal_files = sorted((standardized_dir / "legal").glob("*.md")) if (standardized_dir / "legal").is_dir() else []
    guidance_files = sorted((standardized_dir / "news").glob("*.md")) if (standardized_dir / "news").is_dir() else []
    files = legal_files + guidance_files
    report.standardized_legal_files = len(legal_files)
    report.standardized_guidance_files = len(guidance_files)
    report.standardized_documents = len(files)
    if not legal_files:
        report.errors.append("No standardized legal Markdown files found")
    if not guidance_files:
        report.errors.append("No standardized guidance Markdown files found")
    seen_ids: set[str] = set()
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            report.errors.append(f"Cannot read standardized file {path.name}: {exc}")
            continue
        if len(content) <= MIN_STANDARDIZED_CHARS:
            report.errors.append(f"Standardized Markdown is too short: {path}")
        metadata, body = parse_front_matter(content)
        if metadata is None:
            report.errors.append(f"Missing/invalid YAML front matter: {path}")
            continue
        document_id = metadata.get("document_id")
        if document_id in seen_ids:
            report.errors.append(f"Duplicate document_id in standardized corpus: {document_id}")
        elif document_id:
            seen_ids.add(str(document_id))
        for error in metadata_errors(metadata, standardized=True):
            report.errors.append(f"{path.name}: {error}")
        if not _is_https_url(metadata.get("source_page_url") or metadata.get("source_url")):
            report.errors.append(f"{path.name}: missing/invalid source_page_url or source_url")
        if metadata.get("ocr_quality_status") == "failed" and metadata.get("active_corpus") is True:
            report.errors.append(f"OCR-failed source cannot be active_corpus: {path.name}")
        if "draft" in str(metadata.get("document_type") or "").lower() and metadata.get("active_corpus") is True:
            report.errors.append(f"Draft standardized source cannot be active_corpus: {path.name}")
        if metadata.get("ocr_quality_status") == "automatic_unreviewed":
            report.manual_review_required += 1

        body_stripped = body.strip()
        is_legal = path.parent.name == "legal"
        if is_legal:
            if len(body_stripped) < 2000:
                report.errors.append(f"Legal Markdown body is too short ({len(body_stripped)} < 2000 chars): {path.name}")
            if not re.search(r"\bĐiều\s+\d+", body_stripped):
                report.errors.append(f"Legal Markdown body missing 'Điều <number>': {path.name}")

            non_empty_lines = [l.strip() for l in body_stripped.splitlines() if l.strip()]
            if len(non_empty_lines) <= 1 and (not non_empty_lines or non_empty_lines[0].startswith('#')):
                report.errors.append(f"Legal Markdown body contains title only: {path.name}")

            processed_pages = metadata.get("processed_pages")
            pdf_pages = metadata.get("pdf_pages") or metadata.get("total_pages")
            source_is_pdf = metadata.get("source_format") == "pdf" or metadata.get("pdf_type") is not None
            if source_is_pdf and (not isinstance(processed_pages, int) or not isinstance(pdf_pages, int)):
                report.errors.append(f"Legal PDF is missing integer processed_pages/pdf_pages metadata: {path.name}")
            elif processed_pages is not None and pdf_pages is not None and processed_pages != pdf_pages:
                report.errors.append(f"OCR processed pages count mismatch ({processed_pages} != {pdf_pages}): {path.name}")

            body_char_count = metadata.get("body_character_count")
            # Keep source-internal whitespace intact.  Only the Markdown
            # delimiter line ending is outside the counted legal body.
            written_body = body.strip("\r\n")
            if not isinstance(body_char_count, int):
                report.errors.append(f"Legal Markdown is missing integer body_character_count: {path.name}")
            elif body_char_count != len(written_body):
                report.errors.append(f"body_character_count mismatch in metadata vs body ({body_char_count} != {len(written_body)}): {path.name}")

        lowered = content.lower()
        for marker in PLACEHOLDERS:
            if marker in lowered:
                report.errors.append(f"Placeholder marker '{marker}' in {path.name}")

    conversion_report = standardized_dir / "conversion_report.json"
    if conversion_report.is_file():
        try:
            conversion = json.loads(conversion_report.read_text(encoding="utf-8"))
            if isinstance(conversion, dict):
                report.ocr_processed = len(conversion.get("ocr_processed") or [])
                report.manual_review_required = max(report.manual_review_required, len(conversion.get("manual_review_required") or []))
            elif isinstance(conversion, list):
                report.ocr_processed = len([item for item in conversion if "paddle_ocr" in str(item.get("extraction_method")) or "paddle_ocr" in str(item.get("extraction method"))])
                report.manual_review_required = max(report.manual_review_required, len([item for item in conversion if item.get("ocr_status") == "automatic_unreviewed" or item.get("OCR status") == "automatic_unreviewed"]))
        except (OSError, json.JSONDecodeError):
            report.warnings.append("conversion_report.json is not readable")


def validate_corpus(
    *,
    landing_dir: Path = LANDING_DIR,
    standardized_dir: Path = STANDARDIZED_DIR,
) -> CorpusValidationReport:
    """Return all local data-quality problems without changing the corpus."""
    report = CorpusValidationReport()
    _validate_legal(report, landing_dir / "legal")
    _validate_guidance(report, landing_dir / "news")
    _validate_standardized(report, standardized_dir)
    return report


def format_report(report: CorpusValidationReport) -> str:
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"Corpus validation: {status}",
        f"Legal originals: {report.legal_documents}",
        f"Official guidance: {report.guidance_documents}",
        f"Standardized legal files: {report.standardized_legal_files}",
        f"Standardized guidance files: {report.standardized_guidance_files}",
        f"OCR processed: {report.ocr_processed}",
        f"Manual review required: {report.manual_review_required}",
        f"Errors: {len(report.errors)}",
        f"Warnings: {len(report.warnings)}",
    ]
    lines.extend(f"ERROR: {error}" for error in report.errors)
    lines.extend(f"WARNING: {warning}" for warning in report.warnings)
    return "\n".join(lines)


def main() -> int:
    report = validate_corpus()
    print(format_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
