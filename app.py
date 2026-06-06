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
import os
import uuid
import functools
from datetime import date, timedelta, datetime
import json
from pathlib import Path

from flask import Flask, redirect, render_template, url_for, request, session, Response, jsonify, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import Case, ChatMessage, Document, Note, db, Setting, Judgment, get_firm_settings
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

    def login_required(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if 'firm_id' not in session:
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function

    # ---- Routes --------------------------------------------------------- #
    @app.get("/")
    @login_required
    def index():
        """Landing — just bounces to the dashboard."""
        return redirect(url_for("dashboard"))

    # ---- Helpers used by both /dashboard and /cases/<id> ------------- #
    def _current_user() -> dict:
        """Pick firm as the "current user"."""
        firm_name = session.get('firm_name', 'Firm')
        initials = "".join([n[0] for n in firm_name.split()[:2]]).upper()
        return {
            "name":            firm_name,
            "designation":     "Law Firm",
            "chamber":         "Firm Workspace",
            "avatar_initials": initials or "LF",
        }

    def _all_cases() -> list[dict]:
        """All cases in the system, hydrated for the UI (sidebar / dashboard)."""
        firm_id = session.get('firm_id')
        if not firm_id: return []
        
        rows = Case.query.filter_by(firm_id=firm_id).order_by(Case.id.desc()).all()
        out = []
        for c in rows:
            d = c.to_dict(include_relations=True)
            # Aliases so the existing JS / templates work unchanged.
            d["name"]            = d.get("title")
            d["client"]          = d.get("client_name")
            d["type"]            = d.get("case_type")
            d["next_hearing"]    = d.get("hearing_date")
            d["id_display"]      = f"CASE-{c.id:04d}"
            out.append(d)
        return out

    def _case_stats(cases: list[dict]) -> dict:
        s = {"total": len(cases), "active": 0, "hearing": 0, "closed": 0}
        for c in cases:
            st = (c.get("status") or "Active").lower()
            if st in s: s[st] += 1
        return s

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            identifier = request.form.get("identifier")
            password = request.form.get("password")
            from models import Firm
            firm = Firm.query.filter((Firm.email == identifier) | (Firm.username == identifier)).first()
            if firm and check_password_hash(firm.password_hash, password):
                session['firm_id'] = firm.id
                session['firm_name'] = firm.name
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash("Invalid username/email or password", "error")
        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            name = request.form.get("name")
            username = request.form.get("username")
            email = request.form.get("email")
            password = request.form.get("password")
            from models import Firm
            if Firm.query.filter((Firm.email == email) | (Firm.username == username)).first():
                flash("Username or Email already registered", "error")
            else:
                new_firm = Firm(
                    name=name, 
                    username=username, 
                    email=email, 
                    password_hash=generate_password_hash(password)
                )
                db.session.add(new_firm)
                db.session.commit()
                flash("Account created! Please log in.", "success")
                return redirect(url_for('login'))
        return render_template("signup.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for('login'))

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
    @login_required
    def dashboard():
        """Render the dashboard — the new entry point for the app."""
        user  = _current_user()
        cases = _all_cases()
        return render_template(
            "dashboard.html",
            user=user,
            cases=cases,
            stats=_case_stats(cases),
        )

    @app.get("/case/<int:case_id>")
    @login_required
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
    @login_required
    def documents_page():
        """Render the all-documents page."""
        user = _current_user()
        cases = _all_cases()
        # Fetch all documents for the firm's cases
        docs = Document.query.join(Case).filter(Case.firm_id == session['firm_id']).order_by(Document.uploaded_at.desc()).all()
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
    @login_required
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

    @app.get("/settings")
    @login_required
    def settings_page():
        """Render the settings page."""
        user = _current_user()
        cases = _all_cases()
        settings = get_firm_settings(session['firm_id'])
        return render_template(
            "settings.html",
            user=user,
            cases=cases,
            settings=settings
        )

    @app.post("/settings")
    @login_required
    def save_settings():
        """Update workspace settings."""
        payload = request.get_json() or {}
        s = get_firm_settings(session['firm_id'])
        
        # Firm Details
        s.firm_name = payload.get("firm_name")
        s.lawyer_name = payload.get("lawyer_name")
        s.address = payload.get("address")
        s.default_court = payload.get("default_court")
        
        # AI Options
        s.ai_language = payload.get("ai_language", "English")
        s.include_ipc_equivalent = bool(payload.get("include_ipc_equivalent"))
        s.max_judgments = int(payload.get("max_judgments", 3))
        
        db.session.commit()
        return {"ok": True}

    @app.post("/cases/<int:case_id>/notes")
    @login_required
    def add_note(case_id: int):
        """POST /cases/<id>/notes — add a new note to a case."""
        case = Case.query.filter_by(id=case_id, firm_id=session['firm_id']).first()
        if not case:
            return {"error": "Case not found or access denied"}, 404
        
        payload = request.get_json(silent=True) or {}
        content = payload.get("content")
        if not content:
            return {"error": "Content is required"}, 400
            
        new_note = Note(
            case_id=case_id,
            title=payload.get("title") or "Note",
            content=content,
            note_type="text"
        )
        try:
            db.session.add(new_note)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500
        
        return {"ok": True, "note": new_note.to_dict()}

    @app.delete("/notes/<int:note_id>")
    @login_required
    def delete_note(note_id: int):
        """DELETE /notes/<id> — remove a note."""
        note = Note.query.join(Case).filter(Note.id == note_id, Case.firm_id == session['firm_id']).first()
        if not note:
            return {"error": "Note not found or access denied"}, 404
        
        db.session.delete(note)
        db.session.commit()
        return {"ok": True}

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
    @login_required
    def extract():
        """Manual trigger for case analysis (research + summary)."""
        case_id = request.json.get("case_id")
        if not case_id:
            return {"error": "case_id is required"}, 400
        
        case = Case.query.filter_by(id=case_id, firm_id=session['firm_id']).first()
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
    @login_required
    def get_chat_history(case_id):
        """Fetch chat history for a specific case."""
        case = Case.query.filter_by(id=case_id, firm_id=session['firm_id']).first()
        if not case:
            return {"error": "Case not found"}, 404
        msgs = ChatMessage.query.filter_by(case_id=case_id).order_by(ChatMessage.created_at.asc()).all()
        return {
            "ok": True,
            "analysis_status": case.analysis_status,
            "messages": [m.to_dict() for m in msgs]
        }

    @app.post("/chat-stream")
    @login_required
    def chat_stream():
        """RAG-based streaming chat with context preservation."""
        case_id = request.json.get("case_id")
        user_msg = request.json.get("message")
        
        if not case_id or not user_msg:
            return {"error": "case_id and message are required"}, 400
            
        case = Case.query.filter_by(id=case_id, firm_id=session['firm_id']).first()
        if not case:
            return {"error": "Case not found"}, 404

        # 1. Fetch history and case facts from DB
        history_msgs = ChatMessage.query.filter_by(case_id=case_id).order_by(ChatMessage.created_at.asc()).all()
        history = [{"role": "user" if m.role in ("user", "lawyer") else "model", "content": m.content} for m in history_msgs]
        
        # Use AI summary for chat context if available, fallback to raw facts
        case_context = (case.ai_summary if case.ai_summary else (case.facts or ""))
        
        # 2. Fetch document summaries and notes
        doc_summaries = []
        judgment_summaries = []
        case_notes = []
        if case:
            for doc in case.documents:
                if doc.summary:
                    doc_summaries.append({"name": doc.original_name, "summary": doc.summary})
            
            for j in case.judgments:
                if j.summary:
                    judgment_summaries.append({"title": j.title, "summary": j.summary})
            
            for note in case.notes:
                case_notes.append({"title": note.title or "Note", "content": note.content})

        # 3. Get RAG context
        relevant = get_relevant_chunks(case_id, user_msg)
        firm_id = session['firm_id']
        settings = get_firm_settings(firm_id)
        ai_lang = settings.ai_language
        
        def generate():
            full_response = ""
            for text in stream_legal_chat(user_msg, relevant, history, case_context, doc_summaries, judgment_summaries, case_notes, language=ai_lang):
                full_response += text
                yield text
            
            # 3. Persist exchange to DB after stream finishes
            with app.app_context():
                db.session.add(ChatMessage(case_id=case_id, role="user", content=user_msg))
                db.session.add(ChatMessage(case_id=case_id, role="ai", content=full_response))
                db.session.commit()
                
        return Response(generate(), mimetype='text/event-stream')

    @app.post("/get-doc")
    @login_required
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
