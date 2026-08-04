# Data Contract — Vietnam Youth Labour Law RAG

This is the hand-off contract from Role 1 / Tasks 1–3 to the members owning
Tasks 4–10.  The raw files are evidence assets; standardized Markdown is the
only indexing input.

```text
data/landing/legal/                     original PDF/DOCX + legal_sources.json
data/landing/news/                      official guidance JSON
data/standardized/legal/*.md            normative legal source Markdown
data/standardized/news/*.md             non-normative guidance Markdown
```

## `LegalDocument` and `LegalChunk`

```python
class LegalDocument(TypedDict):
    content: str
    metadata: LegalMetadata

class LegalChunk(TypedDict):
    content: str
    metadata: LegalMetadata
```

Tasks 4–10 must carry the original metadata in every chunk, retrieval result,
context block and citation. `src/schemas.py` is the canonical machine-readable
definition.

| Field | Meaning / required value |
|---|---|
| `document_id` | Stable unique corpus ID, e.g. `labor_code_45_2019`. |
| `source`, `source_path` | Original filename and repository-relative landing path. |
| `source_url` | Canonical public HTTPS source page. |
| `title`, `document_number`, `document_type` | Human-readable legal source identity. `document_number` may be null for guidance. |
| `issuing_authority`, `issued_date`, `effective_date`, `expiry_date` | Provenance and temporal information; date values are ISO `YYYY-MM-DD` or null. |
| `legal_status` | Exactly one of `in_force`, `partially_effective`, `expired`, `replaced`, `unknown`, `reference`. |
| `normative` | Boolean. Only laws, decrees, circulars and other normative instruments are `true`. |
| `chapter`, `section`, `article`, `clause`, `point` | Filled by legal-aware chunking in Task 4; null before the relevant hierarchy is parsed. |
| `legal_topics` | List from the agreed labour-law scope, never a comma-separated string. |
| `audience_roles` | Zero or more of `job_applicant`, `intern`, `apprentice`, `trainee`, `probationer`, `employee`, `former_employee`, `employer`. |
| `chunk_index` | Integer after Task 4, null in a source document. |

## Normative policy and legal status

- `normative: true` means a statute, code, decree, circular or other normative
  instrument. It is the required basis for a legal conclusion.
- `normative: false` means official guidance, FAQ, communication material or a
  contract template. It may explain or route a query but never replaces the
  cited legal provision.
- `legal_status: reference` is reserved for non-normative guidance.
- `unknown`, `expired` and `replaced` are not safe defaults for an answer about
  current law. They need a later human/legal-status review.

The safe default for Task 4 is implemented by
`schemas.is_indexable_normative`: index only `normative=true` documents with
`legal_status` `in_force` or `partially_effective`. A partially effective text
still needs its amendment history checked before a precise conclusion.

## Markdown front matter

Every standardized document begins with YAML and then the source text. Example:

```yaml
---
document_id: labor_code_45_2019
source: labor-code-45-2019-qh14.pdf
source_path: data/landing/legal/labor-code-45-2019-qh14.pdf
title: Bộ luật Lao động
document_number: 45/2019/QH14
document_type: labor_code
issuing_authority: Quốc hội
issued_date: '2019-11-20'
effective_date: '2021-01-01'
expiry_date: null
legal_status: partially_effective
normative: true
source_url: https://vanban.chinhphu.vn/...
legal_topics:
  - probation
audience_roles:
  - probationer
---
```

## Missing-field and downstream rules

1. Preserve null rather than invent an article, clause, effective date or
   document number.
2. Do not equate `intern`, `apprentice`, `trainee` and `probationer` without
   evidence from the question and source.
3. Task 4 must not split an `Điều` heading from its content. It should add
   `chapter`, `article`, `clause` and `point` when determinable.
4. Tasks 5–10 must return the metadata unchanged alongside result content.
5. Citations should prefer document number + `Điều` + `Khoản` + `Điểm`; a
   guidance source may not be cited as the sole legal authority.

Run the pre-index gate with:

```bash
python -m src.validate_corpus
```
