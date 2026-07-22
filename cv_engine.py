"""
StrokeX — Computer Vision Engine
Pure math functions for processing MediaPipe hand landmark coordinates.
No camera or MediaPipe runtime dependency — these functions operate on
pre-extracted landmark arrays sent from the mobile client.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional


# ============================================================
# MediaPipe Hand Landmark Indices
# ============================================================
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20


def calculate_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """
    Calculate the angle at point B formed by rays BA and BC.
    
    Args:
        a: 2D/3D coordinate of point A (numpy array)
        b: 2D/3D coordinate of vertex point B (numpy array)
        c: 2D/3D coordinate of point C (numpy array)
    
    Returns:
        Angle in degrees (0-180)
    """
    ba = a - b
    bc = c - b

    # Cosine of the angle via dot product
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    # Clamp to avoid numerical issues with arccos
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine_angle))

    return float(angle)


def calculate_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate Euclidean distance between two points."""
    return float(np.linalg.norm(a - b))


def landmarks_to_numpy(landmarks: List[Dict[str, float]]) -> np.ndarray:
    """
    Convert a list of landmark dicts [{x, y, z}, ...] to a numpy array.
    
    Args:
        landmarks: List of 21 hand landmarks with x, y, z keys
    
    Returns:
        numpy array of shape (21, 3)
    """
    return np.array([[lm["x"], lm["y"], lm.get("z", 0.0)] for lm in landmarks])


# ============================================================
# POTION MASTER — Wrist Flexion Check
# ============================================================
def check_wrist_flexion(
    landmarks: List[Dict[str, float]],
    threshold_angle: float = 140.0
) -> Dict:
    """
    Check wrist flexion/extension for the Potion Master minigame.
    
    Measures the angle at the WRIST formed by the forearm direction
    (approximated by the line from MIDDLE_MCP to WRIST) and the
    line from WRIST extended downward.
    
    In practice, we measure the angle at WRIST between:
      - Point A: The midpoint of INDEX_MCP and RING_MCP (palm center)
      - Point B: WRIST (vertex)
      - Point C: A virtual point below the wrist (forearm approximation)
    
    A fully extended wrist ≈ 180°, flexed wrist ≈ 90-130°.
    
    Args:
        landmarks: 21 MediaPipe hand landmarks
        threshold_angle: Angle below which wrist is considered "flexed"
    
    Returns:
        Dict with is_flexed (bool), angle (float), score_multiplier (float)
    """
    pts = landmarks_to_numpy(landmarks)

    # Palm center (midpoint of index and ring MCP joints)
    palm_center = (pts[INDEX_MCP] + pts[RING_MCP]) / 2.0

    # Wrist point
    wrist = pts[WRIST]

    # Virtual forearm point: extend wrist direction away from palm
    forearm_direction = wrist - palm_center
    forearm_point = wrist + forearm_direction  # point below wrist

    # Angle at wrist between palm_center — wrist — forearm_point
    angle = calculate_angle(palm_center, wrist, forearm_point)

    # The actual wrist flexion angle is 180 - angle (deviation from straight)
    wrist_flexion_angle = 180.0 - angle

    is_flexed = wrist_flexion_angle > (180.0 - threshold_angle)

    # Score multiplier: higher flexion = higher score (capped at 2.0x)
    score_multiplier = min(2.0, max(1.0, wrist_flexion_angle / 45.0))

    return {
        "is_flexed": is_flexed,
        "wrist_angle": round(wrist_flexion_angle, 2),
        "raw_angle": round(angle, 2),
        "score_multiplier": round(score_multiplier, 2),
        "quality": _classify_quality(wrist_flexion_angle, 20, 40, 60)
    }


