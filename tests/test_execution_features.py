import numpy as np
import pandas as pd
import pytest

from src.execution_features import ANGLES, FEATURE_NAMES, STATISTICS, angles_from_kinect, summarize, valid_seconds


def angles(frames=90, value=None):
    t = np.arange(frames)
    table = pd.DataFrame({a: 10.0 + 0 * t for a in ANGLES})
    table["shoulder_L"] = 90 + 60 * np.sin(2 * np.pi * t / 30) if value is None else value
    return table


def test_feature_list_is_13_angles_times_6_statistics():
    assert len(FEATURE_NAMES) == 78 == len(ANGLES) * len(STATISTICS)
    assert len(set(FEATURE_NAMES)) == 78


def test_summary_has_exactly_the_feature_columns():
    row = summarize(angles())
    assert list(row) == FEATURE_NAMES


def test_statistics_values():
    row = summarize(angles())
    assert row["shoulder_L__mean"] == pytest.approx(90, abs=0.5)
    assert row["shoulder_L__range"] == pytest.approx(row["shoulder_L__p95"] - row["shoulder_L__p5"])
    assert 100 < row["shoulder_L__range"] < 120
    assert row["elbow_L__std"] == pytest.approx(0)
    assert row["elbow_L__speed"] == pytest.approx(0)
    # sinus de amplitudine 60° cu perioada 1 s: viteza medie absolută = 4 · 60 = 240°/s
    assert row["shoulder_L__speed"] == pytest.approx(240, rel=0.05)


def test_missing_frames_are_ignored_and_do_not_create_speed():
    table = angles(value=np.r_[np.zeros(30), np.full(30, np.nan), np.full(30, 100.0)])
    row = summarize(table)
    assert row["shoulder_L__speed"] == pytest.approx(0)
    assert row["shoulder_L__mean"] == pytest.approx(50)


def test_empty_execution_gives_nan_not_crash():
    row = summarize(angles(value=np.full(90, np.nan)))
    assert np.isnan(row["shoulder_L__mean"])
    assert valid_seconds(angles(value=np.full(90, np.nan))) == 0


def test_valid_seconds_counts_only_complete_frames():
    table = angles()
    table.loc[:29, "trunk_tilt"] = np.nan
    assert valid_seconds(table, fps=30) == pytest.approx(2.0)


def test_kinect_angles_and_kept_fraction():
    points = np.zeros((40, 25, 3))
    for joint, xyz in {4: (-0.2, 1.4, 2), 8: (0.2, 1.4, 2), 5: (-0.2, 1.1, 2), 9: (0.2, 1.1, 2), 6: (-0.2, 0.8, 2),
                       10: (0.2, 0.8, 2), 12: (-0.1, 0.9, 2), 16: (0.1, 0.9, 2), 13: (-0.1, 0.5, 2), 17: (0.1, 0.5, 2),
                       14: (-0.1, 0.1, 2), 18: (0.1, 0.1, 2)}.items():
        points[:, joint] = xyz
    points[:10] = np.nan
    table, kept = angles_from_kinect(points)
    assert kept == pytest.approx(0.75)
    assert table["elbow_L"].iloc[20] == pytest.approx(180)
    assert table["knee_flexion_R"].iloc[20] == pytest.approx(0, abs=1e-6)
