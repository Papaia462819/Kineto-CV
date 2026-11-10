"""Transformă o execuție întreagă într-un rând de numere, pentru modelele învățate (E7, E8).

Rândul nu depinde de exercițiu: aceleași unghiuri și statistici pentru toate execuțiile,
altfel clasificatorul ar primi răspunsul ascuns în date.
"""
import warnings

import numpy as np

from src.features import PRIMARY_ANGLE, REP_PROMINENCE, SYMMETRY_PAIR, compute_angles, named_joints, repetition_table
from src.filters import smooth_keypoints
from src.quality import OK, clean_sequence
from src.reps import find_reps, valleys

ANGLES = [
    "shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "knee_flexion_L", "knee_flexion_R",
    "hip_flexion_L", "hip_flexion_R", "trunk_tilt", "trunk_lean", "trunk_rotation", "pelvis_rotation",
    "shoulder_rotation",
]
STATISTICS = ["mean", "std", "p5", "p95", "range", "speed"]
FEATURE_NAMES = [f"{angle}__{stat}" for angle in ANGLES for stat in STATISTICS]


def joints_from_mediapipe(image_kp, world_kp, fps=30.0, mirrored=False):
    """Verificare, netezire, axe comune. Întoarce ({articulație: cadre × 3}, partea de cadre păstrate)."""
    _, world, status, _ = clean_sequence(image_kp, world_kp, fps, mirrored=mirrored)
    joints = named_joints(smooth_keypoints(world), "mediapipe", mirrored)
    return joints, float(np.mean(status == OK)) if len(status) else 0.0


def joints_from_kinect(points):
    """Kinect nu trece prin verificare (are adâncime măsurată și nu răstoarnă scheletul), doar prin netezire."""
    present = ~np.isnan(points[:, :, 0]).any(axis=1)
    return named_joints(smooth_keypoints(points), "kinect"), float(np.mean(present)) if len(points) else 0.0


def angles_from_mediapipe(image_kp, world_kp, fps=30.0, mirrored=False):
    """Verificare, netezire, unghiuri. Întoarce (unghiuri, partea de cadre păstrate)."""
    joints, kept = joints_from_mediapipe(image_kp, world_kp, fps, mirrored)
    return compute_angles(joints), kept


def angles_from_kinect(points):
    joints, kept = joints_from_kinect(points)
    return compute_angles(joints), kept


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


# Grupul B: măsurători pe repetări. Aici exercițiul e cunoscut, deci știm ce unghi urmărim.
REPETITION_NAMES = [
    "rep__count", "rep__rom_mean", "rep__rom_cv", "rep__rom_fatigue", "rep__peak_mean", "rep__valley_mean",
    "rep__up_s", "rep__down_s", "rep__duration_cv", "rep__interval_cv", "rep__jerk", "rep__compensation",
    "rep__asymmetry",
]


def _cv(values):
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2 or values.mean() == 0:
        return np.nan
    return float(values.std() / abs(values.mean()))


def repetition_summary(angles, exercise, fps=30.0):
    """Rezumă repetările unei execuții: cât de mult, cât de constant, în ce ritm, cu ce compensări."""
    row = dict.fromkeys(REPETITION_NAMES, np.nan)
    primary = angles[PRIMARY_ANGLE[exercise]].to_numpy(dtype=float)
    reps = find_reps(primary, fps, prominence=REP_PROMINENCE[exercise])
    row["rep__count"] = len(reps)
    if not reps:
        return row
    table = repetition_table(angles, reps, exercise, fps)
    rom = np.array([r.amplitude for r in reps])  # vârf minus vale; fereastra repetării e tăiată la 10% deasupra văii
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        row["rep__rom_mean"] = float(np.nanmean(rom))
        row["rep__rom_cv"] = _cv(rom)
        # Oboseala: amplitudinea ultimelor repetări față de primele.
        if len(rom) >= 3:
            third = max(1, len(rom) // 3)
            row["rep__rom_fatigue"] = float(np.nanmean(rom[-third:]) / np.nanmean(rom[:third]))
        row["rep__peak_mean"] = float(np.nanmean([primary[r.peak] for r in reps]))
        row["rep__valley_mean"] = float(np.nanmean(valleys(primary, reps)))
        row["rep__up_s"] = float(table["up_s"].mean())
        row["rep__down_s"] = float(table["down_s"].mean())
        row["rep__duration_cv"] = _cv(table["up_s"] + table["down_s"])
        row["rep__interval_cv"] = _cv(np.diff([r.peak for r in reps]))
        row["rep__jerk"] = float(np.nanmedian(np.log(table["jerk"]))) if table["jerk"].notna().any() else np.nan
        row["rep__compensation"] = float(np.nanmean(table["compensation"]))
        if exercise in SYMMETRY_PAIR:
            row["rep__asymmetry"] = float(np.nanmean(table["asymmetry"]))
    return row
