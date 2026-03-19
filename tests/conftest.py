import pytest

from app import create_app
from app.extensions import db as _db
from app.models import User


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    """Authenticated client (admin user) - default for all existing tests."""
    user = User(username="testadmin", role="admin")
    user.set_password("password123")
    _db.session.add(user)
    _db.session.commit()

    client = app.test_client()
    client.post("/auth/login", data={
        "username": "testadmin",
        "password": "password123",
    })
    return client


@pytest.fixture
def unauthenticated_client(app):
    """A test client that is NOT logged in."""
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


# ── User fixtures ──────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    user = User(username="admin_test", role="admin")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def regular_user(db):
    user = User(username="regular_test", role="user")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def viewer_user(db):
    user = User(username="viewer_test", role="viewer")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def derm_user(db):
    user = User(username="derm_test", role="dermatologist")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def dev_user(db):
    user = User(username="dev_test", role="developer")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


# ── Role-specific authenticated clients ────────────────────────

def _login_client(app, username, password):
    """Helper to create a logged-in test client."""
    c = app.test_client()
    c.post("/auth/login", data={
        "username": username,
        "password": password,
    })
    return c


@pytest.fixture
def admin_client(app, admin_user):
    return _login_client(app, admin_user.username, "password123")


@pytest.fixture
def user_client(app, regular_user):
    return _login_client(app, regular_user.username, "password123")


@pytest.fixture
def viewer_client(app, viewer_user):
    return _login_client(app, viewer_user.username, "password123")


@pytest.fixture
def derm_client(app, derm_user):
    return _login_client(app, derm_user.username, "password123")


@pytest.fixture
def dev_client(app, dev_user):
    return _login_client(app, dev_user.username, "password123")
