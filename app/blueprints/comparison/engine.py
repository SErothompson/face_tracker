import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from skimage import exposure
import io
from PIL import Image
from datetime import datetime

from app.models import PhotoSession, Photo, AnalysisResult


class ComparisonEngine:
    """
    Engine for comparing two PhotoSession objects.
    Computes SSIM scores, generates diff heatmaps, and calculates condition deltas.
    """

    def __init__(self):
        pass

    @staticmethod
    def compute_ssim(image_a, image_b):
        """
        Compute Structural Similarity Index (SSIM) between two images.

        Args:
            image_a: BGR image array from OpenCV
            image_b: BGR image array from OpenCV

        Returns:
            float: SSIM score 0-1 (1 = identical, 0 = completely different)
        """
        # Convert BGR to grayscale for SSIM computation
        gray_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2GRAY)

        # Resize to same dimensions if different
        if gray_a.shape != gray_b.shape:
            height = min(gray_a.shape[0], gray_b.shape[0])
            width = min(gray_a.shape[1], gray_b.shape[1])
            gray_a = cv2.resize(gray_a, (width, height))
            gray_b = cv2.resize(gray_b, (width, height))

        # Compute SSIM
        score, _ = ssim(gray_a, gray_b, full=True)
        return float(score)

    @staticmethod
    def generate_diff_heatmap(image_a, image_b):
        """
        Generate a visual diff heatmap showing differences between two images.

        Args:
            image_a: BGR image array (baseline)
            image_b: BGR image array (comparison)

        Returns:
            numpy array: BGR image with diff overlay (red=different, green=similar)
        """
        # Resize to matching dimensions
        if image_a.shape != image_b.shape:
            height = min(image_a.shape[0], image_b.shape[0])
            width = min(image_a.shape[1], image_b.shape[1])
            image_a = cv2.resize(image_a, (width, height))
            image_b = cv2.resize(image_b, (width, height))

        # Compute absolute difference
        diff = cv2.absdiff(image_a, image_b)

        # Convert to HSV-like heatmap: use intensity of difference
        # High difference = red, low difference = green
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        # Normalize to 0-255
        normalized_diff = cv2.normalize(gray_diff, None, 0, 255, cv2.NORM_MINMAX)

        # Create heatmap: green (low diff) to red (high diff)
        heatmap = np.zeros_like(image_a)
        heatmap[:, :, 2] = normalized_diff  # Red channel = difference intensity
        heatmap[:, :, 1] = 255 - normalized_diff  # Green channel = inverse (green for similar)
        heatmap[:, :, 0] = 0  # Blue channel = 0

        # Blend with original image_a for context (70% heatmap, 30% original)
        result = cv2.addWeighted(heatmap, 0.7, image_a, 0.3, 0)

        return result.astype(np.uint8)

    @staticmethod
    def heatmap_to_png_bytes(heatmap):
        """
        Convert heatmap numpy array to PNG bytes for serving as image.

        Args:
            heatmap: numpy array (BGR)

        Returns:
            bytes: PNG encoded image
        """
        # Convert BGR to RGB for PIL
        rgb_heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        pil_image = Image.fromarray(rgb_heatmap)

        # Encode to PNG bytes
        png_bytes = io.BytesIO()
        pil_image.save(png_bytes, format="PNG")
        png_bytes.seek(0)

        return png_bytes.getvalue()

    @staticmethod
    def calculate_condition_deltas(session_a_id, session_b_id, angle):
        """
        Calculate score deltas for each condition between two sessions.

        Args:
            session_a_id: Baseline session ID
            session_b_id: Comparison session ID
            angle: Photo angle to compare ("front", "left", "right")

        Returns:
            dict: {condition_name: {"score_a": X, "score_b": Y, "delta": Z, "improved": bool}}
        """
        # Query analysis results for both sessions, specific angle
        results_a = AnalysisResult.query.filter_by(
            session_id=session_a_id,
            region=angle
        ).all()

        results_b = AnalysisResult.query.filter_by(
            session_id=session_b_id,
            region=angle
        ).all()

        # Build score maps
        scores_a = {r.condition_name: r.score for r in results_a}
        scores_b = {r.condition_name: r.score for r in results_b}

        # Calculate deltas
        deltas = {}
        all_conditions = set(scores_a.keys()) | set(scores_b.keys())

        for condition in all_conditions:
            score_a = scores_a.get(condition, 0)
            score_b = scores_b.get(condition, 0)
            delta = score_b - score_a

            deltas[condition] = {
                "score_a": int(score_a),
                "score_b": int(score_b),
                "delta": int(delta),
                "improved": delta > 0
            }

        return deltas

    @staticmethod
    def generate_summary(session_a_id, session_b_id, angle):
        """
        Generate overall summary of comparison between two sessions.

        Args:
            session_a_id: Baseline session ID
            session_b_id: Comparison session ID
            angle: Photo angle ("front", "left", "right")

        Returns:
            dict: Summary with overall_delta, status, improved_count, regressed_count, days_span
        """
        # Get both sessions
        session_a = PhotoSession.query.get(session_a_id)
        session_b = PhotoSession.query.get(session_b_id)

        if not session_a or not session_b:
            return {}

        # Calculate deltas
        deltas = ComparisonEngine.calculate_condition_deltas(session_a_id, session_b_id, angle)

        if not deltas:
            return {
                "overall_delta": 0,
                "status": "No data",
                "improved_count": 0,
                "regressed_count": 0,
                "days_span": 0
            }

        # Calculate overall stats
        delta_values = [d["delta"] for d in deltas.values()]
        overall_delta = int(sum(delta_values) / len(delta_values)) if delta_values else 0

        improved_count = sum(1 for d in deltas.values() if d["improved"])
        regressed_count = sum(1 for d in deltas.values() if not d["improved"] and d["delta"] != 0)

        # Determine status
        if overall_delta > 5:
            status = "Improved"
        elif overall_delta < -5:
            status = "Regressed"
        else:
            status = "Stable"

        # Calculate days between sessions
        date_a = session_a.session_date
        date_b = session_b.session_date
        days_span = abs((date_b - date_a).days)

        return {
            "overall_delta": overall_delta,
            "status": status,
            "improved_count": improved_count,
            "regressed_count": regressed_count,
            "days_span": days_span
        }

    @staticmethod
    def interpret_ssim_score(ssim_score):
        """
        Interpret SSIM score and return human-readable description.

        Args:
            ssim_score: Float 0-1

        Returns:
            tuple: (category, description)
        """
        if ssim_score >= 0.95:
            return ("Nearly Identical", "Minimal changes detected. Your skin appears very similar.")
        elif ssim_score >= 0.85:
            return ("Very Similar", "Slight improvements visible. Keep up your routine!")
        elif ssim_score >= 0.75:
            return ("Similar", "Noticeable improvements. Your regimen is working!")
        elif ssim_score >= 0.65:
            return ("Moderate Change", "Significant changes detected. Check your condition scores.")
        else:
            return ("Significant Change", "Major improvements or changes. Review your analysis.")
