from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active_flag = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Account lockout fields
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_failed_login = db.Column(db.DateTime, nullable=True)

    # TOTP two-factor authentication fields
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False, nullable=False)
    recovery_codes_hash = db.Column(db.Text, nullable=True)

    VALID_ROLES = ("user", "viewer", "dermatologist", "admin", "developer")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_flag

    def has_role(self, *roles):
        return self.role in roles


class PhotoSession(db.Model):
    __tablename__ = "photo_session"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )
    session_date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship(
        "User", backref=db.backref("sessions", lazy="dynamic")
    )
    photos = db.relationship(
        "Photo", backref="session", cascade="all, delete-orphan"
    )
    analysis_results = db.relationship(
        "AnalysisResult", backref="session", cascade="all, delete-orphan"
    )
    conditions = db.relationship(
        "SkinCondition", backref="session", cascade="all, delete-orphan"
    )
    regimen_logs = db.relationship(
        "RegimenLog", backref="session", cascade="all, delete-orphan"
    )


class Photo(db.Model):
    __tablename__ = "photo"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("photo_session.id"), nullable=False
    )
    angle = db.Column(db.String(20), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    uploaded_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.UniqueConstraint("session_id", "angle", name="uq_session_angle"),
    )


class AnalysisResult(db.Model):
    __tablename__ = "analysis_result"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("photo_session.id"), nullable=False
    )
    condition_name = db.Column(db.String(50), nullable=False)
    region = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Float, nullable=False)
    details_json = db.Column(db.Text, default="{}")
    computed_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )


class SkinCondition(db.Model):
    __tablename__ = "skin_condition"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("photo_session.id"), nullable=False
    )
    condition_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, default="")
    search_results_json = db.Column(db.Text, default="[]")


class RegimenEntry(db.Model):
    __tablename__ = "regimen_entry"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )
    product_name = db.Column(db.String(200), nullable=False)
    product_type = db.Column(db.String(50), nullable=False)
    frequency = db.Column(db.String(50), nullable=False)
    time_of_day = db.Column(db.String(20), nullable=False)
    started_on = db.Column(db.Date, nullable=True)
    ended_on = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, default="")

    user = db.relationship(
        "User", backref=db.backref("regimen_entries", lazy="dynamic")
    )


class RegimenLog(db.Model):
    __tablename__ = "regimen_log"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("photo_session.id"), nullable=False
    )
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    regimen_snapshot = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, default="")


class ComparisonResult(db.Model):
    __tablename__ = "comparison_result"

    id = db.Column(db.Integer, primary_key=True)
    session_a_id = db.Column(
        db.Integer, db.ForeignKey("photo_session.id"), nullable=False
    )
    session_b_id = db.Column(
        db.Integer, db.ForeignKey("photo_session.id"), nullable=False
    )
    angle = db.Column(db.String(20), nullable=False)
    ssim_score = db.Column(db.Float, nullable=True)
    changes_summary = db.Column(db.Text, default="")
    computed_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    session_a = db.relationship(
        "PhotoSession", foreign_keys=[session_a_id]
    )
    session_b = db.relationship(
        "PhotoSession", foreign_keys=[session_b_id]
    )


class PatientAssignment(db.Model):
    __tablename__ = "patient_assignment"

    id = db.Column(db.Integer, primary_key=True)
    dermatologist_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    patient_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    assigned_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    notes = db.Column(db.Text, default="")

    dermatologist = db.relationship(
        "User",
        foreign_keys=[dermatologist_id],
        backref=db.backref("assigned_patients", lazy="dynamic"),
    )
    patient = db.relationship(
        "User",
        foreign_keys=[patient_id],
        backref=db.backref("assigned_dermatologists", lazy="dynamic"),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "dermatologist_id", "patient_id", name="uq_derm_patient"
        ),
    )


class ClinicalNote(db.Model):
    __tablename__ = "clinical_note"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("photo_session.id"), nullable=False
    )
    author_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime, onupdate=lambda: datetime.now(timezone.utc)
    )

    session = db.relationship(
        "PhotoSession",
        backref=db.backref("clinical_notes", lazy="dynamic"),
    )
    author = db.relationship(
        "User",
        backref=db.backref("clinical_notes", lazy="dynamic"),
    )


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    details = db.Column(db.Text, default="")

    user = db.relationship("User", backref=db.backref("audit_logs", lazy="dynamic"))
