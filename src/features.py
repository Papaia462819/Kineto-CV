"""Transformă punctele în unghiuri, câte unul pe cadru, și rezumă fiecare repetare.

Aceleași formule merg pe MediaPipe și pe Kinect, pentru că ambele sunt aduse la aceleași nume și axe:
x spre stânga persoanei, y în sus, z dinspre cameră spre persoană.
"""
import numpy as np
import pandas as pd

MEDIAPIPE = dict(
    shoulder_L=11, shoulder_R=12, elbow_L=13, elbow_R=14, wrist_L=15, wrist_R=16,
    hip_L=23, hip_R=24, knee_L=25, knee_R=26, ankle_L=27, ankle_R=28,
)
KINECT = dict(
    shoulder_L=4, shoulder_R=8, elbow_L=5, elbow_R=9, wrist_L=6, wrist_R=10,
    hip_L=12, hip_R=16, knee_L=13, knee_R=17, ankle_L=14, ankle_R=18,
)
_SOURCES = {"mediapipe": (MEDIAPIPE, np.array([1.0, -1.0, 1.0])), "kinect": (KINECT, np.array([-1.0, 1.0, 1.0]))}

# Unghiul din care se numără repetările la fiecare exercițiu KIMORE.
PRIMARY_ANGLE = {1: "shoulder_mean", 2: "trunk_tilt", 3: "shoulder_rotation", 4: "trunk_tilt", 5: "knee_flexion_mean"}
# Cât trebuie să iasă un vârf deasupra văii ca să conteze ca repetare, în grade.
REP_PROMINENCE = {1: 25.0, 2: 8.0, 3: 30.0, 4: 5.0, 5: 15.0}
# Unghiuri care ar trebui să rămână aproape constante; mișcarea lor înseamnă compensare.
COMPENSATION_ANGLE = {1: "trunk_lean", 2: "trunk_lean", 3: "pelvis_rotation", 4: "trunk_rotation", 5: "trunk_lean"}
# Perechea stânga/dreapta pentru simetrie, unde exercițiul o are.
SYMMETRY_PAIR = {1: ("shoulder_L", "shoulder_R"), 5: ("knee_flexion_L", "knee_flexion_R")}


def named_joints(points, source="mediapipe", mirrored=False):
    """points: cadre × puncte × (3 sau 4). Întoarce {nume: cadre × 3} în axele comune.

    mirrored: punctele MediaPipe vin dintr-o imagine în oglindă, deci x e inversat.
    """
    mapping, signs = _SOURCES[source]
    if mirrored and source == "mediapipe":
        signs = signs * np.array([-1.0, 1.0, 1.0])
    return {name: points[:, index, :3] * signs for name, index in mapping.items()}


def angle_at(a, b, c):
    """Unghiul în punctul b, între segmentele b→a și b→c, în grade, pentru fiecare cadru."""
    v1, v2 = a - b, c - b
    cosine = np.sum(v1 * v2, axis=1) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1))
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))


def _top_view_direction(left, right):
    """Direcția liniei dreapta→stânga văzută de sus: 0° când persoana stă cu fața la cameră."""
    line = left - right
    return np.arctan2(line[:, 2], line[:, 0])


def _wrap_degrees(radians):
    return np.degrees(np.arctan2(np.sin(radians), np.cos(radians)))


def compute_angles(joints):
    """Un rând pe cadru, o coloană pe unghi, în grade. Un cadru lipsă dă NaN pe tot rândul."""
    shoulders = (joints["shoulder_L"] + joints["shoulder_R"]) / 2
    hips = (joints["hip_L"] + joints["hip_R"]) / 2
    trunk = shoulders - hips
    shoulder_line = _top_view_direction(joints["shoulder_L"], joints["shoulder_R"])
    hip_line = _top_view_direction(joints["hip_L"], joints["hip_R"])
    table = {
        "shoulder_L": angle_at(joints["elbow_L"], joints["shoulder_L"], joints["hip_L"]),
        "shoulder_R": angle_at(joints["elbow_R"], joints["shoulder_R"], joints["hip_R"]),
        "elbow_L": angle_at(joints["shoulder_L"], joints["elbow_L"], joints["wrist_L"]),
        "elbow_R": angle_at(joints["shoulder_R"], joints["elbow_R"], joints["wrist_R"]),
        "knee_flexion_L": 180 - angle_at(joints["hip_L"], joints["knee_L"], joints["ankle_L"]),
        "knee_flexion_R": 180 - angle_at(joints["hip_R"], joints["knee_R"], joints["ankle_R"]),
        "hip_flexion_L": 180 - angle_at(joints["shoulder_L"], joints["hip_L"], joints["knee_L"]),
        "hip_flexion_R": 180 - angle_at(joints["shoulder_R"], joints["hip_R"], joints["knee_R"]),
        "trunk_tilt": np.degrees(np.arctan2(trunk[:, 0], trunk[:, 1])),  # pozitiv spre stânga persoanei
        "trunk_lean": np.degrees(np.arctan2(-trunk[:, 2], trunk[:, 1])),  # pozitiv spre cameră
        "trunk_rotation": _wrap_degrees(shoulder_line - hip_line),
        "pelvis_rotation": _wrap_degrees(hip_line),
        "shoulder_rotation": _wrap_degrees(shoulder_line),
    }
    table = pd.DataFrame(table)
    table["shoulder_mean"] = table[["shoulder_L", "shoulder_R"]].mean(axis=1, skipna=False)
    table["knee_flexion_mean"] = table[["knee_flexion_L", "knee_flexion_R"]].mean(axis=1, skipna=False)
    return table


def _normalized_jerk(values, fps):
    """Cât de bruscă e mișcarea, independent de durată și amplitudine. Mai mic = mai lin."""
    if len(values) < 4 or np.isnan(values).any():
        return np.nan
    amplitude = values.max() - values.min()
    if amplitude == 0:
        return np.nan
    dt = 1.0 / fps
    jerk = np.gradient(np.gradient(np.gradient(values, dt), dt), dt)
    duration = len(values) * dt
    return float(np.sqrt(0.5 * np.sum(jerk ** 2) * dt * duration ** 5 / amplitude ** 2))


def repetition_table(angles, reps, exercise, fps):
    """Un rând pe repetare: amplitudine, tempo, netezime, compensare, simetrie."""
    primary = angles[PRIMARY_ANGLE[exercise]].to_numpy()
    rows = []
    for number, rep in enumerate(reps, 1):
        window = slice(rep.start, rep.end + 1)
        values = primary[window]
        row = {
            "rep": number, "start": rep.start, "peak": rep.peak, "end": rep.end,
            "valid_fraction": rep.valid_fraction,
            "rom": float(np.nanmax(values) - np.nanmin(values)),
            "up_s": (rep.peak - rep.start) / fps,
            "down_s": (rep.end - rep.peak) / fps,
            "jerk": _normalized_jerk(values, fps),
        }
        compensation = angles[COMPENSATION_ANGLE[exercise]].to_numpy()[window]
        row["compensation"] = float(np.nanmax(np.abs(compensation - np.nanmedian(compensation))))
        if exercise in SYMMETRY_PAIR:
            left, right = (angles[name].to_numpy()[window] for name in SYMMETRY_PAIR[exercise])
            row["asymmetry"] = float(abs((np.nanmax(left) - np.nanmin(left)) - (np.nanmax(right) - np.nanmin(right))))
        rows.append(row)
    return pd.DataFrame(rows)
