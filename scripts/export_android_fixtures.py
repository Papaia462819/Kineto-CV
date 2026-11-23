"""Datele de referință pentru testele Kotlin (android/app/src/test/resources), produse de codul Python.

Codul live e scris de două ori: în Python (laptop, calibrare) și în Kotlin (telefon). Testele Kotlin verifică
că portarea dă aceleași rezultate ca Python, pe date sintetice (nimic din KIMORE nu ajunge în git):
    angles.csv    unghiul principal, pe schelete aleatoare
    measures.csv  măsurile regulilor (src/feedback.py: frame_measures), pe aceleași schelete
    reps.csv      numărarea repetărilor, pe curbe cu zgomot și goluri
    feedback.json o secvență de măsuri și repetări, regulile și mesajele spuse de motorul Python

Rulare: python scripts/export_android_fixtures.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.feedback import MEASURES, FeedbackEngine, RepTimes, frame_measures, load_rules
from src.features import PRIMARY_ANGLE, REP_PROMINENCE, compute_angles, named_joints
from src.reps import RepCounter

OUT = ROOT / "android" / "app" / "src" / "test" / "resources"
STANDING = {11: (0.2, -0.5, 0), 12: (-0.2, -0.5, 0), 13: (0.25, -0.2, 0), 14: (-0.25, -0.2, 0), 15: (0.25, 0.1, 0),
            16: (-0.25, 0.1, 0), 23: (0.1, 0, 0), 24: (-0.1, 0, 0), 25: (0.1, 0.45, 0), 26: (-0.1, 0.45, 0),
            27: (0.1, 0.9, 0), 28: (-0.1, 0.9, 0)}


def random_poses(rng, count):
    """Un schelet în picioare (coordonatele MediaPipe: y în jos) cu zgomot mare, ca formulele să vadă multe poziții."""
    base = np.zeros((33, 4))
    base[:, 3] = 0.9
    for i, xyz in STANDING.items():
        base[i, :3] = xyz
    noise = np.concatenate([rng.normal(0, 0.15, (count, 33, 3)), np.zeros((count, 33, 1))], axis=2)
    return base + noise


def angles_and_measures(rng):
    angle_rows, measure_rows = [], []
    for exercise in range(1, 6):
        for mirrored in (False, True):
            world = random_poses(rng, 30)
            joints = named_joints(world, "mediapipe", mirrored)
            primary = compute_angles(joints)[PRIMARY_ANGLE[exercise]].to_numpy()
            angle_rows += [[exercise, int(mirrored), a] + p.ravel().tolist() for a, p in zip(primary, world)]
            measures = frame_measures(joints)
            measure_rows += [[int(mirrored)] + [measures[m][k] for m in MEASURES] + world[k].ravel().tolist()
                             for k in range(len(world))]
    pd.DataFrame(angle_rows).to_csv(OUT / "angles.csv", index=False, header=False, float_format="%.9g")
    pd.DataFrame(measure_rows, columns=["mirrored"] + MEASURES + [f"w{i}" for i in range(132)]).to_csv(
        OUT / "measures.csv", index=False, float_format="%.9g")


def reps(rng):
    lines = []
    for exercise in range(1, 6):
        prominence = REP_PROMINENCE[exercise]
        t = np.arange(0, 40, 1 / 30)
        amplitude = np.interp(t, [0, 40], [3.0 * prominence, 1.2 * prominence])
        series = amplitude * np.clip(np.sin(2 * np.pi * t / 4.5), 0, None) + rng.normal(0, 0.08 * prominence, len(t))
        series[300:320] = np.nan
        counter = RepCounter(30.0, prominence=prominence)
        for value in series:
            counter.update(value)
        lines.append(f"{exercise};{counter.count};" + ",".join("nan" if np.isnan(v) else f"{v:.5f}" for v in series))
    (OUT / "reps.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def feedback(rng):
    """Toate felurile de reguli, pe o secvență care le face să sune: abateri ținute, repetări slabe, pauze."""
    settings, _ = load_rules(1)
    rules = [
        {"id": "arms", "kind": "rep", "measure": "shoulder", "stat": "peak", "bad": "low", "threshold": 140, "priority": 3, "message": "brate"},
        {"id": "elbow", "kind": "rep", "measure": "elbow", "stat": "min", "bad": "low", "threshold": 120, "priority": 2, "message": "cot"},
        {"id": "range", "kind": "rep", "measure": "knee", "stat": "range", "bad": "low", "threshold": 30, "priority": 3, "message": "genunchi"},
        {"id": "high", "kind": "rep", "measure": "knee_diff", "stat": "max", "bad": "high", "threshold": 12, "priority": 2, "message": "simetrie"},
        {"id": "sides", "kind": "rep", "measure": "tilt", "stat": "both_sides", "relative": True, "bad": "low", "threshold": 8, "priority": 3, "message": "inclina"},
        {"id": "diff", "kind": "rep", "measure": "tilt", "stat": "sides_diff", "relative": True, "bad": "high", "threshold": 6, "priority": 2, "message": "egal"},
        {"id": "hips", "kind": "hold", "measure": "pelvis_shift", "relative": True, "threshold": 6, "priority": 1, "message": "solduri"},
        {"id": "rot", "kind": "hold", "measure": "shoulder_rotation", "relative": True, "threshold": 15, "priority": 1, "message": "umeri"},
        {"id": "off", "kind": "hold", "measure": "lean", "relative": True, "threshold": 1, "priority": 1, "message": "oprita", "enabled": False},
        {"id": "too_fast", "kind": "too_fast", "threshold": 0.6, "priority": 2, "message": "incet"},
        {"id": "idle", "kind": "idle", "threshold": 10.0, "priority": 3, "message": "continua"},
        {"id": "tired", "kind": "fatigue", "threshold": 0.6, "priority": 3, "message": "pauza"},
    ]
    baseline = []
    for _ in range(40):
        m = {name: float(rng.normal(0, 1)) for name in MEASURES}
        m["shoulder_rotation"] = 175 + rng.normal(0, 2)  # lângă ±180°, ca să conteze calculul pe cerc
        baseline.append(m)
    frames, t, k = [], 0.0, 0
    period = 2.5
    amplitudes = [60, 60, 58, 50, 30, 25, 60, 60, 20, 20, 60, 60, 60, 60, 60, 60, 60, 60]
    for rep_index, amplitude in enumerate(amplitudes + [None] * 1):  # la final o pauză lungă (regula „idle”)
        length = int((period if amplitude else 14.0) * 30)
        start_t = t
        for i in range(length):
            phase = i / length
            wave = np.sin(np.pi * phase) if amplitude else 0.0
            m = {name: float(rng.normal(0, 0.5)) for name in MEASURES}
            m["shoulder"] = 30 + (amplitude or 0) * 2 * wave
            m["elbow"] = 160 - (50 if rep_index in (3, 4, 5) else 0) * wave
            m["knee"] = 5 + (amplitude or 0) * wave
            m["knee_diff"] = 5 + (15 if rep_index in (8, 9, 10) else 0) * wave
            m["tilt"] = (-4 if rep_index % 4 == 1 else -15) + (amplitude or 0) / 2 * wave
            m["pelvis_shift"] = 10 if 20 <= t < 23 or 30 <= t < 30.5 else 0.3
            m["shoulder_rotation"] = -178 if 35 <= t < 37 else 176  # trece peste ±180° fără să fie abatere mare
            if 42 <= t < 43:
                m["shoulder_rotation"] = 150
            m["lean"] = 50.0
            missing = 400 <= k < 410  # câteva cadre respinse
            rep = None
            if i == length - 1 and amplitude:
                rise = 0.4 if rep_index in (12, 13, 14) else period / 2
                rep = [t - rise - 0.2, t - 0.2, t, float(amplitude)]
            frames.append({"t": t, "m": None if missing else m, "rep": rep})
            t = (k + 1) / 30
            k += 1
    engine = FeedbackEngine([dict(r) for r in rules], settings)
    engine.set_baseline(baseline)
    said = []
    for index, frame in enumerate(frames):
        rep = RepTimes(*frame["rep"]) if frame["rep"] else None
        message = engine.update(frame["t"], frame["m"], rep)
        if message:
            said.append([index, message])
    data = {"settings": settings, "rules": rules, "baseline": baseline, "frames": frames, "said": said,
            "summary": engine.summary()}
    (OUT / "feedback.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"feedback: {len(frames)} cadre, {len(said)} mesaje: {[m for _, m in said]}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    angles_and_measures(rng)
    reps(rng)
    feedback(rng)
    print(f"Scris in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
