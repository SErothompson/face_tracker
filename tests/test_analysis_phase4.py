import os
import json
from io import BytesIO

import cv2
import numpy as np
import pytest
from PIL import Image

from app.blueprints.analysis.detectors.acne import AcneDetector
from app.blueprints.analysis.detectors.dark_spots import DarkSpotsDetector
from app.blueprints.analysis.detectors.regions import extract_region
from app.blueprints.analysis.detectors.scoring import SkinHealthScorer
from app.blueprints.analysis.detectors.texture import TextureDetector
from app.blueprints.analysis.detectors.undereye import UnderEyeDetector
from app.blueprints.analysis.detectors.wrinkles import WrinklesDetector
from app.blueprints.analysis.engine import AnalysisEngine
from app.models import Photo, PhotoSession, AnalysisResult, SkinCondition
from datetime import date


@pytest.fixture
def sample_roi_rgba():
    """Create a sample ROI with realistic colors."""
    roi = np.zeros((200, 200, 3), dtype=np.uint8)
    # Add some skin-tone color (BGR: B=150, G=130, R=110 is roughly skin tone)
    roi[:, :] = [180, 150, 130]

    # Add some blemishes (red areas)
    cv2.circle(roi, (50, 50), 15, (50, 100, 200), -1)  # Reddish blemish
    cv2.circle(roi, (150, 100), 10, (60, 110, 210), -1)  # Another blemish

    # Add some dark spots
    cv2.circle(roi, (100, 150), 20, (100, 100, 100), -1)  # Dark spot

    return roi


@pytest.fixture
def sample_roi_mask():
    """Create a sample mask."""
    mask = np.zeros((200, 200), dtype=np.uint8)
    cv2.ellipse(mask, (100, 100), (90, 80), 0, 0, 360, 255, -1)
    return mask


class TestAcneDetector:
    """Test AcneDetector functionality."""

    def test_acne_detector_init(self):
        """Test detector initialization."""
        detector = AcneDetector()
        assert detector is not None
        assert detector.min_lesion_area == 10
        assert detector.max_lesion_area == 500

    def test_acne_detector_empty_roi(self):
        """Test detector with empty ROI."""
        detector = AcneDetector()
        empty_roi = np.empty((0, 0, 3), dtype=np.uint8)
        result = detector.detect(empty_roi, None)

        assert result["count"] == 0
        assert result["severity"] == 0
        assert result["areas"] == []
        assert result["centers"] == []

    def test_acne_detector_with_roi(self, sample_roi_rgba, sample_roi_mask):
        """Test detector with sample ROI."""
        detector = AcneDetector()
        result = detector.detect(sample_roi_rgba, sample_roi_mask)

        assert isinstance(result, dict)
        assert "count" in result
        assert "severity" in result
        assert "areas" in result
        assert "centers" in result
        assert 0 <= result["severity"] <= 100

    def test_acne_detector_returns_valid_centers(
        self, sample_roi_rgba, sample_roi_mask
    ):
        """Test that detected lesion centers are valid coordinates."""
        detector = AcneDetector()
        result = detector.detect(sample_roi_rgba, sample_roi_mask)

        if result["count"] > 0:
            for cx, cy in result["centers"]:
                assert 0 <= cx < sample_roi_rgba.shape[1]
                assert 0 <= cy < sample_roi_rgba.shape[0]


class TestDarkSpotsDetector:
    """Test DarkSpotsDetector functionality."""

    def test_dark_spots_detector_init(self):
        """Test detector initialization."""
        detector = DarkSpotsDetector()
        assert detector is not None
        assert detector.neighborhood_size == 25
        assert detector.darkness_threshold == 20

    def test_dark_spots_detector_empty_roi(self):
        """Test detector with empty ROI."""
        detector = DarkSpotsDetector()
        empty_roi = np.empty((0, 0, 3), dtype=np.uint8)
        result = detector.detect(empty_roi, None)

        assert result["count"] == 0
        assert result["severity"] == 0
        assert result["total_area"] == 0

    def test_dark_spots_detector_with_roi(self, sample_roi_rgba, sample_roi_mask):
        """Test detector with sample ROI."""
        detector = DarkSpotsDetector()
        result = detector.detect(sample_roi_rgba, sample_roi_mask)

        assert isinstance(result, dict)
        assert "count" in result
        assert "severity" in result
        assert "total_area" in result
        assert "mean_darkness" in result
        assert 0 <= result["severity"] <= 100
        assert 0 <= result["mean_darkness"] <= 255


