"""Offline regression tests for Role 1 / Tasks 1–3.

No test here contacts a remote server or needs a browser binary.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
import yaml

from src import supervisor
from src import task1_collect_legal_docs as task1
from src import task2_crawl_news as task2
from src import task3_convert_markdown as task3
from src.validate_corpus import parse_front_matter, validate_corpus


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + (b"official legal source\n" * 100)


def _metadata(document_id: str, filename: str) -> dict:
    return {
        "document_id": document_id,
        "title": f"Legal source {document_id}",
        "document_number": f"{document_id}/TEST",
        "document_type": "law",
        "issuing_authority": "Quoc hoi",
        "issued_date": "2020-01-01",
        "effective_date": "2021-01-01",
        "expiry_date": None,
        "legal_status": "in_force",
        "normative": True,
        "source_url": "https://example.gov.vn/legal-source",
        "download_url": "https://example.gov.vn/legal-source.pdf",
        "local_filename": filename,
        "amends": [],
        "amended_by": [],
        "replaces": [],
        "replaced_by": [],
        "legal_topics": ["probation"],
        "audience_roles": ["employee"],
    }


@pytest.fixture
def corpus_tree(tmp_path: Path) -> tuple[Path, Path]:
    landing = tmp_path / "landing"
    legal_dir = landing / "legal"
    news_dir = landing / "news"
    standardized = tmp_path / "standardized"
    legal_dir.mkdir(parents=True)
    news_dir.mkdir(parents=True)
    records = []
    for index in range(3):
        filename = f"legal-{index}.pdf"
        path = legal_dir / filename
        path.write_bytes(_pdf_bytes())
        record = _metadata(f"legal_{index}", filename)
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append(record)
    (legal_dir / "legal_sources.json").write_text(json.dumps(records), encoding="utf-8")

    for index in range(5):
        item = {
            "document_id": f"guidance_{index}",
            "url": "https://example.gov.vn/guidance",
            "title": f"Guidance {index}",
            "date_published": "2025-01-01",
            "date_crawled": "2025-01-01T00:00:00+00:00",
            "content_markdown": "Nội dung hướng dẫn chính thức. " * 40,
            "source_domain": "example.gov.vn",
            "issuing_organization": "Cơ quan nhà nước",
            "document_type": "official_guidance",
            "normative": False,
            "legal_status": "reference",
            "legal_topics": ["probation"],
            "audience_roles": ["employee"],
        }
        (news_dir / f"guidance-{index}.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")

    for group, count in (("legal", 3), ("news", 5)):
        (standardized / group).mkdir(parents=True)
        for index in range(count):
            metadata = {
                "document_id": f"{group}_{index}",
                "source": f"{group}-{index}.source",
                "source_path": f"data/landing/{group}/{group}-{index}.source",
                "title": f"{group} source {index}",
                "document_type": "law" if group == "legal" else "official_guidance",
                "legal_status": "in_force" if group == "legal" else "reference",
                "normative": group == "legal",
                "source_url": "https://example.gov.vn/source",
                "legal_topics": ["probation"],
                "audience_roles": ["employee"],
            }
            content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n# Source\n\n" + ("Nội dung có thể kiểm tra. " * 20)
            (standardized / group / f"{group}-{index}.md").write_text(content, encoding="utf-8")
    return landing, standardized


def test_manifest_validation_and_checksum(corpus_tree: tuple[Path, Path]) -> None:
    report = validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1])
    assert report.passed, report.errors
    assert (report.legal_documents, report.guidance_documents, report.standardized_documents) == (3, 5, 8)


def test_duplicate_document_id_is_rejected(corpus_tree: tuple[Path, Path]) -> None:
    manifest = corpus_tree[0] / "legal" / "legal_sources.json"
    records = json.loads(manifest.read_text(encoding="utf-8"))
    records[1]["document_id"] = records[0]["document_id"]
    manifest.write_text(json.dumps(records), encoding="utf-8")
    assert any("Duplicate document_id" in error for error in validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1]).errors)


def test_invalid_legal_status_is_rejected(corpus_tree: tuple[Path, Path]) -> None:
    manifest = corpus_tree[0] / "legal" / "legal_sources.json"
    records = json.loads(manifest.read_text(encoding="utf-8"))
    records[0]["legal_status"] = "definitely-current"
    manifest.write_text(json.dumps(records), encoding="utf-8")
    assert any("legal_status is invalid" in error for error in validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1]).errors)


def test_html_disguised_as_pdf_is_rejected(corpus_tree: tuple[Path, Path]) -> None:
    path = corpus_tree[0] / "legal" / "legal-0.pdf"
    path.write_bytes(b"<html>not a PDF</html>" * 100)
    report = validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1])
    assert any("invalid signature" in error for error in report.errors)


def test_guidance_missing_url_is_rejected(corpus_tree: tuple[Path, Path]) -> None:
    path = corpus_tree[0] / "news" / "guidance-0.json"
    item = json.loads(path.read_text(encoding="utf-8"))
    item["url"] = ""
    path.write_text(json.dumps(item), encoding="utf-8")
    assert any("missing/invalid URL" in error for error in validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1]).errors)


def test_guidance_short_content_is_rejected(corpus_tree: tuple[Path, Path]) -> None:
    path = corpus_tree[0] / "news" / "guidance-0.json"
    item = json.loads(path.read_text(encoding="utf-8"))
    item["content_markdown"] = "short"
    item["audit_note"] = "preserve file-size check order " * 40
    path.write_text(json.dumps(item), encoding="utf-8")
    assert any("content is too short" in error.lower() for error in validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1]).errors)


def test_markdown_missing_front_matter_is_rejected(corpus_tree: tuple[Path, Path]) -> None:
    path = corpus_tree[1] / "legal" / "legal-0.md"
    path.write_text("# Source\n\n" + "content " * 60, encoding="utf-8")
    assert any("front matter" in error for error in validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1]).errors)


def test_convert_guidance_preserves_source_and_normative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    landing = tmp_path / "landing"
    source_dir = landing / "news"
    source_dir.mkdir(parents=True)
    item = {
        "document_id": "guidance_conversion",
        "url": "https://example.gov.vn/guidance",
        "title": "Hướng dẫn chính thức",
        "content_markdown": "Nội dung nguồn công khai. " * 30,
        "document_type": "official_guidance",
        "normative": False,
        "legal_status": "reference",
        "legal_topics": ["probation"],
        "audience_roles": ["probationer"],
    }
    (source_dir / "guidance.json").write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(task3, "LANDING_DIR", landing)
    monkeypatch.setattr(task3, "OUTPUT_DIR", tmp_path / "standardized")
    monkeypatch.setattr(task3, "ROOT_DIR", tmp_path)
    outcomes = task3.convert_guidance_docs()
    assert outcomes[0]["status"] == "success"
    content = (tmp_path / "standardized" / "news" / "guidance.md").read_text(encoding="utf-8")
    metadata, _ = parse_front_matter(content)
    assert metadata is not None
    assert metadata["source_url"] == item["url"]
    assert metadata["normative"] is False


def test_download_error_cannot_overwrite_valid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "valid.pdf"
    original = _pdf_bytes()
    target.write_bytes(original)

    class BrokenSession:
        def get(self, *args, **kwargs):
            raise task1.requests.RequestException("offline")

    monkeypatch.setattr(task1, "_session", lambda retries: BrokenSession())
    with pytest.raises(task1.DownloadError):
        task1.download_document("https://example.gov.vn/source.pdf", target, reuse_existing=False)
    assert target.read_bytes() == original


def test_crawl_failure_keeps_existing_guidance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task2, "DATA_DIR", tmp_path)
    source = task2.GUIDANCE_SOURCES[0]
    target = tmp_path / f"{task2.sanitize_filename(source['document_id'])}.json"
    old = {
        "document_id": source["document_id"],
        "url": source["url"],
        "title": "Old valid guidance",
        "content_markdown": "Nội dung cũ còn hợp lệ. " * 40,
        "normative": False,
    }
    target.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")

    async def fail(*args, **kwargs):
        raise task2.CrawlError("network failure")

    monkeypatch.setattr(task2, "crawl_article", fail)
    outcomes = asyncio.run(task2.crawl_all([source["url"]], force=True))
    assert outcomes[0]["status"] == "failed"
    assert json.loads(target.read_text(encoding="utf-8"))["title"] == "Old valid guidance"


def test_supervisor_inspect_returns_success() -> None:
    assert supervisor.main(["inspect"]) == 0
