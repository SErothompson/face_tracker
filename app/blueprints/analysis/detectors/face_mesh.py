import os

import numpy as np
import cv2
import mediapipe as mp


# Path to the face landmarker model file
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "models",
    "face_landmarker.task",
)


class FaceMeshDetector:
    """
    Wraps MediaPipe Face Landmarker for face detection and landmark extraction.
    Returns 478 facial landmarks as (x, y) pixel coordinates.
    """

    def __init__(self, min_detection_confidence=0.5):
        """
        Initialize the Face Landmarker detector.

        Args:
            min_detection_confidence: Confidence threshold for face detection.
        """
        self.min_detection_confidence = min_detection_confidence
        base_options = mp.tasks.BaseOptions(model_asset_path=_MODEL_PATH)
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=base_options,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            num_faces=1,
        )
        self.landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)

    def detect(self, image_bgr: np.ndarray) -> list:
        """
        Detect face landmarks in an image.

        Args:
            image_bgr: OpenCV BGR image (np.ndarray).

        Returns:
            List of 478 (x, y) pixel coordinates, or None if no face found.
        """
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        result = self.landmarker.detect(mp_image)

        if not result.face_landmarks:
            return None

        face = result.face_landmarks[0]
        h, w = image_bgr.shape[:2]
        landmarks = [(int(lm.x * w), int(lm.y * h)) for lm in face]
        return landmarks

    def close(self):
        """Close and cleanup the MediaPipe resources."""
        if self.landmarker:
            self.landmarker.close()
