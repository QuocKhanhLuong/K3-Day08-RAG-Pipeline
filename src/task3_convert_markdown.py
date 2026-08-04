"""Task 3: standardize legal source files and official guidance as Markdown.

The converter preserves source wording and hierarchy.  It adds only YAML front
matter and a missing document title, making the corpus safe to hand to the
article/clause-aware chunker owned by Task 4.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
LANDING_DIR = ROOT_DIR / "data" / "landing"
OUTPUT_DIR = ROOT_DIR / "data" / "standardized"
LEGAL_MANIFEST_PATH = LANDING_DIR / "legal" / "legal_sources.json"
SUPPORTED_LEGAL_SUFFIXES = {".pdf", ".docx", ".doc", ".html", ".htm", ".txt", ".md"}
MIN_MARKDOWN_CHARS = 200


def _front_matter(metadata: dict[str, Any]) -> str:
    """Serialize only data metadata; document content is never YAML-escaped."""
    ordered = {
        "document_id": metadata.get("document_id"),
        "source": metadata.get("source"),
        "title": metadata.get("title"),
        "document_number": metadata.get("document_number"),
        "document_type": metadata.get("document_type"),
        "issuing_authority": metadata.get("issuing_authority"),
        "issued_date": metadata.get("issued_date"),
        "effective_date": metadata.get("effective_date"),
        "expiry_date": metadata.get("expiry_date"),
        "legal_status": metadata.get("legal_status"),
        "normative": bool(metadata.get("normative", False)),
        "source_url": metadata.get("source_url"),
        "local_source_file": metadata.get("local_source_file"),
        "source_path": metadata.get("source_path"),
        "legal_topics": list(metadata.get("legal_topics") or []),
        "audience_roles": list(metadata.get("audience_roles") or []),
    }
    return "---\n" + yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, default_flow_style=False).strip() + "\n---\n\n"


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".md", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_name = handle.name
    Path(temp_name).replace(path)


def _source_path_for_metadata(path: Path) -> str:
    """Prefer repository-relative paths while keeping isolated tests usable."""
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)


def _load_legal_manifest() -> dict[str, dict[str, Any]]:
    if not LEGAL_MANIFEST_PATH.exists():
        return {}
    try:
        records = json.loads(LEGAL_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(item.get("local_filename")): item for item in records if item.get("local_filename")}


def _convert_with_markitdown(path: Path) -> str:
    """Convert a supported original file lazily, avoiding import-time cost."""
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    try:
        from markitdown import MarkItDown
    except Exception as exc:
        raise RuntimeError("MarkItDown is required for PDF/DOCX/HTML conversion. Install requirements.txt.") from exc
    result = MarkItDown().convert(str(path))
    return str(result.text_content)


def _assemble_markdown(metadata: dict[str, Any], original_content: str) -> str:
    content = original_content.replace("\r\n", "\n").replace("\r", "\n").strip()
    title = str(metadata.get("title") or "Untitled source").strip()
    if not content.startswith("#"):
        content = f"# {title}\n\n{content}"
    return _front_matter(metadata) + content.strip() + "\n"


def convert_legal_docs() -> list[dict[str, str]]:
    """Convert supported legal originals and preserve every manifest field needed downstream."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_legal_manifest()
    outcomes: list[dict[str, str]] = []
    if not legal_dir.exists():
        return [{"status": "failed", "source": str(legal_dir), "reason": "Legal landing directory does not exist"}]

    for source_path in sorted(legal_dir.iterdir()):
        if not source_path.is_file() or source_path.name == LEGAL_MANIFEST_PATH.name:
            continue
        if source_path.suffix.lower() not in SUPPORTED_LEGAL_SUFFIXES:
            outcomes.append({"status": "skipped", "source": source_path.name, "reason": f"Unsupported extension {source_path.suffix}"})
            continue
        source = manifest.get(source_path.name)
        if not source:
            outcomes.append({"status": "skipped", "source": source_path.name, "reason": "No legal_sources.json entry"})
            continue
        metadata = dict(source)
        metadata["source"] = source_path.name
        metadata["local_source_file"] = source_path.name
        metadata["source_path"] = _source_path_for_metadata(source_path)
        try:
            markdown = _assemble_markdown(metadata, _convert_with_markitdown(source_path))
            if len(markdown) <= MIN_MARKDOWN_CHARS:
                raise ValueError(f"Converted Markdown is too short: {len(markdown)} characters")
            output_path = output_dir / f"{source_path.stem}.md"
            _write_text_atomic(output_path, markdown)
            outcomes.append({"status": "success", "source": source_path.name, "output": str(output_path)})
        except Exception as exc:
            outcomes.append({"status": "failed", "source": source_path.name, "reason": str(exc)})
    return outcomes


