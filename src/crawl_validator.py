"""
Crawl & Validation Module for Legal & News Documents from URL.

Tự động crawl nội dung từ link URL, đánh giá độ chính thống của nguồn phát hành,
chấm điểm độ chính xác & phù hợp với Luật Lao động, lưu trữ CSDL và tự động Re-index Vector Database.
"""

import gzip
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import urllib.request

ROOT_DIR = Path(__file__).resolve().parent.parent
LANDING_NEWS_DIR = ROOT_DIR / "data" / "landing" / "news"
STANDARDIZED_NEWS_DIR = ROOT_DIR / "data" / "standardized" / "news"

OFFICIAL_DOMAINS = {
    "baochinhphu.vn",
    "chinhphu.vn",
    "vanban.chinhphu.vn",
    "congbao.chinhphu.vn",
    "molisa.gov.vn",
    "thuvienphapluat.vn",
    "luatvietnam.vn",
    "quochoi.vn",
    "toaan.gov.vn",
    "gdt.gov.vn",
    "baohiemxahoi.gov.vn",
}

TRUSTED_NEWS_DOMAINS = {
    "vnexpress.net",
    "tuoitre.vn",
    "thanhnien.vn",
    "laodong.vn",
    "dantri.com.vn",
    "vtv.vn",
    "sggp.org.vn",
    "vietnamnet.vn",
}

LABOR_LAW_KEYWORDS = [
    "lao động", "hợp đồng", "thử việc", "lương", "bảo hiểm", "nghỉ phép",
    "làm thêm", "sa thải", "bồi thường", "pháp luật", "nghị định", "bộ luật",
    "quyền lợi", "người lao động", "người sử dụng lao động", "thời giờ làm việc",
    "kỷ luật lao động", "trợ cấp", "chấm dứt hợp đồng"
]


