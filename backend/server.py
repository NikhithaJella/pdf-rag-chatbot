import os
import re
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel

from read_pdf_bm25_structured import HybridRAGEngine, ask_featherless

UPLOAD_DIR = "uploaded_pdfs"

from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[str]
    web_search_triggered: bool
    source_type: str = "pdf"        # "pdf" | "web" | "pdf_not_found"
    web_sources: list[dict] = []    # [{title, url}] for web answers


class UploadResponse(BaseModel):
    message: str
    filename: str
    path: str


class IngestRequest(BaseModel):
    file_paths: Optional[list[str]] = None


class IngestResponse(BaseModel):
    message: str
    pdf_paths: list[str]
    chunks_loaded: int


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start with no PDF loaded — engine is ready but empty.
    # Users must call /api/ingest before chatting.
    engine = HybridRAGEngine(pdf_paths=[])
    app.state.engine = engine
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="RAG PDF Chatbot API", version="1.0.0", lifespan=lifespan)

# Dev origins are always allowed.
# In production, set ALLOWED_ORIGINS to a comma-separated list of frontend URLs,
# e.g.  ALLOWED_ORIGINS=https://my-app.vercel.app,https://my-app.pages.dev
_dev_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://lovable.dev",
]
_extra_origins = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_dev_origins + _extra_origins,
    allow_origin_regex=r"https://.*\.lovable\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _PrivateNetworkMiddleware(BaseHTTPMiddleware):
    """Injects Access-Control-Allow-Private-Network on every response.

    Required for Chrome's Private Network Access checks when a public page
    (e.g. Lovable preview) calls a localhost server.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response


app.add_middleware(_PrivateNetworkMiddleware)


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

# The LLM must reference its given source material to trigger Route 2.
# This prevents answers that merely mention negative findings ("the study did
# not find a correlation") from being misclassified as "no context".
_CONTEXT_REFERENCE_PHRASES = [
    "provided context",
    "provided pdf",
    "provided document",
    "provided text",
    "provided material",
    "given context",
    "given document",
    "given text",
    "the context",
    "the pdf",
    "the document",
    "above context",
]

# Explicit signals that the source material contains no relevant information.
# Combined with a context reference, these unambiguously mean "total lack of context".
_ABSENCE_SIGNALS = [
    "does not contain",
    "doesn't contain",
    "does not include",
    "doesn't include",
    "does not have",
    "doesn't have",
    "does not mention",
    "doesn't mention",
    "does not cover",
    "doesn't cover",
    "does not discuss",
    "doesn't discuss",
    "does not provide",
    "doesn't provide",
    "does not address",
    "doesn't address",
    "cannot answer",
    "can't answer",
    "cannot find",
    "can't find",
    "could not find",
    "couldn't find",
    "no information",
    "no relevant information",
    "not found in",
    "not mentioned in",
    "not covered in",
    "not discussed in",
    "insufficient information",
    "not enough information",
    "outside the scope",
]


def _answer_says_not_found(text: str) -> bool:
    """True only when the LLM explicitly signals a total lack of context.

    Both conditions must be satisfied:
    1. The answer references the provided source material (context/pdf/document).
    2. The answer signals that the source contains no relevant information.

    A single keyword match anywhere in the text is intentionally not enough —
    this prevents legitimate PDF answers that contain negative findings
    ("participants did not find...") from being misrouted to web search.
    """
    lower = text.lower()
    has_context_ref = any(phrase in lower for phrase in _CONTEXT_REFERENCE_PHRASES)
    has_absence = any(signal in lower for signal in _ABSENCE_SIGNALS)
    return has_context_ref and has_absence


def _strip_source_markers(text: str) -> str:
    """Remove 'Sources: Page X, Chunk Y' lines the LLM appends.

    For web answers these markers are hallucinated (web results have no real
    page/chunk coordinates), so we strip them before returning to the client.
    """
    return re.sub(r"\n?Sources?:.*$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()


def _tavily_search_with_sources(tavily_client, question: str):
    """Returns (context_str | None, [{title, url}]).

    Calls Tavily directly so server.py can capture raw titles/URLs for
    web_sources without changing the engine's search_tavily helper.
    """
    try:
        result = tavily_client.search(query=question, max_results=3)
        web_parts, web_sources = [], []
        for item in result.get("results", []):
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            web_parts.append(f"[Web: {title}]\n{content}\nSource: {url}")
            if title or url:
                web_sources.append({"title": title, "url": url})
        context = "\n\n".join(web_parts) if web_parts else None
        return context, web_sources
    except Exception as exc:
        print(f"Tavily second-step search error: {exc}")
        return None, []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    engine: HybridRAGEngine = request.app.state.engine

    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    if engine.collection is None:
        return ChatResponse(
            answer="No document has been loaded yet. Please upload and index a PDF using the sidebar first.",
            citations=[],
            web_search_triggered=False,
            source_type="pdf_not_found",
            web_sources=[],
        )

    reranked_chunks = engine.retrieve(payload.question)
    answer_text, selected_chunks, validation, tavily_triggered = engine.answer(
        payload.question, reranked_chunks
    )

    # --- Route 1: engine already triggered Tavily internally (confidence floor
    # or explicit web request). The answer is already web-sourced. PDF chunk
    # citations would be misleading, so they are cleared. The engine consumed
    # the raw Tavily URLs internally, so web_sources is empty here.
    if tavily_triggered:
        return ChatResponse(
            answer=_strip_source_markers(answer_text),
            citations=[],
            web_search_triggered=True,
            source_type="web",
            web_sources=[],
        )

    # --- Route 2: engine returned a PDF answer but the LLM explicitly signals
    # it has no context for the question. We run a second-step Tavily search and
    # re-answer from web results, surfacing the raw source URLs to the client.
    # If Tavily returns nothing, we degrade cleanly to pdf_not_found rather than
    # returning a web response with no sources.
    if _answer_says_not_found(answer_text):
        if engine.tavily_client is not None:
            web_context, web_sources = _tavily_search_with_sources(
                engine.tavily_client, payload.question
            )
            if web_context:
                answer_text = ask_featherless(
                    engine.featherless_client,
                    "No PDF context was found.",
                    payload.question,
                    web_context=web_context,
                    mode="web",
                )
                return ChatResponse(
                    answer=_strip_source_markers(answer_text),
                    citations=[],
                    web_search_triggered=True,
                    source_type="web",
                    web_sources=web_sources,
                )
        # Tavily unavailable or returned no results — surface the not-found
        # answer without misleading web flags or empty source lists.
        return ChatResponse(
            answer=answer_text,
            citations=[],
            web_search_triggered=False,
            source_type="pdf_not_found",
            web_sources=[],
        )

    # --- Route 3: PDF answered successfully. Build citations from the LLM's
    # explicit "Sources: Page X, Chunk Y" markers first; fall back to the top-4
    # evidence chunks when the LLM omits markers. Citation building lives here
    # (not above) because it is only meaningful for PDF-sourced answers.
    citations = [f"Page {p}, Chunk {c}" for p, c in validation.get("cited", [])]
    if not citations and selected_chunks:
        citations = [
            f"Page {chunk['metadata']['page']}, Chunk {chunk['metadata']['chunk_number']}"
            for chunk in selected_chunks[:4]
        ]
    return ChatResponse(
        answer=answer_text,
        citations=citations,
        web_search_triggered=False,
        source_type="pdf",
        web_sources=[],
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Strip directory components and sanitise the filename so it is safe to
    # use as a filesystem path on any OS.
    base = os.path.basename(file.filename)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    return UploadResponse(
        message="Upload successful",
        filename=safe_name,
        path=f"{UPLOAD_DIR}/{safe_name}",
    )


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest(payload: IngestRequest, request: Request):
    pdf_paths = payload.file_paths or ["sample.pdf"]

    for path in pdf_paths:
        if not os.path.exists(path):
            raise HTTPException(
                status_code=400,
                detail=f"File not found: '{path}'. Provide a valid path accessible to the server.",
            )

    # Re-instantiate engine with the new paths and rebuild indexes
    engine = HybridRAGEngine(pdf_paths=pdf_paths)
    engine.setup_pipeline(reset=True)
    request.app.state.engine = engine

    return IngestResponse(
        message="Ingestion complete. Pipeline rebuilt successfully.",
        pdf_paths=engine.pdf_paths,
        chunks_loaded=len(engine.chunks),
    )


# ---------------------------------------------------------------------------
# Entry point (optional — prefer uvicorn CLI)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
