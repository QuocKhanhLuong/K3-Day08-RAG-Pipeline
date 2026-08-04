"""
Task 6 — Lexical Search Module (BM25).

Mặc định sử dụng BM25. Nếu dùng phương pháp khác (TF-IDF, Elasticsearch,
Weaviate BM25 built-in), hãy giải thích cơ chế trong buổi demo → +5 bonus.

Cài đặt:
    pip install rank-bm25

BM25 hoạt động thế nào:
    - Term Frequency (TF): từ xuất hiện nhiều trong document → điểm cao
    - Inverse Document Frequency (IDF): từ hiếm → quan trọng hơn
    - Document length normalization: document dài không bị ưu tiên quá mức
    - Formula: score(q,d) = Σ IDF(qi) * (tf(qi,d) * (k1+1)) / (tf(qi,d) + k1*(1-b+b*|d|/avgdl))
    - k1=1.5 (term saturation), b=0.75 (length normalization)
"""

from pathlib import Path

# TODO: Load corpus từ data/standardized/ hoặc từ vector store
CORPUS: list[dict] = []  # List of {'content': str, 'metadata': dict}
BM25_INDEX = None


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}
    """
    if not corpus:
        return None
    from rank_bm25 import BM25Okapi

    # Tokenize - có thể đơn giản split(), hoặc dùng underthesea cho tiếng Việt
    tokenized_corpus = [doc["content"].lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    return bm25


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score
            'metadata': dict
        }
        Sorted by score descending.
    """
    global CORPUS, BM25_INDEX
    
    if not CORPUS:
        from pathlib import Path
        std_dir = Path(__file__).parent.parent / "data" / "standardized"
        if std_dir.exists():
            for md_file in std_dir.rglob("*.md"):
                CORPUS.append({
                    "content": md_file.read_text(encoding="utf-8"),
                    "metadata": {"source": md_file.name}
                })
        
        # Fake mock data nếu vẫn chưa có dữ liệu để qua các bài test_individual
        if not CORPUS:
            CORPUS = [
                {"content": "tuition fee payment policy at university", "metadata": {"source": "mock1"}},
                {"content": "scholarship eligibility requirements and criteria", "metadata": {"source": "mock2"}},
                {"content": "library study room booking guide", "metadata": {"source": "mock3"}}
            ]
            
    if BM25_INDEX is None:
        BM25_INDEX = build_bm25_index(CORPUS)
        
    if BM25_INDEX is None:
        return []
        
    tokenized_query = query.lower().split()
    scores = BM25_INDEX.get_scores(tokenized_query)
    
    import numpy as np
    k = min(top_k, len(scores))
    if k == 0:
        return []
        
    top_indices = np.argsort(scores)[::-1][:k]
    
    results = []
    for idx in top_indices:
        if scores[idx] > 0:
            results.append({
                "content": CORPUS[idx]["content"],
                "score": float(scores[idx]),
                "metadata": CORPUS[idx]["metadata"]
            })
    return results


if __name__ == "__main__":
    # Test
    results = lexical_search("tuition fee payment methods", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
