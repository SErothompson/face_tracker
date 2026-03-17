import cv2
import numpy as np


# MediaPipe Face Mesh landmark indices for each region
# These are based on the official MediaPipe Face Mesh documentation
REGION_LANDMARKS = {
    "forehead": [
        # Upper forehead area
        10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
        397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
        172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
        # Extended upward
        47, 100, 98, 96, 64, 63, 362, 383, 385, 387, 280, 282,
    ],
    "left_cheek": [
        # Left side of face
        200, 199, 205, 206, 207, 216, 174, 142, 36, 37, 177, 179,
        130, 131, 135, 138, 139, 71, 68, 226, 225, 224, 223, 222,
        113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124,
        194, 195, 196, 197, 198,
    ],
    "right_cheek": [
        # Right side of face
        425, 426, 422, 421, 420, 411, 394, 367, 266, 267, 402, 403,
        360, 359, 355, 352, 351, 301, 298, 445, 444, 443, 442, 441,
        342, 341, 340, 339, 338, 337, 336, 335, 334, 333, 332, 331,
        413, 414, 415, 416, 417,
    ],
    "chin": [
        # Lower face/chin
        17, 18, 19, 20, 21, 22, 23, 24, 25, 26,
        152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170,
        200, 199, 196, 197, 198, 199, 200,
    ],
    "under_eye_left": [
        # Left under-eye region
        33, 7, 163, 144, 145, 153, 154, 155, 133, 246,
    ],
    "under_eye_right": [
        # Right under-eye region
        362, 382, 381, 380, 374, 373, 390, 249, 263, 466,
    ],
    "nose": [
        # Nose region
        1, 2, 98, 327, 4, 5, 6, 195, 236, 131, 48, 220,
        240, 275, 305, 308, 435, 440, 21, 440,
    ],
    "crows_feet_left": [
        # Outer corner of left eye and wrinkles
        33, 7, 163, 144, 145, 153, 154, 155, 133, 246,
        130, 129, 34, 142, 35,
    ],
    "crows_feet_right": [
        # Outer corner of right eye and wrinkles
        362, 382, 381, 380, 374, 373, 390, 249, 263, 466,
        359, 358, 263, 371, 372,
    ],
    "nasolabial_left": [
        # Left side of nose to mouth
        205, 206, 216, 212, 207, 215, 35, 36, 37, 39, 40, 185, 186, 187, 188,
    ],
    "nasolabial_right": [
        # Right side of nose to mouth
        425, 426, 436, 432, 427, 435, 266, 267, 266, 269, 270, 405, 406, 407, 408,
    ],
}


def extract_region(image_bgr: np.ndarray, landmarks: list, region_name: str) -> tuple:
    """
    Extract a masked ROI for the given region.

    Args:
        image_bgr: OpenCV BGR image.
        landmarks: List of 468 landmark (x, y) tuples.
        region_name: Name of the region to extract.

    Returns:
        Tuple of (roi_image, mask, bounding_box) where:
        - roi_image: Cropped region with non-region pixels zeroed
        - mask: Binary region mask
        - bounding_box: (x, y, w, h)
    """
    if region_name not in REGION_LANDMARKS:
        raise ValueError(f"Unknown region: {region_name}")

    indices = REGION_LANDMARKS[region_name]
    if not indices:
        raise ValueError(f"No landmarks defined for region: {region_name}")

    # Get the (x, y) points for this region
    pts = np.array([landmarks[i] for i in indices if i < len(landmarks)], dtype=np.int32)

    if len(pts) < 3:
        raise ValueError(f"Insufficient landmarks for region {region_name}: {len(pts)}")

    # Create a mask for this region
    mask = np.zeros(image_bgr.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)

    # Get bounding box
    x, y, w, h = cv2.boundingRect(pts)

    # Ensure bounding box is within image bounds
    x = max(0, x)
    y = max(0, y)
    w = min(w, image_bgr.shape[1] - x)
    h = min(h, image_bgr.shape[0] - y)

    # Crop the region
    if w > 0 and h > 0:
        roi = image_bgr[y : y + h, x : x + w].copy()
        roi_mask = mask[y : y + h, x : x + w]

        # Zero out pixels outside the polygon
        roi[roi_mask == 0] = 0
    else:
        # Empty region
        roi = np.zeros((1, 1, 3), dtype=np.uint8)
        roi_mask = np.zeros((1, 1), dtype=np.uint8)

    return roi, roi_mask, (x, y, w, h)


def extract_all_regions(image_bgr: np.ndarray, landmarks: list) -> dict:
    """
    Extract all defined regions from an image.

    Args:
        image_bgr: OpenCV BGR image.
        landmarks: List of 468 landmark (x, y) tuples.

    Returns:
        Dictionary mapping region_name -> (roi, mask, bbox)
    """
    regions = {}
    for region_name in REGION_LANDMARKS:
        try:
            regions[region_name] = extract_region(image_bgr, landmarks, region_name)
        except (ValueError, IndexError):
            # Skip regions that fail extraction
            continue

    return regions


def extrapolate_forehead(landmarks: list, extrapolate_factor: float = 0.6) -> np.ndarray:
    """
    Extrapolate forehead region upward from eyebrow landmarks.
    MediaPipe landmarks don't extend to the hairline, so we extend them.

    Args:
        landmarks: List of 468 landmark (x, y) tuples.
        extrapolate_factor: How far to extend upward (as fraction of inter-eye distance).

    Returns:
        Array of extrapolated forehead points.
    """
    # Eyebrow landmarks
    left_eyebrow_indices = [105, 104, 103, 102, 101, 100, 99, 98]
    right_eyebrow_indices = [334, 333, 332, 331, 330, 329, 328, 327]

    eyebrow_points = np.array(
        [landmarks[i] for i in left_eyebrow_indices + right_eyebrow_indices]
    )

    # Find the vertical center of the eyebrows
    center_y = np.mean(eyebrow_points[:, 1])

    # Calculate inter-eye distance as reference
    left_eye_center = np.mean(
        [landmarks[i] for i in [33, 133]], axis=0
    )
    right_eye_center = np.mean(
        [landmarks[i] for i in [362, 263]], axis=0
    )
    inter_eye_dist = np.linalg.norm(right_eye_center - left_eye_center)

    # Extrapolate upward
    extrapolation = inter_eye_dist * extrapolate_factor
    extrapolated_y = center_y - extrapolation

    # Create extrapolated points
    forehead_points = []
    for x, y in eyebrow_points:
        forehead_points.append([x, int(extrapolated_y)])

    return np.array(forehead_points, dtype=np.int32)
