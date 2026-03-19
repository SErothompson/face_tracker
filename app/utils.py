from flask_login import current_user

from app.extensions import db
from app.models import PatientAssignment, PhotoSession, RegimenEntry


def _assigned_patient_ids():
    """Get patient IDs assigned to the current dermatologist."""
    return db.session.query(PatientAssignment.patient_id).filter_by(
        dermatologist_id=current_user.id
    ).subquery()


def user_sessions_query():
    """Return a base query for PhotoSession scoped to the current user's permissions."""
    if current_user.has_role("admin", "developer"):
        return PhotoSession.query
    if current_user.has_role("dermatologist"):
        return PhotoSession.query.filter(
            PhotoSession.user_id.in_(_assigned_patient_ids())
        )
    return PhotoSession.query.filter_by(user_id=current_user.id)


def user_regimen_query():
    """Return a base query for RegimenEntry scoped to the current user."""
    if current_user.has_role("admin", "developer"):
        return RegimenEntry.query
    return RegimenEntry.query.filter_by(user_id=current_user.id)


def can_access_session(session):
    """Check if the current user can access a given PhotoSession."""
    if current_user.has_role("admin", "developer"):
        return True
    if current_user.has_role("dermatologist"):
        assigned = PatientAssignment.query.filter_by(
            dermatologist_id=current_user.id,
            patient_id=session.user_id,
        ).first()
        return assigned is not None
    return session.user_id == current_user.id
