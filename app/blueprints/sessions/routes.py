import os
import shutil
import uuid
from datetime import date

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from PIL import Image
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Photo, PhotoSession

sessions_bp = Blueprint("sessions", __name__, url_prefix="/sessions")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
REQUIRED_ANGLES = ["front", "left", "right"]
OPTIONAL_ANGLES = [
    "three_quarter_left",
    "three_quarter_right",
    "top_down",
    "chin_up",
    "cheek_left",
    "cheek_right",
    "under_eye_left",
    "under_eye_right",
]
ALL_ANGLES = REQUIRED_ANGLES + OPTIONAL_ANGLES

# Display names for angles
ANGLE_LABELS = {
    "front": "Front",
    "left": "Left Profile",
    "right": "Right Profile",
    "three_quarter_left": "Three-Quarter (Left)",
    "three_quarter_right": "Three-Quarter (Right)",
    "top_down": "Top-Down",
    "chin_up": "Chin-Up",
    "cheek_left": "Left Cheek Close-Up",
    "cheek_right": "Right Cheek Close-Up",
    "under_eye_left": "Left Under-Eye Close-Up",
    "under_eye_right": "Right Under-Eye Close-Up",
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@sessions_bp.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        # Validate session date
        session_date_str = request.form.get("session_date", date.today().isoformat())
        try:
            session_date = date.fromisoformat(session_date_str)
        except ValueError:
            flash("Invalid session date.", "danger")
            return redirect(request.url)

        notes = request.form.get("notes", "").strip()

        # Validate required photos are present and valid
        files = {}
        for angle in REQUIRED_ANGLES:
            f = request.files.get(f"photo_{angle}")
            if not f or f.filename == "":
                flash(f"Missing required {ANGLE_LABELS.get(angle, angle)} photo.", "danger")
                return redirect(request.url)
            if not allowed_file(f.filename):
                flash(f"Invalid file type for {ANGLE_LABELS.get(angle, angle)} photo. Allowed: PNG, JPG, JPEG, WebP.", "danger")
                return redirect(request.url)
            files[angle] = f

        # Process optional photos
        for angle in OPTIONAL_ANGLES:
            f = request.files.get(f"photo_{angle}")
            if f and f.filename != "":
                if not allowed_file(f.filename):
                    flash(f"Invalid file type for {ANGLE_LABELS.get(angle, angle)} photo. Allowed: PNG, JPG, JPEG, WebP.", "danger")
                    return redirect(request.url)
                files[angle] = f

        # Create session directory
        session_uuid = str(uuid.uuid4())
        session_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], session_uuid)
        os.makedirs(session_dir, exist_ok=True)

        # Create PhotoSession record
        photo_session = PhotoSession(session_date=session_date, notes=notes)
        db.session.add(photo_session)
        db.session.flush()  # Get the ID

        try:
            # Save photos
            for angle, file_obj in files.items():
                ext = file_obj.filename.rsplit(".", 1)[1].lower()
                safe_filename = f"{angle}.{ext}"
                filepath = os.path.join(session_dir, safe_filename)

                # Open, resize (max 1920px on longest edge), and save
                img = Image.open(file_obj.stream)
                img.thumbnail((1920, 1920), Image.LANCZOS)
                img.save(filepath, quality=90)

                # Create Photo record (filepath is relative to uploads folder)
                photo = Photo(
                    session_id=photo_session.id,
                    angle=angle,
                    filename=safe_filename,
                    filepath=os.path.join(session_uuid, safe_filename),
                )
                db.session.add(photo)

            db.session.commit()
            flash("Session created successfully!", "success")
            return redirect(url_for("sessions.detail", session_id=photo_session.id))

        except Exception as e:
            db.session.rollback()
            # Clean up directory
            shutil.rmtree(session_dir, ignore_errors=True)
            flash(f"Error saving session: {str(e)}", "danger")
            return redirect(request.url)

    return render_template("sessions/upload.html", today=date.today().isoformat())


@sessions_bp.route("/", methods=["GET"])
def list_sessions():
    page = request.args.get("page", 1, type=int)
    sessions = PhotoSession.query.order_by(
        PhotoSession.session_date.desc()
    ).paginate(page=page, per_page=10)
    return render_template("sessions/list.html", sessions=sessions)


@sessions_bp.route("/<int:session_id>", methods=["GET"])
def detail(session_id):
    session = PhotoSession.query.get_or_404(session_id)
    # Group photos by angle
    photos_by_angle = {p.angle: p for p in session.photos}
    return render_template(
        "sessions/detail.html",
        session=session,
        photos_by_angle=photos_by_angle,
        angle_labels=ANGLE_LABELS,
        required_angles=REQUIRED_ANGLES,
        optional_angles=OPTIONAL_ANGLES,
    )


@sessions_bp.route("/<int:session_id>/delete", methods=["POST"])
def delete(session_id):
    session = PhotoSession.query.get_or_404(session_id)

    # Get the session directory to delete
    if session.photos:
        # Extract UUID from first photo's filepath (format: <uuid>/filename)
        filepath = session.photos[0].filepath
        session_dir = os.path.dirname(
            os.path.join(current_app.config["UPLOAD_FOLDER"], filepath)
        )
    else:
        session_dir = None

    # Delete from database
    db.session.delete(session)
    db.session.commit()

    # Delete from filesystem
    if session_dir and os.path.exists(session_dir):
        try:
            shutil.rmtree(session_dir)
        except Exception as e:
            flash(f"Session deleted from database but files could not be removed: {str(e)}", "warning")
            return redirect(url_for("sessions.list_sessions"))

    flash("Session deleted successfully.", "success")
    return redirect(url_for("sessions.list_sessions"))


@sessions_bp.route("/photo/<path:filepath>", methods=["GET"])
def serve_photo(filepath):
    """Serve uploaded photos from the uploads directory."""
    try:
        return send_from_directory(current_app.config["UPLOAD_FOLDER"], filepath)
    except FileNotFoundError:
        flash("Photo not found.", "danger")
        return redirect(url_for("sessions.list_sessions"))
