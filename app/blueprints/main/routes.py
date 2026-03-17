from flask import Blueprint, render_template

from app.models import PhotoSession

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    recent_sessions = (
        PhotoSession.query.order_by(PhotoSession.session_date.desc())
        .limit(5)
        .all()
    )
    return render_template("dashboard.html", recent_sessions=recent_sessions)
