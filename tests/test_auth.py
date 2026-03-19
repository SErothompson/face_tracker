"""Tests for authentication flows: login, register, logout, setup, CLI."""

from app.models import User


class TestLogin:
    """Test login flow."""

    def test_login_page_get(self, unauthenticated_client):
        response = unauthenticated_client.get("/auth/login")
        assert response.status_code == 200
        assert b"Login" in response.data

    def test_login_valid_credentials(self, app, db):
        user = User(username="loginuser", role="user")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        response = client.post("/auth/login", data={
            "username": "loginuser",
            "password": "password123",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Dashboard" in response.data

    def test_login_invalid_password(self, app, db):
        user = User(username="loginuser2", role="user")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        response = client.post("/auth/login", data={
            "username": "loginuser2",
            "password": "wrongpassword",
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid" in response.data

    def test_login_nonexistent_user(self, app):
        client = app.test_client()
        response = client.post("/auth/login", data={
            "username": "ghost",
            "password": "password123",
        }, follow_redirects=True)
        assert b"Invalid" in response.data

    def test_login_disabled_account(self, app, db):
        user = User(username="disabled", role="user", is_active_flag=False)
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        response = client.post("/auth/login", data={
            "username": "disabled",
            "password": "password123",
        }, follow_redirects=True)
        assert b"disabled" in response.data.lower()

    def test_login_redirects_authenticated_user(self, client):
        response = client.get("/auth/login", follow_redirects=True)
        assert response.status_code == 200
        assert b"Dashboard" in response.data


class TestRegister:
    """Test registration flow."""

    def test_register_page_get(self, unauthenticated_client):
        response = unauthenticated_client.get("/auth/register")
        assert response.status_code == 200
        assert b"Register" in response.data

    def test_register_valid(self, app, db):
        # Need at least one user so first-run redirect doesn't trigger
        admin = User(username="existingadmin", role="admin")
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()

        client = app.test_client()
        response = client.post("/auth/register", data={
            "username": "newuser",
            "password": "password123",
            "confirm_password": "password123",
        }, follow_redirects=True)
        assert response.status_code == 200

        user = User.query.filter_by(username="newuser").first()
        assert user is not None
        assert user.role == "user"  # Default role

    def test_register_short_username(self, unauthenticated_client, db):
        # Need a user to prevent first-run redirect
        admin = User(username="admin_seed", role="admin")
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()

        response = unauthenticated_client.post("/auth/register", data={
            "username": "ab",
            "password": "password123",
            "confirm_password": "password123",
        }, follow_redirects=True)
        assert b"at least 3" in response.data

    def test_register_short_password(self, unauthenticated_client, db):
        admin = User(username="admin_seed2", role="admin")
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()

        response = unauthenticated_client.post("/auth/register", data={
            "username": "newuser2",
            "password": "short",
            "confirm_password": "short",
        }, follow_redirects=True)
        assert b"at least 8" in response.data

    def test_register_password_mismatch(self, unauthenticated_client, db):
        admin = User(username="admin_seed3", role="admin")
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()

        response = unauthenticated_client.post("/auth/register", data={
            "username": "newuser3",
            "password": "password123",
            "confirm_password": "different456",
        }, follow_redirects=True)
        assert b"do not match" in response.data

    def test_register_duplicate_username(self, unauthenticated_client, db):
        user = User(username="taken_name", role="user")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        response = unauthenticated_client.post("/auth/register", data={
            "username": "taken_name",
            "password": "password123",
            "confirm_password": "password123",
        }, follow_redirects=True)
        assert b"already taken" in response.data


class TestLogout:
    """Test logout flow."""

    def test_logout(self, client):
        response = client.post("/auth/logout", follow_redirects=True)
        assert response.status_code == 200
        assert b"Login" in response.data


class TestProfile:
    """Test profile page."""

    def test_profile_authenticated(self, client):
        response = client.get("/auth/profile")
        assert response.status_code == 200
        assert b"testadmin" in response.data

    def test_profile_unauthenticated_redirects(self, unauthenticated_client, db):
        # Need a user so first-run doesn't trigger
        admin = User(username="admin_p", role="admin")
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()

        response = unauthenticated_client.get("/auth/profile")
        assert response.status_code == 302


class TestFirstRunSetup:
    """Test first-run setup wizard."""

    def test_setup_page_when_no_users(self, app):
        client = app.test_client()
        response = client.get("/auth/setup")
        assert response.status_code == 200
        assert b"Setup" in response.data or b"setup" in response.data.lower()

    def test_setup_creates_admin(self, app, db):
        client = app.test_client()
        response = client.post("/auth/setup", data={
            "username": "firstadmin",
            "password": "password123",
            "confirm_password": "password123",
        }, follow_redirects=True)
        assert response.status_code == 200

        user = User.query.filter_by(username="firstadmin").first()
        assert user is not None
        assert user.role == "admin"

    def test_setup_blocked_when_users_exist(self, app, db):
        user = User(username="existing", role="admin")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        response = client.get("/auth/setup")
        assert response.status_code == 302  # Redirects away

    def test_first_run_redirect(self, app):
        """When no users exist, visiting / should redirect to setup."""
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 302
        assert "/auth/setup" in response.headers["Location"]


class TestCreateAdminCLI:
    """Test flask create-admin CLI command."""

    def test_create_admin_success(self, app, db):
        runner = app.test_cli_runner()
        result = runner.invoke(args=[
            "create-admin",
            "--username", "cliadmin",
            "--password", "password123",
        ])
        assert "created successfully" in result.output

        user = User.query.filter_by(username="cliadmin").first()
        assert user is not None
        assert user.role == "admin"

    def test_create_admin_short_password(self, app, db):
        runner = app.test_cli_runner()
        result = runner.invoke(args=[
            "create-admin",
            "--username", "badpass",
            "--password", "short",
        ])
        assert "at least 8" in result.output

    def test_create_admin_duplicate(self, app, db):
        user = User(username="dupeadmin", role="admin")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        runner = app.test_cli_runner()
        result = runner.invoke(args=[
            "create-admin",
            "--username", "dupeadmin",
            "--password", "password123",
        ])
        assert "already exists" in result.output


class TestUserModel:
    """Test User model methods."""

    def test_set_and_check_password(self, db):
        user = User(username="passtest", role="user")
        user.set_password("mysecretpass")
        db.session.add(user)
        db.session.commit()

        assert user.check_password("mysecretpass") is True
        assert user.check_password("wrongpass") is False

    def test_has_role(self, db):
        user = User(username="roletest", role="admin")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        assert user.has_role("admin") is True
        assert user.has_role("admin", "developer") is True
        assert user.has_role("user") is False

    def test_is_active_property(self, db):
        active_user = User(username="active", role="user")
        active_user.set_password("password123")
        disabled_user = User(username="disabled2", role="user", is_active_flag=False)
        disabled_user.set_password("password123")
        db.session.add_all([active_user, disabled_user])
        db.session.commit()

        assert active_user.is_active is True
        assert disabled_user.is_active is False

    def test_valid_roles(self):
        assert "user" in User.VALID_ROLES
        assert "viewer" in User.VALID_ROLES
        assert "dermatologist" in User.VALID_ROLES
        assert "admin" in User.VALID_ROLES
        assert "developer" in User.VALID_ROLES
