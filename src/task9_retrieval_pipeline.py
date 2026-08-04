"""
Task 9 — Retrieval Pipeline Hoàn Chỉnh.

Kết hợp semantic search + lexical search + reranking + PageIndex fallback
thành một pipeline thống nhất.

Logic:
    1. Chạy semantic_search + lexical_search (nếu có) song song
    2. Merge kết quả (RRF hoặc dense fallback)
    3. Rerank
    4. Nếu top result score (cosine gốc) < threshold → fallback sang PageIndex
    5. Return top_k results
"""

try:
    from .task5_semantic_search import semantic_search
    from .task7_reranking import rerank, rerank_rrf
    from .task8_pageindex_vectorless import pageindex_search
    from .guidance_matcher import get_guidance_chunks
except ImportError:
    from task5_semantic_search import semantic_search
    from task7_reranking import rerank, rerank_rrf
    from task8_pageindex_vectorless import pageindex_search
    from guidance_matcher import get_guidance_chunks


# =============================================================================
# CONFIGURATION
# =============================================================================

SCORE_THRESHOLD = 0.3   # Nếu best score (cosine gốc) < threshold → fallback PageIndex
DEFAULT_TOP_K = 5
RERANK_METHOD = "rrf"   # "cross_encoder" | "mmr" | "rrf"


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """
    Retrieval pipeline hoàn chỉnh tích hợp Guidance Matcher với fallback logic.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả cuối cùng
        score_threshold: Ngưỡng điểm cosine gốc tối thiểu
        use_reranking: Có áp dụng reranking hay không

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': str  # 'guidance_match', 'hybrid', hoặc 'pageindex'
        }
    """
    if not query.strip():
        return []

    # Step 0: Check guidance matcher for direct guidance title match (>= 0.60 threshold)
    guidance_results = []
    try:
        raw_guidance = get_guidance_chunks(query, threshold=0.60)
        # Take top 2 best guidance matches to leave room for legal statutes
        guidance_results = raw_guidance[:2]
    except Exception as e:
        print(f"  [WARNING] Guidance matcher error: {e}")

    # Step 1: Semantic search (dense)
    dense_results = semantic_search(query, top_k=top_k * 2)

    # Step 1b: Try lexical_search if Task 6 implemented, else handle cleanly
    sparse_results = []
    try:
        from .task6_lexical_search import lexical_search
        sparse_results = lexical_search(query, top_k=top_k * 2)
    except (ImportError, NotImplementedError, Exception):
        sparse_results = []

    # Step 2: Merge bằng RRF nếu cả 2 có kết quả, ngược lại dùng dense_results
    if dense_results and sparse_results:
        merged = rerank_rrf([dense_results, sparse_results], top_k=top_k * 2)
    else:
        merged = [item.copy() for item in dense_results]

    for item in merged:
        item["source"] = "hybrid"

    # Step 3: Rerank hybrid results
    if use_reranking and merged:
        final_results = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
        for item in final_results:
            item["source"] = "hybrid"
    else:
        final_results = merged[:top_k]

    # Prepend direct guidance matches if present (avoiding duplicates)
    if guidance_results:
        existing_sources = {item.get("metadata", {}).get("source") for item in final_results}
        filtered_guidance = [g for g in guidance_results if g.get("metadata", {}).get("source") not in existing_sources]
        final_results = filtered_guidance + final_results


    # Step 4: Check threshold dựa trên điểm Cosine gốc của dense_results (nếu chưa có guidance match)
    best_score = dense_results[0]["score"] if dense_results else 0.0
    if not guidance_results and (best_score < score_threshold or not final_results):
        print(f"  [WARNING] Semantic best score ({best_score:.3f}) < threshold ({score_threshold}). Triggering PageIndex fallback...")
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            for item in fallback:
                item["source"] = "pageindex"
            return fallback[:top_k]

    return final_results[:top_k]


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    test_queries = [
        "Không nghỉ hết phép năm có được thanh toán tiền không?",
        "Thời gian thử việc, tiền lương và bảo hiểm xã hội quy định như thế nào?",
        "Giới hạn thời giờ làm thêm giờ và cách tính tiền lương OT?",
        "xyzabc123nonsense",  # Query không có kết quả → test fallback
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        results = retrieve(q, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['score']:.3f}] [{r['source']}] {r['content'][:80]}...")

