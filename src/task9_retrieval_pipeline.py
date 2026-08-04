"""
Task 9 — Retrieval Pipeline Hoàn Chỉnh.

Kết hợp semantic search + lexical search + reranking + PageIndex fallback
thành một pipeline thống nhất và theo dõi nhật ký truy xuất (Retrieval Log).
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
    return_details: bool = False,
    dense_weight: float = 0.50,
    sparse_weight: float = 0.50,
):
    """
    Retrieval pipeline hoàn chỉnh tích hợp Guidance Matcher với fallback logic và logging.
    """
    if not query.strip():
        if return_details:
            return [], {"strategy": "None", "reason": "Query rỗng"}
        return []

    # Step 0: Check guidance matcher for direct guidance title match (>= 0.60 threshold)
    guidance_results = []
    try:
        raw_guidance = get_guidance_chunks(query, threshold=0.60)
        guidance_results = raw_guidance[:2]
    except Exception as e:
        print(f"  [WARNING] Guidance matcher error: {e}")

    # Step 1: Semantic search (dense)
    dense_results = semantic_search(query, top_k=top_k * 2)

    # Step 1b: Try lexical_search if Task 6 implemented
    sparse_results = []
    try:
        from .task6_lexical_search import lexical_search
        sparse_results = lexical_search(query, top_k=top_k * 2)
    except (ImportError, NotImplementedError, Exception):
        sparse_results = []

    # Step 2: Merge bằng Weighted RRF nếu cả 2 có kết quả, ngược lại dùng dense_results
    if dense_results and sparse_results:
        merged = rerank_rrf(
            [dense_results, sparse_results],
            top_k=top_k * 2,
            weights=[dense_weight, sparse_weight]
        )
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

    # Prepend direct guidance matches if present
    if guidance_results:
        existing_sources = {item.get("metadata", {}).get("source") for item in final_results}
        filtered_guidance = [g for g in guidance_results if g.get("metadata", {}).get("source") not in existing_sources]
        final_results = filtered_guidance + final_results

    best_dense_score = dense_results[0]["score"] if dense_results else 0.0
    used_fallback = False
    strategy_name = ""

    # Step 4: Check threshold dựa trên điểm Cosine gốc của dense_results
    if not guidance_results and (best_dense_score < score_threshold or not final_results):
        print(f"  [WARNING] Semantic best score ({best_dense_score:.3f}) < threshold ({score_threshold}). Triggering PageIndex fallback...")
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            for item in fallback:
                item["source"] = "pageindex"
            final_results = fallback[:top_k]
            used_fallback = True
            strategy_name = "PageIndex Fallback (Vectorless Search)"

    # Determine strategy label if not fallback
    if not strategy_name:
        if guidance_results and (dense_results or sparse_results):
            strategy_name = "Guidance Match + Hybrid RRF (Semantic + Lexical Search)"
        elif guidance_results:
            strategy_name = "Guidance Match Search"
        elif dense_results and sparse_results:
            strategy_name = "Hybrid RRF (Semantic Vector + Lexical BM25)"
        elif dense_results:
            strategy_name = "Semantic Vector Search"
        elif sparse_results:
            strategy_name = "Lexical Search (BM25 Keyword)"
        else:
            strategy_name = "PageIndex Fallback"

    top_chunks = final_results[:top_k]

    k_const = 60
    dense_score_map = {item["content"]: item.get("score", 0.0) for item in dense_results}
    sparse_score_map = {item["content"]: item.get("score", 0.0) for item in sparse_results}

    dense_rank_map = {item["content"]: rank for rank, item in enumerate(dense_results, 1)}
    sparse_rank_map = {item["content"]: rank for rank, item in enumerate(sparse_results, 1)}

    best_rrf_semantic = dense_weight * (1.0 / (k_const + 1)) if dense_results else 0.0
    best_rrf_lexical = sparse_weight * (1.0 / (k_const + 1)) if sparse_results else 0.0
    best_rrf_total = top_chunks[0].get("score", 0.0) if top_chunks else 0.0

    chunk_breakdown = []
    for item in top_chunks:
        content = item.get("content", "")
        d_rank = dense_rank_map.get(content, 0)
        s_rank = sparse_rank_map.get(content, 0)

        rrf_sem = round(dense_weight * (1.0 / (k_const + d_rank)), 6) if d_rank > 0 else 0.0
        rrf_lex = round(sparse_weight * (1.0 / (k_const + s_rank)), 6) if s_rank > 0 else 0.0

        d_score = dense_score_map.get(content, best_dense_score if item.get("source") == "hybrid" else 0.0)
        s_score = sparse_score_map.get(content, 0.50 if item.get("source") == "hybrid" else 0.0)

        chunk_breakdown.append({
            "source": item.get("metadata", {}).get("issuing_authority") or item.get("metadata", {}).get("source", "Tài liệu"),
            "score": round(item.get("score", 0.0), 6),
            "type": item.get("source", "hybrid"),
            "semantic_score": round(d_score, 4),
            "lexical_score": round(s_score, 4),
            "rrf_semantic": rrf_sem,
            "rrf_lexical": rrf_lex,
            "dense_rank": d_rank,
            "sparse_rank": s_rank,
        })

    details_dict = {
        "strategy": strategy_name,
        "hybrid_weights": {
            "semantic_vector": int(round(dense_weight * 100)),
            "lexical_bm25": int(round(sparse_weight * 100))
        },
        "best_rrf_semantic": round(best_rrf_semantic, 6),
        "best_rrf_lexical": round(best_rrf_lexical, 6),
        "best_rrf_total": round(best_rrf_total, 6),
        "best_dense_score": round(best_dense_score, 4),
        "best_sparse_score": round(sparse_results[0]["score"], 4) if sparse_results else 0.50,
        "guidance_matched": bool(guidance_results),
        "guidance_score": round(guidance_results[0]["score"], 4) if guidance_results else 0.0,
        "used_fallback": used_fallback,
        "dense_count": len(dense_results),
        "sparse_count": len(sparse_results),
        "top_chunks": chunk_breakdown
    }




    if return_details:
        return top_chunks, details_dict

    return top_chunks


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    test_queries = [
        "Không nghỉ hết phép năm có được thanh toán tiền không?",
        "Thời gian thử việc, tiền lương và bảo hiểm xã hội quy định như thế nào?",
        "xyzabc123nonsense",
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        results, details = retrieve(q, top_k=3, return_details=True)
        print(f"Strategy: {details['strategy']}")
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['score']:.3f}] [{r['source']}] {r['content'][:80]}...")
