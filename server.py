"""
FastAPI Backend Server for Legal RAG Pipeline System.

Provides REST API endpoints for UI integration:
- POST /api/chat: Receives query, performs RAG retrieval & LLM generation, returns answer and citations.
- POST /api/index: Re-indexes documents when new legal JSON / MD files are added.
- GET /api/health: Health check endpoint.
"""

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.task4_chunking_indexing import run_pipeline
from src.task10_generation import generate_with_citation

app = FastAPI(
    title="Legal RAG Pipeline API",
    description="Backend REST API connecting RAG pipeline (Task 4-10) with UI Frontend",
    version="1.0.0",
)

# Enable CORS for UI Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


class CitationItem(BaseModel):
    source: str
    article: str
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    citations: list[CitationItem]
    retrieval_source: str
    retrieval_log: Optional[dict] = None


from src.guidance_matcher import load_guidance_catalog


@app.get("/")
@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Legal RAG System Backend"}


@app.get("/api/guidance-queries")
def get_guidance_queries():
    """Lấy danh sách các câu hỏi gợi ý từ các file guidance JSON trong data/landing/news."""
    catalog = load_guidance_catalog()
    titles = [item["title"] for item in catalog if item.get("title")]
    return {"queries": titles}



@app.post("/api/chat", response_model=ChatResponse)
def handle_chat_query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        top_k = req.top_k or 5
        rag_output = generate_with_citation(req.query, top_k=top_k)

        raw_sources = rag_output.get("sources", [])
        citations = []

        for src in raw_sources:
            meta = src.get("metadata", {})
            doc_type = meta.get("type", "")
            
            if doc_type == "news" or "guidance" in str(meta.get("source", "")).lower() or meta.get("guidance_match"):
                source_file = meta.get("issuing_authority") or meta.get("issuing_organization") or "Báo Điện tử Chính phủ"
            else:
                source_file = meta.get("source", "Văn bản pháp luật")

            article = meta.get("article") or meta.get("section") or meta.get("title") or "Quy định liên quan"
            content = src.get("content", "").strip()

            citations.append(CitationItem(
                source=source_file,
                article=article,
                excerpt=content[:250] + ("..." if len(content) > 250 else "")
            ))


        return ChatResponse(
            answer=rag_output.get("answer", ""),
            sources=raw_sources,
            citations=citations,
            retrieval_source=rag_output.get("retrieval_source", "hybrid"),
            retrieval_log=rag_output.get("retrieval_log"),
        )

    except Exception as e:
        print(f"[ERROR] Chat processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Error in RAG pipeline: {str(e)}")


class CrawlRequest(BaseModel):
    url: str


@app.post("/api/crawl-url")
def handle_crawl_url(req: CrawlRequest):
    """Crawl URL, kiểm duyệt nguồn chính thống, đánh giá chất lượng và tự động re-index."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    try:
        from src.crawl_validator import crawl_and_validate_url
        result = crawl_and_validate_url(req.url.strip())
        return result
    except Exception as e:
        print(f"[ERROR] Crawl error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing URL: {str(e)}")


@app.post("/api/index")
def trigger_indexing():
    """Trigger re-indexing of all legal docs in data/standardized and data/landing."""
    try:
        run_pipeline()
        return {"status": "success", "message": "Indexing completed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing error: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
