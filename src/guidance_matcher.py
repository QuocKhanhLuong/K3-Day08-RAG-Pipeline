"""
Guidance Matcher Module.

Quét toàn bộ file guidance JSON trong data/landing/news/ để trích xuất các tiêu đề (title).
Nếu query của người dùng có độ tương đồng cao với tiêu đề gợi ý nào, tự động lọc và ưu tiên
các file markdown tương ứng trong data/standardized/news/.
"""

import json
from pathlib import Path

LANDING_NEWS_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"
STANDARDIZED_NEWS_DIR = Path(__file__).parent.parent / "data" / "standardized" / "news"

_guidance_cache = None


def load_guidance_catalog() -> list[dict]:
    """
    Đọc danh sách các bài hướng dẫn guidance từ data/landing/news/.

    Returns:
        List of {'title': str, 'filename': str, 'doc_id': str, 'url': str}
    """
    global _guidance_cache
    if _guidance_cache is not None:
        return _guidance_cache

    catalog = []
    if LANDING_NEWS_DIR.exists():
        for json_file in LANDING_NEWS_DIR.glob("*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                title = data.get("title")
                if title:
                    stem = json_file.stem
                    md_filename = f"{stem}.md"
                    issuing_auth = data.get("issuing_authority") or data.get("issuing_organization") or "Báo Điện tử Chính phủ"
                    catalog.append({
                        "title": title.strip(),
                        "filename": md_filename,
                        "stem": stem,
                        "doc_id": data.get("document_id", stem),
                        "url": data.get("url", ""),
                        "issuing_authority": issuing_auth
                    })
            except Exception as e:
                print(f"[WARNING] Cannot parse guidance json {json_file.name}: {e}")


    _guidance_cache = catalog
    return catalog


def match_guidance_query(query: str, threshold: float = 0.55) -> list[dict]:
    """
    So sánh độ tương đồng giữa query của user và tiêu đề của các bài guidance.

    Args:
        query: Câu hỏi của người dùng
        threshold: Ngưỡng độ tương đồng tối thiểu (0.55)

    Returns:
        Danh sách các bài guidance trùng khớp kèm điểm số [{'title', 'filename', 'score'}]
    """
    if not query or not query.strip():
        return []

    catalog = load_guidance_catalog()
    if not catalog:
        return []

    try:
        from sentence_transformers import SentenceTransformer, util
        try:
            from .task4_chunking_indexing import get_embedding_model
            model = get_embedding_model()
        except ImportError:
            from task4_chunking_indexing import get_embedding_model
            model = get_embedding_model()

        titles = [item["title"] for item in catalog]
        query_emb = model.encode(query, convert_to_tensor=True)
        title_embs = model.encode(titles, convert_to_tensor=True)

        cos_scores = util.cos_sim(query_emb, title_embs)[0]

        matches = []
        for idx, score in enumerate(cos_scores):
            score_val = float(score)
            if score_val >= threshold:
                item = catalog[idx].copy()
                item["score"] = round(score_val, 4)
                matches.append(item)

        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches

    except Exception as e:
        print(f"[WARNING] Error in match_guidance_query: {e}")
        # Simple string keyword fallback if model fails
        q_tokens = set(query.lower().split())
        matches = []
        for item in catalog:
            t_tokens = set(item["title"].lower().split())
            overlap = len(q_tokens.intersection(t_tokens)) / max(len(q_tokens), 1)
            if overlap >= 0.4:
                cand = item.copy()
                cand["score"] = round(overlap, 4)
                matches.append(cand)
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches


def get_guidance_chunks(query: str, threshold: float = 0.50) -> list[dict]:
    """
    Tìm kiếm guidance trùng khớp và chuyển thành các chunk kết quả hoàn chỉnh.
    """
    matches = match_guidance_query(query, threshold=threshold)
    results = []

    for m in matches:
        md_file = STANDARDIZED_NEWS_DIR / m["filename"]
        if md_file.exists():
            text = md_file.read_text(encoding="utf-8").strip()
            if text:
                # Split large document into paragraphs if necessary
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                # Include main title / intro paragraphs or top 3 paragraphs
                combined_content = "\n\n".join(paragraphs[:4]) if len(paragraphs) > 4 else text
                results.append({
                    "content": combined_content,
                    "score": m["score"],
                    "metadata": {
                        "source": m["filename"],
                        "type": "news",
                        "title": m["title"],
                        "issuing_authority": m.get("issuing_authority", "Báo Điện tử Chính phủ"),
                        "guidance_match": True
                    },
                    "source": "guidance_match"
                })

    return results


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_q = "Không nghỉ hết phép năm có được thanh toán tiền không?"
    print(f"Query: {test_q}")
    matched = match_guidance_query(test_q)
    for m in matched:
        print(f"  -> Matched Title: '{m['title']}' (score: {m['score']}) -> File: {m['filename']}")

    chunks = get_guidance_chunks(test_q)
    print(f"\nExtracted {len(chunks)} guidance chunks.")

