"""Task 1: collect verifiable Vietnamese labour-law source documents.

The landing corpus intentionally keeps the original government files.  It does
not convert an error page into a ``.pdf`` file and it never assigns a legal
status based only on a document's publication date.  Statuses in
``legal_sources.json`` are checked against the cited official legal-database
page; an unverified status is explicitly recorded as ``unknown``.

Run with::

    python -m src.task1_collect_legal_docs
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.schemas import LEGAL_STATUSES

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "landing" / "legal"
MANIFEST_PATH = DATA_DIR / "legal_sources.json"
MIN_DOCUMENT_BYTES = 1024
REQUEST_TIMEOUT_SECONDS = 45
USER_AGENT = "VietnamYouthLaborLawCorpus/1.0 (+https://github.com/QuocKhanhLuong/K3-Day08-RAG-Pipeline)"


# Status pages must be directly reachable when the corpus is refreshed.  The
# CSDL VBPL item endpoints recorded during the initial survey returned HTTP 404
# on 2026-08-04, so these records intentionally remain ``unknown`` instead of
# presenting an unverified rule as current law.
LEGAL_DOCUMENTS: tuple[dict[str, Any], ...] = (
    {
        "document_id": "labor_code_45_2019",
        "title": "Bộ luật Lao động",
        "document_number": "45/2019/QH14",
        "document_type": "labor_code",
        "issuing_authority": "Quốc hội",
        "issued_date": "2019-11-20",
        "effective_date": "2021-01-01",
        "expiry_date": None,
        "legal_status": "unknown",
        "normative": True,
        "source_url": "https://vanban.chinhphu.vn/?classid=1&docid=198540&pageid=27160&typegroupid=3",
        "status_source_url": "",
        "status_verification_note": "Official CSDL VBPL status endpoint returned HTTP 404 during direct verification on 2026-08-04; do not use as a current-law source until re-verified.",
        "download_url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2019/12/45.signed.pdf",
        "local_filename": "labor-code-45-2019-qh14.pdf",
        "amends": [],
        "amended_by": [],
        "replaces": [],
        "replaced_by": [],
        "legal_topics": [
            "probation",
            "probation_salary",
            "employment_contract",
            "apprenticeship",
            "salary",
            "overtime",
            "night_work",
            "annual_leave",
            "public_holiday",
            "personal_leave",
            "unilateral_termination",
            "contract_termination",
            "dismissal",
            "labor_discipline",
            "salary_deduction",
            "salary_delay",
        ],
        "audience_roles": ["job_applicant", "intern", "apprentice", "trainee", "probationer", "employee", "employer"],
    },
    {
        "document_id": "decree_145_2020_labor_relations",
        "title": "Nghị định quy định chi tiết và hướng dẫn thi hành một số điều của Bộ luật Lao động về điều kiện lao động và quan hệ lao động",
        "document_number": "145/2020/NĐ-CP",
        "document_type": "decree",
        "issuing_authority": "Chính phủ",
        "issued_date": "2020-12-14",
        "effective_date": "2021-02-01",
        "expiry_date": None,
        "legal_status": "unknown",
        "normative": True,
        "source_url": "https://vanban.chinhphu.vn/default.aspx?docid=201967&pageid=27160",
        "status_source_url": "",
        "status_verification_note": "Official CSDL VBPL status endpoint returned HTTP 404 during direct verification on 2026-08-04; do not use as a current-law source until re-verified.",
        "download_url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2020/12/145.signed.pdf",
        "local_filename": "decree-145-2020-labor-relations.pdf",
        "amends": [],
        "amended_by": [],
        "replaces": [],
        "replaced_by": [],
        "legal_topics": ["employment_contract", "overtime", "night_work", "annual_leave", "labor_discipline", "contract_termination"],
        "audience_roles": ["apprentice", "trainee", "probationer", "employee", "employer"],
    },
    {
        "document_id": "decree_12_2022_labor_penalties",
        "title": "Nghị định quy định xử phạt vi phạm hành chính trong lĩnh vực lao động, bảo hiểm xã hội, người lao động Việt Nam đi làm việc ở nước ngoài theo hợp đồng",
        "document_number": "12/2022/NĐ-CP",
        "document_type": "decree",
        "issuing_authority": "Chính phủ",
        "issued_date": "2022-01-17",
        "effective_date": "2022-01-17",
        "expiry_date": None,
        "legal_status": "unknown",
        "normative": True,
        "source_url": "https://vanban.chinhphu.vn/?classid=1&docid=205182&orggroupid=2&pageid=27160",
        "status_source_url": "",
        "status_verification_note": "Official CSDL VBPL status endpoint returned HTTP 404 during direct verification on 2026-08-04; do not use as a current-law source until re-verified.",
        "download_url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/01/12-2022-nd.signed.pdf",
        "local_filename": "decree-12-2022-labor-penalties.pdf",
        "amends": [],
        "amended_by": [],
        "replaces": ["28/2020/NĐ-CP"],
        "replaced_by": [],
        "legal_topics": ["probation", "employment_contract", "salary", "overtime", "annual_leave", "dismissal", "labor_discipline", "salary_delay"],
        "audience_roles": ["probationer", "employee", "former_employee", "employer"],
    },
    {
        "document_id": "decree_293_2025_minimum_wage",
        "title": "Nghị định quy định mức lương tối thiểu đối với người lao động làm việc theo hợp đồng lao động",
        "document_number": "293/2025/NĐ-CP",
        "document_type": "decree",
        "issuing_authority": "Chính phủ",
        "issued_date": "2025-11-10",
        "effective_date": "2026-01-01",
        "expiry_date": None,
        # The collection source confirms dates but the collector deliberately
        # leaves the status unknown until a CSDL status page is verified.
        "legal_status": "unknown",
        "normative": True,
        "source_url": "https://vanban.chinhphu.vn/?classid=1&docid=215832&pageid=27160",
        "status_source_url": "",
        "status_verification_note": "No directly reachable official legal-status record was verified during collection; do not use as a current-law source until re-verified.",
        "download_url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/11/293-cp.signed.pdf",
        "local_filename": "decree-293-2025-minimum-wage.pdf",
        "amends": [],
        "amended_by": [],
        "replaces": ["74/2024/NĐ-CP"],
        "replaced_by": [],
        "legal_topics": ["salary", "probation_salary"],
        "audience_roles": ["job_applicant", "probationer", "employee", "employer"],
    },
)


class DownloadError(RuntimeError):
    """A remote document failed an authenticity or transport check."""


def setup_directory() -> Path:
    """Create the legal landing directory and return it."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_kind(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    return None


