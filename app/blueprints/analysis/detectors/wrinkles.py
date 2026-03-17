import cv2
import numpy as np
from skimage.filters import frangi, meijering


class WrinklesDetector:
    """
    Detects wrinkles and fine lines using ridge detection (Frangi filter).

    Wrinkles appear as linear features with alternating bright/dark patterns.
    The Frangi filter detects ridge-like structures across multiple scales.
    """

    def __init__(self, scales=(1, 2, 3, 4), alpha=0.5, beta=0.5, gamma=15):
        """
        Initialize wrinkles detector.

        Args:
            scales: Tuple of scales for multi-scale ridge detection
            alpha: Frangi filter alpha parameter (background-to-foreground ratio)
            beta: Frangi filter beta parameter (sharpness control)
            gamma: Frangi filter gamma parameter (contrast enhancement)
        """
        self.scales = scales
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma

    def detect(self, roi_bgr: np.ndarray, roi_mask: np.ndarray) -> dict:
        """
        Detect wrinkles in a region of interest.

        Args:
            roi_bgr: Cropped BGR image of a facial region
            roi_mask: Binary mask (255 where region is active, 0 elsewhere)

        Returns:
            Dict with:
            - wrinkle_density: Average ridge strength (0-1)
            - severity: 0-100 score (100 = most severe)
            - ridge_pixels: Number of pixels marked as wrinkles
            - max_ridge_strength: Strongest wrinkle detected (0-1)
        """
        if roi_bgr.size == 0:
            return {
                "wrinkle_density": 0,
                "severity": 0,
                "ridge_pixels": 0,
                "max_ridge_strength": 0,
            }

        # Convert to grayscale for ridge detection
        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        gray = gray.astype(np.float32) / 255.0

        # Apply Frangi filter
        try:
            frangi_response = frangi(gray, sigmas=self.scales, alpha=self.alpha, beta=self.beta, gamma=self.gamma)
        except Exception:
            # Fallback to Meijering if Frangi fails
            frangi_response = meijering(gray, sigmas=self.scales, alpha=self.alpha)

        # Apply mask
        if roi_mask is not None:
            mask_normalized = roi_mask.astype(np.float32) / 255.0
            frangi_response = frangi_response * mask_normalized

        # Calculate metrics
        max_ridge_strength = float(np.max(frangi_response))
        wrinkle_density = float(np.mean(frangi_response))

        # Threshold to find wrinkle pixels (ridge strength > 0.1)
        wrinkle_threshold = 0.1
        wrinkle_mask = (frangi_response > wrinkle_threshold).astype(np.uint8)
        ridge_pixels = int(np.sum(wrinkle_mask))

        # Severity: density (0-50) + max strength (0-50)
        density_score = min(wrinkle_density * 100, 50)
        strength_score = min(max_ridge_strength * 50, 50)
        severity = int(density_score + strength_score)

        return {
            "wrinkle_density": wrinkle_density,
            "severity": min(severity, 100),
            "ridge_pixels": ridge_pixels,
            "max_ridge_strength": max_ridge_strength,
        }
