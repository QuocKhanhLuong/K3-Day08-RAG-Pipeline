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
from src.legal_markdown_postprocess import postprocess_legal_markdown
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
        "authoritative": True,
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
            "authoritative": False,
            "authority_level": "government_guidance",
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
                "authoritative": group == "legal",
                "authority_level": "national_law" if group == "legal" else "government_guidance",
                "source_url": "https://example.gov.vn/source",
                "legal_topics": ["probation"],
                "audience_roles": ["employee"],
            }
            if group == "legal":
                body = "### Điều 1. Phạm vi điều chỉnh quy định pháp luật\n\n1. Nội dung khoản một...\n\n" + ("Nội dung điều luật pháp luật chi tiết có thể kiểm tra. " * 80)
            else:
                body = "Nội dung hướng dẫn chi tiết có thể kiểm tra. " * 30
            if group == "legal":
                metadata["source_format"] = "txt"
                metadata["body_character_count"] = len("# Title\n\n" + body)
            content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n# Title\n\n" + body
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


def test_scanned_pdf_routed_to_paddleocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PDF scan is routed to PaddleOCR."""
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 scanned content")

    class MockInspection:
        requires_ocr = True
        pdf_type = "scanned"
        total_pages = 2

    class MockOcrResult:
        processed_pages = 2
        total_pages = 2
        native_text_pages = 0
        ocr_pages = 2
        extraction_method = "paddle_ocr"
        status = "success"
        warnings = []
        full_text = "### Điều 1. Phạm vi điều chỉnh\n\nNội dung điều luật pháp luật " * 100

    monkeypatch.setattr(task3, "inspect_pdf", lambda path: MockInspection())
    monkeypatch.setattr(task3, "ocr_pdf_with_paddle", lambda path: MockOcrResult())

    source_meta = {
        "document_id": "test_scanned",
        "title": "Test scanned PDF",
        "source_page_url": "https://example.gov.vn",
    }

    markdown, metadata = task3._convert_legal_source(pdf_path, source_meta)
    assert metadata["extraction_method"] == "paddle_ocr"
    assert "Điều 1" in markdown


def test_text_pdf_bypasses_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PDF with text does not call OCR."""
    pdf_path = tmp_path / "text.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 text content")

    class MockInspection:
        requires_ocr = False
        pdf_type = "born_digital"
        total_pages = 1

    monkeypatch.setattr(task3, "inspect_pdf", lambda path: MockInspection())

    def mock_ocr(path):
        raise RuntimeError("Should not call OCR")

    monkeypatch.setattr(task3, "ocr_pdf_with_paddle", mock_ocr)
    monkeypatch.setattr(task3, "_convert_with_markitdown", lambda path: "### Điều 10. Nội dung khoản\n\n" + ("Nội dung pháp luật có text layer. " * 80))

    source_meta = {
        "document_id": "test_text",
        "title": "Test text PDF",
        "source_page_url": "https://example.gov.vn",
    }

    markdown, metadata = task3._convert_legal_source(pdf_path, source_meta)
    assert metadata["extraction_method"] == "markitdown_native"


def test_yaml_long_body_empty_fails_validation(corpus_tree: tuple[Path, Path]) -> None:
    """YAML long but body empty must fail."""
    path = corpus_tree[1] / "legal" / "legal-0.md"
    metadata = {
        "document_id": "long_yaml_empty_body",
        "title": "Test long yaml",
        "document_type": "law",
        "legal_status": "in_force",
        "normative": True,
        "source_url": "https://example.gov.vn",
        "legal_topics": ["probation"] * 50,
        "audience_roles": ["employee"] * 50,
    }
    content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\n\n"
    path.write_text(content, encoding="utf-8")
    report = validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1])
    assert any("too short" in error for error in report.errors)


def test_legal_body_missing_dieu_fails_validation(corpus_tree: tuple[Path, Path]) -> None:
    """Legal body without 'Điều' must fail."""
    path = corpus_tree[1] / "legal" / "legal-0.md"
    metadata = {
        "document_id": "no_dieu_body",
        "title": "Test body without dieu",
        "document_type": "law",
        "legal_status": "in_force",
        "normative": True,
        "source_url": "https://example.gov.vn",
    }
    body = "Đây là văn bản bản pháp luật nhưng không chứa từ khoá điều luật nào cả. " * 50
    content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\n\n" + body
    path.write_text(content, encoding="utf-8")
    report = validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1])
    assert any("missing 'Điều" in error for error in report.errors)


def test_processed_pages_incomplete_fails_validation(corpus_tree: tuple[Path, Path]) -> None:
    """Incomplete processed pages must fail."""
    path = corpus_tree[1] / "legal" / "legal-0.md"
    metadata = {
        "document_id": "incomplete_pages",
        "title": "Test incomplete pages",
        "document_type": "law",
        "legal_status": "in_force",
        "normative": True,
        "source_url": "https://example.gov.vn",
        "pdf_pages": 10,
        "processed_pages": 8,
    }
    body = "### Điều 1. Quy định\n\n" + ("Nội dung pháp luật hợp lệ. " * 80)
    content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\n\n" + body
    path.write_text(content, encoding="utf-8")
    report = validate_corpus(landing_dir=corpus_tree[0], standardized_dir=corpus_tree[1])
    assert any("processed pages count mismatch" in error.lower() for error in report.errors)


def test_guidance_boilerplate_removed() -> None:
    """Guidance cleans menu and footer boilerplate."""
    raw_guidance = (
        "Nội dung bài viết hướng dẫn chính thức.\n\n"
        "Quyền lợi của người lao động khi thử việc...\n\n"
        "Tham khảo thêm\n"
        "Bài viết khác liên quan 1\n"
        "Tin liên quan"
    )
    cleaned = task3.clean_guidance_markdown(raw_guidance)
    assert "Tham khảo thêm" not in cleaned
    assert "Tin liên quan" not in cleaned
    assert "Nội dung bài viết hướng dẫn chính thức." in cleaned


def test_legal_postprocess_keeps_articles_and_removes_pdf_page_chrome() -> None:
    raw_text = """CÔNG BÁO/Số 131/Ngày 28-02-2026

22

CHƯƠNG I

NHỮNG QUY ĐỊNH CHUNG

Điều 1. Phạm vi điều chỉnh

Nội dung điều luật thứ nhất.

CÔNG BÁO/Số 131/Ngày 28-02-2026

23

Điều 2. Đối tượng áp dụng cho người lao động

làm việc từ xa

Nội dung điều luật thứ hai.
"""

    markdown, article_count = postprocess_legal_markdown(raw_text)

    assert "CÔNG BÁO" not in markdown
    assert "\n22\n" not in markdown
    assert "# CHƯƠNG I — NHỮNG QUY ĐỊNH CHUNG" in markdown
    assert "### Điều 1. Phạm vi điều chỉnh" in markdown
    assert "### Điều 2. Đối tượng áp dụng cho người lao động làm việc từ xa" in markdown
    assert article_count == 2


def test_pdf_is_gitignored() -> None:
    """PDF files under data/landing/legal/ are gitignored."""
    gitignore_path = task3.ROOT_DIR / ".gitignore"
    content = gitignore_path.read_text(encoding="utf-8")
    assert "data/landing/legal/*.pdf" in content
    assert "data/landing/legal/*.docx" in content
    assert "data/processed/" in content
