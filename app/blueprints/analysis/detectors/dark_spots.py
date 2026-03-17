import cv2
import numpy as np
from scipy import ndimage


class DarkSpotsDetector:
    """
    Detects hyperpigmentation, dark spots, and age spots using LAB L-channel analysis.

    Dark spots are regions with significantly lower luminance (darker) than surrounding skin.
    """

    def __init__(self, neighborhood_size=25, darkness_threshold=20):
        """
        Initialize dark spots detector.

        Args:
            neighborhood_size: Size of local neighborhood for deviation calculation
            darkness_threshold: Minimum luminance difference to detect as dark spot
        """
        self.neighborhood_size = neighborhood_size
        self.darkness_threshold = darkness_threshold

    def detect(self, roi_bgr: np.ndarray, roi_mask: np.ndarray) -> dict:
        """
        Detect dark spots in a region of interest.

        Args:
            roi_bgr: Cropped BGR image of a facial region
            roi_mask: Binary mask (255 where region is active, 0 elsewhere)

        Returns:
            Dict with:
            - count: Number of detected dark spot regions
            - severity: 0-100 score (100 = most severe)
            - total_area: Total pixel area of dark spots
            - mean_darkness: Average darkness value (0-255, lower = darker)
        """
        if roi_bgr.size == 0:
            return {
                "count": 0,
                "severity": 0,
                "total_area": 0,
                "mean_darkness": 255,
            }

        # Convert to LAB and extract L channel (luminance)
        lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0].astype(np.float32)

        # Calculate local mean luminance using morphological opening
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self.neighborhood_size, self.neighborhood_size)
        )
        local_mean = cv2.morphologyEx(l_channel, cv2.MORPH_OPEN, kernel)

        # Calculate deviation from local mean
        deviation = local_mean - l_channel

        # Apply mask
        if roi_mask is not None:
            deviation[roi_mask == 0] = 0

        # Threshold: regions significantly darker than surroundings
        dark_spots_mask = (deviation > self.darkness_threshold).astype(np.uint8) * 255

        # Morphological cleanup
        kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        dark_spots_mask = cv2.morphologyEx(dark_spots_mask, cv2.MORPH_CLOSE, kernel_small)

        # Find connected components
        num_spots, labeled = cv2.connectedComponents(dark_spots_mask)

        # Filter out background (label 0)
        num_spots = max(0, num_spots - 1)

        # Calculate areas and darkness values
        total_area = 0
        darkness_values = []
        for spot_id in range(1, num_spots + 1):
            spot_mask = (labeled == spot_id).astype(np.uint8)
            area = cv2.countNonZero(spot_mask)

            # Only count substantial spots
            if area > 5:
                total_area += area
                mean_darkness = np.mean(l_channel[spot_mask > 0])
                darkness_values.append(mean_darkness)

        count = len(darkness_values)
        mean_darkness = (
            np.mean(darkness_values) if darkness_values else 255
        )

        # Severity: count (0-50 points) + coverage (0-50 points)
        roi_area = np.sum(roi_mask > 0) if roi_mask is not None else roi_bgr.shape[0] * roi_bgr.shape[1]
        coverage = total_area / roi_area if roi_area > 0 else 0
        count_score = min(count * 5, 50)
        coverage_score = min(coverage * 100, 50)
        severity = int(count_score + coverage_score)

        return {
            "count": count,
            "severity": min(severity, 100),
            "total_area": int(total_area),
            "mean_darkness": int(mean_darkness),
        }
