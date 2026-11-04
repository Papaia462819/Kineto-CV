"""Construiește tabelele de intrare pentru modelele învățate: un rând pe execuție KIMORE.

Ieșire: data/features/kinect.csv și data/features/mediapipe.csv, cu aceleași 78 de coloane de măsurători,
plus coloane de identificare (subject, group, exercise, scoruri) și de calitate (kept, valid_s).
Coloanele de identificare și calitate nu intră niciodată în model.

Rulare: python scripts/build_execution_features.py
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.execution_features import angles_from_kinect, angles_from_mediapipe, summarize, valid_seconds
from src.kinect import load_kinect

INDEX = ROOT / "data" / "kimore" / "index.csv"
KEYPOINTS = ROOT / "data" / "keypoints" / "kimore"
OUT = ROOT / "data" / "features"
FPS = 30.0
MIRRORED = True  # videoclipurile KIMORE sunt în oglindă față de scheletul Kinect
META = ["subject", "group", "population", "exercise", "score_total", "score_po", "score_cf", "use_score"]


def meta(row):
    out = {key: row[key] for key in META if key != "use_score"}
    out["use_score"] = bool(pd.notna(row["score_total"]))
    return out


def kinect_row(row):
    angles, kept = angles_from_kinect(load_kinect(ROOT / row["skeleton_path"]))
    return {**meta(row), "kept": kept, "valid_s": valid_seconds(angles, FPS), **summarize(angles, FPS)}


def mediapipe_row(row):
    data = np.load(KEYPOINTS / f"{row['subject']}_Es{row['exercise']}.npz")
    angles, kept = angles_from_mediapipe(data["image_kp"], data["world_kp"], FPS, MIRRORED)
    return {**meta(row), "kept": kept, "valid_s": valid_seconds(angles, FPS), **summarize(angles, FPS)}


def main():
    index = pd.read_csv(INDEX)
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = {
        "kinect": (kinect_row, index[index["skeleton_path"].notna()]),
        "mediapipe": (mediapipe_row, index[index["rgb_path"].notna()]),
    }
    for name, (function, rows) in jobs.items():
        with ProcessPoolExecutor(8) as pool:
            table = pd.DataFrame(list(pool.map(function, rows.to_dict("records"))))
        table.to_csv(OUT / f"{name}.csv", index=False)
        print(f"{name}: {len(table)} executii, {table['subject'].nunique()} persoane, "
              f"kept median {table['kept'].median():.2f}, randuri cu valori lipsa {table.isna().any(axis=1).sum()}")


if __name__ == "__main__":
    main()
