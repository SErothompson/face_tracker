import pytest
from datetime import date, timedelta
import numpy as np
import cv2

from app.models import PhotoSession, Photo, AnalysisResult, SkinCondition, ComparisonResult
from app.blueprints.comparison.engine import ComparisonEngine


class TestComparisonEngine:
    """Test ComparisonEngine methods"""

    def test_compute_ssim_identical_images(self):
        """Test SSIM score for identical images"""
        # Create identical image
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[:, :] = (128, 128, 128)

        ssim_score = ComparisonEngine.compute_ssim(image, image)

        assert ssim_score > 0.99  # Should be nearly 1.0 for identical images

    def test_compute_ssim_different_images(self):
        """Test SSIM score for completely different images"""
        # Create two very different images
        image_a = np.zeros((100, 100, 3), dtype=np.uint8)
        image_a[:, :] = (0, 0, 0)  # Black

        image_b = np.ones((100, 100, 3), dtype=np.uint8) * 255
        image_b[:, :] = (255, 255, 255)  # White

        ssim_score = ComparisonEngine.compute_ssim(image_a, image_b)

        assert ssim_score < 0.5  # Should be low for very different images
        assert 0 <= ssim_score <= 1  # Should be in valid range

    def test_compute_ssim_similar_images(self):
        """Test SSIM score for slightly modified images"""
        # Create base image
        image_a = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # Create slightly modified image (90% same, 10% different)
        image_b = image_a.copy()
        image_b[0:10, 0:10] = (200, 100, 50)  # Change small region

        ssim_score = ComparisonEngine.compute_ssim(image_a, image_b)

        assert 0.5 < ssim_score < 0.999  # Should be high (small region changed)
        assert 0 <= ssim_score <= 1

    def test_compute_ssim_different_dimensions(self):
        """Test SSIM handles different image dimensions"""
        image_a = np.ones((100, 100, 3), dtype=np.uint8) * 128
        image_b = np.ones((150, 150, 3), dtype=np.uint8) * 128

        # Should not raise error
        ssim_score = ComparisonEngine.compute_ssim(image_a, image_b)

        assert isinstance(ssim_score, float)
        assert 0 <= ssim_score <= 1

    def test_generate_diff_heatmap_returns_image(self):
        """Test diff heatmap generation returns valid image"""
        image_a = np.ones((100, 100, 3), dtype=np.uint8) * 128
        image_b = image_a.copy()
        image_b[0:20, 0:20] = (200, 100, 50)

        heatmap = ComparisonEngine.generate_diff_heatmap(image_a, image_b)

        assert heatmap is not None
        assert isinstance(heatmap, np.ndarray)
        assert heatmap.shape == (100, 100, 3)
        assert heatmap.dtype == np.uint8

    def test_generate_diff_heatmap_different_dimensions(self):
        """Test diff heatmap handles different dimensions"""
        image_a = np.ones((100, 100, 3), dtype=np.uint8) * 128
        image_b = np.ones((150, 150, 3), dtype=np.uint8) * 128

        # Should resize and process
        heatmap = ComparisonEngine.generate_diff_heatmap(image_a, image_b)

        assert heatmap is not None
        assert heatmap.shape[0] == 100  # Uses smaller dimension
        assert heatmap.shape[1] == 100

    def test_heatmap_to_png_bytes(self):
        """Test heatmap conversion to PNG bytes"""
        heatmap = np.ones((100, 100, 3), dtype=np.uint8) * 128

        png_bytes = ComparisonEngine.heatmap_to_png_bytes(heatmap)

        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 0
        # PNG files start with specific magic bytes
        assert png_bytes[:4] == b'\x89PNG'

    def test_calculate_condition_deltas_no_analysis(self, db):
        """Test deltas with sessions lacking analysis"""
        session_a = PhotoSession(session_date=date.today())
        session_b = PhotoSession(session_date=date.today() + timedelta(days=7))

        db.session.add_all([session_a, session_b])
        db.session.commit()

        deltas = ComparisonEngine.calculate_condition_deltas(session_a.id, session_b.id, "front")

        assert deltas == {}

    def test_calculate_condition_deltas_with_analysis(self, db):
        """Test delta calculation with actual analysis"""
        session_a = PhotoSession(session_date=date.today())
        session_b = PhotoSession(session_date=date.today() + timedelta(days=7))

        db.session.add_all([session_a, session_b])
        db.session.commit()

        # Add analysis results
        for condition_name, score_a, score_b in [
            ("acne", 80, 85),
            ("texture", 75, 70),
            ("dark_spots", 70, 75)
        ]:
            result_a = AnalysisResult(
                session_id=session_a.id,
                condition_name=condition_name,
                region="front",
                score=float(score_a)
            )
            result_b = AnalysisResult(
                session_id=session_b.id,
                condition_name=condition_name,
                region="front",
                score=float(score_b)
            )
            db.session.add_all([result_a, result_b])

        db.session.commit()

        deltas = ComparisonEngine.calculate_condition_deltas(session_a.id, session_b.id, "front")

        assert "acne" in deltas
        assert deltas["acne"]["score_a"] == 80
        assert deltas["acne"]["score_b"] == 85
        assert deltas["acne"]["delta"] == 5
        assert deltas["acne"]["improved"] is True

        assert "texture" in deltas
        assert deltas["texture"]["delta"] == -5
        assert deltas["texture"]["improved"] is False

    def test_generate_summary_no_analysis(self, db):
        """Test summary with no analysis data"""
        session_a = PhotoSession(session_date=date.today())
        session_b = PhotoSession(session_date=date.today() + timedelta(days=7))

        db.session.add_all([session_a, session_b])
        db.session.commit()

        summary = ComparisonEngine.generate_summary(session_a.id, session_b.id, "front")

        assert summary["overall_delta"] == 0
        assert summary["status"] == "No data"

    def test_generate_summary_improved(self, db):
        """Test summary when skin improved"""
        session_a = PhotoSession(session_date=date.today())
        session_b = PhotoSession(session_date=date.today() + timedelta(days=7))

        db.session.add_all([session_a, session_b])
        db.session.commit()

        # Add improvements
        conditions = ["acne", "texture", "dark_spots", "wrinkles", "redness", "under_eye"]
        for condition in conditions:
            result_a = AnalysisResult(
                session_id=session_a.id,
                condition_name=condition,
                region="front",
                score=70.0
            )
            result_b = AnalysisResult(
                session_id=session_b.id,
                condition_name=condition,
                region="front",
                score=80.0  # 10 point improvement
            )
            db.session.add_all([result_a, result_b])

        db.session.commit()

        summary = ComparisonEngine.generate_summary(session_a.id, session_b.id, "front")

        assert summary["overall_delta"] == 10
        assert summary["status"] == "Improved"
        assert summary["improved_count"] == 6
        assert summary["regressed_count"] == 0
        assert summary["days_span"] == 7

    def test_interpret_ssim_score_near_identical(self):
        """Test SSIM interpretation for nearly identical images"""
        category, description = ComparisonEngine.interpret_ssim_score(0.96)

        assert category == "Nearly Identical"
        assert "minimal" in description.lower()

    def test_interpret_ssim_score_very_similar(self):
        """Test SSIM interpretation for very similar images"""
        category, description = ComparisonEngine.interpret_ssim_score(0.90)

        assert category == "Very Similar"
        assert "slight" in description.lower()

    def test_interpret_ssim_score_similar(self):
        """Test SSIM interpretation for similar images"""
        category, description = ComparisonEngine.interpret_ssim_score(0.80)

        assert category == "Similar"
        assert "noticeable" in description.lower()

    def test_interpret_ssim_score_moderate_change(self):
        """Test SSIM interpretation for moderate changes"""
        category, description = ComparisonEngine.interpret_ssim_score(0.70)

        assert category == "Moderate Change"

    def test_interpret_ssim_score_significant_change(self):
        """Test SSIM interpretation for significant changes"""
        category, description = ComparisonEngine.interpret_ssim_score(0.60)

        assert category == "Significant Change"


class TestComparisonRoutes:
    """Test comparison blueprint routes"""

    def test_view_results_nonexistent_sessions(self, client):
        """Test results page with non-existent sessions"""
        response = client.get("/comparison/result/9999/8888")

        assert response.status_code == 404

    def test_get_diff_image_nonexistent_sessions(self, client):
        """Test diff image endpoint with non-existent sessions"""
        response = client.get("/comparison/diff-image/9999/8888/front")

        assert response.status_code == 404
