"""Post-processing and structural normalization for Vietnamese legal text.

Preserves exact legal terminology (CHƯƠNG, Mục, Điều, Khoản, Điểm, số ngày, phần trăm, số hiệu văn bản)
and formats structural Markdown headings without altering content.
"""

from __future__ import annotations

import re


def count_articles(text: str) -> int:
    """Count total 'Điều <number>' occurrences in legal text."""
    if not text:
        return 0
    return len(re.findall(r"\bĐiều\s+\d+", text))


def postprocess_legal_markdown(raw_text: str) -> tuple[str, int]:
    """Standardize legal structure headings into clean Markdown hierarchy.
    
    Returns:
        tuple[str, int]: (processed_markdown_text, article_count)
    """
    if not raw_text:
        return "", 0

    lines = raw_text.splitlines()
    processed_lines: list[str] = []
    
    chuong_pattern = re.compile(r"^\s*(CHƯƠNG\s+[0-9IVXLCDM]+(?::|\.|\s-|\s).*)$", re.IGNORECASE)
    chuong_bare = re.compile(r"^\s*(CHƯƠNG\s+[0-9IVXLCDM]+)$", re.IGNORECASE)
    muc_pattern = re.compile(r"^\s*(Mục\s+\d+(?::|\.|\s-|\s).*)$", re.IGNORECASE)
    muc_bare = re.compile(r"^\s*(Mục\s+\d+)$", re.IGNORECASE)
    dieu_pattern = re.compile(r"^\s*(Điều\s+\d+[a-z]?\.\s*.*)$", re.IGNORECASE)
    dieu_bare = re.compile(r"^\s*(Điều\s+\d+[a-z]?)$", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            processed_lines.append("")
            continue

        # Preserve already-formatted headers if present
        if stripped.startswith("#"):
            processed_lines.append(stripped)
            continue

        # Format CHƯƠNG -> # CHƯƠNG ...
        m_chuong = chuong_pattern.match(stripped) or chuong_bare.match(stripped)
        if m_chuong:
            header_text = m_chuong.group(1).upper()
            processed_lines.append(f"# {header_text}")
            continue

        # Format Mục -> ## Mục ...
        m_muc = muc_pattern.match(stripped) or muc_bare.match(stripped)
        if m_muc:
            header_text = m_muc.group(1)
            processed_lines.append(f"## {header_text}")
            continue

        # Format Điều -> ### Điều ...
        m_dieu = dieu_pattern.match(stripped) or dieu_bare.match(stripped)
        if m_dieu:
            header_text = m_dieu.group(1)
            # Capitalize "Điều"
            header_text = re.sub(r"^điều\b", "Điều", header_text, flags=re.IGNORECASE)
            processed_lines.append(f"### {header_text}")
            continue

        processed_lines.append(stripped)

    result_text = "\n".join(processed_lines)
    article_cnt = count_articles(result_text)
    return result_text, article_cnt