class TestWrinklesDetector:
    """Test WrinklesDetector functionality."""

    def test_wrinkles_detector_init(self):
        """Test detector initialization."""
        detector = WrinklesDetector()
        assert detector is not None
        assert detector.scales == (1, 2, 3, 4)

    def test_wrinkles_detector_empty_roi(self):
        """Test detector with empty ROI."""
        detector = WrinklesDetector()
        empty_roi = np.empty((0, 0, 3), dtype=np.uint8)
        result = detector.detect(empty_roi, None)

        assert result["wrinkle_density"] == 0
        assert result["severity"] == 0
        assert result["ridge_pixels"] == 0

    def test_wrinkles_detector_with_roi(self, sample_roi_rgba, sample_roi_mask):
        """Test detector with sample ROI."""
        detector = WrinklesDetector()
        result = detector.detect(sample_roi_rgba, sample_roi_mask)

        assert isinstance(result, dict)
        assert "wrinkle_density" in result
        assert "severity" in result
        assert "ridge_pixels" in result
        assert "max_ridge_strength" in result
        assert 0 <= result["severity"] <= 100
        assert 0 <= result["wrinkle_density"] <= 1


class TestTextureDetector:
    """Test TextureDetector functionality."""

    def test_texture_detector_init(self):
        """Test detector initialization."""
        detector = TextureDetector()
        assert detector is not None

    def test_texture_detector_empty_roi(self):
        """Test detector with empty ROI."""
        detector = TextureDetector()
        empty_roi = np.empty((0, 0, 3), dtype=np.uint8)
        result = detector.detect(empty_roi, None)

        assert result["severity"] == 0
        assert result["roughness_score"] == 0

    def test_texture_detector_with_roi(self, sample_roi_rgba, sample_roi_mask):
        """Test detector with sample ROI."""
        detector = TextureDetector()
        result = detector.detect(sample_roi_rgba, sample_roi_mask)

        assert isinstance(result, dict)
        assert "laplacian_variance" in result
        assert "severity" in result
        assert "roughness_score" in result
        assert 0 <= result["severity"] <= 100


class TestUnderEyeDetector:
    """Test UnderEyeDetector functionality."""

    def test_undereye_detector_init(self):
        """Test detector initialization."""
        detector = UnderEyeDetector()
        assert detector is not None

    def test_undereye_detector_empty_roi(self):
        """Test detector with empty ROI."""
        detector = UnderEyeDetector()
        empty_roi = np.empty((0, 0, 3), dtype=np.uint8)
        result = detector.detect(empty_roi, None)

        assert result["darkness_score"] == 0
        assert result["severity"] == 0

    def test_undereye_detector_with_roi(self, sample_roi_rgba, sample_roi_mask):
        """Test detector with sample ROI."""
        detector = UnderEyeDetector()
        result = detector.detect(sample_roi_rgba, sample_roi_mask)

        assert isinstance(result, dict)
        assert "darkness_score" in result
        assert "puffiness_score" in result
        assert "severity" in result
        assert "color_difference" in result
        assert 0 <= result["severity"] <= 100


class TestSkinHealthScorer:
    """Test SkinHealthScorer functionality."""

    def test_normalize_condition_score(self):
        """Test score normalization."""
        # Raw score of 0 (no condition) should normalize to 100 (healthiest)
        normalized = SkinHealthScorer.normalize_condition_score(0, "acne")
        assert normalized == 100

        # Raw score of 100 (severe condition) should normalize to 0
        normalized = SkinHealthScorer.normalize_condition_score(100, "acne")
        assert normalized == 0

        # Raw score of 50 (moderate) should normalize to 50
        normalized = SkinHealthScorer.normalize_condition_score(50, "acne")
        assert normalized == 50

    def test_calculate_overall_score(self):
        """Test overall score calculation."""
        condition_scores = {
            "acne": 80,
            "texture": 70,
            "dark_spots": 90,
            "wrinkles": 60,
            "under_eye": 75,
        }
        overall = SkinHealthScorer.calculate_overall_score(condition_scores)
        assert 0 <= overall <= 100
        # Should be weighted average around 74-75
        assert 70 <= overall <= 80

    def test_calculate_overall_score_partial(self):
        """Test overall score with partial conditions."""
        condition_scores = {
            "acne": 80,
            "texture": 70,
        }
        overall = SkinHealthScorer.calculate_overall_score(condition_scores)
        assert 0 <= overall <= 100

    def test_score_to_severity_label(self):
        """Test score to label conversion."""
        assert "Excellent" in SkinHealthScorer.score_to_severity_label(85)
        assert "Good" in SkinHealthScorer.score_to_severity_label(70)
        assert "Fair" in SkinHealthScorer.score_to_severity_label(45)
        assert "Poor" in SkinHealthScorer.score_to_severity_label(25)
        assert "Critical" in SkinHealthScorer.score_to_severity_label(10)

    def test_score_to_badge_color(self):
        """Test score to color conversion."""
        assert SkinHealthScorer.score_to_badge_color(80) == "success"
        assert SkinHealthScorer.score_to_badge_color(50) == "warning"
        assert SkinHealthScorer.score_to_badge_color(30) == "danger"


