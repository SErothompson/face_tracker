import io
from flask import Blueprint, abort, render_template, send_file
from app.models import PhotoSession
from app.blueprints.reports.generators import ReportGenerator
from app.utils import can_access_session

reports_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/reports",
    template_folder="templates"
)


@reports_bp.route("/session/<int:session_id>/html", methods=["GET"])
def view_html_report(session_id):
    """Display HTML report (printable in browser)."""
    session = PhotoSession.query.get_or_404(session_id)
    if not can_access_session(session):
        abort(403)

    # Gather all data
    session_data = ReportGenerator.gather_session_data(session_id)

    # Render HTML template
    return render_template(
        "reports/report.html",
        **session_data
    )


@reports_bp.route("/session/<int:session_id>/pdf", methods=["GET"])
def download_pdf_report(session_id):
    """Generate and download PDF report."""
    session = PhotoSession.query.get_or_404(session_id)
    if not can_access_session(session):
        abort(403)

    # Gather all data
    session_data = ReportGenerator.gather_session_data(session_id)

    # Generate PDF bytes
    pdf_bytes = ReportGenerator.generate_pdf(session_data)

    # Return as downloadable file
    filename = f"skin-report_{session.id}_{session.session_date.isoformat()}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )
