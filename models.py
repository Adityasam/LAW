# models.py
# ---------------------------------------------------------------------------
# SQLAlchemy ORM models for LegalMind.
# Relationships use lazy="select" (the default) so that related objects are
# loaded on first access, which is the simplest and most predictable strategy
# for a small Flask app.
# ---------------------------------------------------------------------------
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Firm(db.Model):
    """A Law Firm or independent practitioner account."""
    __tablename__ = "firms"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    username      = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email         = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    cases   = db.relationship("Case", backref="firm", lazy="select", cascade="all, delete-orphan")
    settings = db.relationship("Setting", backref="firm", uselist=False, lazy="select", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "email": self.email,
        }

class Case(db.Model):
    """A litigation matter handled by a firm."""

    __tablename__ = "cases"

    id           = db.Column(db.Integer, primary_key=True)
    firm_id      = db.Column(db.Integer, db.ForeignKey("firms.id"), nullable=False, index=True)
    title        = db.Column(db.String(200), nullable=False)
    client_name  = db.Column(db.String(120), nullable=False)
    case_type    = db.Column(db.String(40), nullable=False)   # Criminal / Civil
    court        = db.Column(db.String(200))
    # Comma-separated list of BNS / IPC / Act references.
    sections     = db.Column(db.String(400), default="")
    hearing_date = db.Column(db.Date)
    status       = db.Column(db.String(20), default="Active", nullable=False)  # Active / Hearing / Closed
    facts        = db.Column(db.Text)
    ai_summary   = db.Column(db.Text, default="")                    # Gemini-generated summary of facts
    analysis_status = db.Column(db.String(20), default="pending")      # pending, processing, completed, failed
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
    judgments = db.relationship(
        "Judgment", backref="case", lazy="select", cascade="all, delete-orphan"
    )
    hearings = db.relationship(
        "CaseHearing", backref="case", lazy="select", cascade="all, delete-orphan", order_by="CaseHearing.hearing_date.desc()"
    )

    def to_dict(self, include_relations: bool = False) -> dict:
        data = {
            "id": self.id,
            "firm_id": self.firm_id,
            "title": self.title,
            "client_name": self.client_name,
            "case_type": self.case_type,
            "court": self.court,
            "sections": [s.strip() for s in (self.sections or "").split(",") if s.strip()],
            "hearing_date": self.hearing_date.isoformat() if self.hearing_date else None,
            "status": self.status,
            "facts": self.facts,
            "ai_summary": self.ai_summary,
            "analysis_status": self.analysis_status,
            "created_at": self.created_at.isoformat(),
        }
        if include_relations:
            data["documents"] = [d.to_dict() for d in self.documents]
            data["notes"]     = [n.to_dict() for n in self.notes]
            data["judgments"] = [j.to_dict() for j in self.judgments]
            data["hearings"]  = [h.to_dict() for h in self.hearings]
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
    status         = db.Column(db.String(20), default="completed")     # processing, completed, failed
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
            "status": self.status,
            "uploaded_at": self.uploaded_at.isoformat(),
        }


class CaseHearing(db.Model):
    """A record of a specific court hearing for a case."""

    __tablename__ = "hearings"

    id           = db.Column(db.Integer, primary_key=True)
    case_id      = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    hearing_date = db.Column(db.Date, nullable=False)
    notes        = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "date": self.hearing_date.isoformat(),
            "notes": self.notes or "",
            "created_at": self.created_at.isoformat(),
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
    role       = db.Column(db.String(20), nullable=False)  # 'user' | 'ai'
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


class Setting(db.Model):
    """Global and Firm-specific settings for the LegalMind workspace."""

    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    firm_id = db.Column(db.Integer, db.ForeignKey("firms.id"), unique=True, nullable=False)

    # Firm Details
    firm_name = db.Column(db.String(200))
    lawyer_name = db.Column(db.String(200))
    address = db.Column(db.Text)
    default_court = db.Column(db.String(200))

    # AI Options
    ai_language = db.Column(db.String(20), default="English") # English / Hindi
    include_ipc_equivalent = db.Column(db.Boolean, default=True)
    max_judgments = db.Column(db.Integer, default=3) # 3, 6, 9

    def to_dict(self) -> dict:
        return {
            "firm_name": self.firm_name or "",
            "lawyer_name": self.lawyer_name or "",
            "address": self.address or "",
            "default_court": self.default_court or "",
            "ai_language": self.ai_language,
            "include_ipc_equivalent": self.include_ipc_equivalent,
            "max_judgments": self.max_judgments
        }


def get_firm_settings(firm_id: int) -> Setting:
    """Fetch or create default settings for a specific firm."""
    s = Setting.query.filter_by(firm_id=firm_id).first()
    if not s:
        s = Setting(firm_id=firm_id)
        db.session.add(s)
        db.session.commit()
    return s


class Judgment(db.Model):
    """A relevant judgment/case-law fetched for a case."""

    __tablename__ = "judgments"

    id         = db.Column(db.Integer, primary_key=True)
    case_id    = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    title      = db.Column(db.String(500), nullable=False)
    court      = db.Column(db.String(200))
    date       = db.Column(db.String(50))
    url        = db.Column(db.String(500))
    doc_id     = db.Column(db.String(100))
    summary    = db.Column(db.Text)      # ~300 word summary
    full_html  = db.Column(db.Text)      # Full judgment content
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "title": self.title,
            "court": self.court,
            "date": self.date,
            "url": self.url,
            "doc_id": self.doc_id,
            "summary": self.summary,
            "uploaded_at": self.created_at.isoformat(),
        }
