import json
from typing import Optional

import cv2
import numpy as np

from app.blueprints.analysis.detectors.acne import AcneDetector
from app.blueprints.analysis.detectors.dark_spots import DarkSpotsDetector
from app.blueprints.analysis.detectors.face_mesh import FaceMeshDetector
from app.blueprints.analysis.detectors.regions import extract_all_regions, extract_region
from app.blueprints.analysis.detectors.redness import RednessDetector
from app.blueprints.analysis.detectors.scoring import SkinHealthScorer
from app.blueprints.analysis.detectors.texture import TextureDetector
from app.blueprints.analysis.detectors.undereye import UnderEyeDetector
from app.blueprints.analysis.detectors.wrinkles import WrinklesDetector
from app.models import AnalysisResult, Photo, SkinCondition
from app.extensions import db

# Which detectors to run for each photo angle when face landmarks aren't available.
# Maps angle -> list of condition names to analyze.
_FALLBACK_DETECTORS = {
    "left": ["acne", "dark_spots", "texture", "redness", "wrinkles"],
    "right": ["acne", "dark_spots", "texture", "redness", "wrinkles"],
    "three_quarter_left": ["acne", "dark_spots", "texture", "redness", "wrinkles"],
    "three_quarter_right": ["acne", "dark_spots", "texture", "redness", "wrinkles"],
    "cheek_left": ["acne", "dark_spots", "texture", "redness"],
    "cheek_right": ["acne", "dark_spots", "texture", "redness"],
    "under_eye_left": ["under_eye"],
    "under_eye_right": ["under_eye"],
    "chin_up": ["acne", "texture", "redness"],
    "top_down": ["texture", "dark_spots"],
}


