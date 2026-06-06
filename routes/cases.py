# routes/cases.py
# ---------------------------------------------------------------------------
# Blueprint exposing CRUD-ish operations on Case rows.
# All endpoints return JSON. No authentication for now.
# ---------------------------------------------------------------------------
from datetime import datetime
from typing import Optional
import threading
from flask import Blueprint, jsonify, request, current_app, session

from models import Case, db, Judgment
from keyExtractor import extract_case_entities
from chunker import create_vector_db, vector_db_exists
from advisor import get_legal_advice, fetch_doc_by_id, client

cases_bp = Blueprint("cases", __name__, url_prefix="/cases")


def login_required_api(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'firm_id' not in session:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


def _parse_date(s: Optional[str]):
    if not s:
        return None
    try:
        # Accepts "YYYY-MM-DD" or full ISO timestamps.
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def process_case_background(app_instance, case_id, facts):
    """Background task to extract entities, generate summary and research judgments."""
    with app_instance.app_context():
        try:
            # Update status to processing
            case = db.session.query(Case).get(case_id)
            if case:
                case.analysis_status = "processing"
                db.session.commit()

            # 1. AI Analysis (Entities + Summary)
            analysis = extract_case_entities(facts)
            
            # 2. Research Judgments (Indian Kanoon)
            # Fetch firm_id from case for research settings
            firm_id = None
            case = db.session.query(Case).get(case_id)
            if case:
                firm_id = case.firm_id

            research_data = get_legal_advice(facts, analysis, firm_id=firm_id)
            judgments_meta = research_data.get("judgments", [])

            # 3. Update Case record with summary and sections
            case = db.session.query(Case).get(case_id)
            if case:
                if "ai_summary" in analysis:
                    case.ai_summary = analysis["ai_summary"]
                if not case.sections and analysis.get("sections"):
                    sections_list = [s.get("code") for s in analysis["sections"] if s.get("code")]
                    case.sections = ", ".join(sections_list)
                db.session.commit()

            # 4. Fetch Full HTML and Generate Summaries for Judgments
            judgments_to_index = []
            for jm in judgments_meta:
                doc_id = jm.get("doc_id")
                if not doc_id: continue
                
                try:
                    # Fetch HTML
                    full_doc = fetch_doc_by_id(doc_id)
                    doc_html = full_doc.get("doc", "")
                    
                    # Generate short ~300 word summary for this judgment
                    summary_prompt = f"""
                    Summarize this legal judgment in about 300 words using professional legal Markdown. 
                    Highlight the core dispute, key legal principles applied, and the final ruling.
                    
                    Use bold headings for sections like **Core Dispute**, **Key Legal Principles**, and **Final Ruling**.
                    Use bullet points for lists.
                    
                    JUDGMENT TITLE: {jm.get('title')}
                    CONTENT: {doc_html[:10000]} # Send first 10k chars for summary
                    """
                    sum_res = client.models.generate_content(
                        model=current_app.config["GEMINI_MODEL_NAME"],
                        contents=summary_prompt
                    )
                    j_summary = sum_res.text.strip()

                    # Save to judgments table
                    judgment = Judgment(
                        case_id   = case_id,
                        title     = jm.get("title"),
                        court     = jm.get("court"),
                        date      = jm.get("date"),
                        url       = jm.get("url"),
                        doc_id    = str(doc_id),
                        summary   = j_summary,
                        full_html = doc_html
                    )
                    db.session.add(judgment)
                    
                    # Prep for vector DB
                    jm["doc_html"] = doc_html
                    judgments_to_index.append(jm)
                    
                except Exception as e:
                    app_instance.logger.error("Failed to process judgment %s: %s", doc_id, e)
            
            db.session.commit()

            # 5. Create/Update Vector DB (Case Facts + Judgment HTML)
            create_vector_db(case_id, judgments_to_index, facts)
            
            # Final status update
            case = db.session.query(Case).get(case_id)
            if case:
                case.analysis_status = "completed"
                db.session.commit()
                
        except Exception as e:
            app_instance.logger.error("Background processing error for case %s: %s", case_id, e)
            try:
                case = db.session.query(Case).get(case_id)
                if case:
                    case.analysis_status = "failed"
                    db.session.commit()
            except:
                pass


@cases_bp.get("/")
def list_cases():
    """GET /cases — list every case (lightweight payload)."""
    rows = Case.query.order_by(Case.id.desc()).all()
    return jsonify({"ok": True, "count": len(rows), "cases": [c.to_dict() for c in rows]})


@cases_bp.get("/<int:case_id>")
def get_case(case_id: int):
    """GET /cases/<id> — single case with documents and notes embedded."""
    case = db.session.get(Case, case_id)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404
    return jsonify({"ok": True, "case": case.to_dict(include_relations=True)})


@cases_bp.post("/")
@login_required_api
def create_case():
    """POST /cases — create a new case from a JSON body."""
    payload = request.get_json(silent=True) or {}
    firm_id = session['firm_id']

    required = ("title", "client_name", "case_type")
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return jsonify({
            "ok": False,
            "error": f"Missing required field(s): {', '.join(missing)}",
        }), 400

    sections = payload.get("sections", [])
    if isinstance(sections, list):
        sections_str = ", ".join(str(s).strip() for s in sections if str(s).strip())
    else:
        sections_str = str(sections)

    case = Case(
        firm_id      = firm_id,
        title        = payload["title"],
        client_name  = payload["client_name"],
        case_type    = payload["case_type"],
        court        = payload.get("court"),
        sections     = sections_str,
        hearing_date = _parse_date(payload.get("hearing_date")),
        status       = payload.get("status", "Active"),
        facts        = payload.get("facts"),
    )
    db.session.add(case)
    db.session.commit()

    # Trigger background analysis of facts
    if case.facts:
        app_instance = current_app._get_current_object()
        thread = threading.Thread(
            target=process_case_background, 
            args=(app_instance, case.id, case.facts)
        )
        thread.start()

    return jsonify({"ok": True, "case": case.to_dict()}), 201


@cases_bp.put("/<int:case_id>")
@login_required_api
def update_case(case_id: int):
    """PUT /cases/<id> — partial update; currently supports status & hearing_date."""
    case = db.session.query(Case).filter_by(id=case_id, firm_id=session['firm_id']).first()
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404

    payload = request.get_json(silent=True) or {}

    if "status" in payload:
        new_status = str(payload["status"]).strip()
        if new_status not in {"Active", "Hearing", "Closed"}:
            return jsonify({
                "ok": False,
                "error": "status must be one of: Active, Hearing, Closed",
            }), 400
        case.status = new_status

    if "hearing_date" in payload:
        case.hearing_date = _parse_date(payload["hearing_date"])

    # Optional convenience fields — useful for the UI's "edit case" dialog later.
    for fld in ("title", "client_name", "case_type", "court", "facts"):
        if fld in payload and payload[fld] is not None:
            setattr(case, fld, payload[fld])

    if "sections" in payload:
        secs = payload["sections"]
        case.sections = ", ".join(secs) if isinstance(secs, list) else str(secs)

    db.session.commit()
    return jsonify({"ok": True, "case": case.to_dict()})


@cases_bp.delete("/<int:case_id>")
@login_required_api
def delete_case(case_id: int):
    """DELETE /cases/<id> — cascade removes documents, notes, messages."""
    case = db.session.query(Case).filter_by(id=case_id, firm_id=session['firm_id']).first()
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404
    db.session.delete(case)
    db.session.commit()
    return jsonify({"ok": True, "deleted": case_id})
