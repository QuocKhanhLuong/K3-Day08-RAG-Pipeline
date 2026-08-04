"""Streamlit chat UI for the citation-grounded labour-law RAG pipeline.

Run with: ``streamlit run app.py``
"""

from pathlib import Path
import sys

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.task10_generation import generate_with_citation  # noqa: E402


st.set_page_config(
    page_title="Trợ lý Luật Lao động",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_sources(sources: list[dict]) -> None:
    """Render retrieved evidence without assuming every metadata field exists."""
    if not sources:
        return
    with st.expander(f"📚 Nguồn tham khảo ({len(sources)} đoạn)"):
        for index, source in enumerate(sources, 1):
            metadata = source.get("metadata") or {}
            name = (
                metadata.get("display_source")
                or metadata.get("title")
                or metadata.get("source")
                or "Không rõ nguồn"
            )
            kind = metadata.get("type", "document")
            score = source.get("score")
            score_text = f" · score `{score:.4f}`" if isinstance(score, (int, float)) else ""
            st.markdown(f"**[{index}] {name}** · `{kind}`{score_text}")
            content = source.get("content", "")
            st.text(content[:500] + ("…" if len(content) > 500 else ""))


if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

with st.sidebar:
    st.title("⚖️ Trợ lý Luật Lao động")
    st.caption("Tra cứu có dẫn nguồn từ Bộ luật Lao động và văn bản hướng dẫn.")
    st.divider()
    st.subheader("Câu hỏi gợi ý")
    suggestions = [
        "Thời gian thử việc tối đa là bao lâu?",
        "Nghỉ việc với hợp đồng không xác định thời hạn phải báo trước bao lâu?",
        "Công ty chậm trả lương có phải trả thêm tiền không?",
        "Lương làm thêm giờ ngày lễ được tính thế nào?",
        "Người lao động được nghỉ hằng năm bao nhiêu ngày?",
    ]
    for index, suggestion in enumerate(suggestions):
        if st.button(suggestion, use_container_width=True, key=f"suggestion-{index}"):
            st.session_state.pending_query = suggestion
    st.divider()
    top_k = st.slider("Số đoạn truy xuất", min_value=3, max_value=10, value=5)
    if st.button("Xóa hội thoại", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_query = None
        st.rerun()
    st.caption("Hybrid retrieval → reranking → generation có citation")

st.title("⚖️ Hỏi đáp Luật Lao động Việt Nam")
st.caption("Thông tin chỉ mang tính tham khảo; hãy đối chiếu văn bản hiện hành khi ra quyết định pháp lý.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("sources", []))

typed_query = st.chat_input("Nhập câu hỏi về hợp đồng, lương, thử việc, nghỉ phép…")
query = typed_query or st.session_state.pending_query

if query:
    st.session_state.pending_query = None
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm căn cứ và tổng hợp câu trả lời…"):
            try:
                response = generate_with_citation(query, top_k=top_k)
                answer = response.get("answer") or "Tôi không thể xác minh thông tin này từ nguồn hiện có"
                sources = response.get("sources") or []
            except Exception as error:
                answer = f"Không thể chạy RAG pipeline: `{type(error).__name__}: {error}`"
                sources = []
            st.markdown(answer)
            render_sources(sources)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
