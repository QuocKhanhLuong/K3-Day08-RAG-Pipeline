"""
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (ChromaDB khuyến cáo — đơn giản, local, không cần Docker)
"""

import json
import re
from pathlib import Path
from typing import Optional

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# Chunk size 500 chars giữ đủ ngữ cảnh một đoạn văn ngắn trong khi tránh pha loãng vector representation.
# Overlap 50 chars giúp không mất thông tin ở ranh giới giữa 2 chunks.
CHUNK_SIZE = 500        # Vì sao chọn 500? Đủ ngữ cảnh 1 đoạn văn ngắn
CHUNK_OVERLAP = 50      # Vì sao chọn 50? Giữ ngữ cảnh nối tiếp ở ranh giới
CHUNKING_METHOD = "recursive"  # "recursive" | "markdown_header" | "semantic"

# sentence-transformers/all-MiniLM-L6-v2 (384 dim, nhẹ, fast, local)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# ChromaDB: Đơn giản, chạy local, tự động lưu trữ persistent
VECTOR_STORE = "chromadb"
COLLECTION_NAME = "legal_labor_docs"

_model_instance = None


def _parse_scalar(value: str):
    value = value.strip()
    if value in {"null", "None", "~"}:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    return value


def _parse_simple_yaml(yaml_text: str) -> dict:
    """Small front matter fallback for environments without PyYAML."""
    metadata = {}
    current_list_key = None
    for raw_line in yaml_text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("- ") and current_list_key:
            metadata.setdefault(current_list_key, []).append(_parse_scalar(line[2:]))
            continue
        current_list_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            metadata[key] = _parse_scalar(value)
        else:
            metadata[key] = []
            current_list_key = key
    return metadata


