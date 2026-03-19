"""Tests for role-based access control and data isolation."""

from datetime import date

from app.models import (
    ClinicalNote,
    PatientAssignment,
    PhotoSession,
    RegimenEntry,
    User,
)


class TestLoginRequired:
    """All routes redirect to login when unauthenticated."""

    def test_dashboard_requires_login(self, unauthenticated_client, db):
        # Need a user so first-run doesn't redirect to setup
        u = User(username="seed", role="admin")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()

        response = unauthenticated_client.get("/")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["Location"]

    def test_sessions_requires_login(self, unauthenticated_client, db):
        u = User(username="seed2", role="admin")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()

        response = unauthenticated_client.get("/sessions/")
        assert response.status_code == 302

    def test_api_returns_401_unauthenticated(self, unauthenticated_client, db):
        u = User(username="seed3", role="admin")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()

        response = unauthenticated_client.get("/api/trends")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data


class TestViewerRestrictions:
    """Viewers can view but not modify data."""

    def test_viewer_can_see_dashboard(self, viewer_client):
        response = viewer_client.get("/")
        assert response.status_code == 200

    def test_viewer_can_see_sessions_list(self, viewer_client):
        response = viewer_client.get("/sessions/")
        assert response.status_code == 200

    def test_viewer_cannot_upload(self, viewer_client):
        response = viewer_client.get("/sessions/upload")
        assert response.status_code == 403

    def test_viewer_cannot_delete_session(self, viewer_client, db):
        # Create a session owned by the viewer
        viewer = User.query.filter_by(username="viewer_test").first()
        session = PhotoSession(session_date=date.today(), user_id=viewer.id)
        db.session.add(session)
        db.session.commit()

        response = viewer_client.post(f"/sessions/{session.id}/delete")
        assert response.status_code == 403

    def test_viewer_cannot_add_regimen(self, viewer_client):
        response = viewer_client.get("/regimen/add")
        assert response.status_code == 403


class TestUserDataIsolation:
    """Users can only see their own data."""

    def test_user_sees_only_own_sessions(self, user_client, db):
        regular = User.query.filter_by(username="regular_test").first()
        other = User(username="other_user", role="user")
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()

        own = PhotoSession(session_date=date.today(), user_id=regular.id)
        foreign = PhotoSession(session_date=date.today(), user_id=other.id, notes="foreign-session")
        db.session.add_all([own, foreign])
        db.session.commit()

        response = user_client.get("/sessions/")
        assert response.status_code == 200
        assert b"foreign-session" not in response.data

    def test_user_cannot_access_others_session(self, user_client, db):
        other = User(username="other2", role="user")
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()

        session = PhotoSession(session_date=date.today(), user_id=other.id)
        db.session.add(session)
        db.session.commit()

        response = user_client.get(f"/sessions/{session.id}")
        assert response.status_code == 403

    def test_user_sees_only_own_regimen(self, user_client, db):
        regular = User.query.filter_by(username="regular_test").first()
        other = User(username="other3", role="user")
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()

        own_entry = RegimenEntry(
            product_name="My Product",
            product_type="cleanser",
            frequency="daily",
            time_of_day="AM",
            started_on=date.today(),
            user_id=regular.id,
        )
        foreign_entry = RegimenEntry(
            product_name="Foreign Product",
            product_type="cleanser",
            frequency="daily",
            time_of_day="AM",
            started_on=date.today(),
            user_id=other.id,
        )
        db.session.add_all([own_entry, foreign_entry])
        db.session.commit()

        response = user_client.get("/regimen/")
        assert response.status_code == 200
        assert b"My Product" in response.data
        assert b"Foreign Product" not in response.data


