"""Shared data contracts for the Vietnam youth labour-law RAG team.

This module contains no retrieval or model code.  It is the hand-off boundary
between Tasks 1–3 and the members implementing indexing, retrieval, generation
and evaluation in Tasks 4–10.
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


LEGAL_STATUSES = frozenset({"in_force", "partially_effective", "expired", "replaced", "unknown", "reference"})
NORMATIVE_DOCUMENT_TYPES = frozenset({"labor_code", "consolidated_code", "law", "decree", "circular", "resolution"})
AUDIENCE_ROLES = frozenset({"job_applicant", "intern", "apprentice", "trainee", "probationer", "employee", "former_employee", "employer"})


class LegalMetadata(TypedDict, total=False):
    """Metadata that must survive from standardized Markdown to every result."""

    document_id: str
    source: str
    source_path: str
    source_url: str
    title: str
    document_number: str | None
    document_type: str
    issuing_authority: str | None
    issued_date: str | None
    effective_date: str | None
    expiry_date: str | None
    legal_status: str
    normative: bool
    chapter: str | None
    section: str | None
    article: str | None
    clause: str | None
    point: str | None
    legal_topics: list[str]
    audience_roles: list[str]
    chunk_index: int | None


class LegalDocument(TypedDict):
    """A standardized source document before legal-aware chunking."""

    content: str
    metadata: LegalMetadata


class LegalChunk(TypedDict):
    """A legal-aware chunk created by Task 4 and consumed by Tasks 5–10."""

    content: str
    metadata: LegalMetadata


class RetrievalResult(TypedDict):
    """Non-binding interface for downstream retrieval implementations."""

    content: str
    score: float
    metadata: LegalMetadata
    source: NotRequired[str]
    dense_score: NotRequired[float | None]
    bm25_score: NotRequired[float | None]
    rrf_score: NotRequired[float | None]


REQUIRED_STANDARDIZED_METADATA = frozenset(
    {
        "document_id",
        "source",
        "source_path",
        "title",
        "document_type",
        "legal_status",
        "normative",
        "source_url",
        "legal_topics",
        "audience_roles",
    }
)


def metadata_errors(metadata: dict[str, Any], *, standardized: bool = False) -> list[str]:
    """Return contract violations without mutating caller metadata."""
    errors: list[str] = []
    required = REQUIRED_STANDARDIZED_METADATA if standardized else {"document_id", "source_url", "document_type", "legal_status", "normative"}
    for field in sorted(required):
        if field not in metadata or metadata[field] in (None, ""):
            errors.append(f"missing {field}")
    status = metadata.get("legal_status")
    if status is not None and status not in LEGAL_STATUSES:
        errors.append(f"invalid legal_status: {status}")
    normative = metadata.get("normative")
    if normative is not None and not isinstance(normative, bool):
        errors.append("normative must be boolean")
    if status == "reference" and normative is True:
        errors.append("reference documents cannot be normative")
    for list_field in ("legal_topics", "audience_roles"):
        value = metadata.get(list_field)
        if value is not None and not isinstance(value, list):
            errors.append(f"{list_field} must be a list")
    invalid_roles = set(metadata.get("audience_roles") or []) - AUDIENCE_ROLES
    if invalid_roles:
        errors.append(f"invalid audience_roles: {', '.join(sorted(invalid_roles))}")
    return errors


def is_indexable_normative(metadata: dict[str, Any]) -> bool:
    """Safe default Task 4 policy; callers may explicitly broaden it with review.

    ``unknown``, ``expired`` and ``replaced`` records are intentionally excluded
    to avoid presenting an unverified or obsolete rule as a current rule.
    """
    return bool(metadata.get("normative")) and metadata.get("legal_status") in {"in_force", "partially_effective"}
