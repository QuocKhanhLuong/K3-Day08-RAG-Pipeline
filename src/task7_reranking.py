"""
Task 7 — Reranking Module.

Chọn 1 trong các phương pháp:
    - Cross-encoder reranker: Jina Reranker v2 (multilingual) hoặc Qwen3-Reranker
    - MMR (Maximal Marginal Relevance): tự implement
    - RRF (Reciprocal Rank Fusion): tự implement — khuyến nghị vì không cần API key
"""

import math
from typing import Optional


def _cosine_sim(vec1: list[float], vec2: list[float]) -> float:
    """Tính cosine similarity giữa 2 vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def rerank_cross_encoder(
    query: str, candidates: list[dict], top_k: int = 5
) -> list[dict]:
    """
    Rerank candidates sử dụng cross-encoder model.

    Args:
        query: Câu truy vấn
        candidates: List of {'content': str, 'score': float, 'metadata': dict}
        top_k: Số lượng kết quả sau rerank

    Returns:
        List of top_k candidates, re-scored và sorted by rerank_score descending.
    """
    if not candidates:
        return []

    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [[query, c["content"]] for c in candidates]
        scores = model.predict(pairs)

        reranked = []
        for cand, score in zip(candidates, scores):
            item = cand.copy()
            item["score"] = float(score)
            reranked.append(item)

        reranked.sort(key=lambda x: x["score"], reverse=True)
        return reranked[:top_k]
    except Exception:
        # Fallback to simple query keyword matching / score scaling if CrossEncoder model unavailable
        reranked = []
        q_words = set(query.lower().split())
        for c in candidates:
            item = c.copy()
            content_words = set(c["content"].lower().split())
            overlap = len(q_words.intersection(content_words)) / max(len(q_words), 1)
            item["score"] = float(c.get("score", 0.5)) + overlap * 0.5
            reranked.append(item)
        reranked.sort(key=lambda x: x["score"], reverse=True)
        return reranked[:top_k]


def rerank_mmr(
    query_embedding: list[float],
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    """
    Maximal Marginal Relevance — chọn candidates vừa relevant vừa diverse.

    MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, selected_docs))

    Args:
        query_embedding: Vector embedding của query
        candidates: List of {'content': str, 'score': float, 'embedding': list, 'metadata': dict}
        top_k: Số lượng kết quả
        lambda_param: Trade-off giữa relevance (1.0) và diversity (0.0)

    Returns:
        List of top_k candidates selected by MMR.
    """
    if not candidates:
        return []

    # Ensure embeddings exist for MMR calculation
    cand_embeddings = []
    need_embeddings = False
    for c in candidates:
        if "embedding" in c and c["embedding"]:
            cand_embeddings.append(c["embedding"])
        else:
            need_embeddings = True
            break

    if need_embeddings:
        try:
            from .task4_chunking_indexing import get_embedding_model
        except ImportError:
            from task4_chunking_indexing import get_embedding_model
        model = get_embedding_model()
        texts = [c["content"] for c in candidates]
        embs = model.encode(texts)
        cand_embeddings = [emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embs]

    selected_indices = []
    remaining = list(range(len(candidates)))
    target_k = min(top_k, len(candidates))

    for _ in range(target_k):
        best_idx = None
        best_mmr = float("-inf")

        for idx in remaining:
            rel = _cosine_sim(query_embedding, cand_embeddings[idx])
            
            max_sim_to_selected = 0.0
            for sel_idx in selected_indices:
                sim = _cosine_sim(cand_embeddings[idx], cand_embeddings[sel_idx])
                max_sim_to_selected = max(max_sim_to_selected, sim)

            mmr_score = lambda_param * rel - (1 - lambda_param) * max_sim_to_selected

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

    result = []
    for idx in selected_indices:
        item = candidates[idx].copy()
        item["score"] = float(item.get("score", 0.5))
        result.append(item)

    return result


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60
) -> list[dict]:
    """
    Reciprocal Rank Fusion — gộp kết quả từ nhiều ranker.

    RRF(d) = Σ 1 / (k + rank_r(d))

    Args:
        ranked_lists: List of ranked result lists (mỗi list từ 1 ranker)
        top_k: Số lượng kết quả cuối cùng
        k: Smoothing constant (default=60, từ paper Cormack et al. 2009)

    Returns:
        List of top_k candidates sorted by RRF score descending.
    """
    if not ranked_lists:
        return []

    rrf_scores = {}    # content -> score
    content_map = {}   # content -> full item dict

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = item["content"]
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in content_map:
                content_map[key] = item

    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for content, score in sorted_items[:top_k]:
        item = content_map[content].copy()
        item["score"] = round(float(score), 6)
        results.append(item)

    return results


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    method: str = "rrf",  # "cross_encoder" | "mmr" | "rrf"
) -> list[dict]:
    """
    Unified reranking interface.

    Args:
        query: Câu truy vấn
        candidates: Danh sách candidates từ retrieval
        top_k: Số lượng kết quả sau rerank
        method: Phương pháp reranking

    Returns:
        List of top_k reranked candidates.
    """
    if not candidates:
        return []

    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    elif method == "mmr":
        try:
            from .task4_chunking_indexing import get_embedding_model
        except ImportError:
            from task4_chunking_indexing import get_embedding_model
        model = get_embedding_model()
        query_emb = model.encode(query).tolist()
        return rerank_mmr(query_emb, candidates, top_k)
    elif method == "rrf":
        return rerank_rrf([candidates], top_k)
    else:
        raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    # Test with dummy data
    dummy_candidates = [
        {"content": "Tuition fee payment schedule", "score": 0.8, "metadata": {}},
        {"content": "Scholarship eligibility requirements", "score": 0.6, "metadata": {}},
        {"content": "Library study room booking guide", "score": 0.5, "metadata": {}},
    ]
    results = rerank("tuition fee payment", dummy_candidates, top_k=2)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content']}")
