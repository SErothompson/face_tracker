import cv2
import numpy as np


class RednessDetector:
    """
    Detects skin redness, inflammation, and erythema using LAB color analysis.

    Redness indicates inflammation, rosacea, or irritation.
    Uses LAB a-channel (red-green axis) and intensity variations.
    """

    def __init__(self, redness_threshold=140, min_area=20):
        """
        Initialize redness detector.

        Args:
            redness_threshold: LAB a-channel threshold (values > threshold = reddish)
            min_area: Minimum pixel area for a red region to count
        """
        self.redness_threshold = redness_threshold
        self.min_area = min_area

    def detect(self, roi_bgr: np.ndarray, roi_mask: np.ndarray) -> dict:
        """
        Detect redness in a region of interest.

        Args:
            roi_bgr: Cropped BGR image of a facial region
            roi_mask: Binary mask (255 where region is active, 0 elsewhere)

        Returns:
            Dict with:
            - redness_coverage: Percentage of region that is red (0-100)
            - severity: 0-100 score (100 = most severe)
            - mean_a_channel: Average a-channel value (110-160, higher = more red)
            - red_pixel_count: Number of pixels above redness threshold
        """
        if roi_bgr.size == 0:
            return {
                "redness_coverage": 0,
                "severity": 0,
                "mean_a_channel": 128,
                "red_pixel_count": 0,
            }

        # Convert to LAB color space
        lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
        a_channel = lab[:, :, 1]  # Red-green axis (0-255, 128=neutral, >128=red)

        # Apply mask
        if roi_mask is not None:
            a_channel_masked = a_channel.copy()
            a_channel_masked[roi_mask == 0] = 128  # Neutral value outside mask
        else:
            a_channel_masked = a_channel

        # Detect reddish pixels (a > threshold)
        redness_mask = (a_channel_masked > self.redness_threshold).astype(np.uint8) * 255

        # Morphological cleanup to remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        redness_mask = cv2.morphologyEx(redness_mask, cv2.MORPH_CLOSE, kernel)

        # Count red pixels
        red_pixel_count = int(np.sum(redness_mask > 0))

        # Calculate coverage
        roi_area = np.sum(roi_mask > 0) if roi_mask is not None else roi_bgr.shape[0] * roi_bgr.shape[1]
        redness_coverage = (red_pixel_count / roi_area * 100) if roi_area > 0 else 0

        # Calculate mean a-channel (higher = more red)
        mean_a = int(np.mean(a_channel_masked))

        # Severity score based on:
        # 1. Redness coverage (0-50 points)
        # 2. Mean a-channel elevation above neutral (0-50 points)
        coverage_score = min(redness_coverage, 50)
        # Normal skin a-channel ~125-135, healthy is closer to 128
        # Reddened skin a-channel >140
        a_elevation = max(0, mean_a - 128)
        a_score = min(a_elevation / 2, 50)  # 32 points per 64 units above neutral
        severity = int(coverage_score + a_score)

        return {
            "redness_coverage": int(redness_coverage),
            "severity": min(severity, 100),
            "mean_a_channel": mean_a,
            "red_pixel_count": red_pixel_count,
        }
