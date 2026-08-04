# RAG Evaluation Results

- Framework: **RAGAS 0.1.21**
- Số câu hỏi: **15**
- Trạng thái: **Chưa chạy được phép chấm điểm**

## So sánh cấu hình

| Metric | Config A (top_k=3) | Config B (top_k=5) | Δ |
|---|---:|---:|---:|
| faithfulness | N/A | N/A | N/A |
| answer_relevancy | N/A | N/A | N/A |
| context_recall | N/A | N/A | N/A |
| context_precision | N/A | N/A | N/A |

Pipeline đánh giá đã được cài đặt nhưng môi trường hiện tại chưa có `OPENAI_API_KEY` hoặc
`OPENROUTER_API_KEY`, đồng thời chưa cài `ragas`, `langchain-openai` và `streamlit`.
Không có điểm số giả được điền vào bảng. Sau khi cấu hình dependencies và API key, chạy:

```bash
python -m group_project.evaluation.eval_pipeline
```

Lệnh sẽ đánh giá đủ 15 câu cho cả hai cấu hình, ghi bốn chỉ số và bảng chi tiết theo từng
câu hỏi đè lên file này.
