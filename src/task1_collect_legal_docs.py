"""Task 1: collect the approved official Vietnamese labour-law sources.

The source catalog lives in :mod:`src.labor_law_sources`; this module performs
only transport, integrity validation and manifesting.  It never fabricates a
PDF from an HTML error response, and it keeps downloaded binaries local-only.

Run ``python -m src.task1_collect_legal_docs`` or add ``--force`` to refresh.
"""

from __future__ import annotations

import argparse
import html
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.labor_law_sources import LEGAL_SOURCES

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "landing" / "legal"
MANIFEST_PATH = DATA_DIR / "legal_sources.json"
MIN_DOCUMENT_BYTES = 1024
REQUEST_TIMEOUT_SECONDS = 45
MAX_RETRIES = 2
USER_AGENT = "VietnamYouthLaborLawCorpus/2.0 (+https://github.com/QuocKhanhLuong/K3-Day08-RAG-Pipeline)"
PDF_CONTENT_TYPES = ("application/pdf",)
DOCX_CONTENT_TYPES = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",)
OFFICIAL_GOVERNMENT_SUFFIXES = (".chinhphu.vn", ".cdnchinhphu.vn")

# Backward-compatible name used by earlier lab code and a few notebooks.
LEGAL_DOCUMENTS = LEGAL_SOURCES


class DownloadError(RuntimeError):
    """A source document failed transport or authenticity validation."""