# ============================================================
# SHIELD DEFENDER — Finger Abduction Check
# ============================================================
def check_finger_abduction(
    landmarks: List[Dict[str, float]],
    threshold_spread: float = 35.0
) -> Dict:
    """
    Check finger abduction (spread) for the Shield Defender minigame.
    
    Measures the average angle between adjacent fingers at the MCP joints.
    Greater spread = stronger "shield" activation.
    
    Angles measured between adjacent finger pairs:
      1. Index-Middle (at their MCP joints from wrist)
      2. Middle-Ring
      3. Ring-Pinky
    
    Args:
        landmarks: 21 MediaPipe hand landmarks
        threshold_spread: Average angle above which fingers are "spread enough"
    
    Returns:
        Dict with is_spread (bool), avg_angle (float), finger_angles (list), score_multiplier (float)
    """
    pts = landmarks_to_numpy(landmarks)
    wrist = pts[WRIST]

    # Calculate angles between adjacent fingers using MCP-to-TIP vectors from wrist
    finger_mcps = [INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]
    finger_tips = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]

    finger_angles = []
    for i in range(len(finger_mcps) - 1):
        # Vector from wrist to each finger's MCP
        vec_a = pts[finger_tips[i]] - wrist
        vec_b = pts[finger_tips[i + 1]] - wrist

        # Angle between the two finger vectors
        angle = calculate_angle(pts[finger_tips[i]], wrist, pts[finger_tips[i + 1]])
        finger_angles.append(round(angle, 2))

    avg_angle = float(np.mean(finger_angles)) if finger_angles else 0.0
    is_spread = avg_angle >= threshold_spread

    # Score multiplier: wider spread = higher score
    score_multiplier = min(2.0, max(1.0, avg_angle / 30.0))

    return {
        "is_spread": is_spread,
        "avg_spread_angle": round(avg_angle, 2),
        "finger_pair_angles": {
            "index_middle": finger_angles[0] if len(finger_angles) > 0 else 0,
            "middle_ring": finger_angles[1] if len(finger_angles) > 1 else 0,
            "ring_pinky": finger_angles[2] if len(finger_angles) > 2 else 0,
        },
        "score_multiplier": round(score_multiplier, 2),
        "quality": _classify_quality(avg_angle, 15, 30, 45)
    }


# ============================================================
# RHYTHM MAESTRO — Finger Tapping Detection
# ============================================================
def check_finger_tap(
    landmarks: List[Dict[str, float]],
    target_finger: int = INDEX_TIP,
    tap_threshold: float = 0.05
) -> Dict:
    """
    Check if a specific finger is tapping (tip close to thumb tip).
    
    Used for the Rhythm Maestro minigame — detects pinch/tap gestures.
    
    Args:
        landmarks: 21 MediaPipe hand landmarks
        target_finger: Landmark index of the finger tip to check
        tap_threshold: Maximum distance for a "tap" to register
    
    Returns:
        Dict with is_tapping (bool), distance (float)
    """
    pts = landmarks_to_numpy(landmarks)

    thumb_tip = pts[THUMB_TIP]
    finger_tip = pts[target_finger]

    distance = calculate_distance(thumb_tip, finger_tip)
    is_tapping = distance <= tap_threshold

    return {
        "is_tapping": is_tapping,
        "distance": round(distance, 4),
        "finger_index": target_finger,
        "quality": "perfect" if distance < tap_threshold * 0.5 else ("good" if is_tapping else "miss")
    }


# ============================================================
# Utility
# ============================================================
def _classify_quality(value: float, low: float, mid: float, high: float) -> str:
    """Classify a measurement into quality tiers."""
    if value >= high:
        return "excellent"
    elif value >= mid:
        return "good"
    elif value >= low:
        return "fair"
    else:
        return "needs_improvement"


def get_hand_openness(landmarks: List[Dict[str, float]]) -> Dict:
    """
    Calculate overall hand openness (0-100%).
    Useful for general rehabilitation progress tracking.
    """
    pts = landmarks_to_numpy(landmarks)
    wrist = pts[WRIST]

    finger_tips = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
    finger_mcps = [THUMB_MCP, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]

    # Measure how extended each finger is (tip distance vs MCP distance from wrist)
    openness_scores = []
    for tip_idx, mcp_idx in zip(finger_tips, finger_mcps):
        tip_dist = calculate_distance(pts[tip_idx], wrist)
        mcp_dist = calculate_distance(pts[mcp_idx], wrist)
        # Ratio > 1 means finger is extended past MCP
        ratio = tip_dist / (mcp_dist + 1e-8)
        openness_scores.append(min(ratio / 2.0, 1.0))  # Normalize to 0-1

    avg_openness = float(np.mean(openness_scores)) * 100

    return {
        "openness_percent": round(avg_openness, 1),
        "per_finger": {
            "thumb": round(openness_scores[0] * 100, 1),
            "index": round(openness_scores[1] * 100, 1),
            "middle": round(openness_scores[2] * 100, 1),
            "ring": round(openness_scores[3] * 100, 1),
            "pinky": round(openness_scores[4] * 100, 1),
        }
    }
