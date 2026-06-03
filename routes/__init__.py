# routes/__init__.py
# ---------------------------------------------------------------------------
# Re-export the route blueprints so app.py can import them as a single
# namespace, e.g. `from routes import cases_bp, documents_bp, chat_bp`.
# ---------------------------------------------------------------------------
from .cases import cases_bp
from .documents import documents_bp
from .chat import chat_bp

__all__ = ["cases_bp", "documents_bp", "chat_bp"]
