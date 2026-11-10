"""Construiește tabelele pentru scorul clinic (E7): un rând pe execuție KIMORE cu grupurile A, B și C.

A = cele 78 de numere de la E8 (unghiuri × statistici, pe tot videoul)
B = rezumatul repetărilor (rep__*), găsite pe unghiul principal al exercițiului
C = mărimile clinicienilor KIMORE (clin__*), diferite de la un exercițiu la altul (NaN la celelalte)

Ieșire: data/features/kinect_e7.csv și data/features/mediapipe_e7.csv
Rulare: python scripts/build_score_features.py
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clinical_features import clinical_summary
from src.execution_features import (compute_angles, joints_from_kinect, joints_from_mediapipe, repetition_summary,
                                    summarize, valid_seconds)
from src.kinect import load_kinect

INDEX = ROOT / "data" / "kimore" / "index.csv"
KEYPOINTS = ROOT / "data" / "keypoints" / "kimore"
OUT = ROOT / "data" / "features"
FPS = 30.0
MIRRORED = True  # videoclipurile KIMORE sunt în oglindă față de scheletul Kinect
META = ["subject", "group", "population", "exercise", "score_total", "score_po", "score_cf"]


def row_from_joints(row, joints, kept):
    angles = compute_angles(joints)
    exercise = int(row["exercise"])
    return {**{key: row[key] for key in META}, "kept": kept, "valid_s": valid_seconds(angles, FPS),
            **summarize(angles, FPS), **repetition_summary(angles, exercise, FPS),
            **clinical_summary(joints, exercise, FPS)}


def kinect_row(row):
    return row_from_joints(row, *joints_from_kinect(load_kinect(ROOT / row["skeleton_path"])))


def mediapipe_row(row):
    data = np.load(KEYPOINTS / f"{row['subject']}_Es{row['exercise']}.npz")
    return row_from_joints(row, *joints_from_mediapipe(data["image_kp"], data["world_kp"], FPS, MIRRORED))


def main():
    index = pd.read_csv(INDEX)
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = {
        "kinect": (kinect_row, index[index["skeleton_path"].notna()]),
        "mediapipe": (mediapipe_row, index[index["rgb_path"].notna()]),
    }
    for name, (function, rows) in jobs.items():
        with ProcessPoolExecutor(8) as pool:
            table = pd.DataFrame(list(pool.map(function, rows.to_dict("records"), chunksize=4)))
        table.to_csv(OUT / f"{name}_e7.csv", index=False)
        print(f"{name}: {len(table)} executii, {table.shape[1]} coloane, "
              f"repetari gasite (mediana) {table['rep__count'].median():.0f}")


if __name__ == "__main__":
    main()
