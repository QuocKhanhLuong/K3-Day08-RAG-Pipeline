"""Validate the raw and standardized corpus before Task 4 consumes it.

Run with ``python -m src.validate_corpus``.  The checks are deliberately
fail-closed for source integrity but do not perform any network activity.
"""

from __future__ import annotations

import hashlib
import json
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
LEGAL_DIR = LANDING_DIR / "legal"
GUIDANCE_DIR = LANDING_DIR / "news"
MANIFEST_PATH = LEGAL_DIR / "legal_sources.json"
MIN_LEGAL_BYTES = 1024
MIN_GUIDANCE_BYTES = 500
MIN_STANDARDIZED_CHARS = 200
PLACEHOLDERS = ("todo", "lorem ipsum", "example content", "chưa có nội dung")


@dataclass
class CorpusValidationReport:
    legal_documents: int = 0
    guidance_documents: int = 0
    standardized_documents: int = 0
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
    """Parse a YAML header without accepting a header located mid-document."""
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


def _validate_legal(report: CorpusValidationReport, legal_dir: Path, manifest_path: Path) -> None:
    if not legal_dir.is_dir():
        report.errors.append(f"Legal directory does not exist: {legal_dir}")
        return
    files = sorted(path for path in legal_dir.iterdir() if path.is_file() and path.suffix.lower() in {".pdf", ".docx", ".doc"})
    report.legal_documents = len(files)
    if len(files) < 3:
        report.errors.append(f"Expected at least 3 legal PDF/DOCX/DOC files, found {len(files)}")
    for path in files:
        if path.stat().st_size <= MIN_LEGAL_BYTES:
            report.errors.append(f"Legal file is too small: {path.name}")
        if not _is_readable_legal_file(path):
            report.errors.append(f"Legal file has an invalid signature or cannot be read: {path.name}")

    if not manifest_path.is_file():
        report.errors.append(f"Missing legal manifest: {manifest_path}")
        return
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.errors.append(f"Invalid legal manifest: {exc}")
        return
    if not isinstance(records, list):
        report.errors.append("Legal manifest must be a JSON list")
        return
    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            report.errors.append("Legal manifest contains a non-object item")
            continue
        document_id = record.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            report.errors.append("Legal manifest item is missing document_id")
        elif document_id in seen_ids:
            report.errors.append(f"Duplicate document_id in legal manifest: {document_id}")
        else:
            seen_ids.add(document_id)
        if not _is_https_url(record.get("source_url")):
            report.errors.append(f"Manifest source_url is missing/invalid for {document_id}")
        status = record.get("legal_status")
        if status not in LEGAL_STATUSES or status == "reference":
            report.errors.append(f"Manifest legal_status is invalid for {document_id}: {status}")
        filename = record.get("local_filename")
        source_path = legal_dir / str(filename or "")
        if not filename or not source_path.is_file():
            report.errors.append(f"Manifest filename does not exist for {document_id}: {filename}")
            continue
        expected_checksum = record.get("sha256")
        if not isinstance(expected_checksum, str) or _sha256(source_path) != expected_checksum:
            report.errors.append(f"Checksum mismatch for {document_id}")
        errors = metadata_errors(record)
        if errors:
            report.errors.extend(f"{document_id}: {error}" for error in errors)


def _validate_guidance(report: CorpusValidationReport, guidance_dir: Path) -> None:
    if not guidance_dir.is_dir():
        report.errors.append(f"Guidance directory does not exist: {guidance_dir}")
        return
    files = sorted(path for path in guidance_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")
    report.guidance_documents = len(files)
    if len(files) < 5:
        report.errors.append(f"Expected at least 5 guidance JSON files, found {len(files)}")
    for path in files:
        if path.stat().st_size <= MIN_GUIDANCE_BYTES:
            report.errors.append(f"Guidance file is too small: {path.name}")
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report.errors.append(f"Invalid guidance JSON {path.name}: {exc}")
            continue
        if not _is_https_url(item.get("url")):
            report.errors.append(f"Guidance item has missing/invalid URL: {path.name}")
        if not str(item.get("title") or "").strip():
            report.errors.append(f"Guidance item has no title: {path.name}")
        if len(str(item.get("content_markdown") or "").strip()) < MIN_STANDARDIZED_CHARS:
            report.errors.append(f"Guidance content is too short: {path.name}")
        if item.get("normative") is not False:
            report.errors.append(f"Guidance must be normative=false: {path.name}")
        if item.get("legal_status") != "reference":
            report.errors.append(f"Guidance must use legal_status=reference: {path.name}")
        if not isinstance(item.get("legal_topics"), list) or not item["legal_topics"]:
            report.errors.append(f"Guidance has no legal_topics: {path.name}")


def _validate_standardized(report: CorpusValidationReport, standardized_dir: Path) -> None:
    if not standardized_dir.is_dir():
        report.errors.append(f"Standardized directory does not exist: {standardized_dir}")
        return
    files = sorted(standardized_dir.rglob("*.md"))
    report.standardized_documents = len(files)
    if not files:
        report.errors.append("No standardized Markdown files found")
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            report.errors.append(f"Cannot read standardized file {path.name}: {exc}")
            continue
        if len(content) <= MIN_STANDARDIZED_CHARS:
            report.errors.append(f"Standardized Markdown is too short: {path}")
        metadata, _ = parse_front_matter(content)
        if metadata is None:
            report.errors.append(f"Missing/invalid YAML front matter: {path}")
            continue
        for error in metadata_errors(metadata, standardized=True):
            report.errors.append(f"{path.name}: {error}")
        lowered = content.lower()
        for marker in PLACEHOLDERS:
            if marker in lowered:
                report.errors.append(f"Placeholder marker '{marker}' in {path.name}")


def validate_corpus(
    *,
    landing_dir: Path = LANDING_DIR,
    standardized_dir: Path = STANDARDIZED_DIR,
) -> CorpusValidationReport:
    """Run all offline corpus quality checks and return structured findings."""
    report = CorpusValidationReport()
    _validate_legal(report, landing_dir / "legal", landing_dir / "legal" / "legal_sources.json")
    _validate_guidance(report, landing_dir / "news")
    _validate_standardized(report, standardized_dir)
    return report


def format_report(report: CorpusValidationReport) -> str:
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"Corpus validation: {status}",
        f"Legal documents: {report.legal_documents}",
        f"Guidance documents: {report.guidance_documents}",
        f"Standardized documents: {report.standardized_documents}",
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
