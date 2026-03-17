from flask import Blueprint, jsonify
from datetime import date
from sqlalchemy import func
from app.models import PhotoSession, AnalysisResult, SkinCondition
from app.blueprints.analysis.detectors.scoring import SkinHealthScorer

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/trends", methods=["GET"])
def trends():
    """
    Returns array of {date, overall_score} for all sessions with analysis.
    Used for line chart trending.
    """
    # Get all sessions with analysis results, ordered by date
    sessions = (
        PhotoSession.query
        .outerjoin(AnalysisResult)
        .group_by(PhotoSession.id)
        .having(func.count(AnalysisResult.id) > 0)
        .order_by(PhotoSession.session_date.asc())
        .all()
    )

    trend_data = []
    for session in sessions:
        # Calculate overall score for this session (average of all condition scores)
        if session.analysis_results:
            # Get unique condition scores (one per condition type per session)
            condition_scores = []
            condition_names = set()

            for result in session.analysis_results:
                if result.condition_name not in condition_names:
                    condition_names.add(result.condition_name)
                    condition_scores.append(result.score)

            if condition_scores:
                overall_score = int(sum(condition_scores) / len(condition_scores))
                trend_data.append({
                    "date": session.session_date.isoformat(),
                    "overall_score": overall_score
                })

    return jsonify(trend_data)


@api_bp.route("/session/<int:session_id>/breakdown", methods=["GET"])
def session_breakdown(session_id):
    """
    Returns {overall_score, conditions: {name: {score, severity}}} for a specific session.
    Used for radar chart showing condition breakdown.
    """
    session = PhotoSession.query.get(session_id)

    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Get analysis results for this session
    results = AnalysisResult.query.filter_by(session_id=session_id).all()

    if not results:
        return jsonify({"error": "No analysis results for this session"}), 404

    # Build conditions dict with average scores per condition type
    conditions_dict = {}
    condition_lists = {}

    for result in results:
        if result.condition_name not in condition_lists:
            condition_lists[result.condition_name] = []
        condition_lists[result.condition_name].append(result.score)

    # Average scores by condition and get severity
    for condition_name, scores in condition_lists.items():
        avg_score = int(sum(scores) / len(scores))

        # Get severity label from SkinCondition if available
        skin_condition = SkinCondition.query.filter_by(
            session_id=session_id,
            condition_type=condition_name
        ).first()

        severity = skin_condition.severity if skin_condition else "unknown"

        conditions_dict[condition_name] = {
            "score": avg_score,
            "severity": severity
        }

    # Calculate overall score
    all_scores = [result.score for result in results if result.condition_name in condition_lists]
    overall_score = int(sum(all_scores) / len(all_scores)) if all_scores else 0

    return jsonify({
        "overall_score": overall_score,
        "conditions": conditions_dict
    })


@api_bp.route("/sessions/summary", methods=["GET"])
def sessions_summary():
    """
    Returns summary statistics: total_sessions, avg_score, best_score, worst_score, total_conditions_detected.
    """
    # Get all sessions
    all_sessions = PhotoSession.query.all()
    total_sessions = len(all_sessions)

    if total_sessions == 0:
        return jsonify({
            "total_sessions": 0,
            "avg_score": 0,
            "best_score": 0,
            "worst_score": 0,
            "total_conditions_detected": 0
        })

    # Get all analysis results for sessions with analysis
    all_results = AnalysisResult.query.all()

    if not all_results:
        return jsonify({
            "total_sessions": total_sessions,
            "avg_score": 0,
            "best_score": 0,
            "worst_score": 0,
            "total_conditions_detected": 0
        })

    # Calculate stats
    all_scores = [result.score for result in all_results]
    avg_score = int(sum(all_scores) / len(all_scores)) if all_scores else 0
    best_score = max(all_scores) if all_scores else 0
    worst_score = min(all_scores) if all_scores else 0

    # Count unique conditions detected across all sessions
    unique_conditions = set(result.condition_name for result in all_results)
    total_conditions_detected = len(unique_conditions)

    return jsonify({
        "total_sessions": total_sessions,
        "avg_score": avg_score,
        "best_score": int(best_score),
        "worst_score": int(worst_score),
        "total_conditions_detected": total_conditions_detected
    })
