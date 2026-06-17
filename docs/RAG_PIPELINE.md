# RAG Pipeline — Step-by-Step Retrieval Flow

This document walks through every stage of the Retrieval-Augmented Generation pipeline implemented in `backend/read_pdf_bm25_structured.py` and orchestrated by `backend/server.py`.

---

## Stage 1: PDF Ingestion

Triggered by `POST /api/ingest` after a PDF has been uploaded.

### 1.1 PDF Parsing

```
PDF file  →  PyPDF PdfReader  →  raw text per page
```

PyPDF reads each page and extracts the text layer. Scanned-image PDFs without a text layer will produce empty strings (OCR is not included).

### 1.2 Text Cleaning

Each page's raw text goes through `clean_text()`:

- Replace broken Unicode symbols (`¼` → `=`, `�` → space)
- Rejoin hyphenated line breaks (`stake-\nholders` → `stakeholders`)
- Collapse all whitespace sequences into single spaces

### 1.3 Section Detection

The cleaned text is scanned for academic section headers (Abstract, Introduction, Methods, Results, Discussion, Conclusion, References, etc.) using `SECTION_HEADER_MAP`. Each chunk inherits the section label of the heading that precedes it.

### 1.4 Chunking

Each page is split into chunks of approximately **1 200 characters** with **2-sentence overlap** between consecutive chunks.

Metadata stored per chunk:

| Field | Example |
|---|---|
| `page` | 3 |
| `chunk_number` | 7 |
| `section` | `methods` |
| `source` | `uploaded_pdfs/paper.pdf` |

A 10-page research paper typically produces 40–60 chunks.

### 1.5 Vector Indexing (ChromaDB)

Each chunk is encoded into a **384-dimensional vector** using `sentence-transformers/all-MiniLM-L6-v2`. The vectors and their metadata are upserted into a ChromaDB collection. ChromaDB uses cosine similarity for nearest-neighbour search.

### 1.6 BM25 Keyword Indexing

Each chunk is tokenized:

1. Lowercased and stripped of non-alphanumeric characters
2. Stopwords removed (the, a, an, of, to, ...)
3. Simple suffix stemming (methods → method, objectives → objective)

Term frequencies (TF) and inverse document frequencies (IDF) are computed across all chunks and saved to `bm25_index.pkl`.

---

## Stage 2: Question Answering

Triggered by `POST /api/chat`.

### 2.1 Hybrid Retrieval

Two search paths run simultaneously on the user's question:

#### Vector Search (semantic)

```
question  →  embed with all-MiniLM-L6-v2  →  query ChromaDB  →  top 30 chunks
```

Finds chunks whose **meaning** is closest to the question. Handles paraphrasing — "how many people participated?" matches a chunk saying "the sample comprised 150 respondents."

#### BM25 Search (keyword)

```
question  →  tokenize + stem  →  expand with synonyms  →  score all chunks  →  top 30 chunks
```

Query expansion adds domain synonyms:
- "method" → also searches for "analysis", "model", "approach", "technique"
- "participant" → also searches for "sample", "respondent", "subject"
- "objective" → also searches for "aim", "goal", "purpose"

Finds chunks containing the **exact keywords** from the question. Catches specific terms like "PLS-SEM" that semantic search may misclassify.

### 2.2 Merge and Deduplication

The two result lists (up to 60 chunks) are merged by chunk ID. Duplicates are collapsed into a single entry tagged with a `hybrid` source label. Hybrid chunks are the strongest signal — they matched on both meaning and keywords.

### 2.3 Reranking

Every merged chunk is rescored with a weighted combination of signals:

```
final_score = vector_score
            + bm25_score
            + intent_boost
            + section_boost
            + doc_type_boost
            - reference_penalty
```

| Signal | What it measures |
|---|---|
| `vector_score` | Cosine similarity between question embedding and chunk embedding |
| `bm25_score` | BM25 keyword relevance score |
| `intent_boost` | Does the chunk type match the question intent? (count question → chunk with numbers; summary → general overview) |
| `section_boost` | Does the chunk's section match the question topic? ("methods" question → Methods section chunks boosted) |
| `doc_type_boost` | Adjustments based on document type (resume vs. research paper) |
| `reference_penalty` | Bibliography and citation-list chunks are penalized (they rarely contain answers) |

Chunks are sorted by `final_score` descending.

### 2.4 Chunk Selection

The **top 5** chunks after reranking are selected for the LLM prompt.

Special handling:
- **Count questions** ("how many..."): only chunks containing actual numbers are kept.
- **Summary questions**: top general-purpose chunks are used regardless of section.

### 2.5 LLM Answer Generation

The 5 selected chunks are sent to **Meta-Llama-3.1-8B-Instruct** via Featherless AI (OpenAI-compatible API).

System prompt (simplified):
> You are a document QA assistant. Answer ONLY from the provided chunks. Do not use outside knowledge. Cite the page and chunk number for every claim.

The LLM returns a natural-language answer ending with:
```
Sources: Page 3, Chunk 4; Page 5, Chunk 1
```

### 2.6 Citation Validation

The backend parses the `Sources:` line from the LLM's answer and verifies:

- Was Page 3, Chunk 4 actually in the 5 chunks sent to the LLM?
- Was Page 5, Chunk 1 actually sent?

If the LLM invents a citation that wasn't in its context, the citation is flagged as hallucinated. If no citations are present in the answer, the backend falls back to attributing the top 4 evidence chunks.

### 2.7 Routing Decision

The backend inspects the LLM's answer text for two simultaneous conditions:

1. A **context reference** ("the provided context", "the document", "the PDF")
2. An **absence signal** ("does not contain", "no information", "cannot find")

| Condition | Action |
|---|---|
| Tavily triggered internally (engine confidence floor) | Return web answer, `source_type: "web"` |
| LLM signals "context doesn't contain this" AND Tavily is available | Search the web with Tavily (3 results), re-ask LLM with web context, return `source_type: "web"` with `web_sources` |
| LLM signals "not found" but Tavily unavailable/empty | Return the not-found answer, `source_type: "pdf_not_found"` |
| PDF answered successfully | Return answer + page/chunk citations, `source_type: "pdf"` |

### 2.8 Web Search Fallback (Tavily)

When triggered:

1. Tavily searches the web for the original question (`max_results=3`)
2. Each result provides: `title`, `content`, `url`
3. The web results are formatted as context and sent to the LLM with a web-specific prompt
4. The LLM generates a new answer from web context
5. The hallucinated `Sources: Page X, Chunk Y` line (if any) is stripped
6. The response includes `web_sources: [{title, url}, ...]` for clickable links in the UI

---

## Pipeline Summary

```
 ┌───────────────────────────────────────────────────────────┐
 │                    INGESTION (once per PDF)                │
 │                                                           │
 │  PDF → parse → clean → detect sections → chunk            │
 │       → embed (all-MiniLM) → store in ChromaDB            │
 │       → tokenize → build BM25 index                       │
 └───────────────────────────────────────────────────────────┘

 ┌───────────────────────────────────────────────────────────┐
 │                 QUERY (every question)                     │
 │                                                           │
 │  Question → vector search (top 30)                        │
 │           → BM25 search (top 30)                          │
 │           → merge + deduplicate                           │
 │           → rerank (5+ signals)                           │
 │           → select top 5 chunks                           │
 │           → LLM generates answer with citations           │
 │           → validate citations                            │
 │           → route: PDF answer / web fallback / not found  │
 └───────────────────────────────────────────────────────────┘
```
