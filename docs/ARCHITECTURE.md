# Architecture

DocuMind AI is a full-stack RAG (Retrieval-Augmented Generation) chatbot. Users upload a PDF, ask questions in natural language, and receive answers with page-level citations. When the PDF lacks the answer, the system falls back to live web search.

---

## High-Level Diagram

```
┌──────────────────────────────┐
│        User's Browser        │
│   React 19 + TanStack Start │
│   (deployed on Vercel)       │
└─────────────┬────────────────┘
              │  HTTPS  (REST / JSON)
              │  POST /api/upload
              │  POST /api/ingest
              │  POST /api/chat
              ▼
┌──────────────────────────────┐
│   FastAPI Backend (Render)   │
│   server.py                  │
│                              │
│  ┌────────────────────────┐  │
│  │   HybridRAGEngine      │  │
│  │   (read_pdf_bm25_      │  │
│  │    structured.py)       │  │
│  │                         │  │
│  │  ingest: PDF → chunks   │  │
│  │  retrieve: hybrid search│  │
│  │  rerank: multi-signal   │  │
│  │  answer: LLM generation │  │
│  └────────────────────────┘  │
│        │            │        │
│        ▼            ▼        │
│  ┌──────────┐ ┌──────────┐   │
│  │ ChromaDB │ │   BM25   │   │
│  │ (vector) │ │(keyword) │   │
│  └──────────┘ └──────────┘   │
└────────┬─────────────────────┘
         │
   ┌─────┴──────────┐
   ▼                ▼
┌────────────┐ ┌─────────────┐
│Featherless │ │   Tavily    │
│ AI  (LLM)  │ │(web search) │
│Meta-Llama  │ │             │
└────────────┘ └─────────────┘
```

---

## Components

### 1. PDF Upload and Storage

- **Endpoint:** `POST /api/upload`
- The user drags a PDF into the browser. The frontend sends the binary file to the backend.
- `server.py` sanitizes the filename (strips directory traversal characters, replaces unsafe chars) and saves the file to `uploaded_pdfs/` on the Render disk.
- Returns the saved file path so the frontend can trigger ingestion.

### 2. Chunking and Indexing (`POST /api/ingest`)

Ingestion converts a raw PDF into two searchable indexes.

| Step | What happens | Output |
|---|---|---|
| **PDF parsing** | PyPDF reads the file page by page | Raw text per page |
| **Text cleaning** | Fixes broken characters, rejoins hyphenated line breaks, collapses whitespace | Clean text per page |
| **Section detection** | Matches headings against an academic section map (abstract, methods, results, ...) | Section label per page region |
| **Chunking** | Splits each page into ~1 200-character pieces with 2-sentence overlap | List of chunks with metadata: `page`, `chunk_number`, `section` |
| **Vector indexing** | `sentence-transformers/all-MiniLM-L6-v2` encodes each chunk into a 384-dim vector; stored in ChromaDB | Vector index ready for cosine-similarity search |
| **BM25 indexing** | Each chunk is tokenized (lowercased, stopwords removed, stemmed); term frequencies and IDF scores are computed | BM25 index saved to `bm25_index.pkl` |

### 3. Hybrid Retrieval

When a question arrives at `POST /api/chat`, two retrieval paths run simultaneously:

- **Vector search (ChromaDB):** The question is embedded with the same model and the 30 nearest chunks are returned by cosine similarity. This finds chunks that are *semantically* similar — "heart attack" matches "cardiac arrest."
- **BM25 keyword search:** The question is tokenized and expanded with domain synonyms (e.g., "method" → "analysis", "technique"). BM25 scores all chunks by keyword overlap and returns the top 30. This catches exact terminology that semantic search may miss.

Both result sets are merged. A chunk found by both methods gets a `hybrid` label — the strongest retrieval signal.

### 4. Reranking

Merged chunks are rescored using multiple signals:

| Signal | Purpose |
|---|---|
| Vector similarity score | How close in meaning |
| BM25 keyword score | How many query words matched |
| Intent boost | Extra score when chunk type matches question intent (e.g., count question + chunk with numbers) |
| Section boost | "Methods" question → boost chunks from Methods section |
| Document type boost | Resume vs. research paper scoring adjustments |
| Reference penalty | Bibliography / citation-list chunks are penalized (they rarely answer questions) |

The top 5 chunks after reranking are selected for answer generation.

### 5. Answer Generation

The 5 selected chunks are sent to **Featherless AI** (hosting Meta-Llama-3.1-8B-Instruct) via an OpenAI-compatible API call. The system prompt instructs the LLM:

> "Answer ONLY from the provided chunks. Do not use external knowledge. Cite the page and chunk number for each claim."

The LLM appends `Sources: Page X, Chunk Y` markers at the end of its answer.

### 6. Citation Validation

After the LLM responds, the backend parses the `Sources:` line and checks whether each cited page/chunk number was actually in the chunks that were sent. If the LLM invents a citation (a hallucination), it is flagged. When the LLM omits citations entirely, the backend falls back to attributing the top 4 evidence chunks.

### 7. Tavily Web Search Fallback

The backend detects when the LLM's answer signals "the provided context does not contain this information" by matching against two phrase lists:

1. **Context reference phrases** — "provided context", "the document", "the PDF", etc.
2. **Absence signals** — "does not contain", "no information", "cannot find", etc.

Both conditions must match simultaneously to avoid false positives (a legitimate PDF answer like "participants did not find a correlation" won't trigger fallback).

When triggered:
1. Tavily searches the web for the original question (3 results).
2. The LLM is re-invoked with the web results as context instead of PDF chunks.
3. The response includes clickable `web_sources` (title + URL) instead of page citations.

### 8. Response Routing

`server.py` has three return paths:

| Route | Condition | Response shape |
|---|---|---|
| **Route 1** | Tavily was triggered internally by the engine (confidence floor) | `source_type: "web"`, no citations |
| **Route 2** | LLM explicitly said "context doesn't contain this" → server-side Tavily re-answer | `source_type: "web"`, `web_sources: [{title, url}]` |
| **Route 3** | PDF answered successfully | `source_type: "pdf"`, `citations: ["Page X, Chunk Y"]` |

---

## Deployment

| Component | Host | URL |
|---|---|---|
| Frontend | Vercel | `https://pdf-rag-chatbot-pi.vercel.app` |
| Backend | Render | `https://documind-backend-xzwd.onrender.com` |

Both auto-deploy from the `main` branch on GitHub. The frontend communicates with the backend over HTTPS. CORS middleware on the backend allows the Vercel origin.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Hybrid search over vector-only | BM25 catches exact technical terms that semantic search misclassifies |
| Custom reranker over a library | Full control over scoring signals; no external API dependency |
| BM25 from scratch over Elasticsearch | Lightweight, no separate server, sufficient for single-PDF retrieval |
| ChromaDB over Pinecone | Open-source, runs in-process, zero cost |
| Featherless AI over OpenAI | Free tier, OpenAI-compatible API (one-line switch if needed) |
| Sentence overlap in chunking | Prevents information loss at chunk boundaries |
| Section-aware metadata | Enables section-boost reranking for academic papers |
