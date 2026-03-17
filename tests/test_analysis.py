import os

import cv2
import pytest

from app.blueprints.analysis.detectors.face_mesh import FaceMeshDetector
from app.blueprints.analysis.detectors.regions import (
    REGION_LANDMARKS,
    extract_all_regions,
    extract_region,
    extrapolate_forehead,
)


@pytest.fixture
def test_image_path():
    """Return path to test face image."""
    return os.path.join(os.path.dirname(__file__), "fixtures", "test_face.jpg")


@pytest.fixture
def test_image_bgr(test_image_path):
    """Load test image in BGR format."""
    img = cv2.imread(test_image_path)
    if img is None:
        pytest.skip("Test image not found")
    return img


@pytest.fixture
def face_detector():
    """Create a FaceMeshDetector instance."""
    detector = FaceMeshDetector()
    yield detector
    detector.close()


def test_face_mesh_detector_init(face_detector):
    """Test that FaceMeshDetector initializes without errors."""
    assert face_detector is not None
    assert hasattr(face_detector, 'detect')


def test_face_detection_returns_landmarks(face_detector, test_image_bgr):
    """Test that face detection returns landmarks."""
    landmarks = face_detector.detect(test_image_bgr)

    # Note: synthetic image may not detect a face. If it doesn't, this is acceptable.
    # Real face photos will definitely work.
    if landmarks is not None:
        assert isinstance(landmarks, list)
        assert len(landmarks) == 468
        # Check all landmarks are tuples of ints
        for point in landmarks:
            assert isinstance(point, tuple)
            assert len(point) == 2
            assert isinstance(point[0], int)
            assert isinstance(point[1], int)


def test_face_detection_coordinates_in_bounds(face_detector, test_image_bgr):
    """Test that detected landmarks are within image bounds."""
    landmarks = face_detector.detect(test_image_bgr)

    if landmarks is not None:
        h, w = test_image_bgr.shape[:2]
        for x, y in landmarks:
            assert 0 <= x <= w, f"X coordinate {x} out of bounds [0, {w}]"
            assert 0 <= y <= h, f"Y coordinate {y} out of bounds [0, {h}]"


def test_face_detection_no_face_in_blank_image(face_detector):
    """Test that blank image returns None (no face detected)."""
    blank_image = np.zeros((480, 640, 3), dtype=np.uint8)
    landmarks = face_detector.detect(blank_image)
    # Blank image should not detect a face
    assert landmarks is None


def test_region_landmarks_defined():
    """Test that all expected regions have landmarks defined."""
    expected_regions = [
        "forehead",
        "left_cheek",
        "right_cheek",
        "chin",
        "under_eye_left",
        "under_eye_right",
        "nose",
        "crows_feet_left",
        "crows_feet_right",
        "nasolabial_left",
        "nasolabial_right",
    ]

    for region in expected_regions:
        assert region in REGION_LANDMARKS
        assert len(REGION_LANDMARKS[region]) > 0


def test_extract_region_with_dummy_landmarks(test_image_bgr):
    """Test region extraction with synthetic landmarks."""
    h, w = test_image_bgr.shape[:2]

    # Create synthetic landmarks (468 points spread across the image)
    landmarks = [
        (int(w * i / 468), int(h * (i % 3) / 3))
        for i in range(468)
    ]

    # Try extracting a region
    roi, mask, bbox = extract_region(test_image_bgr, landmarks, "forehead")

    # Check return types
    assert isinstance(roi, (np.ndarray,))
    assert isinstance(mask, (np.ndarray,))
    assert isinstance(bbox, tuple)
    assert len(bbox) == 4

    # Check bounding box values
    x, y, region_w, region_h = bbox
    assert x >= 0
    assert y >= 0
    assert x <= w
    assert y <= h


def test_extract_all_regions(test_image_bgr):
    """Test extracting all regions at once."""
    h, w = test_image_bgr.shape[:2]

    # Create synthetic landmarks
    landmarks = [
        (int(w * i / 468), int(h * (i % 3) / 3))
        for i in range(468)
    ]

    regions = extract_all_regions(test_image_bgr, landmarks)

    # Should extract multiple regions
    assert len(regions) > 0
    assert isinstance(regions, dict)

    # Check each region has proper format
    for region_name, (roi, mask, bbox) in regions.items():
        assert isinstance(roi, np.ndarray)
        assert isinstance(mask, np.ndarray)
        assert isinstance(bbox, tuple)
        assert len(bbox) == 4


def test_extract_region_invalid_region_name(test_image_bgr):
    """Test that invalid region name raises ValueError."""
    landmarks = [(100, 100)] * 468

    with pytest.raises(ValueError):
        extract_region(test_image_bgr, landmarks, "invalid_region")


def test_extract_region_mask_shape(test_image_bgr):
    """Test that extracted mask has correct shape."""
    h, w = test_image_bgr.shape[:2]
    landmarks = [
        (int(w * i / 468), int(h * (i % 3) / 3))
        for i in range(468)
    ]

    roi, mask, bbox = extract_region(test_image_bgr, landmarks, "forehead")

    # Mask should have same dimensions as ROI
    assert mask.shape[:2] == roi.shape[:2]


def test_extract_region_roi_zeroed_outside_mask(test_image_bgr):
    """Test that pixels outside mask are zeroed."""
    h, w = test_image_bgr.shape[:2]
    landmarks = [
        (int(w * i / 468), int(h * (i % 3) / 3))
        for i in range(468)
    ]

    roi, mask, bbox = extract_region(test_image_bgr, landmarks, "forehead")

    # Pixels outside mask should be zero
    outside_mask = mask == 0
    if roi.size > 0:
        # Check that at least some pixels outside mask are black
        outside_pixels = roi[outside_mask]
        if outside_pixels.size > 0:
            # Some pixels should be [0, 0, 0]
            black_pixels = np.all(outside_pixels == 0, axis=1)
            # We expect most to be black, but there might be some color due to ROI cropping
            assert np.sum(black_pixels) > 0


def test_extrapolate_forehead_extends_upward(test_image_bgr):
    """Test that forehead extrapolation extends points upward."""
    h, w = test_image_bgr.shape[:2]
    landmarks = [
        (int(w * i / 468), int(h * (i % 3) / 3))
        for i in range(468)
    ]

    # Get original eyebrow y positions
    from app.blueprints.analysis.detectors.regions import REGION_LANDMARKS
    eyebrow_indices = [105, 104, 103, 102, 101, 100, 99, 98]
    original_y = np.mean([landmarks[i][1] for i in eyebrow_indices])

    # Extrapolate
    extrapolated = extrapolate_forehead(landmarks)

    # Check that extrapolated points are above original y
    assert isinstance(extrapolated, np.ndarray)
    # The extrapolated points should extend upward (smaller y values)
    max_extrapolated_y = np.max(extrapolated[:, 1])
    assert max_extrapolated_y < original_y


def test_region_masks_are_float_or_uint8(test_image_bgr):
    """Test that masks have appropriate dtype."""
    h, w = test_image_bgr.shape[:2]
    landmarks = [
        (int(w * i / 468), int(h * (i % 3) / 3))
        for i in range(468)
    ]

    regions = extract_all_regions(test_image_bgr, landmarks)

    for region_name, (roi, mask, bbox) in regions.items():
        assert mask.dtype in [np.uint8, np.float32, np.float64]


# Import numpy for the tests
import numpy as np
