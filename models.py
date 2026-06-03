# models.py
# ---------------------------------------------------------------------------
# SQLAlchemy ORM models for VakilAI.
# Relationships use lazy="select" (the default) so that related objects are
# loaded on first access, which is the simplest and most predictable strategy
# for a small Flask app.
# ---------------------------------------------------------------------------
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Lawyer(db.Model):
    """A practising advocate. The owner/assignee of one or more cases."""

    __tablename__ = "lawyers"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    chamber       = db.Column(db.String(200))
    avatar_initials = db.Column(db.String(8))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # A lawyer can have many cases.
    cases = db.relationship(
        "Case",
        backref="lawyer",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "chamber": self.chamber,
            "avatar_initials": self.avatar_initials,
        }


class Case(db.Model):
    """A litigation matter handled by a lawyer."""

    __tablename__ = "cases"

    id           = db.Column(db.Integer, primary_key=True)
    lawyer_id    = db.Column(db.Integer, db.ForeignKey("lawyers.id"), nullable=False, index=True)
    title        = db.Column(db.String(200), nullable=False)
    client_name  = db.Column(db.String(120), nullable=False)
    case_type    = db.Column(db.String(40), nullable=False)   # Criminal / Civil
    court        = db.Column(db.String(200))
    # Comma-separated list of BNS / IPC / Act references.
    sections     = db.Column(db.String(400), default="")
    hearing_date = db.Column(db.Date)
    status       = db.Column(db.String(20), default="Active", nullable=False)  # Active / Hearing / Closed
    facts        = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    documents = db.relationship(
        "Document", backref="case", lazy="select", cascade="all, delete-orphan"
    )
    notes = db.relationship(
        "Note", backref="case", lazy="select", cascade="all, delete-orphan"
    )
    messages = db.relationship(
        "ChatMessage", backref="case", lazy="select", cascade="all, delete-orphan"
    )

    def to_dict(self, include_relations: bool = False) -> dict:
        data = {
            "id": self.id,
            "lawyer_id": self.lawyer_id,
            "title": self.title,
            "client_name": self.client_name,
            "case_type": self.case_type,
            "court": self.court,
            "sections": [s.strip() for s in (self.sections or "").split(",") if s.strip()],
            "hearing_date": self.hearing_date.isoformat() if self.hearing_date else None,
            "status": self.status,
            "facts": self.facts,
            "created_at": self.created_at.isoformat(),
        }
        if include_relations:
            data["documents"] = [d.to_dict() for d in self.documents]
            data["notes"]     = [n.to_dict() for n in self.notes]
        return data


class Document(db.Model):
    """A file uploaded against a case (FIR, charge sheet, etc.)."""

    __tablename__ = "documents"

    id             = db.Column(db.Integer, primary_key=True)
    case_id        = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    filename       = db.Column(db.String(255), nullable=False)         # on-disk filename
    original_name  = db.Column(db.String(255), nullable=False)         # as uploaded
    file_type      = db.Column(db.String(20))                          # pdf, docx, jpg ...
    file_size      = db.Column(db.Integer, default=0)                   # bytes
    extracted_text = db.Column(db.Text, default="")                    # OCR / pdfplumber output
    summary        = db.Column(db.Text, default="")                    # Gemini-generated summary
    uploaded_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "summary": self.summary,
            "uploaded_at": self.uploaded_at.isoformat(),
        }


class Note(db.Model):
    """Free-text or voice memo attached to a case."""

    __tablename__ = "notes"

    id         = db.Column(db.Integer, primary_key=True)
    case_id    = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    content    = db.Column(db.Text, nullable=False)
    note_type  = db.Column(db.String(20), default="text", nullable=False)  # text / voice
    title      = db.Column(db.String(200))
    duration   = db.Column(db.String(10))   # mm:ss for voice notes
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "title": self.title,
            "content": self.content,
            "note_type": self.note_type,
            "duration": self.duration,
            "created_at": self.created_at.isoformat(),
        }


class ChatMessage(db.Model):
    """A single message in the per-case AI chat thread."""

    __tablename__ = "chat_messages"

    id         = db.Column(db.Integer, primary_key=True)
    case_id    = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    role       = db.Column(db.String(20), nullable=False)  # 'lawyer' | 'ai'
    content    = db.Column(db.Text, nullable=False)
    citations  = db.Column(db.Text, default="")            # JSON-encoded list of citations
    sections   = db.Column(db.Text, default="")            # JSON-encoded list of section tags
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        import json
        try:
            citations = json.loads(self.citations) if self.citations else []
        except (ValueError, TypeError):
            citations = []
        try:
            sections = json.loads(self.sections) if self.sections else []
        except (ValueError, TypeError):
            sections = []
        return {
            "id": self.id,
            "case_id": self.case_id,
            "role": self.role,
            "content": self.content,
            "citations": citations,
            "sections": sections,
            "created_at": self.created_at.isoformat(),
        }
