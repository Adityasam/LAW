# VakilAI — Legal Research Workspace

AI-powered workspace for Indian lawyers. Manage cases, analyze facts, and research judgments with RAG-based assistance.

## Features

- **Case Management**: Organize criminal and civil matters with client details, hearing dates, and notes.
- **Entity Extraction**: Automatically extract sections (BNS/IPC), parties, and courts from case facts using Gemini 3.1 Flash.
- **Smart Research**: Instant retrieval of relevant judgments via Indian Kanoon integration.
- **RAG Chat**: Context-aware AI assistant that answers questions based strictly on retrieved judgment snippets and specific case facts.
- **Document Vault**: Upload and manage FIRs, charge sheets, and applications.
- **Voice Notes**: Capture quick memos with a visual waveform interface.

## Tech Stack

- **Backend**: Python 3.9+, Flask, SQLAlchemy (SQLite)
- **AI/LLM**: Google Gemini 3.1 Flash (via Vertex AI SDK)
- **Frontend**: Modern CSS3 (CSS Variables, Flexbox/Grid), Vanilla JS
- **Research**: Indian Kanoon API

## Getting Started

### 1. Prerequisites
- Python 3.9 or higher
- Google Gemini API Key

### 2. Installation
```bash
# Clone repository
git clone <repo-url>
cd LAW

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `config.py` (or update existing) with your Gemini API key:
```python
class Config:
    GEMINI_API_KEY = "your-api-key-here"
    # ... other settings
```

### 4. Run Application
```bash
python run.py
```
Access the dashboard at `http://localhost:5000`.

## Project Structure

- `app.py`: Main application entry and API routes.
- `models.py`: Database schema (Cases, Documents, Chat, Notes).
- `keyExtractor.py`: Entity extraction logic.
- `advisor.py`: Gemini RAG and streaming chat logic.
- `chunker.py`: Document cleaning, chunking, and persistent vector storage.
- `services/`: External API integrations (Kanoon).
- `static/`: Modern UI assets (CSS/JS).
- `templates/`: Jinja2 HTML templates.

## License
Proprietary / Internal Use
