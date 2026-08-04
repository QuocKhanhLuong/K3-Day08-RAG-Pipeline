---
title: Gen Z Labor Law Assistant
emoji: ⚖️
colorFrom: amber
colorTo: red
sdk: streamlit
sdk_version: "1.35.0"
app_file: app.py
pinned: false
---

# ⚖️ Trợ Lý Hỏi Đáp Luật Lao Động Cho Người Trẻ

Corpus-first RAG project for common Vietnamese employment-law questions:
probation, employment contracts, pay, overtime/night work, leave, termination,
discipline and salary delay/deduction. The system is an information-retrieval
aid, not a lawyer or a substitute for professional legal advice.

This branch completes the data-engineering handoff (Tasks 1–3) and the shared
architecture contract. Tasks 4–10 remain owned by their assigned members and
are **not claimed as implemented here**.

## Scope and safety policy

- Ground truth is limited to official Vietnamese legal sources and official
  Government Portal guidance.
- A guidance item is always `normative: false`; it cannot replace a code,
  decree or circular as the basis for a legal conclusion.
- Current-law answers need verified status metadata. `unknown`, `expired` and
  `replaced` sources are not a safe default. `partially_effective` sources
  require article-level amendment review.
- Out of scope: divorce, land, criminal law, traffic, tax, in-depth social
  insurance, foreign workers and specialist trade-union matters.

## Data flow

```text
Official Government / CSDL VBPL sources
               │
               ▼
Download + magic-byte + checksum validation
               │
      ┌────────┴─────────┐
      ▼                  ▼
Legal PDF/DOCX     Official guidance JSON
      │                  │
      └────────┬─────────┘
               ▼
Markdown + YAML legal metadata
               ▼
Offline corpus validation
               ▼
Ready for Task 4 legal-aware chunking and indexing
```

The intended downstream architecture is:

```text
Markdown corpus → legal-aware chunks → BGE-M3 / ChromaDB
                                      └→ BM25
                                            │
                                      RRF + evidence gate
                                            │
                               citation-grounded generation
```

RRF is a fusion rank, not a measure of evidence strength; any later fallback
gate must use the original dense cosine score. See
[DATA_CONTRACT.md](docs/DATA_CONTRACT.md) and
[HANDOFF_NOTES.md](docs/HANDOFF_NOTES.md).

## Corpus collected

`data/landing/legal/legal_sources.json` is the source-of-truth manifest. It
stores canonical URL, download URL, dates, status, amendment lists, collection
time and SHA-256 for every binary file.

| Document | Number | Source | Status recorded | Effective date |
|---|---|---|---|---|
| Bộ luật Lao động | 45/2019/QH14 | [Government Portal](https://vanban.chinhphu.vn/?classid=1&docid=198540&pageid=27160&typegroupid=3) | `unknown` — CSDL status URL was not directly reachable at collection | 2021-01-01 |
| Nghị định về điều kiện lao động và quan hệ lao động | 145/2020/NĐ-CP | [Government Portal](https://vanban.chinhphu.vn/default.aspx?docid=201967&pageid=27160) | `unknown` — CSDL status URL was not directly reachable at collection | 2021-02-01 |
| Nghị định xử phạt vi phạm hành chính lĩnh vực lao động | 12/2022/NĐ-CP | [Government Portal](https://vanban.chinhphu.vn/?classid=1&docid=205182&orggroupid=2&pageid=27160) | `unknown` — CSDL status URL was not directly reachable at collection | 2022-01-17 |
| Nghị định về mức lương tối thiểu | 293/2025/NĐ-CP | [Government Portal](https://vanban.chinhphu.vn/?classid=1&docid=215832&pageid=27160) | `unknown` pending CSDL status verification | 2026-01-01 |

The corpus also contains six official guidance records from
[Báo Điện tử Chính phủ](https://baochinhphu.vn/): probation, overtime,
unilateral termination, annual leave, salary delay and rights under the 2019
Labour Code. They are supplementary evidence only.

## Repository layout

```text
data/
  landing/legal/             original legal PDFs + legal_sources.json
  landing/news/              official guidance JSON (historical folder name)
  standardized/legal/        Markdown with legal YAML front matter
  standardized/news/         guidance Markdown with YAML front matter
docs/DATA_CONTRACT.md        shared input/output contract for Tasks 4–10
docs/HANDOFF_NOTES.md        implementation safeguards for later roles
src/task1_collect_legal_docs.py
src/task2_crawl_news.py
src/task3_convert_markdown.py
src/schemas.py               TypedDict contract; no retrieval implementation
src/validate_corpus.py       offline quality gate
src/supervisor.py            data-only orchestration CLI
```

## Setup

Use the requested Conda environment; do not create a project venv.

```bash
conda activate data-foundations
python -m pip install --prefer-binary -r requirements.txt
playwright install chromium
```

`Crawl4AI` is imported lazily and uses a local ignored runtime cache. If a
browser is missing, Task 2 prints `playwright install chromium` and records a
transparent normal-HTTPS fallback rather than bypassing a WAF.

## Run the data pipeline

```bash
python -m src.task1_collect_legal_docs
python -m src.task2_crawl_news
python -m src.task3_convert_markdown --rebuild-all
python -m src.validate_corpus
```

Or use the Role 1 supervisor:

```bash
python -m src.supervisor inspect
python -m src.supervisor prepare-data
python -m src.supervisor status
```

`prepare-data` does not replace valid files on a failed request. Add `--force`
to either collection command only when intentionally refreshing sources.

## Handoff to Task 4

Task 4 reads only `data/standardized/{legal,news}/*.md`, parses YAML first and
preserves metadata on all chunks. The safe default is:

```python
from src.schemas import is_indexable_normative

# True only for normative in_force / partially_effective sources.
is_indexable_normative(metadata)
```

Chunking must preserve `Chương → Mục → Điều → Khoản → Điểm`. It must never use
a contract template or guidance article as a normative rule. The full field
schema and missing-value policy are in [DATA_CONTRACT.md](docs/DATA_CONTRACT.md).
**Current handoff caveat:** all four collected normative records are currently
`unknown` because their status endpoints were not directly reachable on
2026-08-04. Task 4 must therefore wait for a renewed official status check (or
place them in a quarantined, non-current collection) rather than index them as
current law.

## Tests for this scope

```bash
conda activate data-foundations
pytest tests/test_individual.py::TestTask1 -v
pytest tests/test_individual.py::TestTask2 -v
pytest tests/test_individual.py::TestTask3 -v
pytest tests/test_data_pipeline.py -v
```

Run the data validator before handing the corpus to Task 4:

```bash
python -m src.validate_corpus
```

## Team responsibilities

| Workstream | Owner | Status on this branch |
|---|---|---|
| Role 1 architecture, data contract, corpus validation, supervisor | Lương Quốc Khánh | Implemented in scope |
| Tasks 1–3 data engineering | Lương Quốc Khánh | Implemented in scope |
| Tasks 4–10, app and RAG evaluation | Assigned teammates | Not implemented or modified on this branch |

## Known limitations

- Legal status is only as current as the recorded official verification page;
  `unknown` status is intentionally excluded by the safe default.
- Browser-backed Crawl4AI needs local Chromium; public static HTML fallback is
  logged explicitly in JSON rather than disguised as crawler output.
- This branch does not provide embeddings, a vector store, retrieval, response
  generation, a Streamlit UX or RAGAS evaluation.