class AnalysisEngine:
    """
    Orchestrates the entire skin analysis pipeline:
    1. Load photo
    2. Detect face landmarks
    3. Extract facial regions
    4. Run 6 condition detectors
    5. Score and aggregate results
    6. Save to database
    """

    def __init__(self):
        """Initialize all detectors."""
        self.face_detector = FaceMeshDetector()
        self.acne_detector = AcneDetector()
        self.dark_spots_detector = DarkSpotsDetector()
        self.wrinkles_detector = WrinklesDetector()
        self.texture_detector = TextureDetector()
        self.undereye_detector = UnderEyeDetector()
        self.redness_detector = RednessDetector()

    def analyze_photo(self, photo: Photo, image_bgr) -> Optional[dict]:
        """
        Run complete analysis on a photo.

        Args:
            photo: Photo model instance
            image_bgr: OpenCV BGR image (already loaded)

        Returns:
            Dict with overall_score and condition results, or None if analysis fails
        """
        # Step 1: Detect face landmarks
        landmarks = self.face_detector.detect(image_bgr)
        if landmarks is None:
            return self._analyze_fallback(photo, image_bgr)

        # Step 2: Extract facial regions
        regions = extract_all_regions(image_bgr, landmarks)
        if not regions:
            return None

        # Step 3: Run detectors
        condition_results = {}

        # Acne (run on cheeks and chin)
        acne_scores = []
        for region_name in ["left_cheek", "right_cheek", "chin"]:
            if region_name in regions:
                roi, mask, bbox = regions[region_name]
                result = self.acne_detector.detect(roi, mask)
                acne_scores.append(result["severity"])
        acne_severity = int(sum(acne_scores) / len(acne_scores)) if acne_scores else 0
        condition_results["acne"] = {
            "severity": acne_severity,
            "details": {"regions": ["cheeks", "chin"], "scores": acne_scores},
        }

        # Dark spots (run on all main regions)
        dark_spot_scores = []
        for region_name in [
            "forehead",
            "left_cheek",
            "right_cheek",
            "chin",
        ]:
            if region_name in regions:
                roi, mask, bbox = regions[region_name]
                result = self.dark_spots_detector.detect(roi, mask)
                dark_spot_scores.append(result["severity"])
        dark_spots_severity = (
            int(sum(dark_spot_scores) / len(dark_spot_scores))
            if dark_spot_scores
            else 0
        )
        condition_results["dark_spots"] = {
            "severity": dark_spots_severity,
            "details": {"regions": ["face"], "scores": dark_spot_scores},
        }

        # Wrinkles (run on forehead and around eyes)
        wrinkle_scores = []
        for region_name in ["forehead", "crows_feet_left", "crows_feet_right"]:
            if region_name in regions:
                roi, mask, bbox = regions[region_name]
                result = self.wrinkles_detector.detect(roi, mask)
                wrinkle_scores.append(result["severity"])
        wrinkles_severity = (
            int(sum(wrinkle_scores) / len(wrinkle_scores)) if wrinkle_scores else 0
        )
        condition_results["wrinkles"] = {
            "severity": wrinkles_severity,
            "details": {
                "regions": ["forehead", "crow's feet"],
                "scores": wrinkle_scores,
            },
        }

        # Texture (run on cheeks and nose)
        texture_scores = []
        for region_name in ["left_cheek", "right_cheek", "nose"]:
            if region_name in regions:
                roi, mask, bbox = regions[region_name]
                result = self.texture_detector.detect(roi, mask)
                texture_scores.append(result["severity"])
        texture_severity = (
            int(sum(texture_scores) / len(texture_scores)) if texture_scores else 0
        )
        condition_results["texture"] = {
            "severity": texture_severity,
            "details": {"regions": ["cheeks", "nose"], "scores": texture_scores},
        }

        # Under-eye (run on under_eye regions)
        undereye_scores = []
        for region_name in ["under_eye_left", "under_eye_right"]:
            if region_name in regions:
                roi, mask, bbox = regions[region_name]
                result = self.undereye_detector.detect(roi, mask)
                undereye_scores.append(result["severity"])
        undereye_severity = (
            int(sum(undereye_scores) / len(undereye_scores)) if undereye_scores else 0
        )
        condition_results["under_eye"] = {
            "severity": undereye_severity,
            "details": {"sides": ["left", "right"], "scores": undereye_scores},
        }

        # Redness (run on face regions - cheeks, nose, chin indicate inflammation)
        redness_scores = []
        for region_name in ["left_cheek", "right_cheek", "nose", "chin"]:
            if region_name in regions:
                roi, mask, bbox = regions[region_name]
                result = self.redness_detector.detect(roi, mask)
                redness_scores.append(result["severity"])
        redness_severity = (
            int(sum(redness_scores) / len(redness_scores)) if redness_scores else 0
        )
        condition_results["redness"] = {
            "severity": redness_severity,
            "details": {"regions": ["cheeks", "nose", "chin"], "scores": redness_scores},
        }

        # Step 4: Normalize and score
        normalized_scores = {
            condition: SkinHealthScorer.normalize_condition_score(
                results["severity"], condition
            )
            for condition, results in condition_results.items()
        }
        overall_score = SkinHealthScorer.calculate_overall_score(normalized_scores)

        return {
            "overall_score": overall_score,
            "condition_scores": normalized_scores,
            "condition_details": condition_results,
            "landmarks_detected": len(landmarks),
            "regions_extracted": len(regions),
        }

    def _center_crop(self, image_bgr):
        """Extract the center 60% of the image as an ROI with a full mask."""
        h, w = image_bgr.shape[:2]
        margin_x = int(w * 0.2)
        margin_y = int(h * 0.2)
        roi = image_bgr[margin_y:h - margin_y, margin_x:w - margin_x].copy()
        mask = np.full(roi.shape[:2], 255, dtype=np.uint8)
        return roi, mask

    def _analyze_fallback(self, photo: Photo, image_bgr) -> Optional[dict]:
        """
        Fallback analysis for photos where face landmarks can't be detected
        (profiles, close-ups, unusual angles). Runs relevant detectors on
        the center crop of the image.
        """
        detectors_to_run = _FALLBACK_DETECTORS.get(photo.angle) if photo else None
        if not detectors_to_run:
            return None

        roi, mask = self._center_crop(image_bgr)
        condition_results = {}

        detector_map = {
            "acne": self.acne_detector,
            "dark_spots": self.dark_spots_detector,
            "wrinkles": self.wrinkles_detector,
            "texture": self.texture_detector,
            "under_eye": self.undereye_detector,
            "redness": self.redness_detector,
        }

        for condition_name in detectors_to_run:
            detector = detector_map.get(condition_name)
            if detector:
                result = detector.detect(roi, mask)
                condition_results[condition_name] = {
                    "severity": result["severity"],
                    "details": {"regions": [photo.angle], "scores": [result["severity"]]},
                }

        if not condition_results:
            return None

        normalized_scores = {
            condition: SkinHealthScorer.normalize_condition_score(
                results["severity"], condition
            )
            for condition, results in condition_results.items()
        }
        overall_score = SkinHealthScorer.calculate_overall_score(normalized_scores)

        return {
            "overall_score": overall_score,
            "condition_scores": normalized_scores,
            "condition_details": condition_results,
            "landmarks_detected": 0,
            "regions_extracted": 0,
        }

    def save_analysis(self, session, photo, analysis_result: dict):
        """
        Save analysis results to database.

        Args:
            session: PhotoSession instance
            photo: Photo instance
            analysis_result: Dict from analyze_photo()
        """
        # Save individual condition results for each region
        for condition_name, results in analysis_result["condition_details"].items():
            # Save one AnalysisResult per condition (we'll aggregate details in the JSON)
            score = analysis_result["condition_scores"].get(condition_name, 0)

            result = AnalysisResult(
                session_id=session.id,
                condition_name=condition_name,
                region=photo.angle,  # Use photo angle as region (front, left, right)
                score=score,
                details_json=json.dumps(results.get("details", {})),
            )
            db.session.add(result)

        # Save individual condition severity records
        for condition_name, score in analysis_result["condition_scores"].items():
            # Convert name format (snake_case -> label)
            label = condition_name.replace("_", " ").title()
            severity_label = SkinHealthScorer.score_to_severity_label(score)

            condition = SkinCondition(
                session_id=session.id,
                condition_type=condition_name,
                severity=severity_label.lower(),
                description=f"{label} severity: {severity_label}",
                search_results_json=json.dumps({}),  # Populated in Phase 8
            )
            db.session.add(condition)

        db.session.commit()

    def close(self):
        """Clean up DetectorFactory resources."""
        self.face_detector.close()
