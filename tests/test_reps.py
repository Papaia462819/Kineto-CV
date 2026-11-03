import numpy as np
import pytest

from src.reps import RepCounter, find_reps

FPS = 30


def wave(reps=5, period_s=3.0, rest_s=2.0, amplitude=90.0):
    """Repaus, apoi repetări line, apoi repaus."""
    rest = np.zeros(int(rest_s * FPS))
    t = np.arange(int(period_s * FPS)) / (period_s * FPS)
    one = amplitude * (1 - np.cos(2 * np.pi * t)) / 2
    return np.concatenate([rest, *[one] * reps, rest])


def live(signal, **options):
    counter = RepCounter(FPS, **options)
    return [r for r in (counter.update(v) for v in signal) if r], counter


def test_counts_five_clean_reps():
    assert len(find_reps(wave(), FPS)) == 5


def test_noise_does_not_create_reps():
    noisy = wave() + np.random.default_rng(0).normal(0, 2, len(wave()))
    assert len(find_reps(noisy, FPS)) == 5


def test_small_movement_is_ignored():
    assert find_reps(wave(amplitude=9.0), FPS) == []


def test_flat_or_empty_signal_has_no_reps():
    assert find_reps(np.zeros(100), FPS) == []
    assert find_reps(np.full(100, np.nan), FPS) == []


def test_double_hump_counts_once():
    x = wave(reps=1, period_s=4.0)
    x = x + 12 * np.sin(np.arange(len(x)) / 3.0) * (x > 70)
    assert len(find_reps(x, FPS)) == 1


def test_rep_boundaries_exclude_rest():
    rep = find_reps(wave(reps=1), FPS)[0]
    assert rep.start > 2.0 * FPS
    assert rep.end < 5.0 * FPS
    assert rep.start < rep.peak < rep.end
    assert rep.amplitude == pytest.approx(90, abs=1)


def test_short_gap_is_bridged_and_reported():
    x = wave()
    peak = int(3.5 * FPS)
    x[peak - 3:peak + 3] = np.nan
    reps = find_reps(x, FPS)
    assert len(reps) == 5
    assert reps[0].valid_fraction < 1.0
    assert reps[1].valid_fraction == 1.0


def test_long_gap_loses_the_rep_instead_of_inventing_one():
    x = wave()
    x[int(2.5 * FPS):int(5.5 * FPS)] = np.nan
    assert len(find_reps(x, FPS)) == 4


def test_live_counter_matches_offline():
    x = wave() + np.random.default_rng(3).normal(0, 2, len(wave()))
    reps, counter = live(x)
    offline = find_reps(x, FPS)
    assert counter.count == len(offline) == 5
    assert all(abs(a.peak - b.peak) <= 10 for a, b in zip(reps, offline))


def test_live_reports_after_the_peak_not_before():
    reps, _ = live(wave(reps=1))
    assert reps[0].end > reps[0].peak


def test_live_ignores_small_movement_and_missing_frames():
    assert live(wave(amplitude=9.0))[1].count == 0
    assert live(np.full(100, np.nan))[1].count == 0


def test_live_survives_short_gap():
    x = wave()
    x[int(3.0 * FPS):int(3.2 * FPS)] = np.nan
    assert live(x)[1].count == 5


def test_live_does_not_join_movement_across_long_gap():
    x = wave(reps=1)
    x[int(3.0 * FPS):int(6.0 * FPS)] = np.nan
    assert live(x)[1].count == 0
