"""Transformă o execuție întreagă într-un rând de numere, pentru modelele învățate (E7, E8).

Rândul nu depinde de exercițiu: aceleași unghiuri și statistici pentru toate execuțiile,
altfel clasificatorul ar primi răspunsul ascuns în date.
"""
import warnings

import numpy as np

from src.features import compute_angles, named_joints
from src.filters import smooth_keypoints
from src.quality import OK, clean_sequence

ANGLES = [
    "shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "knee_flexion_L", "knee_flexion_R",
    "hip_flexion_L", "hip_flexion_R", "trunk_tilt", "trunk_lean", "trunk_rotation", "pelvis_rotation",
    "shoulder_rotation",
]
STATISTICS = ["mean", "std", "p5", "p95", "range", "speed"]
FEATURE_NAMES = [f"{angle}__{stat}" for angle in ANGLES for stat in STATISTICS]


def angles_from_mediapipe(image_kp, world_kp, fps=30.0, mirrored=False):
    """Verificare, netezire, unghiuri. Întoarce (unghiuri, partea de cadre păstrate)."""
    _, world, status, _ = clean_sequence(image_kp, world_kp, fps, mirrored=mirrored)
    angles = compute_angles(named_joints(smooth_keypoints(world), "mediapipe", mirrored))
    return angles, float(np.mean(status == OK)) if len(status) else 0.0


def angles_from_kinect(points):
    """Kinect nu trece prin verificare (are adâncime măsurată și nu răstoarnă scheletul), doar prin netezire."""
    present = ~np.isnan(points[:, :, 0]).any(axis=1)
    angles = compute_angles(named_joints(smooth_keypoints(points), "kinect"))
    return angles, float(np.mean(present)) if len(points) else 0.0


def summarize(angles, fps=30.0):
    """78 de numere: 6 statistici pentru fiecare din cele 13 unghiuri, pe cadrele măsurate."""
    row = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for angle in ANGLES:
            values = angles[angle].to_numpy(dtype=float)
            valid = values[~np.isnan(values)]
            if len(valid) < 2:
                row.update({f"{angle}__{stat}": np.nan for stat in STATISTICS})
                continue
            p5, p95 = np.percentile(valid, [5, 95])
            row[f"{angle}__mean"] = valid.mean()
            row[f"{angle}__std"] = valid.std()
            row[f"{angle}__p5"] = p5
            row[f"{angle}__p95"] = p95
            row[f"{angle}__range"] = p95 - p5
            # Viteza doar între cadre vecine măsurate: un gol nu devine o mișcare bruscă.
            row[f"{angle}__speed"] = np.nanmean(np.abs(np.diff(values))) * fps
    return row


def valid_seconds(angles, fps=30.0):
    return float(angles[ANGLES].notna().all(axis=1).sum() / fps)