class TestAdminAccess:
    """Admins can see all data and manage users."""

    def test_admin_sees_all_sessions(self, admin_client, db):
        user1 = User(username="u1", role="user")
        user1.set_password("password123")
        user2 = User(username="u2", role="user")
        user2.set_password("password123")
        db.session.add_all([user1, user2])
        db.session.commit()

        s1 = PhotoSession(session_date=date.today(), user_id=user1.id, notes="sess-u1")
        s2 = PhotoSession(session_date=date.today(), user_id=user2.id, notes="sess-u2")
        db.session.add_all([s1, s2])
        db.session.commit()

        response = admin_client.get("/sessions/")
        assert response.status_code == 200
        assert b"sess-u1" in response.data
        assert b"sess-u2" in response.data

    def test_admin_can_access_admin_panel(self, admin_client):
        response = admin_client.get("/admin/")
        assert response.status_code == 200

    def test_admin_can_list_users(self, admin_client):
        response = admin_client.get("/admin/users")
        assert response.status_code == 200

    def test_admin_can_change_role(self, admin_client, db):
        target = User(username="target", role="user")
        target.set_password("password123")
        db.session.add(target)
        db.session.commit()

        response = admin_client.post(
            f"/admin/users/{target.id}/role",
            data={"role": "viewer"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        db.session.refresh(target)
        assert target.role == "viewer"

    def test_admin_can_toggle_active(self, admin_client, db):
        target = User(username="target2", role="user")
        target.set_password("password123")
        db.session.add(target)
        db.session.commit()

        response = admin_client.post(
            f"/admin/users/{target.id}/toggle-active",
            follow_redirects=True,
        )
        assert response.status_code == 200
        db.session.refresh(target)
        assert target.is_active_flag is False


class TestDermatologistAccess:
    """Dermatologists see only assigned patients."""

    def test_derm_sees_assigned_patient_sessions(self, derm_client, db):
        derm = User.query.filter_by(username="derm_test").first()
        patient = User(username="patient1", role="user")
        patient.set_password("password123")
        db.session.add(patient)
        db.session.commit()

        assignment = PatientAssignment(
            dermatologist_id=derm.id, patient_id=patient.id
        )
        db.session.add(assignment)
        session = PhotoSession(
            session_date=date.today(), user_id=patient.id, notes="assigned-sess"
        )
        db.session.add(session)
        db.session.commit()

        response = derm_client.get("/sessions/")
        assert response.status_code == 200
        assert b"assigned-sess" in response.data

    def test_derm_cannot_see_unassigned_patient(self, derm_client, db):
        unassigned = User(username="unassigned_pt", role="user")
        unassigned.set_password("password123")
        db.session.add(unassigned)
        db.session.commit()

        session = PhotoSession(
            session_date=date.today(), user_id=unassigned.id, notes="hidden-sess"
        )
        db.session.add(session)
        db.session.commit()

        response = derm_client.get("/sessions/")
        assert b"hidden-sess" not in response.data

    def test_derm_can_add_clinical_note(self, derm_client, db):
        derm = User.query.filter_by(username="derm_test").first()
        patient = User(username="patient2", role="user")
        patient.set_password("password123")
        db.session.add(patient)
        db.session.commit()

        assignment = PatientAssignment(
            dermatologist_id=derm.id, patient_id=patient.id
        )
        session = PhotoSession(session_date=date.today(), user_id=patient.id)
        db.session.add_all([assignment, session])
        db.session.commit()

        response = derm_client.post(
            f"/sessions/{session.id}/clinical-note",
            data={"content": "Recommend moisturizer."},
            follow_redirects=True,
        )
        assert response.status_code == 200
        note = ClinicalNote.query.filter_by(session_id=session.id).first()
        assert note is not None
        assert note.content == "Recommend moisturizer."


class TestDeveloperAccess:
    """Developer gets admin panel + debug tools."""

    def test_developer_can_access_admin(self, dev_client):
        response = dev_client.get("/admin/")
        assert response.status_code == 200

    def test_developer_can_access_debug(self, dev_client):
        response = dev_client.get("/admin/debug")
        assert response.status_code == 200

    def test_regular_user_cannot_access_admin(self, user_client):
        response = user_client.get("/admin/")
        assert response.status_code == 403

    def test_regular_user_cannot_access_debug(self, user_client):
        response = user_client.get("/admin/debug")
        assert response.status_code == 403


class TestAssignments:
    """Test patient-dermatologist assignment management."""

    def test_admin_can_create_assignment(self, admin_client, db):
        derm = User(username="derm_a", role="dermatologist")
        derm.set_password("password123")
        patient = User(username="patient_a", role="user")
        patient.set_password("password123")
        db.session.add_all([derm, patient])
        db.session.commit()

        response = admin_client.post("/admin/assignments", data={
            "dermatologist_id": derm.id,
            "patient_id": patient.id,
        }, follow_redirects=True)
        assert response.status_code == 200

        assignment = PatientAssignment.query.filter_by(
            dermatologist_id=derm.id, patient_id=patient.id
        ).first()
        assert assignment is not None

    def test_admin_can_delete_assignment(self, admin_client, db):
        derm = User(username="derm_d", role="dermatologist")
        derm.set_password("password123")
        patient = User(username="patient_d", role="user")
        patient.set_password("password123")
        db.session.add_all([derm, patient])
        db.session.commit()

        assignment = PatientAssignment(
            dermatologist_id=derm.id, patient_id=patient.id
        )
        db.session.add(assignment)
        db.session.commit()
        aid = assignment.id

        response = admin_client.post(
            f"/admin/assignments/{aid}/delete",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert PatientAssignment.query.get(aid) is None
