"""Task 2: collect official, non-normative labour-law guidance.

The historical module name is retained for lab compatibility.  Every stored
item is explicitly ``normative: false``: it can help retrieval but must never
override the legal source documents collected in Task 1.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "landing" / "news"
CRAWL4AI_RUNTIME_DIR = ROOT_DIR / ".crawl4ai_runtime"
MIN_FILE_BYTES = 500
MIN_CONTENT_CHARS = 350
REQUEST_TIMEOUT_SECONDS = 45
USER_AGENT = "VietnamYouthLaborLawCorpus/1.0 (+https://github.com/QuocKhanhLuong/K3-Day08-RAG-Pipeline)"


# Chinhphu.vn is the official Government Portal.  These are supplementary
# guidance/answers, not the normative source for a legal conclusion.
GUIDANCE_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "document_id": "guidance_labor_code_rights_2021",
        "url": "https://baochinhphu.vn/tu-2021-them-nhieu-quyen-loi-cho-nguoi-lao-dong-102285092.htm",
        "date_published": "2021-01-01",
        "issuing_organization": "Báo Điện tử Chính phủ",
        "legal_topics": ["probation", "employment_contract", "annual_leave", "overtime"],
        "audience_roles": ["job_applicant", "probationer", "employee"],
    },
    {
        "document_id": "guidance_overtime_limits_2023",
        "url": "https://baochinhphu.vn/khi-nao-doanh-nghiep-duoc-dang-ky-tang-gio-lam-them-102230316160746128.htm",
        "date_published": "2023-03-16",
        "issuing_organization": "Báo Điện tử Chính phủ",
        "legal_topics": ["overtime", "night_work"],
        "audience_roles": ["employee", "employer"],
    },
    {
        "document_id": "guidance_unilateral_termination_2023",
        "url": "https://baochinhphu.vn/the-nao-la-don-phuong-cham-dut-hop-dong-lao-dong-dung-luat-102230428144412753.htm",
        "date_published": "2023-04-30",
        "issuing_organization": "Báo Điện tử Chính phủ",
        "legal_topics": ["unilateral_termination", "contract_termination"],
        "audience_roles": ["employee", "former_employee"],
    },
    {
        "document_id": "guidance_annual_leave_payment_2025",
        "url": "https://baochinhphu.vn/khong-nghi-het-phep-nam-co-duoc-thanh-toan-tien-10225090516273483.htm",
        "date_published": "2025-09-05",
        "issuing_organization": "Báo Điện tử Chính phủ",
        "legal_topics": ["annual_leave", "contract_termination"],
        "audience_roles": ["employee", "former_employee"],
    },
    {
        "document_id": "guidance_salary_delay_force_majeure_2026",
        "url": "https://baochinhphu.vn/the-nao-la-cham-tra-luong-do-truong-hop-bat-kha-khang-102260303133428943.htm",
        "date_published": "2026-03-05",
        "issuing_organization": "Báo Điện tử Chính phủ",
        "legal_topics": ["salary", "salary_delay", "unilateral_termination"],
        "audience_roles": ["employee", "employer"],
    },
    {
        "document_id": "guidance_probation_insurance_2026",
        "url": "https://baochinhphu.vn/thu-viec-khong-dong-bao-hiem-nguoi-lao-dong-co-duoc-chi-tra-bu-102260211100941544.htm",
        "date_published": "2026-02-11",
        "issuing_organization": "Báo Điện tử Chính phủ",
        "legal_topics": ["probation", "employment_contract"],
        "audience_roles": ["probationer", "employee"],
    },
)
ARTICLE_URLS = [item["url"] for item in GUIDANCE_SOURCES]


class CrawlError(RuntimeError):
    """A guidance page could not be obtained as a sufficiently useful article."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def setup_directory() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def sanitize_filename(value: str, *, max_length: int = 90) -> str:
    """Return a portable, readable JSON filename stem."""
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")[:max_length] or "guidance"


def _compact_markdown(content: str) -> str:
    banned = ("cookie", "chính sách cookie", "đăng nhập", "đăng ký", "menu", "trang chủ", "quảng cáo")
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw_line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        compact_key = line.lower()
        if not line or compact_key in seen or any(token in compact_key for token in banned):
            continue
        seen.add(compact_key)
        cleaned.append(line)
    return "\n\n".join(cleaned).strip()


async def _crawl_with_crawl4ai(url: str) -> tuple[str, str]:
    """Use the installed Crawl4AI 0.7 API with TLS verification enabled."""
    # Crawl4AI 0.7 creates a database when imported.  Scope it to an ignored
    # workspace runtime directory and keep this import out of module import time.
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(CRAWL4AI_RUNTIME_DIR))
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except Exception as exc:  # dependency/import error is reported, not hidden
        raise CrawlError(f"Crawl4AI import failed: {exc}") from exc

    CRAWL4AI_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    browser = BrowserConfig(
        headless=True,
        ignore_https_errors=False,
        verbose=False,
        user_agent=USER_AGENT,
    )
    run_config = CrawlerRunConfig(
        only_text=True,
        excluded_tags=["nav", "footer", "header", "aside", "form", "script", "style"],
        remove_overlay_elements=True,
        cache_mode=CacheMode.BYPASS,
        page_timeout=REQUEST_TIMEOUT_SECONDS * 1000,
        verbose=False,
    )
    try:
        async with AsyncWebCrawler(config=browser, base_directory=str(CRAWL4AI_RUNTIME_DIR)) as crawler:
            result = await asyncio.wait_for(crawler.arun(url=url, config=run_config), timeout=REQUEST_TIMEOUT_SECONDS + 20)
    except Exception as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "browser" in message.lower():
            message += ". Install a browser with: playwright install chromium"
        raise CrawlError(f"Crawl4AI failed for {url}: {message}") from exc

    if not getattr(result, "success", False):
        raise CrawlError(f"Crawl4AI returned unsuccessful result for {url}: {getattr(result, 'error_message', '')}")
    markdown = getattr(result, "fit_markdown", None) or getattr(result, "markdown", None) or ""
    content = _compact_markdown(str(markdown))
    metadata = getattr(result, "metadata", None) or {}
    title = str(metadata.get("title") or "").strip()
    if len(content) < MIN_CONTENT_CHARS:
        raise CrawlError(f"Crawl4AI content too short for {url}: {len(content)} characters")
    return title, content


