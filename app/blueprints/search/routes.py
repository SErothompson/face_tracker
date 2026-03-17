import json
from flask import Blueprint, render_template, jsonify
from app.models import PhotoSession, SkinCondition, RegimenEntry
from app.blueprints.search.client import SkinRemedySearcher
from app.extensions import db

search_bp = Blueprint("search", __name__, url_prefix="/search")
searcher = SkinRemedySearcher()


@search_bp.route("/recommendations/<int:session_id>", methods=["GET"])
def recommendations(session_id):
    """
    Display recommendations for a session based on detected conditions.
    """
    session = PhotoSession.query.get_or_404(session_id)

    # Get all conditions for this session
    conditions = SkinCondition.query.filter_by(session_id=session_id).all()

    if not conditions:
        return "No analysis results found for this session.", 404

    # Get active regimen at time of session (or current active regimen)
    regimen = RegimenEntry.query.filter(
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

            # Store results
            condition.search_results_json = json.dumps(search_results)
            db.session.commit()

        recommendations_data[condition.condition_type] = {
            "condition": condition,
            "search_results": search_results,
            "severity": condition.severity
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

    regimen = RegimenEntry.query.filter(
        RegimenEntry.ended_on == None
    ).all()

    return render_template(
        "search/condition_detail.html",
        session=session,
        condition=condition,
        search_results=search_results,
        regimen=regimen
    )
