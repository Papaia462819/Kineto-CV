"""Calibrează regulile de feedback live pe KIMORE și scrie config/feedback.json.

Pentru fiecare execuție KIMORE (punctele MediaPipe), simulează aplicația live cadru cu cadru:
verificare → netezire One Euro → măsuri → numărarea repetărilor → regulile.
Poziția de start = cadrele de dinaintea primei repetări (în KIMORE nu există numărătoarea de 5 secunde).

1. Prima trecere, fără praguri: adună valorile fiecărei reguli.
2. Pragul = percentila din config/feedback.yaml, pe execuțiile bune (scorul medicului >= good_score).
   Regulile „rep”: pe valorile repetărilor. Regulile „hold”: pe cea mai mare abatere ținută hold_s secunde.
3. A doua trecere, cu praguri: cât de des sună fiecare regulă la execuțiile bune, medii și slabe.
   O regulă utilă sună rar la cei buni și mult mai des la cei slabi.

Rulare: python scripts/calibrate_feedback.py
Ieșire: config/feedback.json, data/feedback/report.txt
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.features import PRIMARY_ANGLE, REP_PROMINENCE, named_joints
from src.feedback import FeedbackEngine, RepTimes, frame_measures
from src.filters import OneEuroFilter
from src.quality import OK, QualityChecker
from src.reps import RepCounter
from src.session import PRIMARY_MEASURE

FPS = 30.0
MIRRORED = True  # videoclipurile KIMORE sunt în oglindă
KEYPOINTS = ROOT / "data" / "keypoints" / "kimore"
FEATURES = ROOT / "data" / "features" / "mediapipe_e7.csv"
SOURCE = ROOT / "config" / "feedback.yaml"
TARGET = ROOT / "config" / "feedback.json"
REPORT = ROOT / "data" / "feedback"
MIN_KEPT = 0.5  # execuțiile cu detecție foarte proastă nu spun nimic despre mișcare
BASELINE_S = 5.0


def live_simulation(subject, exercise):
    """Măsurile pe cadru (după verificare și netezire live) și repetările anunțate live."""
    data = np.load(KEYPOINTS / f"{subject}_Es{exercise}.npz")
    checker, smoother = QualityChecker(fps=FPS, mirrored=MIRRORED), OneEuroFilter()
    smooth = np.full(data["world_kp"].shape, np.nan)
    for i, (image, world) in enumerate(zip(data["image_kp"], data["world_kp"])):
        _, world, status = checker.update(image, world)
        if status == OK:
            smooth[i, :, :3] = smoother(world[:, :3], i / FPS)
        else:
            smoother.reset()
    measures = frame_measures(named_joints(smooth, "mediapipe", MIRRORED))
    counter = RepCounter(FPS, prominence=REP_PROMINENCE[exercise])
    primary = measures[PRIMARY_MEASURE[PRIMARY_ANGLE[exercise]]]
    reps = {}
    for i, value in enumerate(primary):
        rep = counter.update(value)
        if rep is not None:
            reps[i] = RepTimes(rep.start / FPS, rep.peak / FPS, rep.end / FPS, rep.amplitude)
    return measures, reps


def run(job):
    subject, exercise, rules, settings = job
    measures, reps = live_simulation(subject, exercise)
    frames = len(next(iter(measures.values())))
    rows = [{m: float(v[i]) for m, v in measures.items()} for i in range(frames)]
    ok = [i for i in range(frames) if np.isfinite(rows[i]["shoulder"])]
    # Poziția de start: cadrele bune din cele 5 secunde de dinaintea primei repetări (de dinaintea văii ei).
    valley = int(reps[min(reps)].start * FPS) if reps else 0
    start = [i for i in ok if valley - BASELINE_S * FPS <= i < valley]
    if len(start) < 10:
        start = ok[:30]
    engine = FeedbackEngine(rules, settings)
    engine.set_baseline([rows[i] for i in start])
    for i in range(start[0] if start else 0, frames):
        engine.update(i / FPS, rows[i] if i in ok else None, reps.get(i))
    return subject, exercise, engine.trace, engine.counts, len(reps)


def held_maximum(trace, hold_s):
    """Cea mai mare abatere care a ținut cel puțin hold_s secunde (minimul pe fereastră, apoi maximul)."""
    if not trace:
        return np.nan
    t, v = np.array(trace).T
    best = np.nan
    for k in range(len(t)):
        window = v[(t >= t[k]) & (t <= t[k] + hold_s)]
        if t[k] + hold_s <= t[-1]:
            best = np.nanmax([best, window.min()])
    return best


def simulate(table, config, rules_by_exercise):
    jobs = [(r.subject, int(r.exercise), rules_by_exercise[int(r.exercise)], config["settings"]) for r in table.itertuples()]
    with ProcessPoolExecutor(8) as pool:
        return list(pool.map(run, jobs, chunksize=4))


def main():
    source = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    settings = {k: source[k] for k in ("hold_s", "repeat_s", "gap_s")}
    config = {"settings": settings, "general": source["general"],
              "exercises": {str(e): rules + [dict(source["too_fast"])] for e, rules in source["exercises"].items()}}
    table = pd.read_csv(FEATURES)
    table = table[(table["kept"] >= MIN_KEPT) & table["score_total"].notna()].reset_index(drop=True)
    table["band"] = pd.cut(table["score_total"], [0, 30, source["good_score"], 51], right=False,
                           labels=["slab (<30)", "mediu", f"bun (>={source['good_score']})"])

    # 1. Fără praguri: doar valorile.
    rules = {int(e): [dict(r) for r in rs] + [] for e, rs in config["exercises"].items()}
    first = simulate(table, config, rules)
    good = set(table.loc[table["score_total"] >= source["good_score"], ["subject", "exercise"]].itertuples(index=False, name=None))
    for exercise, exercise_rules in config["exercises"].items():
        for rule in exercise_rules:
            values = []
            for subject, ex, trace, _, _ in first:
                if ex != int(exercise) or (subject, ex) not in good or rule["id"] not in trace:
                    continue
                if rule["kind"] == "hold":
                    values.append(held_maximum(trace[rule["id"]], settings["hold_s"]))
                else:
                    values += [v for _, v in trace[rule["id"]]]
            values = np.array(values, dtype=float)
            values = values[np.isfinite(values)]
            threshold = float(np.percentile(values, rule["percentile"]))
            rule["threshold"] = round(min(threshold, rule.get("max_threshold", np.inf)), 2)
            rule["calibrated_on"] = int(len(values))

    # 2. Cu praguri: cât de des sună.
    second = simulate(table, config, {int(e): rs + config["general"] for e, rs in config["exercises"].items()})
    fired = pd.DataFrame([{"subject": s, "exercise": e, "reps": n, **{k: v for k, v in counts.items()}}
                          for s, e, _, counts, n in second]).fillna(0)
    fired = table[["subject", "exercise", "band", "population", "score_total"]].merge(fired, on=["subject", "exercise"])

    lines = ["Cat de des suna fiecare regula: procentul executiilor in care a sunat macar o data, pe grupe de scor",
             f"(executii KIMORE MediaPipe cu kept >= {MIN_KEPT}; prag = percentila din executiile cu scor >= {source['good_score']})", ""]
    for exercise, exercise_rules in config["exercises"].items():
        part = fired[fired["exercise"] == int(exercise)]
        lines.append(f"===== Es{exercise}: {len(part)} executii, " +
                     ", ".join(f"{b} {n}" for b, n in part["band"].value_counts(sort=False).items()))
        for rule in exercise_rules + config["general"]:
            column = part[rule["id"]] if rule["id"] in part else pd.Series(0, index=part.index)
            rates = (column > 0).groupby(part["band"], observed=False).mean()
            rule_rates = " | ".join(f"{band}: {100 * rate:4.0f}%" for band, rate in rates.items())
            threshold = rule.get("threshold")
            lines.append(f"  {rule['id']:22s} prag {threshold!s:>8s}   {rule_rates}")
            if rule in exercise_rules:
                rule["fires_percent"] = {str(b): round(100 * r) for b, r in rates.items()}
                good_rate, weak_rate = 100 * rates.iloc[-1], 100 * rates.iloc[0]
                rule["enabled"] = bool(rule.get("keep") or (good_rate <= 10 and weak_rate >= max(2 * good_rate, 15)))
                lines[-1] += "" if rule["enabled"] else "   -> scoasa"
        lines.append("")
    report = "\n".join(lines)
    print(report)
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / "report.txt").write_text(report, encoding="utf-8")
    fired.to_csv(REPORT / "fired.csv", index=False)
    TARGET.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Scris {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
