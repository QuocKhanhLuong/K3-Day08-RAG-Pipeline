"""Small, data-only orchestrator owned by Role 1.

It stops at a validated Markdown corpus.  It deliberately does not import or
run Tasks 4–10, which belong to other members of the team.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent


def _print_outcomes(label: str, outcomes: Sequence[dict]) -> bool:
    succeeded = [item for item in outcomes if item.get("status") == "success"]
    skipped = [item for item in outcomes if item.get("status") == "skipped"]
    failed = [item for item in outcomes if item.get("status") == "failed"]
    print(f"{label}: {len(succeeded)} succeeded, {len(skipped)} skipped, {len(failed)} failed")
    for item in failed:
        print(f"  - {item.get('document_id') or item.get('source')}: {item.get('reason')}")
    return not failed


def collect_legal(force: bool) -> bool:
    from src.task1_collect_legal_docs import collect_legal_documents

    report = collect_legal_documents(force=force)
    outcomes = [dict(item, status="success") for item in report["success"]]
    outcomes += [dict(item, status="skipped") for item in report["skipped"]]
    outcomes += [dict(item, status="failed") for item in report["failed"]]
    return _print_outcomes("Legal collection", outcomes)


def crawl_guidance(force: bool) -> bool:
    from src.task2_crawl_news import crawl_all

    return _print_outcomes("Guidance collection", asyncio.run(crawl_all(force=force)))


def standardize() -> bool:
    from src.task3_convert_markdown import convert_all

    report = convert_all()
    outcomes = report["success"] + report["skipped"] + report["failed"]
    return _print_outcomes("Markdown standardization", outcomes)


def validate() -> bool:
    from src.validate_corpus import format_report, validate_corpus

    report = validate_corpus()
    print(format_report(report))
    return report.passed


def status() -> None:
    legal = list((ROOT_DIR / "data" / "landing" / "legal").glob("*.pdf")) + list((ROOT_DIR / "data" / "landing" / "legal").glob("*.docx"))
    guidance = list((ROOT_DIR / "data" / "landing" / "news").glob("*.json"))
    markdown = list((ROOT_DIR / "data" / "standardized").rglob("*.md"))
    source_files = legal + guidance + markdown
    latest = max((path.stat().st_mtime for path in source_files), default=None)
    latest_text = datetime.fromtimestamp(latest, tz=timezone.utc).isoformat() if latest else "not available"
    index_manifest = ROOT_DIR / "chroma_db" / "index_manifest.json"
    print(f"Legal documents: {len(legal)}")
    print(f"Guidance documents: {len(guidance)}")
    print(f"Standardized Markdown: {len(markdown)}")
    print(f"Latest corpus update (UTC): {latest_text}")
    print(f"Task 4 index manifest: {'present' if index_manifest.exists() else 'not created'}")


def inspect() -> None:
    print("Role 1 / Data Engineering scope")
    print("Owned: architecture handoff, Task 1 collection, Task 2 guidance crawl, Task 3 Markdown, validation, data orchestration.")
    print("Handoff to Task 4: data/standardized/{legal,news}/*.md plus data/landing/legal/legal_sources.json")
    print("Default indexing policy: only normative=true with legal_status in_force or partially_effective; preserve all legal metadata.")
    print("Not run here: embeddings, Chroma indexing, semantic/BM25 retrieval, RRF, PageIndex, generation, app, evaluation.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Data-only supervisor for the legal RAG corpus")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("collect-legal", "crawl-guidance", "prepare-data"):
        command = subparsers.add_parser(name)
        command.add_argument("--force", action="store_true", help="Request fresh sources; failed refreshes never delete a valid file")
    for name in ("standardize", "validate", "status", "inspect"):
        subparsers.add_parser(name)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "collect-legal":
        return 0 if collect_legal(args.force) else 1
    if args.command == "crawl-guidance":
        return 0 if crawl_guidance(args.force) else 1
    if args.command == "standardize":
        return 0 if standardize() else 1
    if args.command == "validate":
        return 0 if validate() else 1
    if args.command == "status":
        status()
        return 0
    if args.command == "inspect":
        inspect()
        return 0
    # prepare-data is intentionally sequential so a failed collection cannot
    # be mistaken for a validated corpus. Existing valid files are skipped.
    collected = collect_legal(args.force)
    crawled = crawl_guidance(args.force)
    standardized = standardize()
    validated = validate()
    return 0 if all((collected, crawled, standardized, validated)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
