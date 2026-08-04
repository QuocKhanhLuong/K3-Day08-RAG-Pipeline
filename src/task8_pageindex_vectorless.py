"""
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — sử dụng
structural understanding của document thay vì embedding.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


def upload_documents():
    """
    Upload toàn bộ markdown documents lên PageIndex.
    """
    if not PAGEINDEX_API_KEY:
        print("[WARNING] PAGEINDEX_API_KEY is not set in .env")
        return []

    uploaded = []
    try:
        from pageindex.client import PageIndexClient
        client = PageIndexClient(api_key=PAGEINDEX_API_KEY)

        for md_file in STANDARDIZED_DIR.rglob("*.md"):
            resp = client.submit_document(str(md_file))
            doc_id = resp.get("doc_id") or resp.get("id")
            uploaded.append(doc_id)
            print(f"  [OK] Uploaded: {md_file.name} -> {doc_id}")
    except Exception as e:
        print(f"[WARNING] Error uploading documents to PageIndex: {e}")

    return uploaded


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    if not query.strip():
        return []

    # Attempt PageIndex SDK query if API Key is configured
    if PAGEINDEX_API_KEY:
        try:
            from pageindex.client import PageIndexClient
            client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
            resp = client.submit_query(query=query)
            retrieval_id = resp.get("retrieval_id") or resp.get("id")

            if retrieval_id:
                retrieval = client.get_retrieval(retrieval_id)
                results = []
                for node in retrieval.get("retrieved_nodes", [])[:top_k]:
                    for group in node.get("relevant_contents", []):
                        for item in group:
                            results.append({
                                "content": item.get("relevant_content", ""),
                                "score": 0.85,
                                "metadata": {"section": item.get("section_title", "")},
                                "source": "pageindex",
                            })
                if results:
                    return results[:top_k]
        except Exception as e:
            print(f"⚠ PageIndex API query error: {e}")

    # Local structural fallback if PageIndex API is unavailable
    results = []
    if STANDARDIZED_DIR.exists():
        q_tokens = set(query.lower().split())
        for md_file in STANDARDIZED_DIR.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs:
                p_tokens = set(p.lower().split())
                overlap = len(q_tokens.intersection(p_tokens))
                score = round(overlap / max(len(q_tokens), 1), 4)
                results.append({
                    "content": p,
                    "score": score if score > 0 else 0.1,
                    "metadata": {"source": md_file.name},
                    "source": "pageindex",
                })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not PAGEINDEX_API_KEY:
        print("[WARNING] PAGEINDEX_API_KEY is not set in .env")
        print("  Register at: https://pageindex.ai/")
    else:
        print("Uploading documents...")
        upload_documents()

    print("\nTest query:")
    results = pageindex_search("tuition fee payment methods", top_k=3)
    for r in results:
        print(f"[{r['score']:.3f}] [{r['source']}] {r['content'][:100]}...")
