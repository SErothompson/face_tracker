import pytest
from datetime import date, datetime, timezone
from app.models import PhotoSession, Photo, AnalysisResult, SkinCondition


class TestApiTrends:
    """Test /api/trends endpoint"""

    def test_trends_empty_database(self, client):
        """Test trends endpoint with no sessions"""
        response = client.get("/api/trends")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_trends_session_without_analysis(self, client, db):
        """Test trends endpoint with session but no analysis"""
        session = PhotoSession(
            session_date=date.today(),
            notes="Test session without analysis"
        )
        db.session.add(session)
        db.session.commit()

        response = client.get("/api/trends")
        assert response.status_code == 200
        data = response.get_json()
        assert data == []

    def test_trends_single_session_with_analysis(self, client, db):
        """Test trends endpoint with single analyzed session"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Add analysis results (6 conditions in the same session)
        conditions = ["acne", "texture", "dark_spots", "wrinkles", "under_eye", "redness"]
        for condition in conditions:
            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition,
                region="front",
                score=75.5
            )
            db.session.add(result)
        db.session.commit()

        response = client.get("/api/trends")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 1
        assert data[0]["date"] == date.today().isoformat()
        assert data[0]["overall_score"] == 75  # Average of all condition scores (int)

    def test_trends_multiple_sessions(self, client, db):
        """Test trends endpoint with multiple analyzed sessions"""
        dates = [
            date(2026, 3, 10),
            date(2026, 3, 17),
            date(2026, 3, 24)
        ]
        conditions = ["acne", "texture", "dark_spots", "wrinkles", "under_eye", "redness"]

        for session_date in dates:
            session = PhotoSession(session_date=session_date)
            db.session.add(session)
            db.session.commit()

            for condition in conditions:
                result = AnalysisResult(
                    session_id=session.id,
                    condition_name=condition,
                    region="front",
                    score=70.0 + len(dates) * 2  # Increasing scores
                )
                db.session.add(result)
            db.session.commit()

        response = client.get("/api/trends")
        assert response.status_code == 200
        data = response.get_json()

        assert len(data) == 3
        assert data[0]["date"] == "2026-03-10"
        assert data[2]["date"] == "2026-03-24"
        # Verify data is sorted by date
        for i in range(len(data) - 1):
            assert data[i]["date"] <= data[i + 1]["date"]

    def test_trends_json_structure(self, client, db):
        """Test trends response has correct JSON structure"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        for condition in ["acne", "texture", "dark_spots"]:
            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition,
                region="front",
                score=80.0
            )
            db.session.add(result)
        db.session.commit()

        response = client.get("/api/trends")
        data = response.get_json()

        assert isinstance(data, list)
        assert len(data) > 0
        assert "date" in data[0]
        assert "overall_score" in data[0]
        assert isinstance(data[0]["overall_score"], int)
        assert 0 <= data[0]["overall_score"] <= 100


class TestApiSessionBreakdown:
    """Test /api/session/<id>/breakdown endpoint"""

    def test_breakdown_invalid_session(self, client):
        """Test breakdown endpoint with non-existent session"""
        response = client.get("/api/session/9999/breakdown")
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_breakdown_session_without_analysis(self, client, db):
        """Test breakdown endpoint with session but no analysis"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        response = client.get(f"/api/session/{session.id}/breakdown")
        assert response.status_code == 404

    def test_breakdown_with_analysis_results(self, client, db):
        """Test breakdown endpoint with valid analysis data"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Add analysis results for all 6 conditions
        conditions = [
            ("acne", 82),
            ("texture", 75),
            ("dark_spots", 68),
            ("wrinkles", 70),
            ("under_eye", 65),
            ("redness", 80)
        ]

        for condition_name, score in conditions:
            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition_name,
                region="front",
                score=float(score)
            )
            skin_condition = SkinCondition(
                session_id=session.id,
                condition_type=condition_name,
                severity="mild" if score > 75 else "moderate"
            )
            db.session.add(result)
            db.session.add(skin_condition)
        db.session.commit()

        response = client.get(f"/api/session/{session.id}/breakdown")
        assert response.status_code == 200
        data = response.get_json()

        assert "overall_score" in data
        assert "conditions" in data
        assert isinstance(data["conditions"], dict)
        assert len(data["conditions"]) == 6

        # Verify each condition has score and severity
        for condition_name, expected_score in conditions:
            assert condition_name in data["conditions"]
            assert "score" in data["conditions"][condition_name]
            assert "severity" in data["conditions"][condition_name]
            assert data["conditions"][condition_name]["score"] == expected_score

    def test_breakdown_overall_score_calculation(self, client, db):
        """Test that overall score is correctly calculated"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        scores = [80, 75, 70, 65, 60, 50]  # Average = 70
        for i, score in enumerate(scores):
            condition_name = ["acne", "texture", "dark_spots", "wrinkles", "under_eye", "redness"][i]
            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition_name,
                region="front",
                score=float(score)
            )
            db.session.add(result)
        db.session.commit()

        response = client.get(f"/api/session/{session.id}/breakdown")
        data = response.get_json()

        expected_overall = int(sum(scores) / len(scores))
        assert data["overall_score"] == expected_overall

    def test_breakdown_multiple_regions_same_condition(self, client, db):
        """Test breakdown with multiple regions for same condition"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        # Add acne results for 3 regions
        for region in ["front", "left", "right"]:
            result = AnalysisResult(
                session_id=session.id,
                condition_name="acne",
                region=region,
                score=90.0 if region == "front" else 80.0
            )
            db.session.add(result)

        # Add other conditions
        for condition in ["texture", "dark_spots", "wrinkles", "under_eye", "redness"]:
            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition,
                region="front",
                score=75.0
            )
            db.session.add(result)
        db.session.commit()

        response = client.get(f"/api/session/{session.id}/breakdown")
        data = response.get_json()

        # Acne should be average of 90, 80, 80
        acne_score = data["conditions"]["acne"]["score"]
        expected_acne = int((90 + 80 + 80) / 3)
        assert acne_score == expected_acne


