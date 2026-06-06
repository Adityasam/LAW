# LegalMind — Legal Research Workspace

**LegalMind** is a professional, AI-powered workspace designed for Indian lawyers to manage litigation matters, automate legal research, and analyze case documents using advanced Retrieval-Augmented Generation (RAG).

## Key Features

- **Document Intelligence (OCR & Summarization)**: Upload PDFs or images (FIRs, charge sheets, evidence). Gemini automatically performs OCR and generates professional legal summaries in structured Markdown.
- **Asynchronous Background Processing**: Long-running AI tasks (summarization, Kanoon research, vector indexing) run on background workers, ensuring a smooth, non-blocking UI experience.
- **Advanced RAG Chat**: A dedicated AI Legal Assistant that uses:
    - **Case Facts**: Your manually entered matter details.
    - **AI Case Brief**: Automatically generated summary of facts.
    - **Document Summaries**: Context from all uploaded evidence.
    - **Live Research**: Top-3 relevant judgments fetched from **Indian Kanoon**.
- **Unified Documents Repository**: A centralized view of every document across all active matters, with instant AI-powered search and summary previews.
- **Active Matters Management**: Track Criminal and Civil cases with hearing dates, sections (BNS/IPC/BSA), and counsel assignments.
- **Persistent Vector DB**: Case-specific JSON-based vector stores that index facts, judgment HTML, and document text for precise retrieval during chat.

## Tech Stack

- **Backend**: Python 3.9+, Flask, SQLAlchemy (SQLite)
- **AI/LLM**: Google Gemini 1.5 & 3.1 Flash (Multi-modal for OCR + RAG)
- **Vector Storage**: Custom JSON-based persistent indexing (in `data/vectors/`)
- **Frontend**: Vanilla JS (Modular), Modern CSS3, Jinja2 Templates, Marked.js (Markdown rendering)
- **APIs**: Indian Kanoon API integration

## Getting Started

### 1. Installation
```bash
# Clone the repository
git clone <repo-url>
cd LAW

# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file in the root directory:
```bash
SECRET_KEY=your-secret-key
GEMINI_API_KEY=your-gemini-api-key
INDIAN_KANOON_API_KEY=your-kanoon-api-key
GEMINI_MODEL_NAME=models/gemini-3.1-flash-lite-preview
```

### 3. Running the App
```bash
python run.py
```
Visit `http://localhost:5000` to access your workspace.

## Architecture

- `app.py`: Application factory and core API endpoints.
- `models.py`: Database schema for Cases, Documents, Judgments, and Chat history.
- `routes/`: Modular blueprints for Cases, Documents, and Chat logic.
- `services/doc_processor.py`: Multi-modal Gemini integration for OCR and document analysis.
- `advisor.py`: RAG orchestration and streaming chat response generation.
- `chunker.py`: Persistent vector storage, text cleaning, and overlap-based chunking.
- `keyExtractor.py`: Legal entity extraction and automated case brief generation.

## Project Status
**LegalMind v1.0** — Robust document management and automated research pipeline implemented.
