import json

import numpy as np
import pytest

from src.feedback import GOOD_JOB, RULES_FILE, FeedbackEngine, RepTimes, load_rules

SETTINGS = {"hold_s": 0.7, "repeat_s": 6.0, "gap_s": 3.0}
ARMS = {"id": "arms_higher", "kind": "rep", "measure": "shoulder", "stat": "peak", "bad": "low", "threshold": 145,
        "priority": 3, "message": "Ridică brațele mai sus."}
HIPS = {"id": "hips_still", "kind": "hold", "measure": "pelvis_shift", "relative": True, "threshold": 10,
        "priority": 1, "message": "Ține șoldurile nemișcate."}
TILT = {"id": "tilt_more", "kind": "rep", "measure": "tilt", "stat": "both_sides", "relative": True, "bad": "low",
        "threshold": 10, "priority": 3, "message": "Înclină-te mai mult."}


def measures(**values):
    base = {"shoulder": 20.0, "pelvis_shift": 0.0, "tilt": 0.0}
    return {**base, **values}


def run_reps(engine, peaks, start_t=0.0, period=3.0, measure="shoulder", low=20.0):
    """O repetare pe perioadă: urcă până la vârf și coboară; întoarce mesajele spuse (timp, mesaj)."""
    said = []
    t = start_t
    for peak in peaks:
        for k in range(int(period * 30)):
            phase = k / (period * 30)
            value = low + (peak - low) * np.sin(np.pi * phase)
            rep = RepTimes(t - period + 1 / 30, t - period / 2, t, peak - low) if k == 0 and t > start_t else None
            message = engine.update(t, measures(**{measure: value}), rep)
            if message:
                said.append((round(t, 1), message))
            t += 1 / 30
    return said, t


def test_rep_rule_needs_two_of_three_and_praises_the_fix():
    engine = FeedbackEngine([ARMS], SETTINGS)
    said, _ = run_reps(engine, [160, 120, 160, 120, 120, 160, 160, 160])
    messages = [m for _, m in said]
    assert messages.count("Ridică brațele mai sus.") == 1  # o greșeală izolată nu sună; două din trei da
    assert messages[-1] == GOOD_JOB
    assert engine.summary() == {"Ridică brațele mai sus.": 1}


def test_hold_rule_needs_the_deviation_to_last():
    engine = FeedbackEngine([HIPS], SETTINGS)
    engine.set_baseline([measures(pelvis_shift=5.0)] * 10)  # bazinul stă natural deplasat: acesta e „normalul”
    said = []
    for k in range(300):
        t = k / 30
        shift = 5.0 + (15.0 if 1.0 <= t < 1.4 or t >= 5.0 else 0.0)  # 0,4 s scurt, apoi lung
        message = engine.update(t, measures(pelvis_shift=shift))
        if message:
            said.append((round(t, 2), message))
    assert said == [(5.7, "Ține șoldurile nemișcate.")]


def test_rejected_frames_do_not_trigger_hold_rules():
    engine = FeedbackEngine([HIPS], SETTINGS)
    engine.set_baseline([measures()] * 10)
    assert all(engine.update(k / 30, None) is None for k in range(90))


def test_side_rules_skip_the_first_rep_and_measure_both_sides():
    engine = FeedbackEngine([TILT], SETTINGS)
    engine.set_baseline([measures()] * 10)
    said, t = [], 0.0
    # Înclinări: spre dreapta doar -4°, apoi spre stânga +20°; repetarea se anunță la revenire.
    for cycle in range(6):
        cycle_start = t
        for target in (-4.0, 20.0):
            for _ in range(30):
                engine.update(t, measures(tilt=target))
                t += 1 / 30
        rep = RepTimes(cycle_start + 0.5, cycle_start + 1.5, t, 24.0)
        message = engine.update(t, measures(tilt=-4.0), rep)
        if message:
            said.append(message)
        t += 1 / 30
    assert said and said[0] == "Înclină-te mai mult."
    assert len(engine.trace["tilt_more"]) == 5  # prima repetare nu se măsoară
    assert all(v == pytest.approx(4.0) for _, v in engine.trace["tilt_more"])  # partea mai slabă


def test_one_message_at_a_time_most_important_first():
    engine = FeedbackEngine([ARMS, HIPS], SETTINGS)
    engine.set_baseline([measures()] * 10)
    said = []
    for k in range(600):
        t = k / 30
        rep = RepTimes(t - 2, t - 1, t, 20) if k % 90 == 89 else None
        message = engine.update(t, measures(shoulder=100.0, pelvis_shift=20.0), rep)
        if message:
            said.append((round(t, 1), message))
    assert said[0][1] == "Ține șoldurile nemișcate."  # stabilitatea are prioritate
    gaps = np.diff([t for t, _ in said])
    assert (gaps >= SETTINGS["gap_s"] - 1e-9).all()


def test_calibrated_rules_file_is_complete():
    config = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    for exercise in range(1, 6):
        settings, rules = load_rules(exercise)
        enabled = [r for r in rules if r.get("enabled", True)]
        assert enabled, f"Es{exercise} fără reguli"
        for rule in enabled:
            assert rule["message"]
            if rule["kind"] in ("rep", "hold", "too_fast", "idle", "fatigue"):
                assert np.isfinite(rule["threshold"])
    assert config["settings"]["hold_s"] > 0
