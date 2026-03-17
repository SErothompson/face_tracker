from datetime import date, datetime, timezone

from .extensions import db


class PhotoSession(db.Model):
    __tablename__ = "photo_session"

    id = db.Column(db.Integer, primary_key=True)
    session_date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
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
    product_name = db.Column(db.String(200), nullable=False)
    product_type = db.Column(db.String(50), nullable=False)
    frequency = db.Column(db.String(50), nullable=False)
    time_of_day = db.Column(db.String(20), nullable=False)
    started_on = db.Column(db.Date, nullable=True)
    ended_on = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, default="")


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