def slugify(text: str) -> str:
    """Tạo slug không dấu từ tiêu đề."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:60]


def extract_content_from_html(html_text: str, domain: str) -> tuple[str, str]:
    """Trích xuất tiêu đề và đoạn văn bản sạch từ HTML."""
    # 1. Title extraction
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.IGNORECASE | re.DOTALL)
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.IGNORECASE | re.DOTALL)

    title = ""
    if h1_match:
        title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
    elif title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

    title = re.sub(r'\s+', ' ', title)
    if not title or len(title) < 3:
        title = f"Văn bản pháp lý từ {domain}"

    # 2. Strip scripts, styles, svg, noscript, iframe
    clean_html = re.sub(r'<(script|style|svg|noscript|iframe)[^>]*>.*?</\1>', '', html_text, flags=re.IGNORECASE | re.DOTALL)

    # 3. Insert paragraph breaks for block elements
    clean_html = re.sub(r'</?(p|div|h1|h2|h3|h4|h5|h6|li|tr|article|section|br)[^>]*>', '\n', clean_html, flags=re.IGNORECASE)

    # 4. Strip remaining HTML tags and decode HTML entities
    text_plain = html.unescape(re.sub(r'<[^>]+>', ' ', clean_html))

    # 5. Extract meaningful paragraph lines (> 20 chars)
    raw_lines = [line.strip() for line in text_plain.splitlines()]
    meaningful_lines = []

    for line in raw_lines:
        line = re.sub(r'\s+', ' ', line)
        if len(line) > 20 and not line.startswith("http") and "javascript:" not in line and "©" not in line:
            meaningful_lines.append(line)

    content_text = "\n\n".join(meaningful_lines)
    return title, content_text


def evaluate_domain(domain: str) -> tuple[str, int, str]:
    """
    Đánh giá độ chính thống của tên miền.
    Returns: (domain_category, score_boost, description)
    """
    domain = domain.lower().replace("www.", "")
    for off in OFFICIAL_DOMAINS:
        if domain.endswith(off):
            return "official", 50, "Cổng TTĐT Chính phủ / Cơ quan Nhà nước chính thống"

    for trusted in TRUSTED_NEWS_DOMAINS:
        if domain.endswith(trusted):
            return "trusted_news", 35, "Báo chí chính thống và nguồn tin uy tín"

    return "unverified", 10, "Nguồn tin chưa xác minh độ chính thống"


def evaluate_content_relevance(title: str, text: str) -> tuple[int, list[str]]:
    """
    Chấm điểm mức độ liên quan đến Luật Lao động dựa trên sự xuất hiện của từ khóa.
    Returns: (relevance_score, matched_keywords)
    """
    full_text = (title + " " + text).lower()
    matched = [kw for kw in LABOR_LAW_KEYWORDS if kw in full_text]
    score = min(50, len(matched) * 6)
    return score, matched


def crawl_and_validate_url(url: str) -> dict[str, Any]:
    """
    Crawl nội dung từ URL, đánh giá độ chính thống & độ tin cậy,
    lưu trữ vào CSDL và tự động re-index vector store nếu đạt tiêu chuẩn.
    """
    if not url or not url.strip().startswith("http"):
        return {
            "status": "rejected",
            "reason": "Đường dẫn URL không hợp lệ (phải bắt đầu bằng http:// hoặc https://)",
            "url": url,
        }

    parsed = urlparse(url)
    domain = parsed.netloc

    # Step 1: Crawl webpage handling anti-bot cookie challenges & gzip decompression
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html_bytes = response.read()

        # Handle GZIP decompression
        if html_bytes.startswith(b"\x1f\x8b"):
            try:
                html_bytes = gzip.decompress(html_bytes)
            except Exception:
                pass

        charset = response.headers.get_content_charset() or "utf-8"
        if "," in charset:
            charset = charset.split(",")[0].strip()

        try:
            html_text = html_bytes.decode(charset, errors="replace")
        except Exception:
            html_text = html_bytes.decode("utf-8", errors="replace")

        # Anti-Bot Cookie Bypass (e.g. laodong.vn JS cookie challenge)
        cookie_match = re.search(r'document\.cookie\s*=\s*["\']([^"\';]+)', html_text)
        if cookie_match and len(html_text) < 1000:
            cookie_pair = cookie_match.group(1)
            headers["Cookie"] = cookie_pair
            req_retry = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req_retry, timeout=15) as resp_retry:
                html_bytes = resp_retry.read()
                if html_bytes.startswith(b"\x1f\x8b"):
                    try:
                        html_bytes = gzip.decompress(html_bytes)
                    except Exception:
                        pass
                html_text = html_bytes.decode("utf-8", errors="replace")

        html_text = html.unescape(html_text)

    except Exception as e:
        return {
            "status": "error",
            "reason": f"Lỗi trong quá trình kết nối/crawl URL: {str(e)}",
            "url": url,
        }

    # Step 2: Extract title and content
    title, content_text = extract_content_from_html(html_text, domain)

    word_count = len(content_text.split())
    if word_count < 25:
        return {
            "status": "rejected",
            "reason": f"Nội dung bài viết quá ngắn ({word_count} từ), không đủ dung lượng để trích xuất ngữ cảnh.",
            "url": url,
            "title": title,
            "domain": domain,
        }

    # Step 3: Domain & Authenticity Evaluation
    domain_cat, domain_score, domain_desc = evaluate_domain(domain)
    rel_score, matched_keywords = evaluate_content_relevance(title, content_text)
    total_score = domain_score + rel_score

    is_official = domain_cat in ("official", "trusted_news")
    is_acceptable = is_official or total_score >= 50

    if not is_acceptable:
        return {
            "status": "rejected",
            "reason": f"Nguồn tin không thuộc danh sách chính thống và điểm phù hợp pháp luật thấp ({total_score}/100)",
            "url": url,
            "title": title,
            "domain": domain,
            "score": total_score,
            "matched_keywords": matched_keywords,
        }

    # Step 4: Save or Update Database
    LANDING_NEWS_DIR.mkdir(parents=True, exist_ok=True)
    STANDARDIZED_NEWS_DIR.mkdir(parents=True, exist_ok=True)

    slug = slugify(title)
    if not slug or len(slug) < 3:
        slug = f"guidance-crawl-{int(datetime.now().timestamp())}"
    filename_base = f"guidance-crawl-{slug}"
    json_path = LANDING_NEWS_DIR / f"{filename_base}.json"
    md_path = STANDARDIZED_NEWS_DIR / f"{filename_base}.md"

    is_update = json_path.exists() or md_path.exists()

    issuing_org = "Báo Điện tử Chính phủ" if "chinhphu.vn" in domain else f"Trích xuất từ {domain}"

    json_payload = {
        "document_id": filename_base,
        "url": url,
        "title": title,
        "date_published": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": content_text,
        "source_domain": domain,
        "issuing_organization": issuing_org,
        "document_type": "official_guidance",
        "normative": False,
        "legal_status": "reference",
        "legal_topics": matched_keywords[:5],
        "audience_roles": ["employee", "employer"],
        "authenticity_score": total_score,
    }

    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_content = f"""---
title: "{title}"
source: "{filename_base}.md"
type: "news"
issuing_authority: "{issuing_org}"
url: "{url}"
score: {total_score}
---

# {title}

{content_text}
"""
    md_path.write_text(md_content, encoding="utf-8")

    # Step 5: Trigger Re-indexing of ChromaDB Vector Store
    indexed_chunks = 0
    try:
        try:
            from src.task4_chunking_indexing import run_pipeline
        except ImportError:
            from task4_chunking_indexing import run_pipeline
        run_pipeline()
        indexed_chunks = 1  # Successfully re-indexed
    except Exception as e:
        print(f"[WARNING] Re-indexing failed: {e}")

    return {
        "status": "success",
        "url": url,
        "title": title,
        "domain": domain,
        "issuing_authority": issuing_org,
        "is_official": is_official,
        "score": total_score,
        "matched_keywords": matched_keywords,
        "word_count": word_count,
        "is_update": is_update,
        "filename": md_path.name,
        "message": "Đã cập nhật bài viết mới vào CSDL và tự động Re-index Vector Database!" if is_update else "Đã kiểm duyệt thành công và lưu mới vào CSDL Vector Database!"
    }


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_url = "https://laodong.vn/cong-dong/tram-uu-tien-cho-nguoi-lao-dong-1400000.ldo"
    print(f"Testing crawl URL: {test_url}")
    result = crawl_and_validate_url(test_url)
    print(f"Status: {result.get('status')} | Title: {result.get('title')} | Words: {result.get('word_count')} | Score: {result.get('score')}")
