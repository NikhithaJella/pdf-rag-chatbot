# Manual Test Plan

This project does not have automated unit tests yet. Use the checklist below to verify the full pipeline manually after any change.

## Prerequisites

- Backend running at `http://localhost:8000` (or use the deployed URL)
- Frontend running at `http://localhost:5173`
- A test PDF (any research paper or multi-page document)

---

## Test Cases

### 1. PDF Upload

| Step | Action | Expected Result |
|---|---|---|
| 1.1 | Open the app in a browser | Left sidebar shows upload area; chat panel is empty |
| 1.2 | Drag a PDF onto the upload area | Status changes to "Uploading..." then "Building index..." |
| 1.3 | Wait for ingestion to complete | Status shows "X chunks indexed and ready to query" with a green indicator |
| 1.4 | Try uploading a non-PDF file (e.g., .txt) | Backend returns 400; UI shows an error message |

### 2. Ask a Factual Question

| Step | Action | Expected Result |
|---|---|---|
| 2.1 | Type a specific question about the PDF content (e.g., "What methods did the researchers use?") | Answer appears referencing content from the PDF |
| 2.2 | Check the citations below the answer | Indigo citation pills show "Page X, Chunk Y" |
| 2.3 | Click a citation pill | The citation text is copied to clipboard |

### 3. Summary Question

| Step | Action | Expected Result |
|---|---|---|
| 3.1 | Ask "Summarize this document" or "Give me an overview" | Answer covers key sections: objective, methods, results, conclusion |
| 3.2 | Check that the summary draws from multiple pages | Citations reference chunks from different pages |

### 4. Count / Participant Question

| Step | Action | Expected Result |
|---|---|---|
| 4.1 | Ask "How many participants were in the study?" (or similar count question) | Answer contains a specific number from the PDF |
| 4.2 | Verify the number against the actual PDF content | The reported number matches the document |

### 5. Web Search Fallback

| Step | Action | Expected Result |
|---|---|---|
| 5.1 | Ask a question unrelated to the PDF (e.g., "What is the capital of France?") | The answer is sourced from the web, not the PDF |
| 5.2 | Check the source indicator | Sky-blue web source links appear (not indigo PDF citations) |
| 5.3 | Click a web source link | Opens the source URL in a new tab |

### 6. Explicit Web Search Request

| Step | Action | Expected Result |
|---|---|---|
| 6.1 | Ask something clearly outside the document's domain | `source_type` in the API response is `"web"` or `"pdf_not_found"` |
| 6.2 | If Tavily is configured, verify `web_sources` is non-empty | Response includes `[{title, url}]` entries |

### 7. No Document Loaded

| Step | Action | Expected Result |
|---|---|---|
| 7.1 | Start the backend fresh without uploading any PDF | Engine starts with no collection |
| 7.2 | Send a chat request via the UI or `POST /api/chat` | Returns: "No document has been loaded yet. Please upload and index a PDF using the sidebar first." |

### 8. API Endpoint Smoke Tests

Run these with `curl` or any HTTP client against the backend:

```bash
# Upload
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.pdf"

# Ingest
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"file_paths": ["uploaded_pdfs/test.pdf"]}'

# Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?"}'
```

Expected: each returns a 200 JSON response matching the schemas in `server.py`.

---

## Adding Automated Tests

Future automated tests should cover:

- `clean_text()` — encoding fixes, hyphen rejoining
- `tokenize()` — stopword removal, stemming
- `expand_query_tokens()` — synonym expansion
- BM25 scoring — known query against known chunks
- Reranking signal combination
- `_answer_says_not_found()` — false positive / true positive detection
- Citation parsing and validation
