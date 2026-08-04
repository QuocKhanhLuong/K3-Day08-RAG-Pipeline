"""
Task 10 — Generation Có Citation.

Hướng dẫn:
    1. Chọn top_k, top_p phù hợp (giải thích lý do)
    2. Sắp xếp lại chunks sau reranking để tránh "lost in the middle"
    3. Inject context vào prompt
    4. Yêu cầu LLM trả lời có citation
    5. Nếu không đủ evidence → "Tôi không thể xác minh thông tin này từ nguồn hiện có"
"""

import os
from dotenv import load_dotenv

load_dotenv()

try:
    from .task9_retrieval_pipeline import retrieve
except ImportError:
    from task9_retrieval_pipeline import retrieve


# =============================================================================
# CONFIGURATION
# =============================================================================

# top_k: 5 chunks đủ ngữ cảnh mà không gây quá tải cho prompt
TOP_K = 5

# top_p (nucleus sampling): 0.9 đủ đa dạng từ vựng mà vẫn kiểm soát độ chính xác
TOP_P = 0.9

# temperature: 0.3 vì RAG yêu cầu trung thực với dữ liệu gốc (factual)
TEMPERATURE = 0.3

# OpenAI hoặc OpenRouter model ID
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """Bạn là trợ lý tư vấn pháp luật lao động Việt Nam (Bộ luật Lao động 2019, các Nghị định và tài liệu hướng dẫn chính thống).

Quy tắc bắt buộc:
1. Chỉ sử dụng thông tin từ context được cung cấp — KHÔNG bịa đặt
2. Mỗi khẳng định phải có trích dẫn nguồn văn bản hoặc điều luật tương ứng (ví dụ: [Bộ luật Lao động 2019], [Nghị định 145/2020/NĐ-CP])
3. Nếu context không đủ thông tin → trả lời: "Tôi không thể xác minh thông tin này từ nguồn hiện có"
4. Trả lời bằng tiếng Việt, có cấu trúc rõ ràng, chuyên nghiệp và dễ hiểu
5. Không suy luận hay mở rộng ngoài những gì được nêu trong context"""


# =============================================================================
# DOCUMENT REORDERING (tránh lost in the middle)
# =============================================================================

def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle" effect.

    Input order (by score):  [1, 2, 3, 4, 5]
    Output order:            [1, 3, 5, 4, 2]
    """
    if not chunks or len(chunks) <= 2:
        return chunks

    front = chunks[::2]   # index 0, 2, 4 -> đặt ở đầu
    back = chunks[1::2]   # index 1, 3    -> đặt ở cuối (reversed)
    return front + back[::-1]


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    Mỗi chunk có label source để LLM có thể cite.
    """
    if not chunks:
        return "Không có ngữ cảnh phù hợp."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("metadata", {}).get("source", f"Source {i}")
        doc_type = chunk.get("metadata", {}).get("type", "unknown")
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk['content']}\n"
        )
    return "\n---\n".join(context_parts)


# =============================================================================
# GENERATION
# =============================================================================

def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.
    """
    if not query.strip():
        return {
            "answer": "Vui lòng nhập câu hỏi.",
            "sources": [],
            "retrieval_source": "none"
        }

    # Step 1: Retrieve
    chunks = retrieve(query, top_k=top_k)

    if not chunks:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có",
            "sources": [],
            "retrieval_source": "none"
        }

    # Step 2: Reorder
    reordered = reorder_for_llm(chunks)

    # Step 3: Format context
    context = format_context(reordered)

    # Step 4: Call LLM (OpenAI / OpenRouter)
    openai_key = os.getenv("OPENAI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if openai_key:
        try:
            from openai import OpenAI
            client_args = {"api_key": openai_key}
            if os.getenv("OPENAI_BASE_URL"):
                client_args["base_url"] = os.getenv("OPENAI_BASE_URL")
            client = OpenAI(**client_args)

            user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"
            model_name = LLM_MODEL.replace("openai/", "")
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=TEMPERATURE,
                top_p=TOP_P,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            print(f"[WARNING] OpenAI API call error: {e}")
            answer = f"Theo thông tin tìm được từ nguồn dữ liệu:\n\n{context}\n\n[Trích dẫn tự động]"
    elif openrouter_key:
        try:
            from openai import OpenAI
            base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            client = OpenAI(api_key=openrouter_key, base_url=base_url)

            user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"
            model_id = LLM_MODEL if "/" in LLM_MODEL else f"openai/{LLM_MODEL}"
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=TEMPERATURE,
                top_p=TOP_P,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            print(f"[WARNING] OpenRouter API call error: {e}")
            answer = f"Theo thông tin tìm được từ nguồn dữ liệu:\n\n{context}\n\n[Trích dẫn tự động]"
    else:
        # Structured fallback response when no API key configured
        source_names = [c.get("metadata", {}).get("source", "Tài liệu") for c in chunks[:3]]
        answer = f"Dựa trên các văn bản pháp luật và hướng dẫn [{', '.join(source_names)}]:\n\n" + \
                 "\n".join([f"• {c['content'][:250]}..." for c in chunks[:3]])

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none"
    }


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    test_queries = [
        "Không nghỉ hết phép năm có được thanh toán tiền?",
        "Thời gian thử việc tối đa và mức lương thử việc quy định như thế nào?",
        "Giới hạn thời giờ làm thêm giờ và thủ tục đăng ký tăng giờ làm thêm?",
    ]

    for q in test_queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")