class TestApiSessionsSummary:
    """Test /api/sessions/summary endpoint"""

    def test_summary_empty_database(self, client):
        """Test summary endpoint with no data"""
        response = client.get("/api/sessions/summary")
        assert response.status_code == 200
        data = response.get_json()

        assert data["total_sessions"] == 0
        assert data["avg_score"] == 0
        assert data["best_score"] == 0
        assert data["worst_score"] == 0
        assert data["total_conditions_detected"] == 0

    def test_summary_sessions_without_analysis(self, client, db):
        """Test summary with sessions but no analysis"""
        for i in range(3):
            session = PhotoSession(
                session_date=date.today(),
                notes=f"Session {i+1}"
            )
            db.session.add(session)
        db.session.commit()

        response = client.get("/api/sessions/summary")
        assert response.status_code == 200
        data = response.get_json()

        assert data["total_sessions"] == 3
        assert data["avg_score"] == 0
        assert data["total_conditions_detected"] == 0

    def test_summary_with_analysis(self, client, db):
        """Test summary with analyzed sessions"""
        # Create 3 sessions with analysis
        for session_idx in range(3):
            session = PhotoSession(session_date=date.today())
            db.session.add(session)
            db.session.commit()

            # Add analysis for 6 conditions
            base_score = 70 + (session_idx * 5)
            for condition in ["acne", "texture", "dark_spots", "wrinkles", "under_eye", "redness"]:
                result = AnalysisResult(
                    session_id=session.id,
                    condition_name=condition,
                    region="front",
                    score=float(base_score)
                )
                db.session.add(result)
            db.session.commit()

        response = client.get("/api/sessions/summary")
        assert response.status_code == 200
        data = response.get_json()

        assert data["total_sessions"] == 3
        assert data["total_conditions_detected"] == 6
        assert data["avg_score"] > 0
        assert data["best_score"] >= data["avg_score"]
        assert data["worst_score"] <= data["avg_score"]

    def test_summary_calculates_best_worst_scores(self, client, db):
        """Test that best and worst scores are correctly calculated"""
        session = PhotoSession(session_date=date.today())
        db.session.add(session)
        db.session.commit()

        scores = [95, 85, 75, 65, 55, 45]  # Best: 95, Worst: 45, Avg: 70
        for i, score in enumerate(scores):
            condition = ["acne", "texture", "dark_spots", "wrinkles", "under_eye", "redness"][i]
            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition,
                region="front",
                score=float(score)
            )
            db.session.add(result)
        db.session.commit()

        response = client.get("/api/sessions/summary")
        data = response.get_json()

        assert data["best_score"] == 95
        assert data["worst_score"] == 45
        assert data["avg_score"] == 70

    def test_summary_counts_unique_conditions(self, client, db):
        """Test that unique conditions are counted correctly"""
        session1 = PhotoSession(session_date=date.today())
        db.session.add(session1)
        db.session.commit()

        # Add only 3 conditions to first session
        for condition in ["acne", "texture", "dark_spots"]:
            result = AnalysisResult(
                session_id=session1.id,
                condition_name=condition,
                region="front",
                score=75.0
            )
            db.session.add(result)
        db.session.commit()

        response = client.get("/api/sessions/summary")
        data = response.get_json()

        assert data["total_conditions_detected"] == 3

    def test_summary_json_structure(self, client):
        """Test summary response has correct JSON structure"""
        response = client.get("/api/sessions/summary")
        assert response.status_code == 200
        data = response.get_json()

        required_keys = {"total_sessions", "avg_score", "best_score", "worst_score", "total_conditions_detected"}
        assert required_keys.issubset(data.keys())

        # Verify types
        assert isinstance(data["total_sessions"], int)
        assert isinstance(data["avg_score"], int)
        assert isinstance(data["best_score"], int)
        assert isinstance(data["worst_score"], int)
        assert isinstance(data["total_conditions_detected"], int)
