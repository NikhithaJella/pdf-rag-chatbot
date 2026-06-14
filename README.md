# DocuMind AI — PDF RAG Chatbot

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

## Deployment

### Backend → Render (free)

1. Go to [render.com](https://render.com) and sign in with GitHub
2. Click **New → Blueprint** and select this repo — Render auto-detects `render.yaml`
3. In the Render dashboard, add environment variables:
   - `FEATHERLESS_API_KEY` — your Featherless AI key
   - `TAVILY_API_KEY` — your Tavily key
   - `ALLOWED_ORIGINS` — your frontend URL (fill this in after step below)
4. Click **Deploy** — your backend URL will be `https://documind-backend.onrender.com`

### Frontend → Vercel (free)

1. Go to [vercel.com](https://vercel.com) and sign in with GitHub
2. Click **Add New → Project** and import this repo
3. Set **Root Directory** to `frontend`
4. Add environment variable:
   - `VITE_API_BASE_URL` = `https://documind-backend.onrender.com` (your Render URL)
   - `NITRO_PRESET` = `vercel`
5. Click **Deploy** — your app will be live at `https://your-app.vercel.app`
6. Go back to Render and update `ALLOWED_ORIGINS` to your Vercel URL, then redeploy

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

## License

MIT
