# app.py
# ---------------------------------------------------------------------------
# LegalMind Flask application entry point.
#
#  * Bootstraps the Flask app with config from config.py
#  * Initialises SQLAlchemy (db lives in models.py to avoid circular imports)
#  * Registers the case / document / chat blueprints
#  * Exposes a / route that renders the LegalMind workspace UI
#  * Exposes a /seed route that wipes & repopulates the database with
#    realistic Indian dummy data (2 lawyers, 3 cases, 4 documents, 2 notes
#    per case)
# ---------------------------------------------------------------------------
from datetime import date, timedelta
import json

from flask import Flask, redirect, render_template, url_for, request, session, Response

from config import Config
from models import Case, ChatMessage, Document, Lawyer, Note, db
from routes import cases_bp, chat_bp, documents_bp
from keyExtractor import extract_case_entities
from advisor import get_legal_advice, fetch_doc_by_id, stream_legal_chat
from chunker import create_vector_db, get_relevant_chunks, vector_db_exists


def create_app(config_class: type[Config] = Config) -> Flask:
    """Application factory. Returns a fully configured Flask instance."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Make sure the uploads directory exists at boot.
    import os
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialise extensions.
    db.init_app(app)

    # Auto-create the schema on first boot (no migrations yet).
    with app.app_context():
        db.create_all()

    # Register blueprints.
    app.register_blueprint(cases_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(chat_bp)

    # ---- Routes --------------------------------------------------------- #
    @app.get("/")
    def index():
        """Landing — just bounces to the dashboard."""
        return redirect(url_for("dashboard"))

    # ---- Helpers used by both /dashboard and /cases/<id> ------------- #
    def _current_user() -> dict:
        """Pick the first lawyer as the "current user" — no auth yet."""
        lawyer = Lawyer.query.order_by(Lawyer.id.asc()).first()
        return {
            "name":            lawyer.name            if lawyer else "Advocate",
            "designation":     "Senior Counsel",
            "chamber":         lawyer.chamber         if lawyer else "Independent Chamber",
            "avatar_initials": lawyer.avatar_initials if lawyer else "AC",
        }

    def _all_lawyers() -> list[dict]:
        return [l.to_dict() for l in Lawyer.query.order_by(Lawyer.id.asc()).all()]

    def _all_cases() -> list[dict]:
        """All cases in the system, hydrated for the UI (sidebar / dashboard)."""
        rows = Case.query.order_by(Case.id.desc()).all()
        out = []
        for c in rows:
            d = c.to_dict(include_relations=True)
            # Aliases so the existing JS / templates work unchanged.
            d["name"]            = d.get("title")
            d["client"]          = d.get("client_name")
            d["type"]            = d.get("case_type")
            d["next_hearing"]    = d.get("hearing_date")
            d["lawyer"]          = c.lawyer.name if c.lawyer else None
            d["assigned_lawyer"] = c.lawyer.name if c.lawyer else None
            d["id_display"]      = f"CASE-{c.id:04d}"
            out.append(d)
        return out

    def _case_stats(cases: list[dict]) -> dict:
        s = {"total": len(cases), "active": 0, "hearing": 0, "closed": 0}
        for c in cases:
            st = (c.get("status") or "Active").lower()
            if st in s: s[st] += 1
        return s

    def _chat_for(case_id: int) -> list[dict]:
        msgs = (
            ChatMessage.query
            .filter_by(case_id=case_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(50)
            .all()
        )
        out = []
        for m in msgs:
            item = m.to_dict()
            if m.role == "ai":
                item["citations"] = item.get("citations") or []
                item["sections"]  = item.get("sections")  or []
            out.append(item)
        return out

    @app.get("/dashboard")
    def dashboard():
        """Render the dashboard — the new entry point for the app."""
        user  = _current_user()
        cases = _all_cases()
        return render_template(
            "dashboard.html",
            user=user,
            cases=cases,
            lawyers=_all_lawyers(),
            stats=_case_stats(cases),
        )

    @app.get("/case/<int:case_id>")
    def case_detail(case_id: int):
        """Render the case-details page for a specific case."""
        case = db.session.get(Case, case_id)
        if not case:
            return ("Case not found", 404)

        user  = _current_user()
        cases = _all_cases()

        # Pick the requested case as the "active" one.
        active = next((c for c in cases if c["id"] == case_id), None)
        if active is None:
            return ("Case not found", 404)

        # Pre-shape the active case so the template can render it directly.
        active_case = dict(active)
        active_case["documents"] = active_case.get("documents") or []
        active_case["notes"]     = active_case.get("notes")     or []
        active_case["sections"]  = active_case.get("sections")  or []

        return render_template(
            "case.html",
            user=user,
            cases=cases,
            active_case=active_case,
            chat_history=_chat_for(case_id),
            quick_queries=[],
        )

    @app.get("/documents")
    def documents_page():
        """Render the all-documents page."""
        user = _current_user()
        cases = _all_cases()
        # Fetch all documents with their case information
        docs = Document.query.order_by(Document.uploaded_at.desc()).all()
        hydrated_docs = []
        for d in docs:
            item = d.to_dict()
            item["case_name"] = d.case.title if d.case else "Unassigned"
            item["case_id_display"] = f"CASE-{d.case.id:04d}" if d.case else "N/A"
            hydrated_docs.append(item)
            
        return render_template(
            "documents.html",
            user=user,
            cases=cases,
            documents=hydrated_docs
        )

    @app.get("/cases")
    def cases_page():
        """Render the full case-list page."""
        user = _current_user()
        cases = _all_cases()
        return render_template(
            "cases.html",
            user=user,
            cases=cases,
            stats=_case_stats(cases)
        )

    @app.get("/health")
    def health():
        """Lightweight liveness probe — returns DB connectivity status."""
        try:
            db.session.execute(db.text("SELECT 1"))
            db_ok = True
        except Exception as exc:  # pragma: no cover
            db_ok = False
            app.logger.exception("Health check DB error: %s", exc)
        return {"ok": True, "db": db_ok, "app": app.config["APP_NAME"]}

    @app.post("/seed")
    def seed():
        """
        Wipe and re-populate the database with dummy data.
        Idempotent — safe to call repeatedly during development.
        """
        with app.app_context():
            # Drop & recreate the schema for a true clean slate.
            db.drop_all()
            db.create_all()
            # No dummy data inserted

        return {
            "ok": True,
            "seeded": {
                "lawyers":   Lawyer.query.count(),
                "cases":     Case.query.count(),
                "documents": Document.query.count(),
                "notes":     Note.query.count(),
            },
        }

    @app.post("/extract")
    def extract():
        """Manual trigger for case analysis (research + summary)."""
        case_id = request.json.get("case_id")
        if not case_id:
            return {"error": "case_id is required"}, 400
        
        case = Case.query.get(case_id)
        if not case:
            return {"error": "Case not found"}, 404
            
        if not case.facts:
            return {"error": "No facts recorded for this case"}, 400

        # Trigger background analysis
        from routes.cases import process_case_background
        import threading
        
        app_instance = current_app._get_current_object()
        thread = threading.Thread(
            target=process_case_background, 
            args=(app_instance, case.id, case.facts)
        )
        thread.start()
        
        return {
            "ok": True,
            "message": "Analysis started in background."
        }

    @app.get("/cases/<int:case_id>/chat")
    def get_chat_history(case_id):
        """Fetch chat history for a specific case."""
        case = db.session.get(Case, case_id)
        msgs = ChatMessage.query.filter_by(case_id=case_id).order_by(ChatMessage.created_at.asc()).all()
        return {
            "ok": True,
            "analysis_status": case.analysis_status if case else "pending",
            "messages": [m.to_dict() for m in msgs]
        }

    @app.post("/chat-stream")
    def chat_stream():
        """RAG-based streaming chat with context preservation."""
        case_id = request.json.get("case_id")
        user_msg = request.json.get("message")
        
        if not case_id or not user_msg:
            return {"error": "case_id and message are required"}, 400
            
        # 1. Fetch history and case facts from DB
        history_msgs = ChatMessage.query.filter_by(case_id=case_id).order_by(ChatMessage.created_at.asc()).all()
        history = [{"role": m.role, "content": m.content} for m in history_msgs]
        
        case = Case.query.get(case_id)
        # Use AI summary for chat context if available, fallback to raw facts
        case_context = (case.ai_summary if case and case.ai_summary else (case.facts if case else ""))
        
        # 2. Fetch document summaries
        doc_summaries = []
        judgment_summaries = []
        if case:
            for doc in case.documents:
                if doc.summary:
                    doc_summaries.append({"name": doc.original_name, "summary": doc.summary})
            
            for j in case.judgments:
                if j.summary:
                    judgment_summaries.append({"title": j.title, "summary": j.summary})

        # 3. Get RAG context
        relevant = get_relevant_chunks(case_id, user_msg)
        
        def generate():
            full_response = ""
            for text in stream_legal_chat(user_msg, relevant, history, case_context, doc_summaries, judgment_summaries):
                full_response += text
                yield text
            
            # 3. Persist exchange to DB after stream finishes
            with app.app_context():
                db.session.add(ChatMessage(case_id=case_id, role="lawyer", content=user_msg))
                db.session.add(ChatMessage(case_id=case_id, role="ai", content=full_response))
                db.session.commit()
                
        return Response(generate(), mimetype='text/event-stream')

    @app.post("/get-doc")
    def get_doc():
        """Fetch document content by ID."""
        doc_id = request.json.get("doc_id")
        if not doc_id:
            return {"error": "doc_id is required"}
        doc = fetch_doc_by_id(doc_id)
        return {
            "ok": True,
            "content": doc,
        }

    return app





# --------------------------------------------------------------------------- #
# WSGI entry point
# --------------------------------------------------------------------------- #
app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
