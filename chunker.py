import os
import json
import math
from bs4 import BeautifulSoup
from pathlib import Path

from google import genai
from google.genai import types
from config import Config

# Shared Gemini client for embeddings.
_client = genai.Client(api_key=Config.GEMINI_API_KEY)
EMBED_MODEL = Config.EMBEDDING_MODEL_NAME
_EMBED_BATCH = 100  # Gemini embed_content batch cap.


def clean_html(html_content):
    """Extracts plain text from HTML."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    text = soup.get_text()
    # Break into lines and remove leading/trailing whitespace
    lines = (line.strip() for line in text.splitlines())
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    return "\n".join(chunk for chunk in chunks if chunk)

def chunk_text(text, chunk_size=1000, overlap=100):
    """Simple character-based chunking."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


# ── Embeddings ──────────────────────────────────────────────────────────────

def _embed(texts, task_type):
    """
    Embed a list of texts with the Gemini embedding model.
    Returns a list of vectors (list[float]) aligned with `texts`, or a list of
    Nones if the API call fails so callers can degrade gracefully.
    """
    if not texts:
        return []
    vectors = []
    try:
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i:i + _EMBED_BATCH]
            resp = _client.models.embed_content(
                model=EMBED_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            vectors.extend([list(e.values) for e in resp.embeddings])
        return vectors
    except Exception as e:
        print(f"Embedding failed ({task_type}): {e}")
        return [None] * len(texts)


def _embed_documents(texts):
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def _embed_query(text):
    v = _embed([text], "RETRIEVAL_QUERY")
    return v[0] if v else None


def _cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _keyword_score(query, text):
    """Fallback lexical overlap score (legacy behaviour)."""
    query_words = set(query.lower().split())
    chunk_words = set(text.lower().split())
    return len(query_words.intersection(chunk_words))


# Data directory for persistent storage
DATA_DIR = Path(__file__).resolve().parent / "data" / "vectors"
os.makedirs(DATA_DIR, exist_ok=True)

def _get_storage_path(case_id):
    return DATA_DIR / f"case_{case_id}.json"

def _load(path):
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading vector data at {path}: {e}")
        return []

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def create_vector_db(case_id, judgments_data, case_facts=None):
    """
    Creates or updates persistent JSON storage of embedded chunks from
    judgments and case facts.
    """
    path = _get_storage_path(case_id)
    all_data = _load(path)  # keep any previously indexed documents

    new_chunks = []  # (text, metadata) awaiting embedding

    # 1. Index case facts
    if case_facts:
        # Check if we already have case facts to avoid duplication
        has_facts = any(item.get("metadata", {}).get("type") == "case_facts" for item in all_data)
        if not has_facts:
            for chunk in chunk_text(case_facts):
                new_chunks.append((chunk, {"title": "Initial Case Facts", "type": "case_facts"}))

    # 2. Index judgments
    for j in judgments_data:
        doc_id = j.get("doc_id")
        # Check if this judgment is already indexed
        if doc_id and any(item.get("metadata", {}).get("doc_id") == str(doc_id) for item in all_data):
            continue

        text = clean_html(j.get("doc_html", ""))
        metadata = {
            "title": j.get("title"),
            "court": j.get("court"),
            "date": j.get("date"),
            "url": j.get("url"),
            "doc_id": str(doc_id) if doc_id else None,
        }
        for chunk in chunk_text(text):
            new_chunks.append((chunk, metadata))

    all_data.extend(_embed_chunks(new_chunks))

    _save(path, all_data)
    print(f"Updated vector DB for case {case_id}: total {len(all_data)} chunks. Saved to {path}.")
    return True

def add_to_vector_db(case_id, text, metadata):
    """
    Chunks new text, embeds it, and appends to existing vector data.
    """
    path = _get_storage_path(case_id)
    all_data = _load(path)

    # Simple deduplication check for documents based on filename
    filename = metadata.get("filename")
    if filename and any(item.get("metadata", {}).get("filename") == filename for item in all_data):
        print(f"Document {filename} already indexed for case {case_id}. Skipping.")
        return True

    new_chunks = [(chunk, metadata) for chunk in chunk_text(text)]
    embedded = _embed_chunks(new_chunks)
    all_data.extend(embedded)

    _save(path, all_data)
    print(f"Added {len(embedded)} new chunks for case {case_id} to {path}.")
    return True


def _embed_chunks(chunks):
    """chunks: list[(text, metadata)] -> list[{text, metadata, embedding}]."""
    if not chunks:
        return []
    texts = [c[0] for c in chunks]
    vectors = _embed_documents(texts)
    return [
        {"text": t, "metadata": m, "embedding": v}
        for (t, m), v in zip(chunks, vectors)
    ]


def get_relevant_chunks(case_id, query, top_k=5):
    """
    Semantic retrieval over the persisted embeddings (cosine similarity).
    Falls back to lexical keyword overlap when embeddings are unavailable
    (embed API down, or legacy stores written before embeddings existed).
    Returns list of dicts with 'text' and 'metadata'.
    """
    path = _get_storage_path(case_id)
    all_data = _load(path)
    if not all_data:
        return []

    query_vec = _embed_query(query)
    has_embeddings = any(item.get("embedding") for item in all_data)

    if query_vec and has_embeddings:
        scored = []
        for item in all_data:
            emb = item.get("embedding")
            score = _cosine(query_vec, emb) if emb else 0.0
            scored.append((score, item))
        threshold = 0.0
    else:
        # Fallback: lexical overlap (legacy behaviour).
        scored = [(_keyword_score(query, item["text"]), item) for item in all_data]
        threshold = 0

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"text": item["text"], "metadata": item.get("metadata", {})}
        for score, item in scored[:top_k]
        if score > threshold
    ]
