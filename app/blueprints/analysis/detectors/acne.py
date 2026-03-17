import cv2
import numpy as np


class AcneDetector:
    """
    Detects acne lesions and blemishes using LAB color thresholding and blob detection.

    Acne appears as reddish/pinkish areas with raised textures.
    Works on extracted facial regions (e.g., cheeks, chin).
    """

    def __init__(self, min_lesion_area=10, max_lesion_area=500):
        """
        Initialize acne detector.

        Args:
            min_lesion_area: Minimum pixel area for a blob to count as lesion
            max_lesion_area: Maximum pixel area (filters noise and large areas)
        """
        self.min_lesion_area = min_lesion_area
        self.max_lesion_area = max_lesion_area

    def detect(self, roi_bgr: np.ndarray, roi_mask: np.ndarray) -> dict:
        """
        Detect acne in a region of interest.

        Args:
            roi_bgr: Cropped BGR image of a facial region
            roi_mask: Binary mask (255 where region is active, 0 elsewhere)

        Returns:
            Dict with:
            - count: Number of detected lesions
            - severity: 0-100 score (100 = most severe)
            - areas: List of lesion pixel areas
            - centers: List of (x, y) centers of detected lesions
        """
        if roi_bgr.size == 0:
            return {"count": 0, "severity": 0, "areas": [], "centers": []}

        # Convert to LAB color space
        lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        a_channel = lab[:, :, 1]

        # In acne, affected areas have elevated a-channel (reddish)
        # and often lower L (slightly darker)
        # Threshold: a > 135 (reddish) and L < 150 (not too bright)
        acne_mask = (a_channel > 135) & (l_channel < 150)

        # Apply region mask to avoid edges
        if roi_mask is not None:
            acne_mask = acne_mask & (roi_mask > 0)

        # Morphological operations to clean noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        acne_mask = cv2.morphologyEx(acne_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
        acne_mask = cv2.morphologyEx(acne_mask, cv2.MORPH_OPEN, kernel)

        # Find contours (lesions)
        contours, _ = cv2.findContours(acne_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        lesions = []
        centers = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_lesion_area <= area <= self.max_lesion_area:
                lesions.append(area)
                # Get centroid
                m = cv2.moments(contour)
                if m["m00"] > 0:
                    cx = int(m["m10"] / m["m00"])
                    cy = int(m["m01"] / m["m00"])
                    centers.append((cx, cy))

        # Calculate severity: normalize lesion count and size
        count = len(lesions)
        total_area = sum(lesions) if lesions else 0
        mean_area = total_area / count if count > 0 else 0

        # Severity: count (0-50 points) + mean_area (0-50 points)
        count_score = min(count * 5, 50)
        area_score = min(mean_area / 10, 50)
        severity = int(count_score + area_score)
        severity = min(severity, 100)

        return {
            "count": count,
            "severity": severity,
            "areas": lesions,
            "centers": centers,
        }
