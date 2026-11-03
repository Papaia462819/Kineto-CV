import numpy as np
import pytest

from src.filters import OneEuroFilter, fill_gaps, savgol, smooth_keypoints

FPS = 30.0


def test_fill_gaps_fills_short_gap_linearly():
    assert fill_gaps([0, np.nan, 2])[1] == pytest.approx(1)


def test_fill_gaps_keeps_long_gap_and_edges():
    x = fill_gaps([np.nan, 0, np.nan, np.nan, np.nan, 4, np.nan], max_gap=2)
    assert np.isnan(x[[0, 2, 3, 4, 6]]).all()


def test_savgol_reduces_noise_and_keeps_peak_height():
    t = np.arange(300) / FPS
    clean = 45 * np.sin(2 * np.pi * t / 4) + 45
    noisy = clean + np.random.default_rng(0).normal(0, 3, len(t))
    smooth = savgol(noisy)
    assert np.std(smooth - clean) < 0.6 * np.std(noisy - clean)
    assert abs(smooth.max() - clean.max()) < 3


def test_savgol_does_not_cross_a_long_gap():
    x = np.concatenate([np.zeros(40), np.full(30, np.nan), np.full(40, 100.0)])
    smooth = savgol(x, max_gap=15)
    assert np.isnan(smooth[50])
    assert smooth[39] == pytest.approx(0)
    assert smooth[70] == pytest.approx(100)


def test_savgol_leaves_short_run_unfiltered():
    x = np.concatenate([[1.0, 5.0, 2.0], np.full(30, np.nan)])
    assert savgol(x, max_gap=2)[:3] == pytest.approx([1, 5, 2])


def test_smooth_keypoints_keeps_shape_and_visibility():
    kp = np.random.default_rng(1).normal(size=(50, 33, 4))
    out = smooth_keypoints(kp)
    assert out.shape == kp.shape
    assert np.array_equal(out[:, :, 3], kp[:, :, 3])
    assert not np.array_equal(out[:, :, 0], kp[:, :, 0])


def test_one_euro_reduces_noise_at_rest():
    noisy = np.random.default_rng(2).normal(0, 0.01, 300)
    f = OneEuroFilter(min_cutoff=1.0, beta=1.0)
    out = np.array([f(v, i / FPS) for i, v in enumerate(noisy)])
    assert out[30:].std() < 0.5 * noisy[30:].std()


def test_one_euro_follows_fast_motion_better_with_higher_beta():
    t = np.arange(120) / FPS
    x = 0.5 * np.sin(2 * np.pi * t)
    def error(beta):
        f = OneEuroFilter(min_cutoff=0.5, beta=beta)
        return np.abs(np.array([f(v, s) for v, s in zip(x, t)]) - x).mean()
    assert error(5.0) < error(0.0)


def test_one_euro_filters_whole_matrix_and_resets_on_missing_frame():
    f = OneEuroFilter()
    frame = np.ones((33, 3))
    assert f(frame, 0.0).shape == (33, 3)
    f(frame * 2, 1 / FPS)
    assert np.isnan(f(frame * np.nan, 2 / FPS)).all()
    assert f(frame * 9, 3 / FPS) == pytest.approx(frame * 9)


def test_one_euro_rejects_time_going_backwards():
    f = OneEuroFilter()
    f(1.0, 1.0)
    with pytest.raises(ValueError):
        f(1.0, 1.0)
