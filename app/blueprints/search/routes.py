import json
from flask import Blueprint, abort, render_template, jsonify
from app.models import PhotoSession, SkinCondition, RegimenEntry
from app.blueprints.search.client import SkinRemedySearcher, PRODUCT_SUGGESTIONS
from app.extensions import db
from app.utils import can_access_session, user_regimen_query

search_bp = Blueprint("search", __name__, url_prefix="/search", template_folder="templates")
searcher = SkinRemedySearcher()


@search_bp.route("/recommendations/<int:session_id>", methods=["GET"])
def recommendations(session_id):
    """
    Display recommendations for a session based on detected conditions.
    """
    session = PhotoSession.query.get_or_404(session_id)
    if not can_access_session(session):
        abort(403)

    # Get all conditions for this session
    conditions = SkinCondition.query.filter_by(session_id=session_id).all()

    if not conditions:
        return "No analysis results found for this session.", 404

    # Get active regimen at time of session (or current active regimen)
    regimen = user_regimen_query().filter(
        RegimenEntry.ended_on == None
    ).order_by(RegimenEntry.product_name).all()

    # Get recommendations
    recommendations_data = {}
    conditions_by_type = {c.condition_type: c for c in conditions}

    for condition in conditions:
        # Check if search results already stored
        search_results = []
        if condition.search_results_json:
            try:
                search_results = json.loads(condition.search_results_json)
            except:
                search_results = []

        # If no results stored, search now
        if not search_results:
            search_results = searcher.search_condition_remedies(condition.condition_type)

            # Only cache non-empty results so we can retry later
            if search_results:
                condition.search_results_json = json.dumps(search_results)
                db.session.commit()

        # Get rule-based suggestions as fallback/supplement
        ingredient_check = searcher.suggest_ingredients_for_condition(
            condition.condition_type, regimen
        )

        recommendations_data[condition.condition_type] = {
            "condition": condition,
            "search_results": search_results,
            "severity": condition.severity,
            "ingredient_check": ingredient_check,
            "product_suggestion": PRODUCT_SUGGESTIONS.get(condition.condition_type),
        }

    return render_template(
        "search/recommendations.html",
        session=session,
        conditions=conditions_by_type,
        recommendations=recommendations_data,
        regimen=regimen
    )


@search_bp.route("/condition/<int:session_id>/<condition_name>", methods=["GET"])
def condition_detail(session_id, condition_name):
    """
    Display detailed remedies for a specific condition.
    """
    session = PhotoSession.query.get_or_404(session_id)
    if not can_access_session(session):
        abort(403)
    condition = SkinCondition.query.filter_by(
        session_id=session_id,
        condition_type=condition_name
    ).first_or_404()

    # Get search results
    search_results = []
    if condition.search_results_json:
        try:
            search_results = json.loads(condition.search_results_json)
        except:
            search_results = []

    # If no results, search now
    if not search_results:
        search_results = searcher.search_condition_remedies(condition_name)
        condition.search_results_json = json.dumps(search_results)
        db.session.commit()

    regimen = user_regimen_query().filter(
        RegimenEntry.ended_on == None
    ).all()

    return render_template(
        "search/condition_detail.html",
        session=session,
        condition=condition,
        search_results=search_results,
        regimen=regimen
    )
