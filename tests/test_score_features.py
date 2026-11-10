import numpy as np
import pandas as pd
import pytest

from src.clinical_features import clinical_feature_names, clinical_summary
from src.execution_features import ANGLES, REPETITION_NAMES, repetition_summary

FPS = 30.0


def angles_with_reps(amplitudes, period_s=3.0, rest_s=1.0):
    """Unghiul umerilor urcă și coboară o dată pe repetare, cu pauză între repetări."""
    pieces = [np.zeros(int(rest_s * FPS))]
    for amplitude in amplitudes:
        t = np.arange(int(period_s * FPS))
        pieces += [amplitude * np.sin(np.pi * t / len(t)), np.zeros(int(rest_s * FPS))]
    curve = 20 + np.concatenate(pieces)
    table = pd.DataFrame({a: np.full(len(curve), 10.0) for a in ANGLES})
    table["shoulder_L"] = table["shoulder_R"] = curve
    table["shoulder_mean"] = curve
    table["knee_flexion_mean"] = 0.0
    return table


def test_repetition_summary_counts_and_measures_reps():
    row = repetition_summary(angles_with_reps([100] * 5), exercise=1, fps=FPS)
    assert set(row) == set(REPETITION_NAMES)
    assert row["rep__count"] == 5
    assert row["rep__rom_mean"] == pytest.approx(100, rel=0.05)
    assert row["rep__rom_cv"] == pytest.approx(0, abs=0.02)
    assert row["rep__interval_cv"] == pytest.approx(0, abs=0.02)
    assert row["rep__asymmetry"] == pytest.approx(0, abs=1e-6)


def test_fatigue_sees_shrinking_amplitude():
    row = repetition_summary(angles_with_reps([120, 120, 100, 80, 60, 60]), exercise=1, fps=FPS)
    assert row["rep__count"] == 6
    assert row["rep__rom_fatigue"] == pytest.approx(0.5, rel=0.05)
    assert row["rep__rom_cv"] > 0.2


def test_no_reps_gives_zero_count_and_nan():
    row = repetition_summary(angles_with_reps([]), exercise=1, fps=FPS)
    assert row["rep__count"] == 0
    assert np.isnan(row["rep__rom_mean"])


def standing_joints(frames=300):
    base = {"shoulder_L": (0.2, 1.4, 2.0), "shoulder_R": (-0.2, 1.4, 2.0), "elbow_L": (0.2, 1.1, 2.0),
            "elbow_R": (-0.2, 1.1, 2.0), "wrist_L": (0.2, 0.8, 2.0), "wrist_R": (-0.2, 0.8, 2.0),
            "hip_L": (0.1, 0.9, 2.0), "hip_R": (-0.1, 0.9, 2.0), "knee_L": (0.1, 0.5, 2.0),
            "knee_R": (-0.1, 0.5, 2.0), "ankle_L": (0.1, 0.1, 2.0), "ankle_R": (-0.1, 0.1, 2.0)}
    return {name: np.tile(np.array(xyz, dtype=float), (frames, 1)) for name, xyz in base.items()}


@pytest.mark.parametrize("exercise", [1, 2, 3, 4, 5])
def test_clinical_summary_matches_names(exercise):
    row = clinical_summary(standing_joints(), exercise, FPS)
    assert list(row) == clinical_feature_names(exercise)


def test_forward_arm_raise_angle_and_peaks():
    """Es1: brațele întinse urcă în față de la 0° la 90° de 5 ori; unghiul MATLAB din plan sagital urmărește asta."""
    joints = standing_joints(frames=5 * 90 + 30)
    t = np.arange(len(joints["elbow_L"]))
    lift = np.radians(90) * np.clip(np.sin(np.pi * (t - 15) / 90), 0, None) * ((t >= 15) & (t < 15 + 5 * 90))
    for side in "LR":
        shoulder = joints[f"shoulder_{side}"]
        for joint, length in (("elbow", 0.3), ("wrist", 0.6)):
            joints[f"{joint}_{side}"] = shoulder + length * np.c_[0 * t, -np.cos(lift), -np.sin(lift)]
    row = clinical_summary(joints, 1, FPS)
    assert row["clin__shoulder_ext_L__peak_mean"] == pytest.approx(90, abs=2)
    assert row["clin__shoulder_ext_L__valley_mean"] == pytest.approx(0, abs=2)
    assert row["clin__shoulder_ext_L__interval_cv"] == pytest.approx(0, abs=0.02)
    assert row["clin__elbow_L__mean"] == pytest.approx(180, abs=1e-6)
    assert row["clin__hand_distance__mean"] == pytest.approx(0.4 / 0.5)  # 40 cm între mâini / trunchi de 50 cm


def test_distances_do_not_depend_on_body_size():
    small, big = standing_joints(), {k: 1.3 * v for k, v in standing_joints().items()}
    a, b = clinical_summary(small, 1, FPS), clinical_summary(big, 1, FPS)
    for name in ("clin__trunk_area__mean", "clin__hand_distance__mean", "clin__ankle_distance__mean"):
        assert a[name] == pytest.approx(b[name])


def test_missing_frames_do_not_crash():
    joints = standing_joints()
    for value in joints.values():
        value[50:120] = np.nan
    row = clinical_summary(joints, 4, FPS)
    assert row["clin__shoulder_width__mean"] == pytest.approx(0.4 / 0.5)


def test_clinical_score_model_learns_and_stays_in_range():
    from src.clinical_features import clinical_feature_names
    from src.clinical_score import ClinicalScoreModel
    from src.execution_features import FEATURE_NAMES

    rng = np.random.default_rng(0)
    rows = []
    for exercise in range(1, 6):
        names = FEATURE_NAMES + REPETITION_NAMES + clinical_feature_names(exercise)
        for i in range(40):
            quality = rng.uniform(0, 1)
            row = {name: rng.normal() for name in names}
            row["shoulder_L__range"] = 100 * quality + rng.normal(0, 5)  # mișcarea mai amplă → scor mai mare
            rows.append({**row, "exercise": exercise, "score_total": 10 + 40 * quality})
    table = pd.DataFrame(rows)
    train, test = table.iloc[::2].reset_index(drop=True), table.iloc[1::2].reset_index(drop=True)
    prediction = ClinicalScoreModel().fit(train).predict(test)
    assert prediction.min() >= 0 and prediction.max() <= 50
    assert np.corrcoef(prediction, test["score_total"])[0, 1] > 0.8
