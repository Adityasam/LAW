# config.py
# ---------------------------------------------------------------------------
# Centralised configuration for the LegalMind Flask application.
# Keep secrets out of source control in real deployments — use environment
# variables (e.g. python-dotenv) and override values here.
# ---------------------------------------------------------------------------
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration shared across environments."""

    # --- Core Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "vakilai-dev-secret-change-me")

    # --- Database ---
    # SQLite file lives next to the app for easy local development.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'vakilai.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Uploads ---
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # Allowed extensions for case documents.
    ALLOWED_EXTENSIONS = {
        "pdf", "doc", "docx", "txt", "jpg", "jpeg", "png",
    }

    # --- External API keys ---
    INDIAN_KANOON_API_KEY = os.environ.get("INDIAN_KANOON_API_KEY", "")
    INDIAN_KANOON_BASE_URL = "https://api.indiankanoon.org"

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "models/gemini-3.1-flash-lite-preview")
    # Embedding model used by chunker.py for semantic retrieval.
    EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "gemini-embedding-001")

    # --- App metadata ---
    APP_NAME = "LegalMind"
    DEBUG = True
