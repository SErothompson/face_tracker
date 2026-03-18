import cv2
import os
import io
from flask import Blueprint, render_template, request, redirect, url_for, send_file
from app.models import PhotoSession, Photo, AnalysisResult, ComparisonResult
from app.blueprints.comparison.engine import ComparisonEngine
from app.extensions import db

comparison_bp = Blueprint("comparison", __name__, url_prefix="/comparison", template_folder="templates")


@comparison_bp.route("/", methods=["GET"])
def select_sessions():
    """
    Display session pair selection form.
    Only shows sessions that have analysis results.
    """
    # Get sessions with analysis
    sessions_with_analysis = (
        PhotoSession.query
        .filter(PhotoSession.analysis_results.any())
        .order_by(PhotoSession.session_date.desc())
        .all()
    )

    return render_template(
        "comparison/select.html",
        sessions=sessions_with_analysis
    )


@comparison_bp.route("/select", methods=["POST"])
def process_selection():
    """
    Process session pair selection and redirect to results.
    """
    session_a_id = request.form.get("session_a_id")
    session_b_id = request.form.get("session_b_id")

    # Validate
    if not session_a_id or not session_b_id:
        return redirect(url_for("comparison.select_sessions"))

    try:
        session_a_id = int(session_a_id)
        session_b_id = int(session_b_id)
    except ValueError:
        return redirect(url_for("comparison.select_sessions"))

    # Prevent same session comparison
    if session_a_id == session_b_id:
        return redirect(url_for("comparison.select_sessions"))

    # Verify both sessions exist and have analysis
    session_a = PhotoSession.query.get(session_a_id)
    session_b = PhotoSession.query.get(session_b_id)

    if not session_a or not session_b:
        return redirect(url_for("comparison.select_sessions"))

    if not session_a.analysis_results or not session_b.analysis_results:
        return redirect(url_for("comparison.select_sessions"))

    return redirect(url_for("comparison.view_results", session_a_id=session_a_id, session_b_id=session_b_id))


@comparison_bp.route("/result/<int:session_a_id>/<int:session_b_id>", methods=["GET"])
def view_results(session_a_id, session_b_id):
    """
    Display comparison results for two sessions.
    Compute SSIM, diff heatmaps, and condition deltas for all angles.
    """
    # Load sessions
    session_a = PhotoSession.query.get_or_404(session_a_id)
    session_b = PhotoSession.query.get_or_404(session_b_id)

    # Verify both have analysis
    if not session_a.analysis_results or not session_b.analysis_results:
        return redirect(url_for("comparison.select_sessions"))

    # Get photos by angle
    photos_a = {p.angle: p for p in session_a.photos}
    photos_b = {p.angle: p for p in session_b.photos}

    comparison_data = {}

    # Process each angle that exists in both sessions
    angles = set(photos_a.keys()) & set(photos_b.keys())

    for angle in angles:
        photo_a = photos_a[angle]
        photo_b = photos_b[angle]

        # Load images
        image_a_path = os.path.join("uploads", photo_a.filepath)
        image_b_path = os.path.join("uploads", photo_b.filepath)

        if not os.path.exists(image_a_path) or not os.path.exists(image_b_path):
            continue

        image_a = cv2.imread(image_a_path)
        image_b = cv2.imread(image_b_path)

        if image_a is None or image_b is None:
            continue

        # Compute SSIM
        ssim_score = ComparisonEngine.compute_ssim(image_a, image_b)

        # Generate diff heatmap (store in memory)
        diff_heatmap = ComparisonEngine.generate_diff_heatmap(image_a, image_b)

        # Calculate condition deltas
        deltas = ComparisonEngine.calculate_condition_deltas(session_a_id, session_b_id, angle)

        # Generate summary
        summary = ComparisonEngine.generate_summary(session_a_id, session_b_id, angle)

        # Get SSIM interpretation
        ssim_category, ssim_description = ComparisonEngine.interpret_ssim_score(ssim_score)

        # Store comparison data
        comparison_data[angle] = {
            "ssim_score": round(ssim_score, 3),
            "ssim_category": ssim_category,
            "ssim_description": ssim_description,
            "deltas": deltas,
            "summary": summary,
            "heatmap": diff_heatmap,  # Store in memory for this request
            "baseline_photo": photo_a.filepath,
            "comparison_photo": photo_b.filepath
        }

        # Create/update ComparisonResult in database
        comparison_result = ComparisonResult.query.filter_by(
            session_a_id=session_a_id,
            session_b_id=session_b_id,
            angle=angle
        ).first()

        if not comparison_result:
            comparison_result = ComparisonResult(
                session_a_id=session_a_id,
                session_b_id=session_b_id,
                angle=angle
            )
            db.session.add(comparison_result)

        comparison_result.ssim_score = ssim_score
        comparison_result.changes_summary = summary.get("status", "Unknown")

        db.session.commit()

    # If no valid angle comparisons, redirect
    if not comparison_data:
        return redirect(url_for("comparison.select_sessions"))

    # Convert deltas dict to list for template
    for angle in comparison_data:
        comparison_data[angle]["deltas_list"] = [
            {
                "name": name,
                **data
            }
            for name, data in comparison_data[angle]["deltas"].items()
        ]

    return render_template(
        "comparison/result.html",
        session_a=session_a,
        session_b=session_b,
        comparison_data=comparison_data,
        angles=sorted(comparison_data.keys())
    )


@comparison_bp.route("/diff-image/<int:session_a_id>/<int:session_b_id>/<angle>", methods=["GET"])
def get_diff_image(session_a_id, session_b_id, angle):
    """
    Serve diff heatmap as PNG image.
    This route is called by the template to load the image.
    """
    # Load sessions
    session_a = PhotoSession.query.get_or_404(session_a_id)
    session_b = PhotoSession.query.get_or_404(session_b_id)

    # Get photos by angle
    photos_a = {p.angle: p for p in session_a.photos}
    photos_b = {p.angle: p for p in session_b.photos}

    if angle not in photos_a or angle not in photos_b:
        return "No image", 404

    photo_a = photos_a[angle]
    photo_b = photos_b[angle]

    # Load images
    image_a_path = os.path.join("uploads", photo_a.filepath)
    image_b_path = os.path.join("uploads", photo_b.filepath)

    if not os.path.exists(image_a_path) or not os.path.exists(image_b_path):
        return "Image not found", 404

    image_a = cv2.imread(image_a_path)
    image_b = cv2.imread(image_b_path)

    if image_a is None or image_b is None:
        return "Cannot load image", 500

    # Generate diff heatmap
    diff_heatmap = ComparisonEngine.generate_diff_heatmap(image_a, image_b)

    # Convert to PNG bytes
    png_bytes = ComparisonEngine.heatmap_to_png_bytes(diff_heatmap)

    # Return as image
    return send_file(
        io.BytesIO(png_bytes),
        mimetype="image/png"
    )
