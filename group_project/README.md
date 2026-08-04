# Nhóm — ⚖️ Trợ Lý Hỏi Đáp Luật Lao Động Cho Người Trẻ

## Product goal

The team is building a legal-information assistant for common early-career
employment questions: probation, contracts, wages, overtime, leave,
termination and labour discipline. It must retrieve evidence before answering,
cite the real legal document/article/clause where available, and state that it
is not legal advice.

## Architecture

```text
Official legal sources ─┐
                         ├→ Markdown + legal metadata → article/clause chunks
Official guidance ───────┘                                  │
                                               BGE-M3/Chroma + BM25
                                                           │
                                                         RRF
                                                           │
                                             dense evidence gate / PageIndex
                                                           │
                                           citation-grounded LLM → Streamlit
```

The branch `agent/legal-data-pipeline` delivers only the data handoff on the
left side of this diagram. It does not claim that indexing, retrieval,
generation, chatbot or evaluation are complete.

## Data handoff

| Input | Contract |
|---|---|
| `data/landing/legal/legal_sources.json` | Canonical source, status, dates and SHA-256 manifest. |
| `data/standardized/legal/*.md` | Normative government text with YAML front matter. |
| `data/standardized/news/*.md` | Official guidance, always `normative: false`, `legal_status: reference`. |
| `src/schemas.py` | Shared TypedDict contract and safe indexing predicate. |

Read [DATA_CONTRACT.md](../docs/DATA_CONTRACT.md) and
[HANDOFF_NOTES.md](../docs/HANDOFF_NOTES.md) before changing Task 4–10.

## Team allocation

| Member | MSSV | Responsibility | Current scope |
|---|---|---|---|
| Lương Quốc Khánh | 2A202601713 | Role 1 team lead/RAG architect; Tasks 1–3 data engineering | Data contract, collection, standardization, validation, supervisor |
| TBD | TBD | Tasks 4–6 | Legal-aware chunking, Chroma, dense and BM25 retrieval |
| TBD | TBD | Tasks 7–8 | RRF/reranking and PageIndex fallback |
| TBD | TBD | Tasks 9–10 and app | Retrieval pipeline, grounded generation, Streamlit |
| TBD | TBD | Evaluation | Golden dataset, RAGAS and A/B report |

## Integration rules

1. Preserve `document_id`, `source_url`, `normative`, `legal_status` and legal
   hierarchy metadata in every chunk/result/citation.
2. Never answer a current-law question using `unknown`, `expired`, `replaced`
   or guidance-only evidence.
3. Do not use RRF score as the evidence-quality threshold; use original dense
   cosine similarity.
4. Guidance and contract templates are explanatory only, never the legal rule.
5. Maintain the disclaimer in the user interface and refuse when evidence is
   insufficient.

## Data setup and checks

```bash
conda activate data-foundations
python -m pip install --prefer-binary -r requirements.txt
python -m src.supervisor prepare-data
python -m src.validate_corpus
pytest tests/test_data_pipeline.py -v
```

Subsequent owners should document their Task 4–10 verification and evaluation
results here when those implementations are actually available.
