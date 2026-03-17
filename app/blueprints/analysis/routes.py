import os
from flask import Blueprint, render_template, redirect, url_for, flash, abort
import cv2

from app.blueprints.analysis.engine import AnalysisEngine
from app.blueprints.analysis.detectors.scoring import SkinHealthScorer
from app.models import PhotoSession, Photo, AnalysisResult, SkinCondition
from app.extensions import db

analysis_bp = Blueprint(
    "analysis",
    __name__,
    url_prefix="/analysis",
    template_folder="templates",
)


@analysis_bp.route("/run/<int:session_id>", methods=["POST"])
def run_analysis(session_id):
    """
    Trigger analysis for all photos in a session.

    Args:
        session_id: PhotoSession ID

    Returns:
        Redirect to analysis results page or error flash
    """
    session = PhotoSession.query.get_or_404(session_id)

    # Initialize engine
    engine = AnalysisEngine()

    try:
        # Analyze each photo
        for photo in session.photos:
            # Load image
            photo_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "uploads",
                photo.filepath,
            )

            if not os.path.exists(photo_path):
                flash(f"Photo file not found: {photo.filepath}", "error")
                return redirect(url_for("sessions.detail", session_id=session_id))

            image_bgr = cv2.imread(photo_path)
            if image_bgr is None:
                flash(f"Could not load photo: {photo.filename}", "error")
                return redirect(url_for("sessions.detail", session_id=session_id))

            # Run analysis
            analysis_result = engine.analyze_photo(photo, image_bgr)
            if analysis_result is None:
                flash(f"No face detected in {photo.angle} photo", "warning")
                continue

            # Save to database
            engine.save_analysis(session, photo, analysis_result)

        flash("Analysis completed successfully", "success")
        return redirect(url_for("analysis.analysis_results", session_id=session_id))

    except Exception as e:
        flash(f"Analysis failed: {str(e)}", "error")
        return redirect(url_for("sessions.detail", session_id=session_id))

    finally:
        engine.close()


@analysis_bp.route("/results/<int:session_id>")
def analysis_results(session_id):
    """
    Display analysis results for a session.

    Args:
        session_id: PhotoSession ID

    Returns:
        Rendered results template
    """
    session = PhotoSession.query.get_or_404(session_id)

    # Get analysis results
    results = AnalysisResult.query.filter_by(session_id=session_id).all()
    if not results:
        flash("No analysis results for this session", "info")
        return redirect(url_for("sessions.detail", session_id=session_id))

    # Get conditions
    conditions = SkinCondition.query.filter_by(session_id=session_id).all()

    # Group conditions by type for easier display
    conditions_by_type = {}
    for condition in conditions:
        if condition.condition_type not in conditions_by_type:
            conditions_by_type[condition.condition_type] = []
        conditions_by_type[condition.condition_type].append(condition)

    # Calculate overall score from condition scores
    # Group results by condition_name to aggregate scores
    condition_scores_by_name = {}
    for result in results:
        if result.condition_name not in condition_scores_by_name:
            condition_scores_by_name[result.condition_name] = []
        condition_scores_by_name[result.condition_name].append(result.score)

    # Average scores for each condition
    condition_summary = {}
    avg_scores = []
    for condition_name, scores in condition_scores_by_name.items():
        avg_score = int(sum(scores) / len(scores)) if scores else 50
        condition_summary[condition_name] = avg_score
        avg_scores.append(avg_score)

    session_overall_score = int(sum(avg_scores) / len(avg_scores)) if avg_scores else 0

    return render_template(
        "analysis/results.html",
        session=session,
        results=results,
        conditions=conditions_by_type,
        condition_summary=condition_summary,
        session_overall_score=session_overall_score,
        severity_label=SkinHealthScorer.score_to_severity_label(session_overall_score),
        badge_color=SkinHealthScorer.score_to_badge_color(session_overall_score),
    )
