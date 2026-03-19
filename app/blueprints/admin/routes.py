from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.blueprints.auth.decorators import role_required
from app.extensions import db
from app.models import (
    ClinicalNote,
    PatientAssignment,
    PhotoSession,
    RegimenEntry,
    User,
)

admin_bp = Blueprint(
    "admin", __name__, url_prefix="/admin", template_folder="templates"
)


@admin_bp.route("/")
@role_required("admin", "developer")
def admin_dashboard():
    """Admin dashboard with system stats."""
    total_users = User.query.count()
    total_sessions = PhotoSession.query.count()
    total_regimen = RegimenEntry.query.count()
    role_counts = {}
    for role in User.VALID_ROLES:
        role_counts[role] = User.query.filter_by(role=role).count()
    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_sessions=total_sessions,
        total_regimen=total_regimen,
        role_counts=role_counts,
    )


@admin_bp.route("/users")
@role_required("admin", "developer")
def list_users():
    """List all users."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/<int:user_id>")
@role_required("admin", "developer")
def user_detail(user_id):
    """View/edit a single user."""
    user = User.query.get_or_404(user_id)
    assignments = PatientAssignment.query.filter(
        (PatientAssignment.dermatologist_id == user_id)
        | (PatientAssignment.patient_id == user_id)
    ).all()
    return render_template(
        "admin/user_detail.html",
        user=user,
        assignments=assignments,
        valid_roles=User.VALID_ROLES,
    )


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def change_role(user_id):
    """Change a user's role."""
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role", "").strip()
    if new_role not in User.VALID_ROLES:
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    if user.id == current_user.id:
        flash("You cannot change your own role.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    user.role = new_role
    db.session.commit()
    flash(f"Role for '{user.username}' changed to '{new_role}'.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@role_required("admin")
def toggle_active(user_id):
    """Enable or disable a user account."""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot disable your own account.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    user.is_active_flag = not user.is_active_flag
    db.session.commit()
    status = "enabled" if user.is_active_flag else "disabled"
    flash(f"Account '{user.username}' {status}.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/assignments")
@role_required("admin", "developer")
def list_assignments():
    """List patient-dermatologist assignments."""
    assignments = PatientAssignment.query.order_by(
        PatientAssignment.assigned_at.desc()
    ).all()
    dermatologists = User.query.filter_by(role="dermatologist").all()
    patients = User.query.filter(User.role.in_(("user", "viewer"))).all()
    return render_template(
        "admin/assignments.html",
        assignments=assignments,
        dermatologists=dermatologists,
        patients=patients,
    )


@admin_bp.route("/assignments", methods=["POST"])
@role_required("admin")
def create_assignment():
    """Create a new patient-dermatologist assignment."""
    derm_id = request.form.get("dermatologist_id", type=int)
    patient_id = request.form.get("patient_id", type=int)
    notes = request.form.get("notes", "").strip()

    if not derm_id or not patient_id:
        flash("Both dermatologist and patient are required.", "danger")
        return redirect(url_for("admin.list_assignments"))

    existing = PatientAssignment.query.filter_by(
        dermatologist_id=derm_id, patient_id=patient_id
    ).first()
    if existing:
        flash("This assignment already exists.", "warning")
        return redirect(url_for("admin.list_assignments"))

    assignment = PatientAssignment(
        dermatologist_id=derm_id, patient_id=patient_id, notes=notes
    )
    db.session.add(assignment)
    db.session.commit()
    flash("Assignment created.", "success")
    return redirect(url_for("admin.list_assignments"))


@admin_bp.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
@role_required("admin")
def delete_assignment(assignment_id):
    """Remove a patient-dermatologist assignment."""
    assignment = PatientAssignment.query.get_or_404(assignment_id)
    db.session.delete(assignment)
    db.session.commit()
    flash("Assignment removed.", "success")
    return redirect(url_for("admin.list_assignments"))


@admin_bp.route("/debug")
@role_required("developer")
def debug_info():
    """Display debug information for developers."""
    from flask import current_app

    config_items = {}
    for key in sorted(current_app.config):
        val = current_app.config[key]
        if "SECRET" in key or "PASSWORD" in key:
            config_items[key] = "********"
        else:
            config_items[key] = str(val)

    db_stats = {
        "users": User.query.count(),
        "sessions": PhotoSession.query.count(),
        "regimen_entries": RegimenEntry.query.count(),
        "clinical_notes": ClinicalNote.query.count(),
        "assignments": PatientAssignment.query.count(),
    }

    return render_template(
        "admin/debug.html",
        config_items=config_items,
        db_stats=db_stats,
    )
