"""Grupul C: mărimile alese de clinicienii KIMORE pentru fiecare exercițiu, traduse din MATLAB.

Sursa: data/kimore/raw/.../Script/feat_extract_Ex1..5.m. Scripturile calculează curbe (o valoare pe cadru);
aici calculăm aceleași curbe, apoi le rezumăm în numere, ca modelul să le poată folosi.

Adaptări față de MATLAB:
- Spine_Shoulder și Spine_Base nu există în MediaPipe: folosim mijlocul umerilor și mijlocul șoldurilor,
  la fel și pentru Kinect, ca cele două surse să fie comparabile.
- Hand (Kinect) devine încheietura, pe care o au ambele surse.
- MediaPipe dă coordonate față de mijlocul șoldurilor, nu față de cameră, deci pozițiile absolute nu au sens.
  Unde MATLAB folosește o poziție absolută (Es4: baza coloanei), folosim poziția față de glezne.
- Distanțele se împart la lungimea trunchiului persoanei, ca să nu depindă de cât de înaltă e.
"""
import warnings

import numpy as np

from src.features import angle_at
from src.reps import find_reps, valleys

CURVE_STATISTICS = ["mean", "std", "range"]
PEAK_STATISTICS = ["peak_mean", "peak_cv", "valley_mean", "interval_cv"]
PEAK_PROMINENCE = 0.3  # un vârf trebuie să iasă cu 30% din amplitudinea curbei peste vale


def _distance(a, b):
    return np.linalg.norm(a - b, axis=1)


def _atan2_degrees(y, x):
    return np.degrees(np.arctan2(y, x))


def _trunk_area(j):
    """Aria trunchiului ca două triunghiuri (formula lui Heron), exact ca în MATLAB."""
    def heron(a, b, c):
        s = (a + b + c) / 2
        return np.sqrt(np.clip(s * (s - a) * (s - b) * (s - c), 0, None))
    shoulders = _distance(j["shoulder_L"], j["shoulder_R"])
    hips = _distance(j["hip_L"], j["hip_R"])
    diagonal = _distance(j["shoulder_R"], j["hip_L"])
    right = heron(hips, diagonal, _distance(j["shoulder_R"], j["hip_R"]))
    left = heron(shoulders, diagonal, _distance(j["shoulder_L"], j["hip_L"]))
    return right + left


def clinical_curves(j, exercise):
    """Curbele din scriptul MATLAB al exercițiului. Întoarce (curbe principale, curbe de control)."""
    mid_shoulder = (j["shoulder_L"] + j["shoulder_R"]) / 2
    mid_hip = (j["hip_L"] + j["hip_R"]) / 2
    mid_ankle = (j["ankle_L"] + j["ankle_R"]) / 2
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        trunk = np.nanmedian(_distance(mid_shoulder, mid_hip))
    if not np.isfinite(trunk) or trunk == 0:
        trunk = np.nan

    def side(name, function):
        return {f"{name}_L": function("L", "R"), f"{name}_R": function("R", "L")}

    elbow = side("elbow", lambda s, o: angle_at(j[f"shoulder_{s}"], j[f"elbow_{s}"], j[f"wrist_{s}"]))
    knee = side("knee", lambda s, o: angle_at(j[f"hip_{s}"], j[f"knee_{s}"], j[f"ankle_{s}"]))
    # Unghiul axilei: brațul față de linia umăr → șoldul opus (în MATLAB, „fianco”).
    axilla = side("axilla", lambda s, o: angle_at(j[f"elbow_{s}"], j[f"shoulder_{s}"], j[f"hip_{o}"]))
    # „Angolo C”: șoldul față de baza coloanei; cu baza = mijlocul șoldurilor, e înclinarea bazinului în plan frontal.
    pelvis_tilt = _atan2_degrees(j["hip_L"][:, 1] - j["hip_R"][:, 1], np.abs(j["hip_L"][:, 0] - j["hip_R"][:, 0]))
    hip_depth = (j["hip_L"][:, 2] - j["hip_R"][:, 2]) / trunk

    if exercise == 1:  # ridicarea brațelor în față
        primary = side("shoulder_ext", lambda s, o: _atan2_degrees(
            mid_shoulder[:, 2] - j[f"elbow_{s}"][:, 2], mid_shoulder[:, 1] - j[f"elbow_{s}"][:, 1]))
        control = {**elbow, **knee, "pelvis_tilt": pelvis_tilt, "trunk_area": _trunk_area(j) / trunk ** 2,
                   "hand_distance": _distance(j["wrist_L"], j["wrist_R"]) / trunk,
                   "ankle_distance": _distance(j["ankle_L"], j["ankle_R"]) / trunk}
    elif exercise == 2:  # înclinarea laterală a trunchiului, brațele sus
        primary = side("trunk_side", lambda s, o: _atan2_degrees(
            j[f"shoulder_{s}"][:, 0] - j[f"hip_{s}"][:, 0], j[f"shoulder_{s}"][:, 1] - j[f"hip_{s}"][:, 1]))
        control = {**elbow, **knee, **axilla, "pelvis_tilt": pelvis_tilt, "hip_depth": hip_depth,
                   **side("wrist_depth", lambda s, o: (j[f"wrist_{s}"][:, 2] - mid_shoulder[:, 2]) / trunk),
                   "pelvis_shift_x": (mid_hip[:, 0] - mid_ankle[:, 0]) / trunk}
    elif exercise == 3:  # rotația trunchiului cu brațele în față
        primary = {"elbow_gap": np.abs(j["elbow_L"][:, 0] - j["elbow_R"][:, 0]) / trunk}
        control = {**elbow, **knee, **axilla, "pelvis_tilt": pelvis_tilt, "hip_depth": hip_depth,
                   **side("arm_spine", lambda s, o: angle_at(j[f"elbow_{s}"], j[f"shoulder_{s}"], mid_shoulder)),
                   **side("wrist_height", lambda s, o: (2 * j[f"wrist_{s}"][:, 1] - j[f"elbow_{s}"][:, 1]
                                                        - j[f"shoulder_{s}"][:, 1]) / trunk),
                   "hip_width": _distance(j["hip_L"], j["hip_R"]) / trunk}
    elif exercise == 4:  # rotația bazinului
        primary = {"pelvis_shift_z": (mid_hip[:, 2] - mid_ankle[:, 2]) / trunk,
                   "pelvis_shift_x": (mid_hip[:, 0] - mid_ankle[:, 0]) / trunk}
        control = {**elbow, **knee, **axilla, "hip_depth": hip_depth,
                   "hip_height": (j["hip_L"][:, 1] - j["hip_R"][:, 1]) / trunk,
                   "shoulder_depth": (j["shoulder_L"][:, 2] - j["shoulder_R"][:, 2]) / trunk,
                   "shoulder_width": _distance(j["shoulder_L"], j["shoulder_R"]) / trunk}
    elif exercise == 5:  # genuflexiuni
        primary = side("knee_sagittal", lambda s, o: _atan2_degrees(
            j[f"hip_{s}"][:, 1] - j[f"knee_{s}"][:, 1], j[f"hip_{s}"][:, 2] - j[f"knee_{s}"][:, 2])
            + _atan2_degrees(j[f"knee_{s}"][:, 1] - j[f"ankle_{s}"][:, 1], j[f"ankle_{s}"][:, 2] - j[f"knee_{s}"][:, 2]))
        control = {"trunk_area": _trunk_area(j) / trunk ** 2,
                   "shoulder_shift_z": (mid_shoulder[:, 2] - mid_hip[:, 2]) / trunk,
                   "shoulder_shift_x": (mid_shoulder[:, 0] - mid_hip[:, 0]) / trunk,
                   "knee_height": (j["knee_R"][:, 1] - j["knee_L"][:, 1]) / trunk}
    else:
        raise ValueError(f"exercitiu necunoscut: {exercise}")
    return primary, control


