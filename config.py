# config.py
# ---------------------------------------------------------------------------
# Centralised configuration for the VakilAI Flask application.
# Keep secrets out of source control in real deployments — use environment
# variables (e.g. python-dotenv) and override values here.
# ---------------------------------------------------------------------------
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


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

    # --- External API keys (placeholders) ---
    # Replace with real values from environment variables in production.
    INDIAN_KANOON_API_KEY = os.environ.get("INDIAN_KANOON_API_KEY", "")
    INDIAN_KANOON_BASE_URL = "https://api.indiankanoon.org"

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    # --- App metadata ---
    APP_NAME = "VakilAI"
    APP_VERSION = "0.1.0"
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
