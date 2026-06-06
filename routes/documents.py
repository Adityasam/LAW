# routes/documents.py
# ---------------------------------------------------------------------------
# Blueprint for uploading and deleting case documents.
# Files are written to the UPLOAD_FOLDER defined in config.py.
# ---------------------------------------------------------------------------
import os
import uuid
import threading
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory, session
from werkzeug.utils import secure_filename

from models import Document, db
from services.doc_processor import process_document
from chunker import add_to_vector_db

documents_bp = Blueprint("documents", __name__)


def login_required_api(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'firm_id' not in session:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


def _allowed(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", set())


def process_document_background(app_instance, doc_id, file_path, original_name):
    """Background task to process document via Gemini and update DB/Vector DB."""
    with app_instance.app_context():
        try:
            # 1. Gemini processing
            extracted_text, summary = process_document(file_path)
            
            # 2. Update DB
            doc = db.session.query(Document).get(doc_id)
            if doc:
                doc.extracted_text = extracted_text
                doc.summary = summary
                doc.status = "completed"
                db.session.commit()

                # 3. Add to vector DB
                if extracted_text:
                    add_to_vector_db(
                        doc.case_id, 
                        extracted_text, 
                        {
                            "title": f"Document: {original_name}",
                            "type": "uploaded_document",
                            "filename": doc.filename,
                            "original_name": original_name
                        }
                    )
        except Exception as e:
            app_instance.logger.error("Background processing error for doc %s: %s", doc_id, e)
            try:
                doc = db.session.query(Document).get(doc_id)
                if doc:
                    doc.status = "failed"
                    doc.summary = "AI extraction failed."
                    db.session.commit()
            except:
                pass


@documents_bp.post("/cases/<int:case_id>/documents")
@login_required_api
def upload_document(case_id: int):
    """
    POST /cases/<id>/documents
        multipart/form-data with one or more `file` fields.
        Saves the uploads under UPLOAD_FOLDER and records metadata.
    """
    from models import Case  # local import to avoid circulars
    case = db.session.query(Case).filter_by(id=case_id, firm_id=session['firm_id']).first()
    if not case:
        return jsonify({"ok": False, "error": "Case not found"}), 404

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file part in request"}), 400

    files = request.files.getlist("file")
    uploaded_docs = []

    for f in files:
        if not f or f.filename == "":
            continue
        if not _allowed(f.filename):
            continue

        upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
        upload_dir.mkdir(parents=True, exist_ok=True)

        original = secure_filename(f.filename)
        ext = original.rsplit(".", 1)[1].lower() if "." in original else ""
        stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
        target = upload_dir / stored
        f.save(target)

        size = target.stat().st_size

        # 1. Create document record immediately (status: processing)
        doc = Document(
            case_id        = case_id,
            filename       = stored,
            original_name  = original,
            file_type      = ext,
            file_size      = size,
            extracted_text = "",
            summary        = "",
            status         = "processing"
        )
        db.session.add(doc)
        db.session.commit()

        # 2. Trigger background processing (Gemini + Vector DB)
        app_instance = current_app._get_current_object()
        thread = threading.Thread(
            target=process_document_background, 
            args=(app_instance, doc.id, str(target), original)
        )
        thread.start()
        uploaded_docs.append(doc.to_dict())

    # Return updated document list
    docs = Document.query.filter_by(case_id=case_id).all()
    return jsonify({
        "ok": True, 
        "documents": [d.to_dict() for d in docs]
    }), 201


@documents_bp.get("/uploads/<filename>")
def serve_upload(filename: str):
    """GET /uploads/<filename> — serves the actual file from disk."""
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@documents_bp.delete("/documents/<int:doc_id>")
@login_required_api
def delete_document(doc_id: int):
    """DELETE /documents/<id> — removes from disk and DB."""
    from models import Case  # local import to avoid circulars
    doc = db.session.query(Document).join(Case).filter(Document.id == doc_id, Case.firm_id == session['firm_id']).first()
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