def clinical_feature_names(exercise):
    dummy = {name: np.zeros((3, 3)) + np.arange(3)[:, None] for name in (
        "shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "wrist_L", "wrist_R",
        "hip_L", "hip_R", "knee_L", "knee_R", "ankle_L", "ankle_R")}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        primary, control = clinical_curves(dummy, exercise)
    return ([f"clin__{c}__{s}" for c in primary for s in CURVE_STATISTICS + PEAK_STATISTICS]
            + [f"clin__{c}__{s}" for c in control for s in CURVE_STATISTICS])


def _curve_statistics(values):
    valid = values[~np.isnan(values)]
    if len(valid) < 2:
        return dict.fromkeys(CURVE_STATISTICS, np.nan)
    p5, p95 = np.percentile(valid, [5, 95])
    return {"mean": float(valid.mean()), "std": float(valid.std()), "range": float(p95 - p5)}


def _peak_statistics(values, fps):
    """Vârfurile curbei principale, ca findpeaks din MATLAB: cât de sus, cât de constant, în ce ritm."""
    out = dict.fromkeys(PEAK_STATISTICS, np.nan)
    valid = values[~np.isnan(values)]
    if len(valid) < 2:
        return out
    spread = np.percentile(valid, 95) - np.percentile(valid, 5)
    if spread <= 0:
        return out
    reps = find_reps(values, fps, prominence=PEAK_PROMINENCE * spread)
    if not reps:
        return out
    peaks = np.array([values[r.peak] for r in reps])
    intervals = np.diff([r.peak for r in reps])
    out["peak_mean"] = float(peaks.mean())
    out["valley_mean"] = float(valleys(values, reps).mean())
    if len(peaks) >= 2:
        out["peak_cv"] = float(peaks.std() / (abs(peaks.mean()) + spread))
    if len(intervals) >= 2:
        out["interval_cv"] = float(intervals.std() / intervals.mean())
    return out


def clinical_summary(joints, exercise, fps=30.0):
    """Numerele grupului C pentru o execuție, în ordinea din clinical_feature_names."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        primary, control = clinical_curves(joints, exercise)
        row = {}
        for name, values in primary.items():
            values = np.asarray(values, dtype=float)
            stats = {**_curve_statistics(values), **_peak_statistics(values, fps)}
            row.update({f"clin__{name}__{s}": stats[s] for s in CURVE_STATISTICS + PEAK_STATISTICS})
        for name, values in control.items():
            stats = _curve_statistics(np.asarray(values, dtype=float))
            row.update({f"clin__{name}__{s}": stats[s] for s in CURVE_STATISTICS})
    return row
