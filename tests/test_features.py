import numpy as np
import pandas as pd
import pytest

from src.features import MEDIAPIPE, compute_angles, angle_at, named_joints, repetition_table
from src.reps import Rep


def standing():
    """O persoană cu fața la cameră, în axele comune: x spre stânga ei, y în sus, z spre spatele ei."""
    return {
        "shoulder_L": [0.2, 1.4, 0.0], "shoulder_R": [-0.2, 1.4, 0.0],
        "elbow_L": [0.2, 1.1, 0.0], "elbow_R": [-0.2, 1.1, 0.0],
        "wrist_L": [0.2, 0.8, 0.0], "wrist_R": [-0.2, 0.8, 0.0],
        "hip_L": [0.1, 0.9, 0.0], "hip_R": [-0.1, 0.9, 0.0],
        "knee_L": [0.1, 0.5, 0.0], "knee_R": [-0.1, 0.5, 0.0],
        "ankle_L": [0.1, 0.1, 0.0], "ankle_R": [-0.1, 0.1, 0.0],
    }


def as_joints(pose, frames=1):
    return {name: np.tile(np.array(p, dtype=float), (frames, 1)) for name, p in pose.items()}


def test_guide_numeric_example():
    a, b, c = (np.array([v], dtype=float) for v in ([0, -0.30, 0], [0, 0, 0], [0.20, 0.15, 0]))
    assert angle_at(a, b, c)[0] == pytest.approx(126.87, abs=0.01)


def test_standing_person_has_neutral_angles():
    row = compute_angles(as_joints(standing())).iloc[0]
    assert row["elbow_L"] == pytest.approx(180)
    assert row["knee_flexion_R"] == pytest.approx(0)
    assert row["trunk_tilt"] == pytest.approx(0)
    assert row["trunk_rotation"] == pytest.approx(0)
    assert row["pelvis_rotation"] == pytest.approx(0)
    assert row["shoulder_L"] < 20


def test_arm_raised_sideways_is_about_90_degrees():
    pose = standing()
    pose["elbow_L"] = [0.5, 1.4, 0.0]
    pose["shoulder_L"] = [0.2, 1.4, 0.0]
    pose["hip_L"] = [0.2, 0.9, 0.0]
    assert compute_angles(as_joints(pose)).iloc[0]["shoulder_L"] == pytest.approx(90)


def test_trunk_tilt_is_signed_towards_person_left():
    pose = standing()
    pose["shoulder_L"] = [0.5, 1.4, 0.0]
    pose["shoulder_R"] = [0.1, 1.4, 0.0]
    tilt = compute_angles(as_joints(pose)).iloc[0]["trunk_tilt"]
    assert tilt == pytest.approx(np.degrees(np.arctan2(0.3, 0.5)))


def test_shoulder_rotation_relative_to_pelvis():
    pose = standing()
    pose["shoulder_L"] = [0.0, 1.4, 0.2]
    pose["shoulder_R"] = [0.0, 1.4, -0.2]
    row = compute_angles(as_joints(pose)).iloc[0]
    assert abs(row["trunk_rotation"]) == pytest.approx(90)
    assert abs(row["shoulder_rotation"]) == pytest.approx(90)
    assert row["pelvis_rotation"] == pytest.approx(0)


def test_missing_frame_gives_nan_row():
    joints = as_joints(standing(), 3)
    for name in joints:
        joints[name][1] = np.nan
    table = compute_angles(joints)
    assert table.iloc[1].isna().all()
    assert table.iloc[0].notna().all()


def test_same_body_in_both_sources_gives_same_angles():
    pose = standing()
    pose["elbow_L"] = [0.4, 1.2, -0.1]
    pose["knee_R"] = [-0.2, 0.55, -0.2]
    common = as_joints(pose)
    mp = np.zeros((1, 33, 4))
    from src.features import KINECT
    kinect = np.zeros((1, 25, 3))
    for name, value in common.items():
        mp[0, MEDIAPIPE[name], :3] = value[0] * [1, -1, 1]
        kinect[0, KINECT[name]] = value[0] * [-1, 1, 1]
    a = compute_angles(named_joints(mp, "mediapipe"))
    b = compute_angles(named_joints(kinect, "kinect"))
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(a, compute_angles(common))


def test_mirrored_video_gives_tilt_with_correct_sign():
    pose = standing()
    pose["shoulder_L"] = [0.5, 1.4, 0.0]
    pose["shoulder_R"] = [0.1, 1.4, 0.0]
    common = as_joints(pose)
    mirrored = np.zeros((1, 33, 4))
    for name, value in common.items():
        mirrored[0, MEDIAPIPE[name], :3] = value[0] * [-1, -1, 1]
    tilt = compute_angles(named_joints(mirrored, "mediapipe", mirrored=True)).iloc[0]["trunk_tilt"]
    assert tilt == pytest.approx(compute_angles(common).iloc[0]["trunk_tilt"])
    assert tilt > 0


def test_repetition_table_measures_each_rep():
    t = np.arange(90) / 30
    knee = 45 - 45 * np.cos(2 * np.pi * t / 3)
    angles = pd.DataFrame({
        "knee_flexion_mean": knee, "knee_flexion_L": knee, "knee_flexion_R": knee * 0.8,
        "trunk_lean": np.linspace(0, 10, 90),
    })
    table = repetition_table(angles, [Rep(0, 45, 89, 90.0)], 5, 30)
    row = table.iloc[0]
    assert row["rom"] == pytest.approx(90, abs=0.1)
    assert row["up_s"] == pytest.approx(1.5)
    assert row["down_s"] == pytest.approx(44 / 30)
    assert row["asymmetry"] == pytest.approx(18, abs=0.1)
    assert row["compensation"] == pytest.approx(5, abs=0.1)
    assert row["jerk"] > 0


def test_smoother_motion_has_smaller_jerk():
    t = np.arange(90) / 30
    smooth = 45 - 45 * np.cos(2 * np.pi * t / 3)
    shaky = smooth + 3 * np.sin(2 * np.pi * 5 * t)
    def jerk(values):
        angles = pd.DataFrame({"shoulder_mean": values, "shoulder_L": values, "shoulder_R": values,
                               "trunk_lean": np.zeros(90)})
        return repetition_table(angles, [Rep(0, 45, 89, 90.0)], 1, 30).iloc[0]["jerk"]
    assert jerk(smooth) < jerk(shaky)