class SourceResolutionError(DownloadError):
    """The official Công báo page did not expose an acceptable attachment."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def setup_directory() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_kind(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\\x03\\x04"):
        return "docx"
    return None


def is_valid_document(path: Path, minimum_bytes: int = MIN_DOCUMENT_BYTES) -> bool:
    """Check a local PDF/DOCX by size, extension and magic bytes."""
    if not path.is_file() or path.stat().st_size <= minimum_bytes:
        return False
    try:
        with path.open("rb") as handle:
            kind = _file_kind(handle.read(8))
    except OSError:
        return False
    return (path.suffix.lower() == ".pdf" and kind == "pdf") or (path.suffix.lower() == ".docx" and kind == "docx")


def _session(retries: int = MAX_RETRIES) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/html;q=0.8,*/*;q=0.1",
        }
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _is_official_government_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host in {"chinhphu.vn", "cdnchinhphu.vn"} or host.endswith(OFFICIAL_GOVERNMENT_SUFFIXES)
    )


def _fetch_source_page(page_url: str) -> str:
    """Fetch an official detail page for the link resolver; easy to fixture-test."""
    if not _is_official_government_url(page_url):
        raise SourceResolutionError(f"Resolver accepts only official Government HTTPS pages: {page_url}")
    try:
        response = _session().get(page_url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SourceResolutionError(f"Could not fetch Công báo source page {page_url}: {exc}") from exc
    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type:
        raise SourceResolutionError(f"Expected HTML source page, received {content_type or 'missing Content-Type'}")
    return response.text


def resolve_congbao_download(
    page_url: str,
    preferred_extensions: tuple[str, ...] = (".docx", ".pdf"),
) -> str:
    """Resolve a public DOCX/PDF link exposed by a Công báo detail page.

    No CDN URL is guessed.  Relative links are resolved against the detail
    page, then constrained to an official ``*.chinhphu.vn`` HTTPS host.
    """
    desired = tuple(extension.lower() if extension.startswith(".") else f".{extension.lower()}" for extension in preferred_extensions)
    if not desired:
        raise ValueError("preferred_extensions must not be empty")
    page_html = _fetch_source_page(page_url)
    soup = BeautifulSoup(page_html, "html.parser")
    candidates: list[tuple[int, str]] = []
    raw_candidates: list[tuple[str, list[str]]] = []
    for link in soup.find_all("a", href=True):
        raw_candidates.append(
            (
                str(link["href"]).strip(),
                [str(link.get("data-file") or ""), str(link.get("title") or ""), link.get_text(" ", strip=True)],
            )
        )
    # Some Công báo layouts expose the public issue PDF in a JS/data field
    # rather than an anchor. Parse that published URL from the detail page,
    # still subject to the same official-host and extension validation.
    for raw_url in re.findall(r"https?://[^\"'<>\s]+", html.unescape(page_html)):
        raw_candidates.append((raw_url, []))
    for raw_url, element_hints in raw_candidates:
        resolved = urljoin(page_url, raw_url)
        parsed = urlparse(resolved)
        query_values = [unquote(value) for values in parse_qs(parsed.query).values() for value in values]
        filename_hints = [parsed.path, *element_hints, *query_values]
        extension = next((Path(hint).suffix.lower() for hint in filename_hints if Path(hint).suffix.lower() in desired), "")
        if extension not in desired or not _is_official_government_url(resolved):
            continue
        candidates.append((desired.index(extension), resolved))
    if not candidates:
        raise SourceResolutionError(
            f"No official DOCX/PDF download link was found on Công báo page: {page_url}. "
            "The source may have changed; do not guess a CDN URL."
        )
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]


def _expected_kind(expected_types: tuple[str, ...]) -> str | None:
    expected = {value.lower() for value in expected_types}
    if "application/pdf" in expected:
        return "pdf"
    if "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in expected:
        return "docx"
    return None


def download_document(
    url: str,
    output_path: Path,
    expected_types: tuple[str, ...] = PDF_CONTENT_TYPES,
    *,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    retries: int = MAX_RETRIES,
    reuse_existing: bool = True,
) -> dict[str, Any]:
    """Download an official PDF/DOCX atomically without replacing a good file.

    The ``application/octet-stream`` attachment type is accepted only after
    magic-byte validation.  HTML, missing type and mismatched types are always
    rejected before a target can be written.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if reuse_existing and is_valid_document(output_path):
        return {
            "path": str(output_path),
            "size_bytes": output_path.stat().st_size,
            "sha256": sha256_file(output_path),
            "content_type": "existing_valid_file",
            "downloaded_at": utc_now(),
            "reused_existing": True,
        }

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise DownloadError(f"Only an absolute HTTPS URL is accepted: {url}")
    try:
        response = _session(retries).get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DownloadError(f"Request failed for {url}: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
    accepted = {content_type_item.lower() for content_type_item in expected_types}
    if content_type not in accepted and content_type != "application/octet-stream":
        raise DownloadError(f"Unexpected Content-Type for {url}: {content_type or 'missing'}")
    payload = response.content
    if len(payload) <= MIN_DOCUMENT_BYTES:
        raise DownloadError(f"Downloaded document is too small ({len(payload)} bytes): {url}")
    kind = _file_kind(payload[:8])
    expected_kind = _expected_kind(expected_types)
    if kind is None or (expected_kind is not None and kind != expected_kind):
        raise DownloadError(f"Downloaded payload magic bytes do not match the expected document type: {url}")
    suffix = output_path.suffix.lower()
    if (kind == "pdf" and suffix != ".pdf") or (kind == "docx" and suffix != ".docx"):
        raise DownloadError(f"Output filename extension does not match downloaded {kind.upper()}: {output_path.name}")

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=output_path.parent, suffix=f"{output_path.suffix}.tmp", delete=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_name = handle.name
        os.replace(temp_name, output_path)
    except OSError as exc:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        raise DownloadError(f"Could not write document atomically to {output_path}: {exc}") from exc

    return {
        "path": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
        "content_type": content_type,
        "downloaded_at": utc_now(),
        "reused_existing": False,
    }


def _load_manifest() -> dict[str, dict[str, Any]]:
    if not MANIFEST_PATH.is_file():
        return {}
    try:
        records = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(item.get("document_id")): item for item in records if isinstance(item, dict) and item.get("document_id")}


def _filename_for_source(source: dict[str, Any], download_url: str) -> str:
    existing = source.get("local_filename")
    if existing:
        return str(existing)
    extension = _document_extension(download_url)
    if extension not in {".docx", ".pdf"}:
        raise DownloadError(f"Resolved source lacks a supported file extension: {download_url}")
    safe_id = str(source["document_id"]).replace("_", "-")
    return f"{safe_id}{extension}"


def _record_base(source: dict[str, Any]) -> dict[str, Any]:
    record = dict(source)
    record.setdefault("effective_date", None)
    record.setdefault("expiry_date", None)
    record.setdefault("amends", [])
    record.setdefault("amended_by", [])
    record.setdefault("replaces", [])
    record.setdefault("replaced_by", [])
    record.setdefault("legal_topics", [])
    record.setdefault("audience_roles", [])
    # Existing downstream consumers use source_url; canonical data keeps
    # source_page_url, so store both without altering the source catalog.
    record["source_url"] = record["source_page_url"]
    return record


