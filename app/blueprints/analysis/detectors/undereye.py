import cv2
import numpy as np


class UnderEyeDetector:
    """
    Detects under-eye bags, dark circles, and puffiness using color and edge analysis.

    Dark circles are regions with lower luminance and higher red-channel deviation.
    Puffiness shows as swelling/edge prominence around eye area.
    """

    def __init__(self, edge_threshold=30):
        """
        Initialize under-eye detector.

        Args:
            edge_threshold: Threshold for edge detection (Canny)
        """
        self.edge_threshold = edge_threshold

    def detect(self, roi_bgr: np.ndarray, roi_mask: np.ndarray, cheek_roi: np.ndarray = None) -> dict:
        """
        Detect under-eye issues.

        Args:
            roi_bgr: Cropped BGR image of under-eye region
            roi_mask: Binary mask (255 where region is active, 0 elsewhere)
            cheek_roi: Optional reference cheek ROI for color comparison

        Returns:
            Dict with:
            - darkness_score: How dark the under-eye area is (0-100)
            - puffiness_score: How puffy/swollen (0-100)
            - severity: Overall under-eye severity (0-100)
            - color_difference: LAB a-channel deviation from normal
        """
        if roi_bgr.size == 0:
            return {
                "darkness_score": 0,
                "puffiness_score": 0,
                "severity": 0,
                "color_difference": 0,
            }

        # Convert to LAB for color analysis
        lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        a_channel = lab[:, :, 1]

        # Darkness: low L (luminance) values
        # Healthy under-eye: L ~100-140
        # Dark circles: L < 80
        mean_l = np.mean(l_channel)
        darkness_score = max(0, (140 - mean_l)) / 1.4  # Normalize to 0-100
        darkness_score = min(darkness_score, 100)

        # Color deviation: a-channel (red-green axis)
        # Dark circles often have reddish tint (higher a-value)
        # Reference: normal skin a ~130
        mean_a = np.mean(a_channel)
        color_difference = int(mean_a - 130)  # Can be negative or positive

        # Puffiness: detect edges around eye area
        # Puffy eyes show stronger edge gradients
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, self.edge_threshold, self.edge_threshold * 2)

        if roi_mask is not None:
            edges = edges * (roi_mask > 0).astype(np.uint8)

        edge_density = np.sum(edges > 0) / (roi_bgr.shape[0] * roi_bgr.shape[1]) if roi_bgr.size > 0 else 0
        puffiness_score = min(edge_density * 200, 100)  # Normalize to 0-100

        # Overall severity: combination of darkness and puffiness
        severity = int((darkness_score * 0.6) + (puffiness_score * 0.4))

        return {
            "darkness_score": int(darkness_score),
            "puffiness_score": int(puffiness_score),
            "severity": min(severity, 100),
            "color_difference": color_difference,
        }
