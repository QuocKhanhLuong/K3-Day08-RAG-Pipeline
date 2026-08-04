"""Task 2: collect the approved official government guidance articles.

The historical filename is retained for the lab.  These records are guidance,
not legal instruments: each emitted JSON is explicitly non-normative and must
not be used to replace a statute, decree or circular in a later RAG answer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.labor_law_sources import GUIDANCE_SOURCES

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "landing" / "news"
CRAWL4AI_RUNTIME_DIR = ROOT_DIR / ".crawl4ai_runtime"
MIN_FILE_BYTES = 500
MIN_CONTENT_CHARS = 350
REQUEST_TIMEOUT_SECONDS = 45
MAX_RETRIES = 2
USER_AGENT = "VietnamYouthLaborLawCorpus/2.0 (+https://github.com/QuocKhanhLuong/K3-Day08-RAG-Pipeline)"
ARTICLE_URLS = [source["url"] for source in GUIDANCE_SOURCES]


class CrawlError(RuntimeError):
    """An official guidance article could not be collected safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def setup_directory() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def sanitize_filename(value: str, *, max_length: int = 90) -> str:
    """Create a portable JSON filename stem without relying on a page title."""
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower().strip())
    return normalized.strip("-")[:max_length] or "guidance"


def _compact_markdown(content: str) -> str:
    """Remove repeated chrome while retaining paragraph boundaries and wording."""
    blocked = (
        "cookie",
        "chính sách cookie",
        "đăng nhập",
        "đăng ký",
        "quảng cáo",
        "bài liên quan",
        "xem thêm",
        "chia sẻ bài viết",
    )
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        key = line.lower()
        if not line or key in seen or any(marker in key for marker in blocked):
            continue
        seen.add(key)
        lines.append(line)
    return "\n\n".join(lines).strip()


def _date_from_html(soup: BeautifulSoup) -> str | None:
    for selector, attribute in (
        ("meta[property='article:published_time']", "content"),
        ("meta[name='publishdate']", "content"),
        ("meta[name='date']", "content"),
        ("time[datetime]", "datetime"),
    ):
        node = soup.select_one(selector)
        value = str(node.get(attribute, "")).strip() if node else ""
        match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", value)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return None


async def _crawl_with_crawl4ai(url: str) -> tuple[str, str, str | None]:
    """Use Crawl4AI when its browser runtime is available, with normal TLS."""
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(CRAWL4AI_RUNTIME_DIR))
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except Exception as exc:
        raise CrawlError(f"Crawl4AI import failed: {exc}") from exc
    CRAWL4AI_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    browser = BrowserConfig(headless=True, ignore_https_errors=False, verbose=False, user_agent=USER_AGENT)
    config = CrawlerRunConfig(
        only_text=True,
        css_selector="article",
        excluded_tags=["nav", "footer", "header", "aside", "form", "script", "style"],
        excluded_selector=".cookie, .cookies, .advertisement, .ads, .related, .social, .share",
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
        page_timeout=REQUEST_TIMEOUT_SECONDS * 1000,
        verbose=False,
    )
    try:
        async with AsyncWebCrawler(config=browser, base_directory=str(CRAWL4AI_RUNTIME_DIR)) as crawler:
            result = await asyncio.wait_for(crawler.arun(url=url, config=config), timeout=REQUEST_TIMEOUT_SECONDS + 20)
    except Exception as exc:
        message = str(exc)
        if "executable doesn't exist" in message.lower() or "browser" in message.lower():
            message += ". Install a browser with: playwright install chromium"
        raise CrawlError(f"Crawl4AI failed for {url}: {message}") from exc
    if not getattr(result, "success", False):
        raise CrawlError(f"Crawl4AI returned unsuccessful result for {url}: {getattr(result, 'error_message', '')}")
    markdown = getattr(result, "fit_markdown", None) or getattr(result, "markdown", None) or ""
    content = _compact_markdown(str(markdown))
    metadata = getattr(result, "metadata", None) or {}
    title = str(metadata.get("title") or "").strip()
    published = str(metadata.get("published_time") or metadata.get("date") or "").strip() or None
    if not published:
        raw_html = getattr(result, "cleaned_html", None) or getattr(result, "html", None)
        if raw_html:
            published = _date_from_html(BeautifulSoup(str(raw_html), "html.parser"))
    if (
        "báo điện tử chính phủ" in content[:800].lower()
        or "trang chủ" in content[:800].lower()
        or content.lstrip().startswith("* [")
    ):
        raise CrawlError("Crawl4AI output still contains page navigation; routing to article-only HTML extraction")
    if len(content) < MIN_CONTENT_CHARS:
        raise CrawlError(f"Crawl4AI article body is too short ({len(content)} characters): {url}")
    return title, content, published


