# routes/cases.py
# ---------------------------------------------------------------------------
# Blueprint exposing CRUD-ish operations on Case rows.
# All endpoints return JSON. No authentication for now.
# ---------------------------------------------------------------------------
from datetime import datetime
from typing import Optional
from flask import Blueprint, jsonify, request

from models import Case, db

cases_bp = Blueprint("cases", __name__, url_prefix="/cases")


def _parse_date(s: Optional[str]):
    if not s:
        return None
    try:
        # Accepts "YYYY-MM-DD" or full ISO timestamps.
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


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
def create_case():
    """POST /cases — create a new case from a JSON body."""
    payload = request.get_json(silent=True) or {}

    required = ("lawyer_id", "title", "client_name", "case_type")
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
        lawyer_id    = int(payload["lawyer_id"]),
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
    return jsonify({"ok": True, "case": case.to_dict()}), 201


@cases_bp.put("/<int:case_id>")
def update_case(case_id: int):
    """PUT /cases/<id> — partial update; currently supports status & hearing_date."""
    case = db.session.get(Case, case_id)
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
def delete_case(case_id: int):
    """DELETE /cases/<id> — cascade removes documents, notes, messages."""
    case = db.session.get(Case, case_id)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404
    db.session.delete(case)
    db.session.commit()
    return jsonify({"ok": True, "deleted": case_id})
