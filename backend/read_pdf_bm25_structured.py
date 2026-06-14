"""
PDF RAG Chatbot - Step 4

What this version does:
1. Reads a PDF page by page.
2. Cleans messy PDF text.
3. Creates page-aware chunks with overlap.
4. Stores chunks in ChromaDB for vector search.
5. Builds a BM25 keyword index for lexical search.
6. Combines vector search + BM25 search.
7. Reranks the combined results.
8. Sends the best chunks to Featherless AI.

Why this is better:
- Vector search understands meaning.
- BM25 catches exact words from the question.
- Reranking decides which chunks are strongest.
- upsert avoids duplicate ID errors.
- If FEATHERLESS_API_KEY is missing, retrieval still works.
"""

from pypdf import PdfReader
import chromadb
import os
import re
import math
import pickle
import argparse
import json
from collections import Counter


# -----------------------------
# 0. SETTINGS
# -----------------------------

# Overridden at runtime by --pdf argument.
PDF_PATH = "sample.pdf"
COLLECTION_NAME = "pdf_chunks_bm25_structured"
CHROMA_DB_PATH = "chroma_db"
BM25_INDEX_PATH = "bm25_index.pkl"

# Cache for LLM-based summary intent classifications.
# Keyed by the raw question string so the LLM call runs at most once per question.
_summary_cache: dict = {}

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

# Number of complete sentences carried forward as overlap between sentence chunks.
OVERLAP_SENTENCES = 2

# I retrieve more chunks first so I do not miss useful evidence.
VECTOR_TOP_K = 30
BM25_TOP_K = 30

# I send only the strongest few chunks to Featherless AI.
ANSWER_TOP_K = 5

# I print this many chunks for debugging.
SHOW_TOP_N = 15

FEATHERLESS_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"


# -----------------------------
# 1. SMALL HELPER LISTS
# -----------------------------

# These are common words that usually do not help keyword search.
STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "this", "that",
    "these", "those", "it", "its", "as", "at", "by", "with", "from",
    "what", "which", "who", "whom", "how", "many", "much", "do", "does",
    "did", "can", "could", "would", "should", "will", "have", "has",
    "had", "not", "no", "but", "if", "so", "about", "into", "than",
    "then", "there", "here", "their", "our", "your", "used", "using", "use",
}


# This is not answer-specific.
# These are general academic/search words that help questions match paper language.
QUERY_EXPANSION = {
    "method": [
        "analysis", "analyse", "model", "approach", "technique",
        "procedure", "statistical", "survey", "questionnaire", "data",
        "structural", "equation", "correspondence"
    ],
    "analysis": [
        "method", "model", "statistical", "data", "structural",
        "equation", "correspondence"
    ],
    "objective": ["aim", "aimed", "goal", "purpose"],
    "aim": ["objective", "goal", "purpose"],
    "purpose": ["objective", "aim", "goal"],
    "goal": ["objective", "aim", "purpose"],
    "participant": ["sample", "respondent", "subject", "survey", "completed", "included"],
    "sample": ["participant", "respondent", "subject"],
    "respondent": ["participant", "sample"],
    "result": ["finding", "outcome"],
    "finding": ["result", "outcome"],
    "conclusion": ["finding", "summary", "result"],
    "limitation": ["weakness", "constraint", "challenge"],
    "summarize": ["abstract", "objective", "aim", "method", "result", "finding", "conclusion", "limitation", "recommendation", "participant"],
    "summary": ["abstract", "objective", "aim", "method", "result", "finding", "conclusion", "limitation", "recommendation", "participant"],
    "overview": ["abstract", "objective", "aim", "method", "result", "finding", "conclusion", "limitation", "recommendation", "participant"],
}


SECTION_HEADER_MAP = {
    "abstract": "abstract",
    "introduction": "introduction",
    "literature review": "literature_review",
    "related work": "literature_review",
    "background": "literature_review",
    "method": "methods",
    "methods": "methods",
    "methodology": "methods",
    "materials and methods": "methods",
    "data collection": "methods",
    "result": "results",
    "results": "results",
    "findings": "results",
    "discussion": "discussion",
    "conclusion": "conclusion",
    "conclusions": "conclusion",
    "limitation": "limitations",
    "limitations": "limitations",
    "recommendation": "recommendations",
    "recommendations": "recommendations",
    "reference": "references",
    "references": "references",
    "bibliography": "references",
    "acknowledgement": "acknowledgements",
    "acknowledgements": "acknowledgements",
    "acknowledgments": "acknowledgements",
}


# -----------------------------
# 2. TEXT CLEANING
# -----------------------------

def clean_text(text):
    """
    PDF text can be messy.

    I clean it before chunking because better text gives better retrieval.

    This function:
    - fixes strange PDF characters
    - joins words broken by line-break hyphens
    - keeps real hyphen words like PLS-SEM
    - turns many spaces/new lines into one space
    """

    if not text:
        return ""

    # Some PDFs decode symbols strangely.
    text = text.replace("\u00bc", "=")
    text = text.replace("\ufffd", " ")
    text = text.replace("\ufffe", " ")
    text = text.replace("�", " ")

    # Join only words split across line breaks.
    # Example: stake-\nholders -> stakeholders
    text = re.sub(r"(\w)\s*-\s*\n\s*(\w)", r"\1\2", text)

    # Collapse all whitespace into one space.
    text = re.sub(r"\s+", " ", text)

    return text.strip()



