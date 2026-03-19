from flask import Blueprint, render_template
from flask_login import current_user
from sqlalchemy import func

from app.models import AnalysisResult, PhotoSession, RegimenEntry, SkinCondition
from app.blueprints.analysis.detectors.scoring import SkinHealthScorer
from app.utils import user_regimen_query, user_sessions_query

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    base_query = user_sessions_query()

    # Get all recent sessions (for table display)
    recent_sessions = (
        base_query.order_by(PhotoSession.session_date.desc())
        .limit(5)
        .all()
    )

    # Get sessions with analysis results
    sessions_with_analysis = (
        base_query
        .outerjoin(AnalysisResult)
        .group_by(PhotoSession.id)
        .having(func.count(AnalysisResult.id) > 0)
        .order_by(PhotoSession.session_date.desc())
        .all()
    )

    # Get latest session with analysis
    latest_session = None
    latest_session_score = 0
    severity_label_text = ""
    badge_color_text = "secondary"
    condition_scores = {}
    conditions_by_type = {}

    if sessions_with_analysis:
        latest_session = sessions_with_analysis[0]

        # Calculate overall score for latest session
        if latest_session.analysis_results:
            scores = []
            condition_dict = {}

            # Aggregate scores by condition name
            for result in latest_session.analysis_results:
                if result.condition_name not in condition_dict:
                    condition_dict[result.condition_name] = []
                condition_dict[result.condition_name].append(result.score)

            # Average by condition
            for condition_name, condition_scores_list in condition_dict.items():
                avg_score = sum(condition_scores_list) / len(condition_scores_list)
                condition_scores[condition_name] = int(avg_score)
                scores.append(avg_score)

            # Overall score is average of condition averages
            if scores:
                latest_session_score = int(sum(scores) / len(scores))
                severity_label_text = SkinHealthScorer.score_to_severity_label(latest_session_score)
                badge_color_text = SkinHealthScorer.score_to_badge_color(latest_session_score)

        # Get conditions by type for latest session
        for condition in latest_session.conditions:
            conditions_by_type[condition.condition_type] = condition

    # Get active regimen (limit to 5 for dashboard summary)
    active_regimen = (
        user_regimen_query()
        .filter_by(ended_on=None)
        .order_by(RegimenEntry.time_of_day, RegimenEntry.product_name)
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        recent_sessions=recent_sessions,
        sessions_with_analysis=sessions_with_analysis,
        latest_session=latest_session,
        latest_session_score=latest_session_score,
        severity_label_text=severity_label_text,
        badge_color_text=badge_color_text,
        condition_scores=condition_scores,
        conditions_by_type=conditions_by_type,
        active_regimen=active_regimen
    )
