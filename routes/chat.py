# routes/chat.py
# ---------------------------------------------------------------------------
# Chat blueprint placeholder.
#
# The live chat endpoints live in app.py:
#   * GET  /cases/<id>/chat  -> get_chat_history (returns analysis_status too)
#   * POST /chat-stream      -> RAG streaming reply
#
# This blueprint previously defined its own GET/POST /cases/<id>/chat handlers,
# but the GET one shadowed app.py's route (it was registered first) and did NOT
# return `analysis_status`, breaking the front-end's processing poll. The POST
# handler was a dead stub the UI never calls. Both were removed; the blueprint
# is kept registered in case future chat routes are added here.
# ---------------------------------------------------------------------------
from flask import Blueprint

chat_bp = Blueprint("chat", __name__)