def is_valid_document(path: Path, minimum_bytes: int = MIN_DOCUMENT_BYTES) -> bool:
    """Return whether *path* is a non-trivial PDF/DOCX, without parsing remote data."""
    if not path.is_file() or path.stat().st_size <= minimum_bytes:
        return False
    try:
        with path.open("rb") as handle:
            kind = _file_kind(handle.read(8))
    except OSError:
        return False
    suffix = path.suffix.lower()
    return (suffix == ".pdf" and kind == "pdf") or (suffix == ".docx" and kind == "docx")


def _session(retries: int) -> requests.Session:
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
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document;q=0.9,*/*;q=0.1"})
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def download_document(
    url: str,
    output_path: Path,
    expected_types: tuple[str, ...] = ("application/pdf",),
    *,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    retries: int = 2,
    reuse_existing: bool = True,
) -> dict[str, Any]:
    """Download a PDF/DOCX atomically after validating its HTTP and file type.

    A valid existing output is retained unless a caller explicitly removes it.
    This is intentionally conservative: a server error, HTML page or too-small
    response can never replace a previously usable legal source file.
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
        raise DownloadError(f"Only an absolute HTTPS source is accepted: {url}")

    try:
        response = _session(retries).get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DownloadError(f"Request failed for {url}: {exc}") from exc

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
    accepted_types = {value.lower() for value in expected_types}
    if content_type not in accepted_types:
        raise DownloadError(f"Unexpected Content-Type for {url}: {content_type or 'missing'}")

    payload = response.content
    if len(payload) <= MIN_DOCUMENT_BYTES:
        raise DownloadError(f"Response is too small to be a source document: {len(payload)} bytes")
    kind = _file_kind(payload)
    suffix = output_path.suffix.lower()
    expected_kind = "pdf" if suffix == ".pdf" else "docx" if suffix == ".docx" else None
    if kind is None or kind != expected_kind:
        raise DownloadError(f"Magic bytes do not match {suffix or 'the expected format'} for {url}")

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".part", prefix=f".{output_path.name}.", dir=output_path.parent, delete=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_name = handle.name
        os.replace(temp_name, output_path)
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink(missing_ok=True)

    return {
        "path": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "sha256": sha256_file(output_path),
        "content_type": content_type,
        "downloaded_at": utc_now(),
        "reused_existing": False,
    }


def _load_manifest() -> dict[str, dict[str, Any]]:
    if not MANIFEST_PATH.exists():
        return {}
    try:
        records = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {record.get("document_id", ""): record for record in records if record.get("document_id")}


def _write_manifest(records: Iterable[dict[str, Any]]) -> None:
    ordered = sorted(records, key=lambda item: item["document_id"])
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", dir=DATA_DIR, delete=False) as handle:
        json.dump(ordered, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, MANIFEST_PATH)


def collect_legal_documents(*, force: bool = False, documents: Iterable[dict[str, Any]] | None = None) -> dict[str, list[dict[str, str]]]:
    """Collect configured official source documents and refresh the manifest.

    ``force`` causes a fresh request only after moving no files: a valid local
    file remains protected by :func:`download_document` if the fresh request
    fails.  ``documents`` exists for offline tests and future corpus revisions.
    """
    setup_directory()
    configured = tuple(documents or LEGAL_DOCUMENTS)
    existing = _load_manifest()
    report: dict[str, list[dict[str, str]]] = {"success": [], "failed": [], "skipped": []}
    refreshed: list[dict[str, Any]] = []

    for seed in configured:
        document_id = str(seed["document_id"])
        status = str(seed.get("legal_status", "unknown"))
        if status not in LEGAL_STATUSES or status == "reference":
            report["failed"].append({"document_id": document_id, "reason": f"Invalid legal_status: {status}"})
            continue
        output_path = DATA_DIR / str(seed["local_filename"])
        if force and output_path.exists() and not is_valid_document(output_path):
            output_path.unlink(missing_ok=True)
        try:
            download = download_document(
                str(seed["download_url"]),
                output_path,
                expected_types=("application/pdf",),
                reuse_existing=not force,
            )
        except DownloadError as exc:
            if is_valid_document(output_path) and document_id in existing:
                refreshed.append(existing[document_id])
                report["skipped"].append({"document_id": document_id, "reason": f"Retained valid local file after download error: {exc}"})
            else:
                report["failed"].append({"document_id": document_id, "reason": str(exc)})
            continue

        record = {key: value for key, value in seed.items() if key not in {"status_source_url"}}
        record.update(
            {
                "download_url": str(seed["download_url"]),
                "local_filename": output_path.name,
                "collected_at": download["downloaded_at"],
                "sha256": download["sha256"],
                "size_bytes": download["size_bytes"],
                "status_verified_url": seed.get("status_source_url") or None,
                "status_verification_note": seed.get("status_verification_note") or None,
                "converted_from_html": False,
            }
        )
        refreshed.append(record)
        bucket = "skipped" if download["reused_existing"] else "success"
        report[bucket].append({"document_id": document_id, "path": str(output_path)})

    # Retain valid historical manifest entries not included in this run.
    known_ids = {record["document_id"] for record in refreshed}
    for document_id, record in existing.items():
        path = DATA_DIR / str(record.get("local_filename", ""))
        if document_id not in known_ids and is_valid_document(path):
            refreshed.append(record)

    _write_manifest(refreshed)
    return report


def main() -> int:
    report = collect_legal_documents()
    print("Task 1 — Legal source collection")
    for label in ("success", "skipped", "failed"):
        print(f"{label}: {len(report[label])}")
        for item in report[label]:
            print(f"  - {item['document_id']}: {item.get('path') or item.get('reason')}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