def convert_guidance_docs() -> list[dict[str, str]]:
    """Convert crawled JSON guidance files to Markdown with explicit non-normative metadata."""
    guidance_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[dict[str, str]] = []
    if not guidance_dir.exists():
        return [{"status": "failed", "source": str(guidance_dir), "reason": "Guidance landing directory does not exist"}]

    for source_path in sorted(guidance_dir.iterdir()):
        if not source_path.is_file():
            continue
        if source_path.suffix.lower() != ".json":
            outcomes.append({"status": "skipped", "source": source_path.name, "reason": "Only JSON guidance is standardized"})
            continue
        try:
            data = json.loads(source_path.read_text(encoding="utf-8"))
            content = str(data.get("content_markdown") or "")
            metadata = {
                "document_id": data.get("document_id"),
                "source": source_path.name,
                "title": data.get("title"),
                "document_number": None,
                "document_type": data.get("document_type", "official_guidance"),
                "issuing_authority": data.get("issuing_organization"),
                "issued_date": data.get("date_published"),
                "effective_date": None,
                "expiry_date": None,
                "legal_status": data.get("legal_status", "reference"),
                "normative": data.get("normative", False),
                "source_url": data.get("url"),
                "local_source_file": source_path.name,
                "source_path": _source_path_for_metadata(source_path),
                "legal_topics": data.get("legal_topics", []),
                "audience_roles": data.get("audience_roles", []),
            }
            if not metadata["document_id"] or not metadata["source_url"]:
                raise ValueError("JSON guidance is missing document_id or url")
            markdown = _assemble_markdown(metadata, content)
            if len(markdown) <= MIN_MARKDOWN_CHARS:
                raise ValueError(f"Converted Markdown is too short: {len(markdown)} characters")
            output_path = output_dir / f"{source_path.stem}.md"
            _write_text_atomic(output_path, markdown)
            outcomes.append({"status": "success", "source": source_path.name, "output": str(output_path)})
        except Exception as exc:
            outcomes.append({"status": "failed", "source": source_path.name, "reason": str(exc)})
    return outcomes


def convert_news_articles() -> list[dict[str, str]]:
    """Backward-compatible alias retained for the original lab handout."""
    return convert_guidance_docs()


def convert_all() -> dict[str, Any]:
    """Standardize all landing files without stopping on individual failures."""
    legal = convert_legal_docs()
    guidance = convert_guidance_docs()
    all_outcomes = legal + guidance
    return {
        "success": [item for item in all_outcomes if item["status"] == "success"],
        "failed": [item for item in all_outcomes if item["status"] == "failed"],
        "skipped": [item for item in all_outcomes if item["status"] == "skipped"],
        "output_directory": str(OUTPUT_DIR),
    }


def main() -> int:
    report = convert_all()
    print("Task 3 — Markdown standardization")
    print(f"success: {len(report['success'])}")
    print(f"failed: {len(report['failed'])}")
    print(f"skipped: {len(report['skipped'])}")
    for failed in report["failed"]:
        print(f"  - {failed['source']}: {failed['reason']}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
