# Handoff Notes for Tasks 4–10

## Ready inputs

- `data/standardized/legal/*.md`: government PDF converted by MarkItDown,
  YAML metadata sourced from `data/landing/legal/legal_sources.json`.
- `data/standardized/news/*.md`: public Government Portal guidance with
  `normative: false` and `legal_status: reference`.
- `src/schemas.py`: shared typed contract and safe indexing predicate.

## Indexing safeguards for Task 4

1. Read the YAML header before content and preserve it on every chunk.
2. Use the legal hierarchy `Chương → Mục → Điều → Khoản → Điểm`; never detach
   an `Điều` title from its body merely to meet a character limit.
3. Default-index only normative records marked `in_force` or
   `partially_effective`. Do not silently treat `unknown`, `expired` or
   `replaced` as current law.
4. A `partially_effective` source is not automatically unusable, but its
   citation needs the specific provision checked against amendments.
5. Do not use official guidance or a future contract template as the normative
   evidence for a legal conclusion.

At handoff on 2026-08-04, the four collected normative records are marked
`unknown`: their surveyed CSDL VBPL status endpoints returned HTTP 404 when
directly checked. Keep them in a quarantined/non-current collection until a
directly reachable official status record is added to the manifest.

## Retrieval / generation requirements for Tasks 5–10

- Every result must preserve `document_id`, `source_url`, `normative`,
  `legal_status`, legal hierarchy fields and score provenance.
- Evidence gates should favor current normative evidence and refuse a current
  legal conclusion if status/provision cannot be verified.
- A response about probation, apprenticeship, traineeship or internship must
  state its assumption when the worker's legal relationship is unclear.
- Citation formatter should output the real document number and available
  `Điều`, `Khoản`, `Điểm`; it must not invent hierarchy fields.

## Out of scope for this branch

No embedding, Chroma index, lexical/dense retrieval, RRF, PageIndex, LLM,
Streamlit or RAGAS behavior is implemented or changed here.
