# routes/chat.py
# ---------------------------------------------------------------------------
# Blueprint for the per-case AI chat thread.
# For now the AI "response" is a stub: we save the lawyer's message, then
# echo a placeholder reply so the front-end can be wired up before the real
# Gemini / Indian Kanoon pipeline is plugged in.
# ---------------------------------------------------------------------------
from flask import Blueprint, jsonify, request

from models import ChatMessage, Case, db

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/cases/<int:case_id>/chat")
def list_messages(case_id: int):
    """GET /cases/<id>/chat — return the conversation history, oldest first."""
    case = db.session.get(Case, case_id)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404

    msgs = (
        ChatMessage.query
        .filter_by(case_id=case_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    return jsonify({
        "ok": True,
        "count": len(msgs),
        "messages": [m.to_dict() for m in msgs],
    })


@chat_bp.post("/cases/<int:case_id>/chat")
def post_message(case_id: int):
    """
    POST /cases/<id>/chat
        body: { "content": "..." }
    Persists the lawyer's message, persists a placeholder AI reply, returns
    both as JSON so the UI can render them in one round trip.
    """
    case = db.session.get(Case, case_id)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404

    payload = request.get_json(silent=True) or {}
    content = (payload.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "error": "content is required"}), 400

    # 1. Save the lawyer's question.
    user_msg = ChatMessage(case_id=case_id, role="lawyer", content=content)
    db.session.add(user_msg)

    # 2. Stub AI reply. Real implementation will call Gemini + Indian Kanoon.
    ai_msg = ChatMessage(
        case_id = case_id,
        role    = "ai",
        content = "Searching Indian Kanoon database...",
    )
    db.session.add(ai_msg)
    db.session.commit()

    return jsonify({
        "ok": True,
        "user_message": user_msg.to_dict(),
        "ai_message":   ai_msg.to_dict(),
    }), 201
