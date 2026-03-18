import os
from datetime import date
from io import BytesIO

import pytest
from PIL import Image

from app.models import Photo, PhotoSession


@pytest.fixture
def sample_image():
    """Create a sample image in memory."""
    img = Image.new('RGB', (800, 600), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes


def create_image_file(format='JPEG'):
    """Helper to create an image file."""
    img = Image.new('RGB', (800, 600), color='blue')
    img_bytes = BytesIO()
    img.save(img_bytes, format=format)
    img_bytes.seek(0)
    img_bytes.name = f'test_photo.{format.lower()}'
    return img_bytes


def test_upload_page_get(client):
    """Test GET /sessions/upload returns the upload form."""
    response = client.get('/sessions/upload')
    assert response.status_code == 200
    assert b'Upload Session' in response.data
    assert b'Front' in response.data  # Check for required angles section


def test_upload_missing_photo(client):
    """Test that missing a photo triggers an error."""
    response = client.post('/sessions/upload', data={
        'session_date': '2026-03-17',
        'photo_front': (create_image_file(), 'front.jpg'),
        'photo_left': (create_image_file(), 'left.jpg'),
    }, follow_redirects=True)
    assert b'Missing required' in response.data


def test_upload_invalid_file_type(client):
    """Test that invalid file types are rejected."""
    txt_file = BytesIO(b'not an image')
    txt_file.name = 'test.txt'

    response = client.post('/sessions/upload', data={
        'session_date': '2026-03-17',
        'photo_front': (txt_file, 'front.txt'),
        'photo_left': (create_image_file(), 'left.jpg'),
        'photo_right': (create_image_file(), 'right.jpg'),
    }, follow_redirects=True)
    assert b'Invalid file type' in response.data


def test_upload_valid_session(client, db):
    """Test successful session upload with 3 photos."""
    response = client.post('/sessions/upload', data={
        'session_date': '2026-03-17',
        'notes': 'First session',
        'photo_front': (create_image_file(), 'front.jpg'),
        'photo_left': (create_image_file(), 'left.jpg'),
        'photo_right': (create_image_file(), 'right.jpg'),
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Session created successfully' in response.data

    # Check database
    session = PhotoSession.query.first()
    assert session is not None
    assert session.session_date == date(2026, 3, 17)
    assert session.notes == 'First session'
    assert len(session.photos) == 3

    # Check photos have correct angles
    angles = {p.angle for p in session.photos}
    assert angles == {'front', 'left', 'right'}

    # Check files exist on disk
    for photo in session.photos:
        filepath = os.path.join(client.application.config['UPLOAD_FOLDER'], photo.filepath)
        assert os.path.exists(filepath), f"Photo file not found: {filepath}"
        assert os.path.getsize(filepath) > 0


def test_upload_creates_directories(client, db):
    """Test that upload creates proper directory structure."""
    client.post('/sessions/upload', data={
        'session_date': '2026-03-17',
        'photo_front': (create_image_file(), 'front.jpg'),
        'photo_left': (create_image_file(), 'left.jpg'),
        'photo_right': (create_image_file(), 'right.jpg'),
    })

    session = PhotoSession.query.first()
    session_dir = os.path.dirname(
        os.path.join(client.application.config['UPLOAD_FOLDER'], session.photos[0].filepath)
    )
    assert os.path.exists(session_dir)
    assert os.path.isdir(session_dir)


def test_list_sessions(client, db):
    """Test GET /sessions/ lists sessions."""
    # Create 3 sessions
    for i in range(3):
        session = PhotoSession(session_date=date(2026, 3, 10 + i))
        db.session.add(session)
    db.session.commit()

    response = client.get('/sessions/')
    assert response.status_code == 200
    assert b'Sessions' in response.data
    # Should show session dates
    assert b'March 10' in response.data


def test_list_sessions_empty(client):
    """Test /sessions/ when no sessions exist."""
    response = client.get('/sessions/')
    assert response.status_code == 200
    assert b'No sessions yet' in response.data or b'Upload Your First Session' in response.data


def test_session_detail(client, db):
    """Test GET /sessions/<id> shows session details."""
    # Create session with photos
    session = PhotoSession(session_date=date(2026, 3, 17), notes='Test session')
    db.session.add(session)
    db.session.flush()

    for angle in ['front', 'left', 'right']:
        photo = Photo(
            session_id=session.id,
            angle=angle,
            filename=f'{angle}.jpg',
            filepath=f'abc123/{angle}.jpg'
        )
        db.session.add(photo)
    db.session.commit()

    response = client.get(f'/sessions/{session.id}')
    assert response.status_code == 200
    assert b'Session Details' in response.data
    assert b'front' in response.data
    assert b'Test session' in response.data


def test_session_detail_not_found(client):
    """Test 404 when session doesn't exist."""
    response = client.get('/sessions/9999')
    assert response.status_code == 404


def test_serve_photo(client, db):
    """Test serving uploaded photos."""
    session = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add(session)
    db.session.flush()

    # Create actual photo file
    photo = Photo(
        session_id=session.id,
        angle='front',
        filename='front.jpg',
        filepath='test_uuid/front.jpg'
    )
    db.session.add(photo)
    db.session.commit()

    # Create the actual file
    upload_folder = client.application.config['UPLOAD_FOLDER']
    photo_dir = os.path.join(upload_folder, 'test_uuid')
    os.makedirs(photo_dir, exist_ok=True)

    img = Image.new('RGB', (100, 100), color='green')
    img.save(os.path.join(photo_dir, 'front.jpg'))

    # Test serving
    response = client.get('/sessions/photo/test_uuid/front.jpg')
    assert response.status_code == 200
    assert response.content_type.startswith('image/')


def test_delete_session(client, db):
    """Test deleting a session."""
    session = PhotoSession(session_date=date(2026, 3, 17))
    db.session.add(session)
    db.session.flush()

    photo = Photo(
        session_id=session.id,
        angle='front',
        filename='front.jpg',
        filepath='delete_test/front.jpg'
    )
    db.session.add(photo)
    db.session.commit()

    session_id = session.id

    # Create actual file
    upload_folder = client.application.config['UPLOAD_FOLDER']
    photo_dir = os.path.join(upload_folder, 'delete_test')
    os.makedirs(photo_dir, exist_ok=True)
    img = Image.new('RGB', (100, 100), color='red')
    img.save(os.path.join(photo_dir, 'front.jpg'))

    # Delete session
    response = client.post(f'/sessions/{session_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b'Session deleted successfully' in response.data

    # Check database
    deleted_session = PhotoSession.query.get(session_id)
    assert deleted_session is None

    # Check filesystem
    assert not os.path.exists(photo_dir)


def test_delete_session_not_found(client):
    """Test deleting non-existent session."""
    response = client.post('/sessions/9999/delete')
    assert response.status_code == 404


def test_pagination(client, db):
    """Test session list pagination."""
    # Create 15 sessions (default per_page is 10)
    for i in range(15):
        session = PhotoSession(session_date=date(2026, 3, i + 1))
        db.session.add(session)
    db.session.commit()

    # Page 1
    response = client.get('/sessions/')
    assert response.status_code == 200
    assert b'Next' in response.data

    # Page 2
    response = client.get('/sessions/?page=2')
    assert response.status_code == 200
    assert b'Previous' in response.data
