# routes/documents.py
# ---------------------------------------------------------------------------
# Blueprint for uploading and deleting case documents.
# Files are written to the UPLOAD_FOLDER defined in config.py.
# ---------------------------------------------------------------------------
import os
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from models import Document, db

documents_bp = Blueprint("documents", __name__)


def _allowed(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", set())


@documents_bp.post("/cases/<int:case_id>/documents")
def upload_document(case_id: int):
    """
    POST /cases/<id>/documents
        multipart/form-data with a `file` field.
        Saves the upload under UPLOAD_FOLDER and records metadata.
    """
    from models import Case  # local import to avoid circulars
    case = db.session.get(Case, case_id)
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file part in request"}), 400

    f = request.files["file"]
    if not f or f.filename == "":
        return jsonify({"ok": False, "error": "No file selected"}), 400
    if not _allowed(f.filename):
        return jsonify({
            "ok": False,
            "error": "File type not allowed",
        }), 400

    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    original = secure_filename(f.filename)
    ext = original.rsplit(".", 1)[1].lower() if "." in original else ""
    stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    target = upload_dir / stored
    f.save(target)

    size = target.stat().st_size

    doc = Document(
        case_id        = case_id,
        filename       = stored,
        original_name  = original,
        file_type      = ext,
        file_size      = size,
        extracted_text = "",  # OCR / pdfplumber pipeline to be added later
    )
    db.session.add(doc)
    db.session.commit()

    # Return the full list of documents for this case to keep UI in sync
    docs = Document.query.filter_by(case_id=case_id).all()
    return jsonify({
        "ok": True, 
        "document": doc.to_dict(),
        "documents": [d.to_dict() for d in docs]
    }), 201


@documents_bp.delete("/documents/<int:doc_id>")
def delete_document(doc_id: int):
    """DELETE /documents/<id> — removes the DB row and the file on disk."""
    doc = db.session.query(Document).get(doc_id)
    if not doc:
        return jsonify({"ok": False, "error": "Document not found"}), 404

    case_id = doc.case_id
    filename = doc.filename
    
    try:
        db.session.delete(doc)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": f"Database error: {str(e)}"}), 500

    # Try to delete the file after DB commit
    try:
        upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
        target = upload_dir / filename
        if target.exists():
            target.unlink()
    except Exception as e:
        current_app.logger.warning("Could not delete file %s: %s", filename, e)

    # Return updated document list
    docs = db.session.query(Document).filter_by(case_id=case_id).all()
    return jsonify({
        "ok": True, 
        "deleted": doc_id,
        "documents": [d.to_dict() for d in docs]
    })
