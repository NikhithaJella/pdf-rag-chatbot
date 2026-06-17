# DocuMind AI — PDF RAG Chatbot

**[🚀 Live Demo](https://pdf-rag-chatbot-pi.vercel.app)**

A full-stack RAG (Retrieval-Augmented Generation) chatbot that lets you upload any PDF and ask questions about it in natural language. When the PDF doesn't contain the answer, it automatically falls back to a live web search.

---

## How It Works

```
User question
      │
      ▼
 Hybrid Retrieval
  ┌───────────────────────────────────┐
  │  ChromaDB (vector / semantic)     │
  │  +                                │
  │  BM25 (keyword / lexical)         │
  └───────────────────────────────────┘
      │
      ▼
 Reranking + Confidence Check
      │
      ├── High confidence ──▶ Featherless AI answers from PDF chunks
      │                        Returns: answer + page/chunk citations
      │
      └── Low confidence  ──▶ Tavily Web Search fallback
                               Returns: answer + clickable web sources
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| PDF parsing | PyPDF |
| Vector store | ChromaDB |
| Keyword search | BM25 (built from scratch) |
| LLM answering | Featherless AI (OpenAI-compatible) |
| Web search fallback | Tavily |
| Backend API | FastAPI + Uvicorn |
| Frontend | React 19 + TanStack Start + Vite |
| UI components | shadcn/ui + Tailwind CSS v4 |

---

## Project Structure

```
rag-pdf-chatbot/
├── backend/
│   ├── server.py                   # FastAPI app — all API endpoints
│   ├── read_pdf_bm25_structured.py # RAG engine: chunking, retrieval, reranking, LLM
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   └── routes/index.tsx        # Main chat UI
│   ├── package.json
│   └── .env.example
├── docs/
│   ├── ARCHITECTURE.md             # System design and component breakdown
│   └── RAG_PIPELINE.md            # Step-by-step retrieval flow
├── tests/
│   └── README.md                   # Manual test plan and checklist
├── .github/
│   └── workflows/
│       └── project-check.yml       # CI: validates structure, deps, no secrets
├── render.yaml                     # One-click backend deploy config for Render
└── README.md
```

---

## Local Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ (or Bun)

### 1. Clone the repo

```bash
git clone https://github.com/NikhithaJella/pdf-rag-chatbot.git
cd pdf-rag-chatbot
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

Copy the example env file and fill in your API keys:

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

Edit `backend/.env`:
```
FEATHERLESS_API_KEY=your_key_here   # https://featherless.ai
TAVILY_API_KEY=your_key_here        # https://tavily.com
```

Start the backend:
```bash
uvicorn server:app --reload
# Runs on http://localhost:8000
```

### 3. Frontend

```bash
cd frontend
npm install          # or: bun install
npm run dev          # or: bun run dev
# Runs on http://localhost:5173
```

Open `http://localhost:5173` in your browser.

---

## Using the App

1. **Drop a PDF** into the left sidebar (drag & drop or click to browse)
2. Wait for **"Building index..."** to finish — it parses the PDF into searchable chunks
3. **Ask any question** about the document in the chat
4. Answers from the PDF show **page + chunk citations** (click to copy)
5. When the PDF doesn't have the answer, the app **searches the web** and shows clickable sources

---

## API Reference

Base URL (local): `http://localhost:8000`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload a PDF file |
| `POST` | `/api/ingest` | Build the RAG index for uploaded PDF(s) |
| `POST` | `/api/chat` | Ask a question, get an answer |

### POST `/api/chat`

Request:
```json
{ "question": "What are the main findings?" }
```

Response:
```json
{
  "answer": "The study found...",
  "citations": ["Page 3, Chunk 2", "Page 5, Chunk 1"],
  "web_search_triggered": false,
  "source_type": "pdf",
  "web_sources": []
}
```

`source_type` values:
- `"pdf"` — answered from the document, citations included
- `"web"` — web search was triggered, `web_sources` included
- `"pdf_not_found"` — not found in document and web search returned nothing

---

## Known Limitations (Free Tier)

| Limitation | Detail |
|---|---|
| Cold start delay | The Render free instance sleeps after 15 min of inactivity. First request after a break takes **~50 seconds** to wake up. |
| PDF size | ChromaDB loads a ~300 MB embedding model on first ingest. On the free 512 MB tier, keep PDFs **under ~10 pages**. Larger PDFs may cause the server to crash with an out-of-memory error. |
| Workaround | Upgrade to Render's $7/month plan (1 GB RAM) to handle any PDF size without restrictions. |

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `FEATHERLESS_API_KEY` | Yes | LLM inference via Featherless AI |
| `TAVILY_API_KEY` | No | Web search fallback (disabled if missing) |
| `ALLOWED_ORIGINS` | Production | Comma-separated frontend URLs for CORS |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | Production | Deployed backend URL |
| `NITRO_PRESET` | Vercel deploy | Set to `vercel` when deploying to Vercel |

---

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) — system design, component breakdown, and design decisions
- [RAG Pipeline](docs/RAG_PIPELINE.md) — step-by-step retrieval flow from PDF ingestion to answer generation
- [Manual Test Plan](tests/README.md) — checklist for verifying upload, chat, citations, and web fallback

---

## Demo

**Live app:** [https://pdf-rag-chatbot-pi.vercel.app](https://pdf-rag-chatbot-pi.vercel.app)

**Backend API:** `https://documind-backend-xzwd.onrender.com`

> The Render free tier sleeps after 15 min of inactivity. The first request after a break takes ~50 seconds. Give it a moment.

### Quick demo script

1. Open the live app link above
2. Upload any research paper or multi-page PDF (keep under ~10 pages on the free tier)
3. Wait for "X chunks indexed and ready to query"
4. Ask: **"What are the main findings?"** → see PDF citations (indigo pills)
5. Ask: **"Summarize this document"** → see a multi-section summary
6. Ask: **"What is the capital of France?"** → see the web search fallback with clickable sources

### Backend Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload a PDF file (multipart form) |
| `POST` | `/api/ingest` | Build the RAG index for uploaded PDF(s) |
| `POST` | `/api/chat` | Ask a question, get an answer with citations |

---

## Buildathon — RAG Track Relevance

This project demonstrates a complete RAG pipeline built from scratch:

- **Retrieval:** Hybrid vector (ChromaDB) + keyword (BM25) search with query expansion and synonym matching
- **Augmentation:** Top-5 reranked chunks are injected as context into the LLM prompt with strict grounding instructions
- **Generation:** Meta-Llama-3.1-8B produces cited answers; citations are validated against the actual evidence chunks
- **Fallback:** Automatic Tavily web search when the PDF lacks the answer, with transparent source attribution

Key differentiators from a basic RAG tutorial:
- Custom multi-signal reranker (vector score + BM25 + intent + section boost − reference penalty)
- Section-aware chunking with academic header detection
- Citation hallucination detection
- Defensive 3-route answer routing (PDF → web → not found)
- Fully deployed: React frontend on Vercel, FastAPI backend on Render, auto-deploy from GitHub

---

## License

MIT