class TestAnalysisEngine:
    """Test AnalysisEngine functionality."""

    def test_analysis_engine_init(self):
        """Test engine initialization."""
        engine = AnalysisEngine()
        assert engine is not None
        assert engine.face_detector is not None
        assert engine.acne_detector is not None
        assert engine.dark_spots_detector is not None

    def test_analysis_engine_analyze_photo_with_no_face(self):
        """Test analysis with image containing no face."""
        engine = AnalysisEngine()
        # Blank image should have no face
        blank_image = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine.analyze_photo(None, blank_image)
        # No face detected, should return None
        assert result is None

    def test_analysis_engine_close(self):
        """Test engine cleanup."""
        engine = AnalysisEngine()
        engine.close()  # Should not raise
        assert True


class TestAnalysisRoutes:
    """Test analysis blueprint routes."""

    def test_run_analysis_missing_session(self, client):
        """Test analysis on non-existent session."""
        response = client.post("/analysis/run/9999", follow_redirects=True)
        assert response.status_code == 404

    def test_analysis_results_missing_session(self, client):
        """Test results page for non-existent session."""
        response = client.get("/analysis/results/9999")
        assert response.status_code == 404

    def test_analysis_results_no_results_yet(self, client, db):
        """Test results page when no analysis run yet."""
        session = PhotoSession(session_date=date(2026, 3, 17))
        db.session.add(session)
        db.session.commit()

        response = client.get(f"/analysis/results/{session.id}", follow_redirects=True)
        assert response.status_code == 200
        assert b"No analysis results" in response.data or b"Session" in response.data

    def test_run_analysis_with_missing_photo_file(self, client, db):
        """Test analysis when photo file is missing."""
        session = PhotoSession(session_date=date(2026, 3, 17))
        db.session.add(session)
        db.session.flush()

        photo = Photo(
            session_id=session.id,
            angle="front",
            filename="front.jpg",
            filepath="nonexistent/front.jpg",
        )
        db.session.add(photo)
        db.session.commit()

        response = client.post(
            f"/analysis/run/{session.id}", follow_redirects=True
        )
        assert response.status_code == 200
        assert b"not found" in response.data or b"error" in response.data.lower()


class TestAnalysisIntegration:
    """Integration tests for analysis workflow."""

    def test_analysis_results_page_displays_conditions(self, client, db):
        """Test that results page displays condition cards."""
        session = PhotoSession(session_date=date(2026, 3, 17))
        db.session.add(session)
        db.session.flush()

        # Create fake analysis results (one per condition type)
        for condition_name in ["acne", "texture", "dark_spots", "wrinkles", "under_eye"]:
            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition_name,
                region="front",
                score=75,
                details_json=json.dumps({}),
            )
            db.session.add(result)

        # Create fake conditions
        for condition_type in ["acne", "texture", "dark_spots", "wrinkles", "under_eye"]:
            condition = SkinCondition(
                session_id=session.id,
                condition_type=condition_type,
                severity="good",
                description=f"{condition_type} is good",
                search_results_json=json.dumps({}),
            )
            db.session.add(condition)
        db.session.commit()

        response = client.get(f"/analysis/results/{session.id}")
        assert response.status_code == 200
        assert b"Acne" in response.data
        assert b"Texture" in response.data
        assert b"Dark Spots" in response.data
        assert b"Wrinkles" in response.data
        assert b"Under-Eye" in response.data
        assert b"75" in response.data  # Overall score
