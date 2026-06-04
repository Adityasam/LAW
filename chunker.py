import os
import json
import re
from bs4 import BeautifulSoup
from pathlib import Path

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

# Data directory for persistent storage
DATA_DIR = Path(__file__).resolve().parent / "data" / "vectors"
os.makedirs(DATA_DIR, exist_ok=True)

def _get_storage_path(case_id):
    return DATA_DIR / f"case_{case_id}.json"

def vector_db_exists(case_id):
    """Checks if vector data exists for a case."""
    return _get_storage_path(case_id).exists()

def create_vector_db(case_id, judgments_data, case_facts=None):
    """
    Creates persistent JSON storage of chunks from judgments and case facts.
    """
    all_data = []
    
    # 1. Index case facts first
    if case_facts:
        fact_chunks = chunk_text(case_facts)
        for chunk in fact_chunks:
            all_data.append({
                "text": chunk,
                "metadata": {
                    "title": "Initial Case Facts",
                    "type": "case_facts"
                }
            })

    # 2. Index judgments
    for j in judgments_data:
        raw_html = j.get("doc_html", "")
        text = clean_html(raw_html)
        chunks = chunk_text(text)
        
        metadata = {
            "title": j.get("title"),
            "court": j.get("court"),
            "date": j.get("date"),
            "url": j.get("url"),
            "doc_id": j.get("doc_id")
        }
        
        for chunk in chunks:
            all_data.append({
                "text": chunk,
                "metadata": metadata
            })
    
    path = _get_storage_path(case_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_data, f)
        
    print(f"Created {len(all_data)} chunks with metadata for case {case_id}. Saved to {path}.")
    return True

def add_to_vector_db(case_id, text, metadata):
    """
    Chunks new text and appends to existing vector data.
    """
    path = _get_storage_path(case_id)
    all_data = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    
    chunks = chunk_text(text)
    for chunk in chunks:
        all_data.append({
            "text": chunk,
            "metadata": metadata
        })
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_data, f)
    
    print(f"Added {len(chunks)} new chunks for case {case_id} to {path}.")
    return True

def get_relevant_chunks(case_id, query, top_k=5):
    """
    Simple keyword-based retrieval from persistent storage.
    Returns list of dicts with 'text' and 'metadata'.
    """
    path = _get_storage_path(case_id)
    if not path.exists():
        return []
        
    with open(path, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    
    # Simple score based on word overlap
    query_words = set(query.lower().split())
    scored_items = []
    for item in all_data:
        chunk_words = set(item["text"].lower().split())
        score = len(query_words.intersection(chunk_words))
        scored_items.append((score, item))
    
    # Sort by score and return top_k
    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in scored_items[:top_k] if score > 0]