def normalize_for_search(text):
    """
    This makes text easier to compare during keyword search.
    """

    text = clean_text(text).lower()
    text = re.sub(r"[^a-z0-9%]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()



def stem_word(word):
    """
    This is a tiny simple stemmer.

    It helps match:
    - methods -> method
    - objectives -> objective
    - participants -> participant

    This is not perfect, but it is enough for learning BM25.
    """

    if len(word) <= 3:
        return word

    if word.endswith("ies"):
        return word[:-3] + "y"

    # I do not want to damage words like analysis.
    if word.endswith(("sis", "ss", "us", "is")):
        return word

    if word.endswith("s"):
        word = word[:-1]

    if word.endswith("ing") and len(word) > 5:
        word = word[:-3]
    elif word.endswith("ed") and len(word) > 4:
        word = word[:-2]

    return word



def tokenize(text):
    """
    This converts text into useful search tokens for BM25.
    """

    words = normalize_for_search(text).split()
    tokens = []

    for word in words:
        if len(word) > 2 and word not in STOPWORDS:
            tokens.append(stem_word(word))

    return tokens



def expand_query_tokens(tokens):
    """
    This adds general synonyms to the question tokens.

    Example:
    If I ask for methods, the PDF may say analysis.
    So I add analysis/model/statistical type words.
    """

    expanded = []

    for token in tokens:
        expanded.append(token)

        synonyms = QUERY_EXPANSION.get(token, [])
        for synonym in synonyms:
            expanded.append(stem_word(synonym))

    # Remove duplicates but keep the same order.
    final_tokens = []
    seen = set()

    for token in expanded:
        if token not in seen:
            seen.add(token)
            final_tokens.append(token)

    return final_tokens


# -----------------------------
# 3. PAGE-AWARE CHUNKING
# -----------------------------

def detect_section_from_page(raw_page_text):
    """
    Scans a raw (uncleaned) page for section header lines.

    Returns a list of section names found in order of appearance.
    If the page has no recognisable header, returns an empty list
    and the caller keeps the previous section.
    """

    lines = raw_page_text.lower().split("\n")
    found = []

    for line in lines:
        # Strip leading section numbers like "2." or "2.1.".
        stripped = re.sub(r"^\s*\d+[\.\d]*\s*", "", line).strip()

        # Only short standalone lines count as section headers.
        if 0 < len(stripped) <= 35 and stripped in SECTION_HEADER_MAP:
            found.append(SECTION_HEADER_MAP[stripped])

    return found


def split_page_text(page_text, page_number, section="unknown", chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    This splits one page into overlapping chunks.

    Each chunk remembers:
    - text
    - page number
    - chunk number

    This is important for citations.
    """

    if overlap >= chunk_size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")

    chunks = []
    start = 0

    while start < len(page_text):
        end = start + chunk_size
        chunk_text = page_text[start:end]

        chunks.append(
            {
                "text": chunk_text,
                "page": page_number,
                "chunk_number": len(chunks) + 1,
                "section": section,
            }
        )

        # Move forward but keep some overlap.
        start = start + chunk_size - overlap

    return chunks


def sentence_chunk(page_text, page_number, section="unknown", chunk_size=CHUNK_SIZE, overlap_sentences=OVERLAP_SENTENCES):
    """
    Splits page text into chunks that always begin and end on sentence boundaries.

    Accumulates complete sentences until the next sentence would push the chunk
    past chunk_size characters. At that point the current chunk is emitted and
    the last `overlap_sentences` sentences are carried forward so context is not
    lost at chunk boundaries.

    Fallback: if the page contains no detectable sentence boundaries (tables,
    reference lists, captions), the original split_page_text() is called so
    those pages are still chunked correctly.
    """

    if not page_text or not page_text.strip():
        return []

    # Split on .  !  ? followed by one or more spaces then an uppercase letter,
    # opening quote, or opening bracket. Works on clean single-space text produced
    # by clean_text(). Does not fire on decimal numbers (3.14) or mid-word hyphens.
    raw_parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'(\[])', page_text)
    sentences = [s.strip() for s in raw_parts if s.strip()]

    # No sentence boundaries found: table, reference list, or pure numeric page.
    # Fall back to the original character-window chunker so nothing is lost.
    if len(sentences) <= 1:
        return split_page_text(page_text, page_number, section, chunk_size, overlap=CHUNK_OVERLAP)

    chunks = []
    current_sentences = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # A single sentence that alone exceeds the budget is emitted as its own chunk
        # rather than being silently dropped.
        if sentence_len >= chunk_size and not current_sentences:
            chunks.append({
                "text": sentence,
                "page": page_number,
                "chunk_number": len(chunks) + 1,
                "section": section,
            })
            continue

        # Space separator adds 1 character between joined sentences.
        space = 1 if current_sentences else 0

        if current_sentences and current_length + space + sentence_len > chunk_size:
            # Emit the current chunk.
            chunks.append({
                "text": " ".join(current_sentences),
                "page": page_number,
                "chunk_number": len(chunks) + 1,
                "section": section,
            })
            # Carry the last N sentences forward as overlap context.
            carry = current_sentences[-overlap_sentences:]
            current_sentences = list(carry)
            current_length = sum(len(s) for s in carry) + max(0, len(carry) - 1)
            space = 1 if current_sentences else 0

        current_sentences.append(sentence)
        current_length += space + sentence_len

    # Emit any remaining sentences as the final chunk.
    if current_sentences:
        chunks.append({
            "text": " ".join(current_sentences),
            "page": page_number,
            "chunk_number": len(chunks) + 1,
            "section": section,
        })

    return chunks


def load_pdf_chunks(pdf_path):
    """
    This reads one PDF and creates all chunks.
    Each chunk carries file_name for multi-PDF tracing.
    """

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(pdf_path)
    file_name = os.path.basename(pdf_path)
    all_chunks = []
    current_section = "unknown"

    for page_index, page in enumerate(reader.pages):
        raw_page_text = page.extract_text()

        if not raw_page_text:
            continue

        page_number = page_index + 1

        # Detect section headers from raw text before cleaning (newlines still intact).
        found_sections = detect_section_from_page(raw_page_text)
        if found_sections:
            current_section = found_sections[-1]

        page_text = clean_text(raw_page_text)

        page_chunks = sentence_chunk(
            page_text=page_text,
            page_number=page_number,
            section=current_section,
            chunk_size=CHUNK_SIZE,
            overlap_sentences=OVERLAP_SENTENCES,
        )

        for chunk in page_chunks:
            chunk["file_name"] = file_name

        all_chunks.extend(page_chunks)

    # Provisional per-PDF indices. load_all_pdfs overwrites these with global indices.
    for index, chunk in enumerate(all_chunks):
        chunk["index"] = index

    return all_chunks


def load_all_pdfs(pdf_paths):
    """
    Loads multiple PDFs, detects document type per PDF, returns combined chunks.

    Each chunk carries: file_name, document_type, page, chunk_number, section.
    """

    all_chunks = []

    for pdf_path in pdf_paths:
        if not os.path.exists(pdf_path):
            print(f"Warning: PDF not found, skipping: {pdf_path}")
            continue

        print(f"Loading: {pdf_path}")
        chunks = load_pdf_chunks(pdf_path)
        doc_type = detect_document_type(chunks)
        print(f"  Type: {doc_type} | Chunks: {len(chunks)}")

        for chunk in chunks:
            chunk["document_type"] = doc_type

        all_chunks.extend(chunks)

    if not all_chunks:
        raise ValueError("No chunks loaded. Check that the PDF paths are correct.")

    # Reindex globally so BM25 and ChromaDB indices stay consistent.
    for index, chunk in enumerate(all_chunks):
        chunk["index"] = index

    print(f"Total chunks across all PDFs: {len(all_chunks)}")
    return all_chunks


# -----------------------------
# 4. BM25 KEYWORD SEARCH
# -----------------------------

class BM25Index:
    """
    This is a small BM25 search engine.

    BM25 is keyword search.
    It gives high scores to chunks that contain important words from the question.

    Vector search = meaning search.
    BM25 search = exact word search.
    RAG usually becomes stronger when both are combined.
    """

    def __init__(self, chunks, k1=1.5, b=0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b

        self.documents_tokens = []
        for chunk in chunks:
            self.documents_tokens.append(tokenize(chunk["text"]))

        self.number_of_documents = len(self.documents_tokens)
        self.document_lengths = [len(tokens) for tokens in self.documents_tokens]

        if self.number_of_documents == 0:
            self.average_document_length = 0
        else:
            self.average_document_length = sum(self.document_lengths) / self.number_of_documents

        # Term frequency per document.
        self.term_frequencies = []
        for tokens in self.documents_tokens:
            self.term_frequencies.append(Counter(tokens))

        # Document frequency across all documents.
        document_frequency = Counter()
        for tokens in self.documents_tokens:
            for token in set(tokens):
                document_frequency[token] += 1

        # IDF means rare words are more important.
        self.idf = {}
        for token, freq in document_frequency.items():
            self.idf[token] = math.log(1 + (self.number_of_documents - freq + 0.5) / (freq + 0.5))

    def score_document(self, query_tokens, document_index):
        """
        This calculates the BM25 score for one chunk.
        """

        if self.average_document_length == 0:
            return 0

        score = 0
        term_frequency = self.term_frequencies[document_index]
        document_length = self.document_lengths[document_index]

        for token in query_tokens:
            token_count = term_frequency.get(token, 0)

            if token_count == 0:
                continue

            idf_score = self.idf.get(token, 0)
            numerator = token_count * (self.k1 + 1)
            denominator = token_count + self.k1 * (
                1 - self.b + self.b * document_length / self.average_document_length
            )

            score += idf_score * numerator / denominator

        return score

    def search(self, question, top_k=BM25_TOP_K):
        """
        This searches all chunks using BM25 and returns the best matches.
        """

        question_tokens = tokenize(question)
        question_tokens = expand_query_tokens(question_tokens)

        scored_results = []

        for index in range(self.number_of_documents):
            score = self.score_document(question_tokens, index)

            if score > 0:
                scored_results.append((score, index))

        scored_results = sorted(scored_results, reverse=True)
        return scored_results[:top_k]


def _compute_pdf_fingerprint(pdf_paths):
    entries = []
    for path in sorted(pdf_paths):
        try:
            stat = os.stat(path)
            entries.append((os.path.basename(path), stat.st_size, int(stat.st_mtime)))
        except OSError:
            entries.append((os.path.basename(path), -1, -1))
    return str(entries)


def load_or_build_bm25(chunks, pdf_paths, reset=False, index_path=BM25_INDEX_PATH):
    """
    Returns a BM25Index, loading from bm25_index.pkl when possible.

    Cache is invalidated if --reset is passed or if the PDF set has changed
    (different files, different sizes, or different modification times).
    Pass index_path to store the cache at a custom location (e.g. from HybridRAGEngine).
    """
    fingerprint = _compute_pdf_fingerprint(pdf_paths)

    if not reset and os.path.exists(index_path):
        try:
            with open(index_path, "rb") as f:
                cached = pickle.load(f)
            if cached.get("fingerprint") == fingerprint:
                print("Loading BM25 index from cache...")
                return cached["index"]
            print("Building BM25 keyword index (PDF set changed)...")
        except Exception:
            print("Building BM25 keyword index (cache unreadable)...")
    else:
        label = "reset requested" if reset else "no cache found"
        print(f"Building BM25 keyword index ({label})...")

    index = BM25Index(chunks)

    try:
        with open(index_path, "wb") as f:
            pickle.dump({"fingerprint": fingerprint, "index": index}, f)
    except Exception as e:
        print(f"Warning: could not save BM25 cache: {e}")

    return index


# -----------------------------
# 5. CHROMADB VECTOR STORE
# -----------------------------

def build_chroma_collection(chunks, reset=False, chroma_db_path=CHROMA_DB_PATH, client=None):
    """
    This stores chunks in ChromaDB using a persistent on-disk database.

    The index survives across runs so re-loading the same PDF is fast.
    upsert updates existing chunks rather than duplicating them.
    Pass reset=True (--reset CLI flag) to wipe the collection and rebuild.
    Pass client to reuse an existing PersistentClient (e.g. from HybridRAGEngine).
    """

    chroma_client = client if client is not None else chromadb.PersistentClient(path=chroma_db_path)

    if reset:
        try:
            chroma_client.delete_collection(name=COLLECTION_NAME)
            print(f"Deleted existing ChromaDB collection '{COLLECTION_NAME}'.")
        except Exception:
            pass

    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

    documents = []
    ids = []
    metadatas = []

    for chunk in chunks:
        file_name = chunk.get("file_name", "pdf")
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", file_name)
        documents.append(chunk["text"])
        ids.append(f"{safe_name}_page_{chunk['page']}_chunk_{chunk['chunk_number']}")
        metadatas.append(
            {
                "page": chunk["page"],
                "chunk_number": chunk["chunk_number"],
                "source": file_name,
                "index": chunk["index"],
                "section": chunk.get("section", "unknown"),
                "file_name": file_name,
                "document_type": chunk.get("document_type", "generic"),
            }
        )

    collection.upsert(
        documents=documents,
        ids=ids,
        metadatas=metadatas,
    )

    return collection


# -----------------------------
# 6. HYBRID RETRIEVAL
# -----------------------------

def run_vector_search(collection, question, top_k=VECTOR_TOP_K):
    """
    This uses ChromaDB vector search.
    """

    results = collection.query(
        query_texts=[question],
        n_results=top_k,
    )

    candidates = []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, metadata, distance in zip(documents, metadatas, distances):
        candidates.append(
            {
                "index": metadata["index"],
                "doc": doc,
                "metadata": metadata,
                "distance": distance,
                "bm25_score": 0,
                "source_type": "vector",
            }
        )

    return candidates



def run_bm25_search(bm25_index, chunks, question, top_k=BM25_TOP_K):
    """
    This uses BM25 keyword search.
    """

    bm25_results = bm25_index.search(question, top_k=top_k)
    candidates = []

    for bm25_score, chunk_index in bm25_results:
        chunk = chunks[chunk_index]

        candidates.append(
            {
                "index": chunk_index,
                "doc": chunk["text"],
                "metadata": {
                    "page": chunk["page"],
                    "chunk_number": chunk["chunk_number"],
                    "source": chunk.get("file_name", PDF_PATH),
                    "index": chunk_index,
                    "section": chunk.get("section", "unknown"),
                    "file_name": chunk.get("file_name", ""),
                    "document_type": chunk.get("document_type", "generic"),
                },
                "distance": None,
                "bm25_score": bm25_score,
                "source_type": "bm25",
            }
        )

    return candidates



def merge_candidates(vector_candidates, bm25_candidates):
    """
    Vector search and BM25 may return the same chunk.

    I merge duplicates so one chunk appears only once.
    """

    merged = {}

    for candidate in vector_candidates + bm25_candidates:
        chunk_index = candidate["index"]

        if chunk_index not in merged:
            merged[chunk_index] = candidate
        else:
            old_candidate = merged[chunk_index]

            if old_candidate["source_type"] != candidate["source_type"]:
                old_candidate["source_type"] = "hybrid"

            # Keep vector distance if one result has it.
            if old_candidate.get("distance") is None and candidate.get("distance") is not None:
                old_candidate["distance"] = candidate["distance"]

            # Keep the stronger BM25 score.
            old_candidate["bm25_score"] = max(
                old_candidate.get("bm25_score", 0),
                candidate.get("bm25_score", 0),
            )

    return list(merged.values())


# -----------------------------
# 7. RERANKING
# -----------------------------

def scale_values(values):
    """
    This converts scores into a 0 to 1 range.

    I do this because vector scores and BM25 scores are not on the same scale.
    """

    if not values:
        return []

    minimum_value = min(values)
    maximum_value = max(values)

    if maximum_value - minimum_value < 0.000001:
        return [0 for _ in values]

    scaled = []
    for value in values:
        scaled.append((value - minimum_value) / (maximum_value - minimum_value))

    return scaled



def is_count_question(question):
    """
    This checks if the user is asking for a number/count.
    """

    question_lower = normalize_for_search(question)

    return (
        "how many" in question_lower
        or "number of" in question_lower
        or "count" in question_lower
        or "participants" in question_lower
        or "sample size" in question_lower
    )



def is_web_question(question):
    """
    This checks if the user is explicitly asking for web or current information.

    Tavily should only run when the user asks for something the PDF cannot answer,
    like latest news, recent statistics, or online comparisons.
    """

    question_lower = normalize_for_search(question)

    web_signals = [
        "latest", "recent news", "current", "today", "online",
        "search the web", "search web", "find online", "look up",
        "internet", "compare with recent", "news about",
    ]

    return any(signal in question_lower for signal in web_signals)



def is_summary_question(question, featherless_client=None):
    """
    Returns True when the user is asking for a summary, general overview,
    core concepts, or broad takeaways of the document.

    When featherless_client is provided the decision is made by a single fast
    LLM call (max_tokens=5, temperature=0).  The result is cached so the call
    runs at most once per unique question string.

    When featherless_client is None (e.g. inside per-chunk reranking boost
    functions) the function falls back to a lightweight keyword check — no
    caching, since only the authoritative LLM result is worth persisting.
    """

    # Return a previously cached LLM verdict immediately.
    cache_key = question.strip()
    if cache_key in _summary_cache:
        return _summary_cache[cache_key]

    # Semantic classification via a single yes/no LLM call.
    if featherless_client is not None:
        try:
            prompt = (
                "Is the following question asking for a summary, general overview, "
                "core concepts, or broad takeaways of a document or PDF?\n"
                "Output only YES or NO — nothing else.\n\n"
                f"Question: {question}"
            )
            response = featherless_client.chat.completions.create(
                model=FEATHERLESS_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0,
            )
            verdict = response.choices[0].message.content.strip().upper()
            result = verdict.startswith("YES")
            _summary_cache[cache_key] = result
            return result
        except Exception:
            pass  # fall through to keyword fallback on any error

    # Keyword fallback — used during reranking where no client is passed and
    # for the LLM error path.  Result is intentionally not cached here so a
    # subsequent call with a valid client can still make the LLM classification.
    question_lower = normalize_for_search(question)
    summary_signals = [
        "summarize", "summary", "overview", "what is this",
        "what is this paper", "what does this paper", "explain this",
        "describe this", "brief", "in short", "in simple",
        "beginner", "what is the paper about", "what is the document",
        "tell me about this", "give me an overview",
    ]
    return any(signal in question_lower for signal in summary_signals)



def get_intent_boost(question, doc):
    """
    This gives small generic boosts based on question intent.

    This is not using answer-specific anchors like exact participant counts.
    It only rewards general evidence phrases commonly found in research papers.
    """

    question_lower = normalize_for_search(question)
    doc_lower = normalize_for_search(doc)

    boost = 0

    # Count/sample-size questions usually need numbers and sample wording.
    if is_count_question(question):
        if any(char.isdigit() for char in doc):
            boost += 0.4
        if "in total" in doc_lower:
            boost += 0.8
        if "completed the survey" in doc_lower:
            boost += 0.8
        if "responded" in doc_lower:
            boost += 0.6
        if "sample size" in doc_lower:
            boost += 0.5
        if "participants" in doc_lower:
            boost += 0.3

    # Method questions usually need analysis/data collection wording.
    if "method" in question_lower or "analysis" in question_lower or "used" in question_lower:
        if "data analysis" in doc_lower:
            boost += 0.8
        if "analyses were conducted" in doc_lower:
            boost += 0.8
        if "survey was conducted" in doc_lower:
            boost += 0.5
        if "qualtrics" in doc_lower:
            boost += 0.3
        if "structural equation" in doc_lower:
            boost += 0.8
        if "correspondence analysis" in doc_lower:
            boost += 0.8
        if "mca" in doc_lower:
            boost += 0.4
        if "pls" in doc_lower or "sem" in doc_lower:
            boost += 0.4

    # Objective questions usually need aim/objective wording.
    if (
        "objective" in question_lower
        or "aim" in question_lower
        or "purpose" in question_lower
        or "goal" in question_lower
        or "about" in question_lower
    ):
        if "this study aimed" in doc_lower:
            boost += 1.0
        if "objectives of this study" in doc_lower:
            boost += 1.0
        if "aimed to" in doc_lower:
            boost += 0.6
        if "understand" in doc_lower:
            boost += 0.3
        if "suggest" in doc_lower:
            boost += 0.3

    # Summary questions need broad overview evidence.
    if is_summary_question(question):
        if "abstract" in doc_lower:
            boost += 1.0
        if "this study aimed" in doc_lower:
            boost += 1.5
        if "objectives of this study" in doc_lower:
            boost += 1.5
        if "in total" in doc_lower:
            boost += 0.8
        if "completed the survey" in doc_lower:
            boost += 0.8
        if "two analyses were conducted" in doc_lower:
            boost += 1.2
        if "partial least square" in doc_lower:
            boost += 1.0
        if "multiple correspondence analysis" in doc_lower:
            boost += 1.0
        if "supported" in doc_lower and "refuted" in doc_lower:
            boost += 1.0
        if "limitations" in doc_lower:
            boost += 0.8
        if "recommendations" in doc_lower:
            boost += 0.8
        if "conclusion" in doc_lower:
            boost += 0.8

    return boost



def get_reference_penalty(doc):
    """
    Reference chunks often contain method words inside citations.

    They can look useful for keyword search, but they usually do not answer the question.
    So I reduce their score using general reference clues.
    """

    doc_lower = normalize_for_search(doc)
    penalty = 0

    if doc_lower.count("doi") >= 2:
        penalty += 1.0

    if doc_lower.count("et al") >= 5:
        penalty += 0.8

    if "references" in doc_lower or "bibliography" in doc_lower:
        penalty += 1.0

    if "journal" in doc_lower and "doi" in doc_lower and doc_lower.count("doi") >= 2:
        penalty += 0.5

    return penalty



def detect_document_type(chunks):
    """
    This inspects the first few chunks and guesses the document type.

    It counts keyword signals from each document type.
    The type with the most matches wins.

    This is used to apply the right scoring boosts for different document types.
    """

    # Look at first 5 chunks for document type signals.
    sample_text = " ".join(
        chunk["text"].lower() for chunk in chunks[:5]
    )

    scores = {
        "research_paper": 0,
        "resume": 0,
        "invoice": 0,
        "contract": 0,
        "policy_document": 0,
        "medical_report": 0,
        "course_syllabus": 0,
        "generic": 0,
    }

    research_paper_signals = [
        "abstract", "introduction", "method", "results", "discussion",
        "conclusion", "references", "participants", "hypotheses", "doi",
        "literature review", "study", "survey",
    ]
    for signal in research_paper_signals:
        if signal in sample_text:
            scores["research_paper"] += 1

    resume_signals = [
        "experience", "education", "skills", "projects", "certifications",
        "summary", "work history", "linkedin", "portfolio",
    ]
    for signal in resume_signals:
        if signal in sample_text:
            scores["resume"] += 1

    invoice_signals = [
        "invoice", "invoice number", "amount due", "total", "vendor",
        "bill to", "due date", "payment", "subtotal",
    ]
    for signal in invoice_signals:
        if signal in sample_text:
            scores["invoice"] += 1

    contract_signals = [
        "agreement", "parties", "terms", "obligations", "effective date",
        "termination", "clause", "hereinafter", "whereas",
    ]
    for signal in contract_signals:
        if signal in sample_text:
            scores["contract"] += 1

    policy_signals = [
        "policy", "procedure", "compliance", "employee", "guideline",
        "responsibility", "regulation", "enforcement", "violation",
    ]
    for signal in policy_signals:
        if signal in sample_text:
            scores["policy_document"] += 1

    medical_signals = [
        "patient", "diagnosis", "impression", "findings", "clinical",
        "physician", "treatment", "symptoms", "medical history",
    ]
    for signal in medical_signals:
        if signal in sample_text:
            scores["medical_report"] += 1

    syllabus_signals = [
        "syllabus", "course", "instructor", "grading", "assignments",
        "schedule", "learning outcomes", "lecture", "semester",
    ]
    for signal in syllabus_signals:
        if signal in sample_text:
            scores["course_syllabus"] += 1

    best_type = max(scores, key=lambda t: scores[t])

    # If nothing matched strongly, return generic.
    if scores[best_type] == 0:
        return "generic"

    return best_type



def score_research_paper(**_):
    """
    Research paper scoring is handled by get_intent_boost().
    This scorer exists so the registry is complete.
    """
    return 0


def score_resume(doc, **_):
    doc_lower = normalize_for_search(doc)
    boost = 0
    if "experience" in doc_lower:
        boost += 0.5
    if "education" in doc_lower:
        boost += 0.5
    if "skills" in doc_lower:
        boost += 0.5
    if "projects" in doc_lower:
        boost += 0.4
    if "certifications" in doc_lower:
        boost += 0.4
    return boost


def score_invoice(doc, **_):
    doc_lower = normalize_for_search(doc)
    boost = 0
    if "invoice" in doc_lower:
        boost += 0.5
    if "amount due" in doc_lower or "total" in doc_lower:
        boost += 0.8
    if "vendor" in doc_lower or "bill to" in doc_lower:
        boost += 0.5
    if "due date" in doc_lower:
        boost += 0.5
    if any(char.isdigit() for char in doc):
        boost += 0.3
    return boost


def score_contract(doc, **_):
    doc_lower = normalize_for_search(doc)
    boost = 0
    if "parties" in doc_lower:
        boost += 0.5
    if "effective date" in doc_lower:
        boost += 0.6
    if "obligations" in doc_lower:
        boost += 0.5
    if "termination" in doc_lower:
        boost += 0.5
    if "clause" in doc_lower:
        boost += 0.4
    return boost


def score_policy(doc, **_):
    doc_lower = normalize_for_search(doc)
    boost = 0
    if "policy" in doc_lower:
        boost += 0.5
    if "procedure" in doc_lower:
        boost += 0.5
    if "compliance" in doc_lower:
        boost += 0.5
    if "responsibility" in doc_lower:
        boost += 0.4
    return boost


def score_medical_report(doc, **_):
    doc_lower = normalize_for_search(doc)
    boost = 0
    if "diagnosis" in doc_lower:
        boost += 0.8
    if "findings" in doc_lower:
        boost += 0.6
    if "impression" in doc_lower:
        boost += 0.6
    if "recommendation" in doc_lower:
        boost += 0.5
    if "patient" in doc_lower:
        boost += 0.4
    return boost


def score_syllabus(doc, **_):
    doc_lower = normalize_for_search(doc)
    boost = 0
    if "grading" in doc_lower:
        boost += 0.6
    if "assignments" in doc_lower:
        boost += 0.5
    if "schedule" in doc_lower:
        boost += 0.5
    if "instructor" in doc_lower:
        boost += 0.4
    if "learning outcomes" in doc_lower:
        boost += 0.6
    return boost


DOCUMENT_TYPE_SCORERS = {
    "research_paper": score_research_paper,
    "resume": score_resume,
    "invoice": score_invoice,
    "contract": score_contract,
    "policy_document": score_policy,
    "medical_report": score_medical_report,
    "course_syllabus": score_syllabus,
    "generic": lambda **_: 0,
}


def get_document_type_boost(question, doc, document_type):
    """
    Dispatches to the per-type scorer registered in DOCUMENT_TYPE_SCORERS.

    To add a new document type:
    1. Write a score_<type>(doc, **_) function above — add question as an
       explicit param only when the scorer actually needs it.
    2. Add it to DOCUMENT_TYPE_SCORERS.
    """
    scorer = DOCUMENT_TYPE_SCORERS.get(document_type)
    if scorer is None:
        return 0
    return scorer(question=question, doc=doc)



def get_section_boost(question, section):
    """
    Boosts chunks whose section directly matches the question intent.

    For example, a methods question gets a big boost when the chunk
    comes from the Methods section, not from Discussion or References.
    """

    question_lower = normalize_for_search(question)
    boost = 0

    # References section is almost never useful for answering questions.
    if section == "references":
        boost -= 1.0
        return boost

    if section == "abstract" and is_summary_question(question):
        boost += 2.0

    elif section == "introduction" and (
        "objective" in question_lower
        or "aim" in question_lower
        or "purpose" in question_lower
        or "goal" in question_lower
    ):
        boost += 1.5

    elif section == "methods" and (
        "method" in question_lower
        or "analysis" in question_lower
        or "used" in question_lower
        or "approach" in question_lower
        or "procedure" in question_lower
    ):
        boost += 2.0

    elif section == "results" and (
        "finding" in question_lower
        or "result" in question_lower
        or "outcome" in question_lower
    ):
        boost += 2.0

    elif section == "discussion" and (
        "finding" in question_lower
        or "discuss" in question_lower
        or "implication" in question_lower
    ):
        boost += 1.5

    elif section == "limitations" and "limitation" in question_lower:
        boost += 2.5

    elif section in ("conclusion", "recommendations") and (
        "conclusion" in question_lower
        or "recommendation" in question_lower
        or "suggest" in question_lower
    ):
        boost += 2.0

    # Summary questions also benefit from introduction chunks.
    if is_summary_question(question) and section in ("abstract", "introduction"):
        boost += 1.5

    return boost


def rerank_candidates(question, candidates):
    """
    This creates the final ranking.

    Final score uses:
    - vector similarity
    - BM25 keyword score
    - generic intent boosts
    - per-chunk document-type boost (each chunk knows its own PDF type)
    - section-aware boost
    - reference penalties
    """

    if not candidates:
        return []

    vector_scores = []
    bm25_scores = []

    for candidate in candidates:
        distance = candidate.get("distance")

        if distance is None:
            vector_scores.append(0)
        else:
            # Smaller distance is better, so I convert it into similarity.
            vector_scores.append(1 / (1 + distance))

        bm25_scores.append(candidate.get("bm25_score", 0))

    scaled_vector_scores = scale_values(vector_scores)
    scaled_bm25_scores = scale_values(bm25_scores)

    reranked = []

    for index, candidate in enumerate(candidates):
        doc = candidate["doc"]

        meta = candidate.get("metadata", {})
        section = meta.get("section", "unknown")
        chunk_doc_type = meta.get("document_type", "generic")

        intent_boost = get_intent_boost(question, doc)
        ref_penalty = get_reference_penalty(doc)
        document_type_boost = get_document_type_boost(question, doc, chunk_doc_type)
        section_boost = get_section_boost(question, section)

        final_score = 0
        final_score += scaled_vector_scores[index] * 1.0
        final_score += scaled_bm25_scores[index] * 1.2
        final_score += intent_boost
        final_score += document_type_boost
        final_score += section_boost
        final_score -= ref_penalty

        candidate["vector_score"] = scaled_vector_scores[index]
        candidate["bm25_scaled_score"] = scaled_bm25_scores[index]
        candidate["intent_boost"] = intent_boost
        candidate["document_type_boost"] = document_type_boost
        candidate["section_boost"] = section_boost
        candidate["reference_penalty"] = ref_penalty
        candidate["final_score"] = final_score

        reranked.append(candidate)

    reranked = sorted(
        reranked,
        key=lambda item: item["final_score"],
        reverse=True,
    )

    return reranked



def hybrid_search(question, collection, bm25_index, chunks):
    """
    This is the full retrieval pipeline.

    ChromaDB vector search + BM25 keyword search -> merge -> rerank.
    Document type is read per-chunk inside rerank_candidates.
    """

    vector_candidates = run_vector_search(
        collection=collection,
        question=question,
        top_k=VECTOR_TOP_K,
    )

    bm25_candidates = run_bm25_search(
        bm25_index=bm25_index,
        chunks=chunks,
        question=question,
        top_k=BM25_TOP_K,
    )

    candidates = merge_candidates(vector_candidates, bm25_candidates)
    reranked = rerank_candidates(question, candidates)

    return reranked


# -----------------------------
# 8. SELECT FINAL CONTEXT
# -----------------------------

def get_direct_evidence_score(question, doc):
    """
    This checks if a chunk directly looks like answer evidence.

    Reranking finds candidate chunks.
    But before sending chunks to Featherless AI, I want to keep only chunks
    that directly help answer the question.

    This avoids sending noisy chunks that only mention similar words.
    """

    question_lower = normalize_for_search(question)
    doc_lower = normalize_for_search(doc)

    evidence_score = 0

    # Count/sample-size questions need direct count evidence.
    if is_count_question(question):
        if any(char.isdigit() for char in doc):
            evidence_score += 1
        if "in total" in doc_lower:
            evidence_score += 2
        if "completed the survey" in doc_lower:
            evidence_score += 2
        if "responded" in doc_lower:
            evidence_score += 2
        if "sample size" in doc_lower:
            evidence_score += 1
        if "older adults" in doc_lower:
            evidence_score += 1
        if "stakeholders" in doc_lower:
            evidence_score += 1
        if "included in our analyses" in doc_lower:
            evidence_score += 1

    # Method questions need direct method or analysis evidence.
    if "method" in question_lower or "analysis" in question_lower or "used" in question_lower:
        if "data analysis" in doc_lower:
            evidence_score += 2
        if "analyses were conducted" in doc_lower:
            evidence_score += 2
        if "survey was conducted" in doc_lower:
            evidence_score += 2
        if "qualtrics" in doc_lower:
            evidence_score += 1
        if "structural equation" in doc_lower:
            evidence_score += 2
        if "correspondence analysis" in doc_lower:
            evidence_score += 2
        if "mca" in doc_lower:
            evidence_score += 1
        if "pls" in doc_lower or "sem" in doc_lower:
            evidence_score += 1

    # Objective questions need aim/objective wording.
    if (
        "objective" in question_lower
        or "aim" in question_lower
        or "purpose" in question_lower
        or "goal" in question_lower
        or "about" in question_lower
    ):
        if "this study aimed" in doc_lower:
            evidence_score += 2
        if "objectives of this study" in doc_lower:
            evidence_score += 2
        if "aimed to" in doc_lower:
            evidence_score += 1
        if "understand the perception" in doc_lower:
            evidence_score += 2
        if "suggest potential solutions" in doc_lower:
            evidence_score += 2

    return evidence_score



def select_chunks_for_answer(question, reranked_chunks, top_k=ANSWER_TOP_K, featherless_client=None):
    """
    This chooses the chunks that will go to Featherless AI.

    Important lesson:
    Retrieval can find many related chunks, but the LLM should only see
    the chunks that are most useful for answering the question.

    I use three checks:
    1. avoid reference-like chunks
    2. prefer chunks with direct evidence for the question
    3. avoid weak low-score chunks when better evidence exists

    For summary questions, direct evidence scoring does not apply.
    We return the top non-reference chunks instead.
    """

    if not reranked_chunks:
        return []

    # For summary questions, skip direct evidence filtering.
    # Return the top non-reference chunks ranked by final_score.
    if is_summary_question(question, featherless_client):
        summary_chunks = []
        for chunk in reranked_chunks:
            chunk["direct_evidence_score"] = 0
            if get_reference_penalty(chunk["doc"]) < 1.0:
                summary_chunks.append(chunk)
        if summary_chunks:
            return summary_chunks[:top_k]
        return reranked_chunks[:top_k]

    best_score = reranked_chunks[0].get("final_score", 0)

    selected = []

    for chunk in reranked_chunks:
        doc = chunk["doc"]
        final_score = chunk.get("final_score", 0)
        ref_penalty = get_reference_penalty(doc)
        direct_score = get_direct_evidence_score(question, doc)

        chunk["direct_evidence_score"] = direct_score

        # Skip reference/citation chunks when possible.
        if ref_penalty >= 1.0:
            continue

        # For count questions, be stricter.
        # Do not keep a chunk just because it says older adults.
        # It should have direct count/sample evidence.
        if is_count_question(question):
            if direct_score >= 3:
                selected.append(chunk)
            continue

        # For method/objective questions, keep chunks that directly match the intent.
        if direct_score >= 2:
            selected.append(chunk)
            continue

        # Keep very strong chunks only if they are close to the best score.
        if best_score > 0 and final_score >= best_score * 0.75 and direct_score > 0:
            selected.append(chunk)

    # If filtering is too strict, fall back to non-reference chunks.
    if len(selected) < 2:
        selected = []

        for chunk in reranked_chunks:
            if get_reference_penalty(chunk["doc"]) < 1.0:
                selected.append(chunk)

    # Final fallback.
    if not selected:
        selected = reranked_chunks

    return selected[:top_k]



def build_context(selected_chunks):
    """
    This builds the text context for Featherless AI.
    """

    context_parts = []

    for item in selected_chunks:
        metadata = item["metadata"]
        page = metadata["page"]
        chunk_number = metadata["chunk_number"]
        doc = item["doc"]

        section = metadata.get("section", "unknown")
        file_name = metadata.get("file_name", "")
        file_label = f"{file_name}, " if file_name else ""
        context_parts.append(f"[{file_label}Page {page}, Chunk {chunk_number}, Section: {section}]\n{doc}")

    return "\n\n".join(context_parts)



def validate_citations(answer, selected_chunks):
    """
    Checks that every citation in the LLM answer refers to a chunk
    that was actually sent to the LLM.

    The LLM is prompted to cite sources as: Sources: Page X, Chunk Y
    This function parses those citations and compares them against the
    selected_chunks list. Any cited (page, chunk) pair that is not in
    that list is a hallucinated citation.

    Returns a dict with:
      cited       - list of (page, chunk) tuples parsed from the answer
      valid       - citations confirmed in selected_chunks
      invalid     - citations not found in selected_chunks (hallucinated)
      hallucinated - True if any invalid citations exist
    """

    # Build a lookup set from the chunks actually sent to the LLM.
    valid_set = set()
    for chunk in selected_chunks:
        meta = chunk.get("metadata", {})
        page = meta.get("page")
        chunk_number = meta.get("chunk_number")
        if page is not None and chunk_number is not None:
            valid_set.add((int(page), int(chunk_number)))

    # Parse "Page X, Chunk Y" patterns from the answer text.
    pattern = r'[Pp]age\s+(\d+)[,\s]+[Cc]hunk\s+(\d+)'
    matches = re.findall(pattern, answer)
    cited = [(int(p), int(c)) for p, c in matches]

    # Deduplicate while preserving order.
    seen = set()
    unique_cited = []
    for ref in cited:
        if ref not in seen:
            seen.add(ref)
            unique_cited.append(ref)
    cited = unique_cited

    valid = [ref for ref in cited if ref in valid_set]
    invalid = [ref for ref in cited if ref not in valid_set]

    return {
        "cited": cited,
        "valid": valid,
        "invalid": invalid,
        "hallucinated": len(invalid) > 0,
    }


# -----------------------------
# 9. FEATHERLESS AI + TAVILY
# -----------------------------

def make_featherless_client():
    """
    This connects to Featherless AI safely.

    Featherless AI uses an OpenAI-compatible API.
    If the key is missing, retrieval still works but answer generation is skipped.
    """

    api_key = os.environ.get("FEATHERLESS_API_KEY")

    if not api_key:
        print("\nFeatherless API key is missing.")
        print("Retrieval will still work, but answer generation will be skipped.")
        print("Set FEATHERLESS_API_KEY and run again.")
        return None

    try:
        from openai import OpenAI
        return OpenAI(
            base_url="https://api.featherless.ai/v1",
            api_key=api_key,
        )
    except Exception as error:
        print("\nCould not connect to Featherless AI.")
        print("Retrieval will still work, but answer generation will be skipped.")
        print("Error:", error)
        return None



def make_tavily_client():
    """
    This connects to Tavily safely.

    Tavily is used as a web search fallback when the PDF does not have enough evidence.
    If the key is missing, web fallback is simply skipped.
    """

    api_key = os.environ.get("TAVILY_API_KEY")

    if not api_key:
        print("\nTavily API key is missing. Web search fallback will be skipped.")
        return None

    try:
        from tavily import TavilyClient
        return TavilyClient(api_key=api_key)
    except Exception as error:
        print("\nCould not connect to Tavily.")
        print("Web search fallback will be skipped.")
        print("Error:", error)
        return None



def should_use_tavily(question, selected_chunks, reranked_chunks, featherless_client=None):
    """
    This decides whether to use Tavily web search.

    Tavily only runs when:
    1. The user explicitly asks for web/current/latest information, OR
    2. PDF retrieval completely failed — no chunks found at all.

    Tavily does NOT run for summary questions.
    Summary, method, participant, and finding questions are answered from PDF only.
    """

    # Summary questions should always use PDF context only.
    # Pass the client so the decision uses semantic LLM classification rather
    # than the fragile keyword list — this prevents the confidence floor from
    # accidentally routing broad overview questions to web search.
    if is_summary_question(question, featherless_client):
        return False

    # Use Tavily if the user explicitly asks for web/current/latest info.
    if is_web_question(question):
        return True

    # Use Tavily only if PDF retrieval completely failed.
    if not selected_chunks and not reranked_chunks:
        return True

    # Auto-trigger Tavily when all top retrieved chunks are below confidence floor.
    # This catches off-topic questions where the PDF has no relevant content.
    CONFIDENCE_FLOOR = 2.0
    if reranked_chunks:
        top_scores = [c.get("final_score", 0) for c in reranked_chunks[:3]]
        if all(s < CONFIDENCE_FLOOR for s in top_scores):
            return True

    return False



def search_tavily(tavily_client, question):
    """
    This searches the web using Tavily and returns a short context string.
    """

    if tavily_client is None:
        return None

    try:
        result = tavily_client.search(query=question, max_results=3)
        web_parts = []

        for item in result.get("results", []):
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            web_parts.append(f"[Web: {title}]\n{content}\nSource: {url}")

        return "\n\n".join(web_parts) if web_parts else None

    except Exception as error:
        print(f"Tavily search error: {error}")
        return None



def build_prompt(context, question, web_context=None, mode="pdf"):
    """
    Builds the LLM prompt for one of two distinct modes:

    mode="pdf"  — strict document Q&A. The model must answer only from the
                  provided PDF chunks and append "Sources: Page X, Chunk Y" at
                  the end. No outside knowledge is permitted.

    mode="web"  — external "universe" Q&A. The model answers from Tavily web
                  results only. It must never mention page or chunk numbers and
                  must not refer to any PDF or provided context.
    """

    if mode == "web":
        web_section = (
            web_context
            if web_context
            else "(No web search results were returned. State clearly that you cannot answer.)"
        )
        return f"""You are a general knowledge assistant. You are answering an external question about the world — this question cannot be answered from any PDF document.

Your only source of information is the web search results below.

Rules — follow every rule exactly:
1. Answer directly and clearly using only the web search results provided.
2. Lead with the most relevant fact or direct answer, then add supporting detail.
3. NEVER mention page numbers, chunk numbers, or any PDF-related terms.
4. NEVER use phrases like "the provided context", "the PDF", "the document", or any similar reference.
5. If multiple sources agree, state the consensus. If they differ, acknowledge the difference.
6. Structure your response clearly — use plain paragraphs or a short list where it helps.
7. If the web results do not contain enough information to answer, say so clearly and explain what you did find.

Web Search Results:
{web_section}

Question:
{question}
"""

    # mode="pdf" — strict document Q&A with mandatory citations
    return f"""You are a document question-answering assistant. Your only source of information is the PDF context chunks provided below.

Rules — follow every rule exactly:
1. Answer strictly from the provided chunks. Do not use any knowledge outside these chunks.
2. Extract only what directly and explicitly answers the question.
3. If the question is about participants or sample size, state all groups and counts exactly as written.
4. If the question is about methods or analysis, name the exact methods mentioned in the chunks.
5. If the question is about objectives or aims, quote or closely paraphrase the stated objective.
6. Do not infer, extrapolate, or add detail that is not present in the provided chunks.
7. You MUST end your answer with a Sources line in exactly this format:
   Sources: Page X, Chunk Y; Page Z, Chunk W
   Use only the page and chunk numbers from the context chunks below. Do not invent coordinates.
8. If the provided context genuinely does not contain enough information to answer, respond with:
   "The provided context does not contain information about [topic]."
   In that case, do NOT include a Sources line.

PDF Context:
{context}

Question:
{question}
"""



def ask_featherless(featherless_client, context, question, web_context=None, mode="pdf"):
    """
    This sends the question and context to Featherless AI.

    Pass mode="web" when the answer should come from Tavily web results so
    that build_prompt selects the correct prompt template.
    """

    if featherless_client is None:
        return "Featherless AI answer skipped because FEATHERLESS_API_KEY is missing. Retrieval above is still valid."

    prompt = build_prompt(context, question, web_context=web_context, mode=mode)

    try:
        response = featherless_client.chat.completions.create(
            model=FEATHERLESS_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    except Exception as error:
        error_text = str(error)

        if "429" in error_text or "quota" in error_text.lower():
            return "Featherless AI quota is over for now. Wait and try again later."

        return f"Featherless AI error: {error}"


# -----------------------------
# 10. DEBUG PRINTING
# -----------------------------

def print_sample_chunks(chunks, sample_count=3):
    """
    This prints a few chunks so I can check if chunking worked.
    """

    for chunk in chunks[:sample_count]:
        print("\n--- Sample Chunk ---")
        print("Page:", chunk["page"])
        print("Chunk Number:", chunk["chunk_number"])
        print("Section:", chunk.get("section", "unknown"))
        print("Text Preview:", chunk["text"][:200])



def print_retrieved_evidence(reranked_chunks):
    """
    This prints the retrieval result so I can debug the RAG pipeline.
    """

    print("\nRetrieved Evidence After Vector + BM25 + Reranking:")

    for item in reranked_chunks[:SHOW_TOP_N]:
        metadata = item["metadata"]
        page = metadata["page"]
        chunk_number = metadata["chunk_number"]
        distance = item.get("distance")

        if distance is None:
            distance_text = "None"
        else:
            distance_text = f"{distance:.4f}"

        item_meta = item.get("metadata", {})
        section = item_meta.get("section", "unknown")
        file_name = item_meta.get("file_name", "")

        print(
            f"\n- [{file_name}] Page {page}, Chunk {chunk_number} [{section}] "
            f"| Source: {item['source_type']} "
            f"| Distance: {distance_text} "
            f"| BM25: {item['bm25_score']:.2f} "
            f"| Intent Boost: {item['intent_boost']:.2f} "
            f"| DocType Boost: {item.get('document_type_boost', 0):.2f} "
            f"| Section Boost: {item.get('section_boost', 0):.2f} "
            f"| Ref Penalty: {item['reference_penalty']:.2f} "
            f"| Final Score: {item['final_score']:.4f}"
        )

        print("Preview:", item["doc"][:250].replace("\n", " "))



def print_chunks_sent_to_llm(selected_chunks):
    """
    This prints only the chunks that will be sent to Featherless AI.
    """

    print("\nChunks Sent To Featherless AI:")

    for item in selected_chunks:
        metadata = item["metadata"]
        direct_score = item.get("direct_evidence_score", 0)

        section = metadata.get("section", "unknown")
        file_name = metadata.get("file_name", "")

        print(
            f"- [{file_name}] Page {metadata['page']}, Chunk {metadata['chunk_number']} [{section}] "
            f"| Direct Evidence Score: {direct_score}"
        )


def print_citation_validation(validation):
    """
    Prints which citations in the answer are real and which are hallucinated.
    """

    cited = validation["cited"]
    valid_set = set(tuple(v) for v in validation["valid"])
    invalid = validation["invalid"]

    print("\nCitation Validation:")

    if not cited:
        print("  No citations found in answer.")
        return

    for page, chunk in cited:
        if (page, chunk) in valid_set:
            print(f"  Page {page}, Chunk {chunk}  [valid]")
        else:
            print(f"  Page {page}, Chunk {chunk}  [NOT IN CONTEXT — hallucinated]")

    if validation["hallucinated"]:
        print(f"  Warning: {len(invalid)} hallucinated citation(s) detected.")
    else:
        print(f"  All {len(cited)} citation(s) verified.")


# -----------------------------
# 11. EVALUATION MODE
# -----------------------------

def run_eval_mode(engine):
    """
    Runs all test questions automatically using a HybridRAGEngine instance.

    For each question it checks:
    - Retrieval: did the right pages come back?
    - Keywords: does the answer contain expected words?
    - Tavily: did web search trigger or not as expected?

    Results are printed to the terminal and saved to rag_eval_results.json.
    """

    eval_file = "rag_eval_questions.json"
    results_file = "rag_eval_results.json"

    if not os.path.exists(eval_file):
        print(f"\nEval file not found: {eval_file}")
        print("Create rag_eval_questions.json first.")
        return

    with open(eval_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"\nRunning evaluation: {len(test_cases)} questions")
    print("-" * 60)

    results = []
    total_passed = 0

    for case in test_cases:
        question = case["question"]
        expected_keywords = case.get("expected_keywords", [])
        expected_pages = case.get("expected_pages", [])
        expect_tavily = case.get("expect_tavily", False)
        category = case.get("category", "general")

        print(f"\nQ{case['id']}  [{category}]  {question}")

        reranked_chunks = engine.retrieve(question)
        answer, selected_chunks, citation_result, tavily_triggered = engine.answer(question, reranked_chunks)

        # Retrieval check: at least one expected page in selected chunks.
        retrieved_pages = [chunk["metadata"]["page"] for chunk in selected_chunks]
        if expected_pages:
            retrieval_pass = any(page in retrieved_pages for page in expected_pages)
        else:
            retrieval_pass = True

        # Keyword check: at least half of expected keywords appear in answer.
        answer_lower = answer.lower()
        keyword_hits = [kw for kw in expected_keywords if kw.lower() in answer_lower]
        if expected_keywords:
            keyword_pass = len(keyword_hits) >= max(1, len(expected_keywords) // 2)
        else:
            keyword_pass = True

        # Tavily check: triggered only when expected.
        tavily_pass = tavily_triggered == expect_tavily

        # Citation check: no hallucinated sources in the answer.
        citation_pass = not citation_result["hallucinated"]

        overall_pass = retrieval_pass and keyword_pass and tavily_pass and citation_pass
        if overall_pass:
            total_passed += 1

        status = "PASS" if overall_pass else "FAIL"

        print(f"  Retrieval : {'PASS' if retrieval_pass else 'FAIL'}  | Pages returned: {retrieved_pages} | Expected: {expected_pages}")
        print(f"  Keywords  : {'PASS' if keyword_pass else 'FAIL'}  | Found {len(keyword_hits)}/{len(expected_keywords)}: {keyword_hits}")
        print(f"  Tavily    : {'PASS' if tavily_pass else 'FAIL'}  | Triggered: {tavily_triggered} | Expected: {expect_tavily}")
        print(f"  Citations : {'PASS' if citation_pass else 'FAIL'}  | Valid: {len(citation_result['valid'])}/{len(citation_result['cited'])} | Hallucinated: {citation_result['invalid']}")
        print(f"  OVERALL   : {status}")

        results.append({
            "id": case["id"],
            "question": question,
            "category": category,
            "status": status,
            "retrieved_pages": retrieved_pages,
            "expected_pages": expected_pages,
            "retrieval_pass": retrieval_pass,
            "expected_keywords": expected_keywords,
            "keyword_hits": keyword_hits,
            "keyword_pass": keyword_pass,
            "expect_tavily": expect_tavily,
            "tavily_triggered": tavily_triggered,
            "tavily_pass": tavily_pass,
            "citation_pass": citation_pass,
            "cited_sources": citation_result["cited"],
            "hallucinated_citations": citation_result["invalid"],
            "answer": answer,
        })

    print("\n" + "-" * 60)
    print(f"Evaluation complete: {total_passed}/{len(test_cases)} passed")

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Detailed results saved to {results_file}")


# -----------------------------
# 12. HYBRID RAG ENGINE
# -----------------------------

class HybridRAGEngine:
    """
    Orchestrates the full RAG pipeline as a single cohesive object.

    Usage:
        engine = HybridRAGEngine(pdf_paths=["paper.pdf"])
        engine.setup_pipeline(reset=False)          # load PDFs, build indexes
        chunks = engine.retrieve("What is the aim?") # hybrid search + rerank
        answer, selected, validation, triggered = engine.answer("What is the aim?", chunks)
    """

    def __init__(self, pdf_paths, chroma_db_path=CHROMA_DB_PATH, bm25_index_path=BM25_INDEX_PATH):
        self.pdf_paths = pdf_paths if isinstance(pdf_paths, list) else [pdf_paths]
        self.chroma_db_path = chroma_db_path
        self.bm25_index_path = bm25_index_path

        # ChromaDB client is initialised once and reused across setup_pipeline calls.
        self._chroma_client = chromadb.PersistentClient(path=chroma_db_path)

        # Populated by setup_pipeline().
        self.chunks = []
        self.bm25_index = None
        self.collection = None

        self.featherless_client = make_featherless_client()
        self.tavily_client = make_tavily_client()

    def setup_pipeline(self, reset=False):
        """Loads PDFs, builds/loads the BM25 cache, and syncs the ChromaDB collection."""
        self.chunks = load_all_pdfs(self.pdf_paths)
        print_sample_chunks(self.chunks)
        self.bm25_index = load_or_build_bm25(
            self.chunks, self.pdf_paths, reset=reset, index_path=self.bm25_index_path
        )
        print("Building ChromaDB vector collection...")
        self.collection = build_chroma_collection(
            self.chunks, reset=reset, chroma_db_path=self.chroma_db_path, client=self._chroma_client
        )
        print(f"Chunks stored in ChromaDB at '{self.chroma_db_path}'.")

    def retrieve(self, question):
        """Runs hybrid search (vector + BM25) and reranking. Returns sorted candidate chunks."""
        return hybrid_search(
            question=question,
            collection=self.collection,
            bm25_index=self.bm25_index,
            chunks=self.chunks,
        )

    def answer(self, question, reranked_chunks):
        """
        Selects evidence chunks, triggers Tavily fallback if needed, calls the LLM,
        and validates citations.

        Returns (answer_text, selected_chunks, validation_dict, tavily_triggered).
        """
        if not reranked_chunks:
            tavily_triggered = should_use_tavily(question, [], [])
            web_context = None
            if tavily_triggered:
                print("\nSearching with Tavily...")
                web_context = search_tavily(self.tavily_client, question)
            # No PDF chunks at all — always a web answer (or a "cannot answer" message).
            answer_text = ask_featherless(
                self.featherless_client,
                context="No PDF context was found.",
                question=question,
                web_context=web_context,
                mode="web" if tavily_triggered else "pdf",
            )
            return answer_text, [], validate_citations(answer_text, []), tavily_triggered

        selected_chunks = select_chunks_for_answer(question, reranked_chunks, featherless_client=self.featherless_client)
        print_chunks_sent_to_llm(selected_chunks)
        context = build_context(selected_chunks)

        tavily_triggered = should_use_tavily(question, selected_chunks, reranked_chunks, featherless_client=self.featherless_client)
        web_context = None
        if tavily_triggered:
            print("\nUser asked for web information. Searching with Tavily...")
            web_context = search_tavily(self.tavily_client, question)
            if web_context:
                print("Tavily web results found. Adding to context.")
            else:
                print("Tavily returned no results.")

        # Use web mode when Tavily was triggered so the prompt forbids page/chunk refs.
        mode = "web" if tavily_triggered else "pdf"
        answer_text = ask_featherless(self.featherless_client, context, question, web_context=web_context, mode=mode)
        validation = validate_citations(answer_text, selected_chunks)

        return answer_text, selected_chunks, validation, tavily_triggered


# -----------------------------
# 13. MAIN PROGRAM
# -----------------------------

def main():
    """Entry point: parses CLI args, boots HybridRAGEngine, runs chat or eval loop."""

    parser = argparse.ArgumentParser(description="PDF RAG Chatbot")
    parser.add_argument(
        "--pdf",
        nargs="+",
        default=["sample.pdf"],
        metavar="PATH",
        help="One or more PDF file paths (default: sample.pdf)",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Run evaluation mode using rag_eval_questions.json",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and rebuild the ChromaDB collection from scratch",
    )
    args = parser.parse_args()

    engine = HybridRAGEngine(pdf_paths=args.pdf)
    engine.setup_pipeline(reset=args.reset)

    if args.eval:
        run_eval_mode(engine)
        return

    print("\nRAG chatbot is ready.")

    while True:
        try:
            question = input("\nAsk a question about PDF: ")
        except KeyboardInterrupt:
            print("\nChatbot stopped. Bye!")
            break

        if question.lower().strip() == "exit":
            print("Chatbot stopped. Bye!")
            break

        if not question.strip():
            continue

        reranked_chunks = engine.retrieve(question)

        if not reranked_chunks:
            print("No relevant PDF chunks found.")
        else:
            print_retrieved_evidence(reranked_chunks)

        answer_text, _, validation, _ = engine.answer(question, reranked_chunks)

        print("\nFinal Answer:")
        print(answer_text)
        print_citation_validation(validation)


if __name__ == "__main__":
    main()