def _requests_article(url: str) -> tuple[str, str, str | None]:
    """Read a normal public HTML response without bypassing access controls."""
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CrawlError(f"Static HTML retrieval failed for {url}: {exc}") from exc
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise CrawlError(f"Expected a public HTML article, got {response.headers.get('Content-Type', 'missing')}")
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup.select(
        "script, style, noscript, nav, footer, header, aside, form, [role='navigation'], "
        ".cookie, .cookies, .advertisement, .ads, .related, .social, .share"
    ):
        node.decompose()
    title_node = soup.select_one("h1") or soup.select_one("title")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    article = soup.select_one("article") or soup.select_one("main") or soup.select_one(".detail-content") or soup.body
    content = _compact_markdown(article.get_text("\n", strip=True) if article else "")
    if len(content) < MIN_CONTENT_CHARS:
        raise CrawlError(f"Static HTML article body is too short ({len(content)} characters): {url}")
    return title, content, _date_from_html(soup)


def _source_for_url(url: str) -> dict[str, Any]:
    for source in GUIDANCE_SOURCES:
        if source["url"] == url:
            return dict(source)
    raise CrawlError(f"URL is not in the approved guidance catalog: {url}")


async def crawl_article(url: str, *, source: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the fixed, non-normative guidance record schema for one URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "baochinhphu.vn":
        raise CrawlError(f"Only approved Báo Điện tử Chính phủ HTTPS URLs are accepted: {url}")
    descriptor = dict(source or _source_for_url(url))
    method = "crawl4ai"
    try:
        title, content, date_published = await _crawl_with_crawl4ai(url)
    except CrawlError as crawler_error:
        print(f"⚠ {crawler_error}")
        print("  Fallback: normal HTTPS HTML retrieval only. If Chromium is missing, run: playwright install chromium")
        title, content, date_published = await asyncio.to_thread(_requests_article, url)
        method = "requests_html_fallback"
    return {
        "document_id": descriptor["document_id"],
        "url": url,
        "title": title or descriptor["document_id"].replace("_", " ").title(),
        "date_published": date_published,
        "date_crawled": utc_now(),
        "content_markdown": content,
        "source_domain": "baochinhphu.vn",
        "issuing_organization": "Báo Điện tử Chính phủ",
        "document_type": "official_guidance",
        "normative": False,
        "authoritative": False,
        "authority_level": "government_guidance",
        "legal_status": "reference",
        "legal_topics": list(descriptor.get("legal_topics", [])),
        "audience_roles": list(descriptor.get("audience_roles", [])),
        "crawl_method": method,
    }


def _valid_guidance_file(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= MIN_FILE_BYTES:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        data.get("document_id")
        and data.get("url")
        and data.get("title")
        and len(str(data.get("content_markdown", ""))) >= MIN_CONTENT_CHARS
        and data.get("normative") is False
        and data.get("authoritative") is False
        and data.get("legal_status") == "reference"
    )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, path)


async def crawl_all(
    urls: list[str] | None = None,
    max_concurrency: int = 3,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Crawl catalog URLs concurrently, retaining valid data after failures."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")
    setup_directory()
    selected_urls = urls or ARTICLE_URLS
    semaphore = asyncio.Semaphore(max_concurrency)
    outcomes: list[dict[str, Any]] = []

    async def worker(url: str) -> None:
        try:
            descriptor = _source_for_url(url)
        except CrawlError as exc:
            outcomes.append({"url": url, "status": "failed", "reason": str(exc)})
            return
        output_path = DATA_DIR / f"{sanitize_filename(descriptor['document_id'])}.json"
        if not force and _valid_guidance_file(output_path):
            outcomes.append({"document_id": descriptor["document_id"], "url": url, "status": "skipped", "path": str(output_path)})
            return
        async with semaphore:
            try:
                article = await crawl_article(url, source=descriptor)
                if len(json.dumps(article, ensure_ascii=False).encode("utf-8")) <= MIN_FILE_BYTES:
                    raise CrawlError("Serialized guidance record is too small")
                _write_json_atomic(output_path, article)
                outcomes.append(
                    {
                        "document_id": article["document_id"],
                        "url": url,
                        "status": "success",
                        "path": str(output_path),
                        "crawl_method": article["crawl_method"],
                    }
                )
            except Exception as exc:
                # Deliberately retain a previously valid JSON at output_path.
                outcomes.append({"document_id": descriptor["document_id"], "url": url, "status": "failed", "reason": str(exc)})

    await asyncio.gather(*(worker(url) for url in selected_urls))
    return sorted(outcomes, key=lambda result: str(result.get("document_id") or result["url"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl approved official labour-law guidance pages.")
    parser.add_argument("--force", action="store_true", help="Refresh valid local JSON files.")
    args = parser.parse_args(argv)
    outcomes = asyncio.run(crawl_all(force=args.force))
    failures = [item for item in outcomes if item["status"] == "failed"]
    print("Task 2 — Official guidance collection")
    print(f"success: {sum(item['status'] == 'success' for item in outcomes)}")
    print(f"skipped: {sum(item['status'] == 'skipped' for item in outcomes)}")
    print(f"failed: {len(failures)}")
    for outcome in failures:
        print(f"  - {outcome.get('document_id', outcome['url'])}: {outcome.get('reason')}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
