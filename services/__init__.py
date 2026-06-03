# services/__init__.py
# ---------------------------------------------------------------------------
# Re-export service clients so app.py can `from services import kanoon`.
# ---------------------------------------------------------------------------
from .kanoon import IndianKanoon, IndianKanoonError

__all__ = ["IndianKanoon", "IndianKanoonError"]
