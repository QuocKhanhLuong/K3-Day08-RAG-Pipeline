
"""
Task 5 — Semantic Search Module.

Viết module tìm kiếm ngữ nghĩa (dense retrieval) trên vector store.

Yêu cầu:
    - Input: query string + top_k
    - Output: danh sách chunks có score, sorted descending
    - Phải tương thích với embedding model và vector store ở Task 4
"""

try:
    from .task4_chunking_indexing import get_collection, get_embedding_model
except ImportError:
    from task4_chunking_indexing import get_collection, get_embedding_model


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,      # Nội dung chunk
            'score': float,      # Cosine similarity score
            'metadata': dict     # source, doc_type, chunk_index
        }
        Sorted by score descending.
    """
    if not query.strip():
        return []

    try:
        model = get_embedding_model()
        query_vector = model.encode(query).tolist()

        collection = get_collection()
        count = collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"],
        )

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        output = []
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            # ChromaDB cosine space: dist in [0, 2], similarity = 1 - dist
            score = max(0.0, 1.0 - float(dist))
            output.append({
                "content": doc,
                "score": round(score, 4),
                "metadata": meta or {}
            })

        output.sort(key=lambda x: x["score"], reverse=True)
        return output[:top_k]

    except Exception as e:
        print(f"Error in semantic_search: {e}")
        return []


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    # Test
    results = semantic_search("what is the tuition fee", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