def _document_extension(url: str) -> str:
    """Find a PDF/DOCX extension in a normal path or official download query."""
    parsed = urlparse(url)
    hints = [parsed.path, *[unquote(value) for values in parse_qs(parsed.query).values() for value in values]]
    return next((Path(hint).suffix.lower() for hint in hints if Path(hint).suffix.lower() in {".pdf", ".docx"}), "")


def _expected_types_for_url(url: str) -> tuple[str, ...]:
    return DOCX_CONTENT_TYPES if _document_extension(url) == ".docx" else PDF_CONTENT_TYPES


def collect_legal_documents(
    *,
    force: bool = False,
    documents: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Collect every catalog entry and write a complete provenance manifest."""
    setup_directory()
    existing_records = _load_manifest()
    manifest_records: list[dict[str, Any]] = []
    for descriptor in documents or LEGAL_SOURCES:
        source = dict(descriptor)
        record = _record_base(source)
        previous = existing_records.get(str(source["document_id"]), {})
        known_filename = str(source.get("local_filename") or previous.get("local_filename") or "")
        existing_path = DATA_DIR / known_filename if known_filename else None
        if not force and existing_path and is_valid_document(existing_path):
            record.update(
                {
                    "local_filename": existing_path.name,
                    "resolved_download_url": previous.get("resolved_download_url") or source.get("download_url"),
                    "size_bytes": existing_path.stat().st_size,
                    "sha256": sha256_file(existing_path),
                    "collected_at": previous.get("collected_at") or utc_now(),
                    "download_status": "success",
                    "download_reused": True,
                }
            )
            manifest_records.append(record)
            continue
        try:
            resolved_download_url = str(source.get("download_url") or "")
            if source.get("resolve_download_from_page"):
                preferred = (f".{source.get('preferred_format', 'docx')}", f".{source.get('fallback_format', 'pdf')}")
                resolved_download_url = resolve_congbao_download(str(source["source_page_url"]), preferred)
            if not resolved_download_url:
                raise DownloadError(f"Catalog entry has no download URL: {source['document_id']}")
            filename = _filename_for_source(source, resolved_download_url)
            try:
                outcome = download_document(
                    resolved_download_url,
                    DATA_DIR / filename,
                    expected_types=_expected_types_for_url(resolved_download_url),
                    reuse_existing=not force,
                )
            except DownloadError:
                # The catalog requires DOCX preference but permits PDF fallback.
                # Resolve the fallback anew from the authoritative detail page;
                # never construct or persist a guessed CDN/token URL.
                if not source.get("resolve_download_from_page") or _document_extension(resolved_download_url) == ".pdf":
                    raise
                resolved_download_url = resolve_congbao_download(str(source["source_page_url"]), (".pdf",))
                filename = _filename_for_source(source, resolved_download_url)
                outcome = download_document(
                    resolved_download_url,
                    DATA_DIR / filename,
                    expected_types=PDF_CONTENT_TYPES,
                    reuse_existing=not force,
                )
            record.update(
                {
                    "local_filename": filename,
                    "resolved_download_url": resolved_download_url,
                    "size_bytes": outcome["size_bytes"],
                    "sha256": outcome["sha256"],
                    "collected_at": outcome["downloaded_at"],
                    "download_status": "success",
                    "download_reused": bool(outcome.get("reused_existing")),
                }
            )
        except Exception as exc:
            record.update(
                {
                    "local_filename": known_filename or None,
                    "resolved_download_url": source.get("download_url"),
                    "collected_at": utc_now(),
                    "download_status": "failed",
                    "failure_reason": str(exc),
                }
            )
        manifest_records.append(record)

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", dir=DATA_DIR, delete=False) as handle:
        json.dump(manifest_records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, MANIFEST_PATH)
    return manifest_records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download approved official labour-law source documents.")
    parser.add_argument("--force", action="store_true", help="Refresh files even when a valid local copy exists.")
    args = parser.parse_args(argv)
    records = collect_legal_documents(force=args.force)
    successes = [item for item in records if item.get("download_status") == "success"]
    failures = [item for item in records if item.get("download_status") != "success"]
    print("Task 1 — Official legal document collection")
    print(f"success: {len(successes)}")
    print(f"failed: {len(failures)}")
    for item in failures:
        print(f"  - {item['document_id']}: {item.get('failure_reason', 'unknown failure')}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
