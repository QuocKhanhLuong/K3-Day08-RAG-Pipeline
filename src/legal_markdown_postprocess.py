"""Structural normalization for extracted Vietnamese legal text.

The converter deliberately keeps statutory wording intact.  It removes only
repeated PDF page chrome and makes the document hierarchy machine-readable:
``CHƯƠNG`` / ``Mục`` / ``Điều`` become Markdown headings.  This gives the
downstream legal-aware chunker reliable boundaries without treating page
headers, page numbers, or footnote references as articles.
"""

from __future__ import annotations

import re


_PAGE_BANNER = re.compile(
    r"^CÔNG\s+BÁO\s*/\s*Số\s+\d+\s*/\s*Ngày\s+\d{2}-\d{2}-\d{4}$",
    re.IGNORECASE,
)
_PAGE_NUMBER = re.compile(r"^\d{1,3}$")
_CHAPTER = re.compile(r"^CHƯƠNG\s+([0-9IVXLCDM]+)(?:\s*[:.\-]\s*(.*))?$", re.IGNORECASE)
_SECTION = re.compile(r"^Mục\s+(\d+)(?:\s*[:.\-]\s*(.*))?$", re.IGNORECASE)
_ARTICLE = re.compile(r"^Điều\s+(\d+[a-z]?)\.\s*(.*)$", re.IGNORECASE)
_ARTICLE_HEADING = re.compile(r"^###\s+Điều\s+\d+[a-z]?\.", re.IGNORECASE | re.MULTILINE)


def _clean_line(line: str) -> str:
    """Keep text but normalize extraction-only runs of horizontal whitespace."""
    return re.sub(r"[ \t]+", " ", line).strip()


def _without_page_chrome(raw_text: str) -> list[str]:
    """Remove a Gazette banner and its immediately following page number only."""
    cleaned: list[str] = []
    waiting_for_page_number = False
    for raw_line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _clean_line(raw_line)
        if _PAGE_BANNER.fullmatch(line):
            waiting_for_page_number = True
            continue
        if waiting_for_page_number:
            if not line:
                continue
            waiting_for_page_number = False
            if _PAGE_NUMBER.fullmatch(line):
                continue
        cleaned.append(line)
    return cleaned


def _is_uppercase_title(line: str) -> bool:
    """Identify the all-capital chapter/section titles used in the source PDF."""
    letters = [char for char in line if char.isalpha()]
    return bool(letters) and line == line.upper()


def _next_nonempty(lines: list[str], start: int) -> tuple[int | None, str | None]:
    for index in range(start, len(lines)):
        if lines[index]:
            return index, lines[index]
    return None, None


def _collect_uppercase_title(lines: list[str], start: int) -> tuple[str, int]:
    """Return a following multi-line all-capital hierarchy title, if present."""
    title_lines: list[str] = []
    index = start
    while True:
        next_index, candidate = _next_nonempty(lines, index)
        if next_index is None or candidate is None or not _is_uppercase_title(candidate):
            break
        title_lines.append(candidate)
        index = next_index + 1
    return " ".join(title_lines), index


def _starts_lowercase(line: str) -> bool:
    for char in line:
        if char.isalpha():
            return char.islower()
    return False


def _collect_article_title_continuation(lines: list[str], start: int, title: str) -> tuple[str, int]:
    """Join wrapped article titles, never the following capitalized body text."""
    index = start
    while True:
        next_index, candidate = _next_nonempty(lines, index)
        if next_index is None or candidate is None or not _starts_lowercase(candidate):
            break
        # A lower-case line following an article title is a PDF line-wrap.  It
        # is safe to join because statutory article body paragraphs begin with
        # a capital letter or a numbered clause in this source format.
        title = f"{title} {candidate}".strip()
        index = next_index + 1
    return title, index


def count_articles(text: str) -> int:
    """Count structural article headings, excluding cross-references and footnotes."""
    if not text:
        return 0
    return len(_ARTICLE_HEADING.findall(text))


def postprocess_legal_markdown(raw_text: str) -> tuple[str, int]:
    """Convert extracted legal text into a clean, heading-aware Markdown body."""
    if not raw_text:
        return "", 0

    lines = _without_page_chrome(raw_text)
    processed: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            processed.append("")
            index += 1
            continue

        if line.startswith("#"):
            processed.append(line)
            index += 1
            continue

        chapter = _CHAPTER.fullmatch(line)
        if chapter:
            number, inline_title = chapter.groups()
            title, next_index = _collect_uppercase_title(lines, index + 1)
            full_title = " ".join(part for part in (inline_title, title) if part).strip()
            heading = f"# CHƯƠNG {number.upper()}"
            processed.append(f"{heading} — {full_title}" if full_title else heading)
            index = next_index if title else index + 1
            continue

        section = _SECTION.fullmatch(line)
        if section:
            number, inline_title = section.groups()
            title, next_index = _collect_uppercase_title(lines, index + 1)
            full_title = " ".join(part for part in (inline_title, title) if part).strip()
            heading = f"## Mục {number}"
            processed.append(f"{heading} — {full_title}" if full_title else heading)
            index = next_index if title else index + 1
            continue

        article = _ARTICLE.fullmatch(line)
        if article:
            number, title = article.groups()
            title, next_index = _collect_article_title_continuation(lines, index + 1, title)
            processed.append(f"### Điều {number}. {title}".rstrip())
            index = next_index
            continue

        processed.append(line)
        index += 1

    result = "\n".join(processed).strip()
    return result, count_articles(result)
