import numpy as np

from src.session import ExecutionResult, resample


def test_resample_keeps_30_fps_recordings_unchanged():
    points = np.random.default_rng(0).normal(size=(90, 33, 4))
    points[10] = np.nan
    (same,) = resample(np.arange(90) / 30.0, points)
    np.testing.assert_array_equal(same, points)


def test_resample_interpolates_a_slower_camera():
    times = np.arange(0, 3, 0.1)  # 10 cadre pe secundă, 3 secunde
    points = np.repeat(times[:, None, None], 33, axis=1).repeat(4, axis=2)  # valoarea = timpul
    (out,) = resample(times, points)
    assert len(out) == 88  # de la 0 la 2,9 s, din 1/30 în 1/30 s
    np.testing.assert_allclose(out[:, 0, 0], np.arange(88) / 30.0, atol=1e-9)


def test_resample_does_not_invent_missing_frames():
    times = np.arange(10) / 10.0
    points = np.ones((10, 33, 4))
    points[4] = np.nan
    (out,) = resample(times, points)
    grid = np.arange(len(out)) / 30.0
    near_gap = (grid > 0.3) & (grid < 0.5)
    assert np.isnan(out[near_gap]).all()
    assert not np.isnan(out[~near_gap & (grid != 0.4)]).any()


def test_result_dict_turns_nan_into_none():
    result = ExecutionResult(1, 10.0, 0.9, 8.0, 0, np.nan, np.nan, None, 6.0, None, None, ["x"])
    data = result.to_dict()
    assert data["rom_mean"] is None and data["warnings"] == ["x"]