def _requests_article(url: str) -> tuple[str, str]:
    """Transparent static-HTML fallback when the crawler browser is unavailable.

    This is not a WAF bypass: it uses a normal HTTPS GET, honours HTTP errors,
    and does not attempt to access pages that reject that request.
    """
    retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({"GET"}), raise_on_status=False)
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CrawlError(f"Static HTML fallback failed for {url}: {exc}") from exc
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise CrawlError(f"Expected an HTML guidance page, got {response.headers.get('Content-Type', 'missing')}")

    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup.select("script, style, noscript, nav, footer, header, aside, form, [role='navigation'], .cookie, .cookies, .advertisement, .ads"):
        node.decompose()
    title_node = soup.select_one("h1") or soup.select_one("title")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    article = soup.select_one("article") or soup.select_one("main") or soup.body
    content = _compact_markdown(article.get_text("\n", strip=True) if article else "")
    if len(content) < MIN_CONTENT_CHARS:
        raise CrawlError(f"Static HTML content too short for {url}: {len(content)} characters")
    return title, content


def _source_for_url(url: str) -> dict[str, Any]:
    for source in GUIDANCE_SOURCES:
        if source["url"] == url:
            return dict(source)
    return {
        "document_id": f"guidance_{sanitize_filename(urlparse(url).path)}",
        "url": url,
        "date_published": None,
        "issuing_organization": urlparse(url).netloc,
        "legal_topics": [],
        "audience_roles": [],
    }


async def crawl_article(url: str, *, source: dict[str, Any] | None = None) -> dict[str, Any]:
    """Crawl one official guidance page and return the shared JSON schema."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise CrawlError(f"Only absolute HTTPS URLs are accepted: {url}")
    descriptor = dict(source or _source_for_url(url))
    method = "crawl4ai"
    crawler_error: CrawlError | None = None
    for attempt in range(2):
        try:
            title, content = await _crawl_with_crawl4ai(url)
            crawler_error = None
            break
        except CrawlError as exc:
            crawler_error = exc
            if "playwright install chromium" in str(exc).lower() or attempt == 1:
                break
            await asyncio.sleep(0.5 * (attempt + 1))
    if crawler_error is not None:
        # Browser setup can be absent on a fresh lab environment.  Preserve the
        # exact reason in the saved report and use a normal public HTML request.
        print(f"⚠ {crawler_error}")
        print("  Fallback: normal HTTPS HTML retrieval (no WAF bypass). If needed run: playwright install chromium")
        title, content = await asyncio.to_thread(_requests_article, url)
        method = "requests_html_fallback"

    return {
        "document_id": descriptor["document_id"],
        "url": url,
        "title": title or descriptor["document_id"].replace("_", " ").title(),
        "date_published": descriptor.get("date_published"),
        "date_crawled": utc_now(),
        "content_markdown": content,
        "source_domain": parsed.netloc.lower(),
        "issuing_organization": descriptor.get("issuing_organization") or parsed.netloc,
        "document_type": "official_guidance",
        "normative": False,
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
    return bool(data.get("url") and data.get("title") and len(str(data.get("content_markdown", ""))) >= MIN_CONTENT_CHARS and data.get("normative") is False)


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


async def crawl_all(
    urls: list[str] | None = None,
    max_concurrency: int = 3,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Crawl multiple sources concurrently without replacing a good old file."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")
    setup_directory()
    selected_urls = urls or ARTICLE_URLS
    semaphore = asyncio.Semaphore(max_concurrency)
    outcomes: list[dict[str, Any]] = []

    async def worker(url: str) -> None:
        descriptor = _source_for_url(url)
        filename = f"{sanitize_filename(descriptor['document_id'])}.json"
        output_path = DATA_DIR / filename
        if not force and _valid_guidance_file(output_path):
            outcomes.append({"url": url, "document_id": descriptor["document_id"], "status": "skipped", "path": str(output_path)})
            return
        async with semaphore:
            try:
                article = await crawl_article(url, source=descriptor)
                serialized = json.dumps(article, ensure_ascii=False, indent=2).encode("utf-8")
                if len(serialized) <= MIN_FILE_BYTES:
                    raise CrawlError(f"Serialized guidance is too small: {len(serialized)} bytes")
                _write_json_atomic(output_path, article)
                outcomes.append({"url": url, "document_id": article["document_id"], "status": "success", "path": str(output_path), "crawl_method": article["crawl_method"]})
            except Exception as exc:
                # Do not remove a valid historical result when a refresh fails.
                outcomes.append({"url": url, "document_id": descriptor["document_id"], "status": "failed", "reason": str(exc)})

    await asyncio.gather(*(worker(url) for url in selected_urls))
    return sorted(outcomes, key=lambda item: str(item["document_id"]))


def main() -> int:
    outcomes = asyncio.run(crawl_all())
    print("Task 2 — Official guidance collection")
    for outcome in outcomes:
        print(f"{outcome['status']}: {outcome['document_id']} — {outcome.get('path') or outcome.get('reason')}")
    return 0 if all(item["status"] != "failed" for item in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
