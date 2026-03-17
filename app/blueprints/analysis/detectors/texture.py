import cv2
import numpy as np


class TextureDetector:
    """
    Detects skin texture issues (roughness, pores, bumpy surface) using Laplacian variance.

    Healthy skin has smooth, even texture. Poor texture shows high variance in edge detection.
    """

    def __init__(self, blur_kernel=5):
        """
        Initialize texture detector.

        Args:
            blur_kernel: Kernel size for Gaussian blur before Laplacian (odd number)
        """
        self.blur_kernel = blur_kernel if blur_kernel % 2 == 1 else blur_kernel + 1

    def detect(self, roi_bgr: np.ndarray, roi_mask: np.ndarray) -> dict:
        """
        Detect poor skin texture in a region of interest.

        Args:
            roi_bgr: Cropped BGR image of a facial region
            roi_mask: Binary mask (255 where region is active, 0 elsewhere)

        Returns:
            Dict with:
            - laplacian_variance: Measure of texture roughness (higher = rougher)
            - severity: 0-100 score (100 = most severe)
            - roughness_score: Normalized roughness (0-100)
        """
        if roi_bgr.size == 0:
            return {
                "laplacian_variance": 0,
                "severity": 0,
                "roughness_score": 0,
            }

        # Convert to grayscale
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to smooth minor noise
        blurred = cv2.GaussianBlur(gray, (self.blur_kernel, self.blur_kernel), 0)

        # Compute Laplacian (second derivative - sensitive to texture changes)
        laplacian = cv2.Laplacian(blurred, cv2.CV_64F)

        # Apply mask
        if roi_mask is not None:
            mask_normalized = roi_mask.astype(np.uint8)
            laplacian[mask_normalized == 0] = 0

        # Calculate variance of Laplacian
        # Higher variance = more texture variation = rougher skin
        laplacian_variance = float(np.var(laplacian))

        # Normalize to 0-100 score
        # Empirically, healthy skin has variance ~50-200
        # Problem skin has variance ~400+
        # Map: 0 var -> 0 score, 1000 var -> 100 score
        roughness_score = min(laplacian_variance / 10, 100)

        return {
            "laplacian_variance": laplacian_variance,
            "severity": int(roughness_score),
            "roughness_score": int(roughness_score),
        }