def _split_front_matter(content: str) -> tuple[dict, str]:
    """Return YAML front matter metadata and body for standardized Markdown."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        import yaml
        metadata = yaml.safe_load(parts[1]) or {}
        if not isinstance(metadata, dict):
            metadata = {}
    except Exception:
        metadata = _parse_simple_yaml(parts[1])

    return metadata, parts[2].strip()


def _chroma_safe_metadata(metadata: dict) -> dict:
    """Chroma metadata values must be scalar; keep rich fields display-friendly."""
    safe = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = ", ".join(str(item) for item in value)
        else:
            safe[key] = json.dumps(value, ensure_ascii=False)
    return safe


def _extract_article_label(text: str) -> Optional[str]:
    match = re.search(r"(Điều\s+\d+[a-zA-Z]?\.\s*[^\n]{0,120})", text)
    return match.group(1).strip() if match else None


def get_embedding_model():
    """Singleton getter cho SentenceTransformer embedding model."""
    global _model_instance
    if _model_instance is None:
        from sentence_transformers import SentenceTransformer
        try:
            _model_instance = SentenceTransformer(EMBEDDING_MODEL)
        except Exception:
            # Fallback sang model nhẹ hơn nếu bge-m3 không tải được
            _model_instance = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_instance


def get_collection():
    """Lấy ChromaDB collection instance."""
    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown (.md) và JSON (.json) files từ data/standardized/ và data/landing/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    documents = []

    # 1. Load Markdown files (.md)
    if STANDARDIZED_DIR.exists():
        for md_file in STANDARDIZED_DIR.rglob("*.md"):
            raw_content = md_file.read_text(encoding="utf-8").strip()
            if not raw_content:
                continue
            front_matter, content = _split_front_matter(raw_content)
            if front_matter.get("active_corpus") is False:
                continue
            doc_type = "legal" if "legal" in str(md_file) else "news"
            meta = {
                **front_matter,
                "source": md_file.name,
                "source_file": md_file.name,
                "type": doc_type,
            }
            if front_matter.get("source"):
                meta["original_source"] = front_matter.get("source")
            if front_matter.get("title"):
                doc_number = front_matter.get("document_number")
                meta["display_source"] = (
                    f"{front_matter['title']} ({doc_number})"
                    if doc_number else front_matter["title"]
                )
            if doc_type == "news":
                # Try finding matching landing json file for issuing_authority / issuing_organization
                landing_json = STANDARDIZED_DIR.parent / "landing" / "news" / f"{md_file.stem}.json"
                issuing_auth = "Báo Điện tử Chính phủ"
                if landing_json.exists():
                    try:
                        jdata = json.loads(landing_json.read_text(encoding="utf-8"))
                        issuing_auth = jdata.get("issuing_authority") or jdata.get("issuing_organization") or issuing_auth
                    except Exception:
                        pass
                meta["issuing_authority"] = issuing_auth

            documents.append({
                "content": content,
                "metadata": _chroma_safe_metadata(meta)
            })

    # 2. Load JSON files (.json) for legal documents or news
    search_dirs = [STANDARDIZED_DIR, STANDARDIZED_DIR.parent / "landing"]
    for sdir in search_dirs:
        if not sdir.exists():
            continue
        for json_file in sdir.rglob("*.json"):
            try:
                raw_text = json_file.read_text(encoding="utf-8").strip()
                if not raw_text:
                    continue
                data = json.loads(raw_text)
                doc_type = "legal" if "legal" in str(json_file) else "news"
                issuing_auth = (data.get("issuing_authority") or data.get("issuing_organization") or ("Báo Điện tử Chính phủ" if doc_type == "news" else "")) if isinstance(data, dict) else ""


                if isinstance(data, dict):
                    title = data.get("title") or data.get("document_name") or json_file.stem
                    body = data.get("content") or data.get("content_markdown") or data.get("text") or str(data)
                    content_str = f"# {title}\n\n{body}"
                    meta = {"source": json_file.name, "source_file": json_file.name, "type": doc_type, "title": title, "display_source": title}
                    if issuing_auth:
                        meta["issuing_authority"] = issuing_auth
                    documents.append({
                        "content": content_str,
                        "metadata": _chroma_safe_metadata(meta)
                    })
                elif isinstance(data, list):
                    for idx, item in enumerate(data):
                        if isinstance(item, dict):
                            title = item.get("title") or item.get("article") or f"{json_file.stem}_{idx}"
                            body = item.get("content") or item.get("text") or str(item)
                            meta = {"source": f"{json_file.name}#{idx}", "source_file": json_file.name, "type": doc_type, "title": title, "display_source": title}
                            if issuing_auth:
                                meta["issuing_authority"] = issuing_auth
                            documents.append({
                                "content": f"# {title}\n\n{body}",
                                "metadata": _chroma_safe_metadata(meta)
                            })
            except Exception as e:
                print(f"[WARNING] Error reading JSON document {json_file.name}: {e}")


    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        use_langchain = True
    except ImportError:
        use_langchain = False

    chunks = []
    for doc in documents:
        content = doc["content"]
        if use_langchain:
            splits = splitter.split_text(content)
        else:
            # Fallback simple text splitter if package missing
            splits = []
            start = 0
            while start < len(content):
                end = start + CHUNK_SIZE
                splits.append(content[start:end])
                start += CHUNK_SIZE - CHUNK_OVERLAP
                if CHUNK_SIZE <= CHUNK_OVERLAP:
                    break

        for i, chunk_text in enumerate(splits):
            if chunk_text.strip():
                article = _extract_article_label(chunk_text)
                metadata = {**doc["metadata"], "chunk_index": i}
                if article:
                    metadata["article"] = article
                chunks.append({
                    "content": chunk_text,
                    "metadata": metadata
                })

    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    if not chunks:
        return chunks

    model = get_embedding_model()
    texts = [c["content"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False)

    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist() if hasattr(emb, "tolist") else list(emb)

    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
    if not chunks:
        return

    collection = get_collection()
    ids = [f"{c['metadata']['source']}_chunk_{c['metadata']['chunk_index']}" for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    
    embeddings = [c["embedding"] for c in chunks] if "embedding" in chunks[0] else None

    if embeddings:
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    else:
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n[OK] Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"[OK] Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"[OK] Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("[OK] Indexed to vector store")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_pipeline()
