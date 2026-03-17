import numpy as np
import cv2


class FaceMeshDetector:
    """
    Wraps MediaPipe Face Landmarker for face detection and landmark extraction.
    Returns 468 facial landmarks.

    Note: Simplified version for testing. Actual deployment requires the
    face_landmarker.task model from MediaPipe.
    """

    def __init__(self, min_detection_confidence=0.5):
        """
        Initialize the Face Landmarker detector.

        Args:
            min_detection_confidence: Confidence threshold for face detection.
        """
        self.min_detection_confidence = min_detection_confidence
        self.landmarker = None

    def detect(self, image_bgr: np.ndarray) -> list:
        """
        Detect face landmarks in an image.

        Args:
            image_bgr: OpenCV BGR image (np.ndarray).

        Returns:
            List of 468 (x, y) pixel coordinates, or None if no face found.
        """
        # Return None in test mode - actual MediaPipe would require model file
        return None

    def close(self):
        """Close and cleanup the MediaPipe resources."""
        pass
