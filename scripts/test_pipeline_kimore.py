"""Testează lanțul complet pe KIMORE: puncte → verificare → netezire → unghiuri → repetări.

Numărul de repetări se compară cu adnotările independente (abediai/repetition-segmentation),
iar unghiurile cu scheletul Kinect. Subiecții sunt împărțiți în două: fold 0 pentru reglaj, fold 1 pentru test.

Rulare: python scripts/test_pipeline_kimore.py [--fold 1]
Rezultate în data/pipeline_test/. Are nevoie de punctele din data/keypoints/kimore.
"""
import argparse
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from src.features import PRIMARY_ANGLE, REP_PROMINENCE, compute_angles, named_joints
from src.filters import OneEuroFilter, smooth_keypoints
from src.kinect import load_kinect
from src.quality import OK, QualityChecker, clean_sequence
from src.reps import RepCounter, find_reps

INDEX = ROOT / "data" / "kimore" / "index.csv"
KEYPOINTS = ROOT / "data" / "keypoints" / "kimore"
REPETITIONS = ROOT / "data" / "kimore" / "repetitions"
OUT = ROOT / "data" / "pipeline_test"
FPS = 30.0
MIRRORED = True  # videoclipurile KIMORE sunt în oglindă față de scheletul Kinect
MAX_LAG = 30
COMPARED_ANGLES = ["shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "knee_flexion_L", "knee_flexion_R",
                   "trunk_tilt", "trunk_rotation", "pelvis_rotation"]
EXAMPLE_SUBJECTS = {"E_ID2", "NE_ID2", "B_ID2", "P_ID2", "S_ID2", "P_ID3", "S_ID3"}


def subject_folds(index):
    subjects = index[["subject", "group"]].drop_duplicates().sort_values(["group", "subject"])
    return dict(zip(subjects["subject"], subjects.groupby("group").cumcount() % 2))


def _seconds(text):
    hours, minutes, seconds = text.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def load_annotations():
    """Un rând pe repetare adnotată: subject, exercise (1-5), start_s, end_s, incomplete."""
    table = pd.read_csv(REPETITIONS / "kimore_annotations_all_exercises.csv")
    mapping = pd.read_csv(REPETITIONS / "video_person_exercise_mapping.csv")
    table["ExerciseNum"] = table["Exercise"].str.split("_").str[1].astype(int)
    table = table.merge(mapping, left_on=["ExerciseNum", "Video"], right_on=["ExerciseNum", "AnnotationVideoNum"])
    return pd.DataFrame({
        "subject": table["PersonID"], "exercise": table["ExerciseNum"] + 1,
        "start_s": table["Start"].map(_seconds), "end_s": table["End"].map(_seconds),
        "incomplete": table["Incomplete"].astype(bool),
    })


def declared_fps(row):
    """Adnotările sunt în timpul de redare al videoclipului, deci folosesc fps-ul declarat, nu cel real."""
    capture = cv2.VideoCapture(str(ROOT / row["rgb_path"]))
    fps = capture.get(cv2.CAP_PROP_FPS)
    capture.release()
    return fps


def angles_from_mediapipe(image_kp, world_kp, use_quality=True, use_filter=True):
    status, swaps = None, 0
    if use_quality:
        image_kp, world_kp, status, swaps = clean_sequence(image_kp, world_kp, FPS, mirrored=MIRRORED)
    if use_filter:
        world_kp = smooth_keypoints(world_kp)
    return compute_angles(named_joints(world_kp, "mediapipe", MIRRORED)), status, swaps


def live_count(image_kp, world_kp, exercise):
    """Aceeași trecere, dar cadru cu cadru, fără să se uite în viitor, ca în aplicație."""
    checker = QualityChecker(FPS, mirrored=MIRRORED)
    smoother = OneEuroFilter()
    counter = RepCounter(FPS, prominence=REP_PROMINENCE[exercise])
    filtered = []
    for i, (image, world) in enumerate(zip(image_kp, world_kp)):
        _, clean, _ = checker.update(image, world)
        xyz = smoother(clean[:, :3], i / FPS)
        frame = np.empty((1, 33, 4))
        frame[0, :, :3] = xyz
        frame[0, :, 3] = clean[:, 3]
        filtered.append(frame)
    all_frames = np.concatenate(filtered)
    signal = compute_angles(named_joints(all_frames, "mediapipe", MIRRORED))[PRIMARY_ANGLE[exercise]].to_numpy()
    return sum(counter.update(v) is not None for v in signal)


def side_agreement(world_kp, kinect_points):
    """Se mișcă încheietura „stângă” din MediaPipe ca aceea stângă din Kinect? Nu folosește regula de ordine."""
    ours = named_joints(world_kp, "mediapipe", MIRRORED)
    theirs = named_joints(kinect_points, "kinect")
    def curve(joints, wrist):
        return pd.Series(joints[wrist][:, 0] - (joints["hip_L"][:, 0] + joints["hip_R"][:, 0]) / 2)
    same = np.nanmean([curve(ours, w).corr(curve(theirs, w)) for w in ("wrist_L", "wrist_R")])
    return same


def chain_cost_ms(image_kp, world_kp, exercise):
    """Timpul pe cadru al celor patru pași, fără model: verificare, netezire, unghiuri, repetări."""
    checker = QualityChecker(FPS, mirrored=MIRRORED)
    smoother = OneEuroFilter()
    counter = RepCounter(FPS, prominence=REP_PROMINENCE[exercise])
    frames = min(300, len(world_kp))
    start = time.perf_counter()
    for i in range(frames):
        _, clean, _ = checker.update(image_kp[i], world_kp[i])
        one = np.array(clean)[None]
        one[0, :, :3] = smoother(clean[:, :3], i / FPS)
        value = compute_angles(named_joints(one, "mediapipe", MIRRORED))[PRIMARY_ANGLE[exercise]].iloc[0]
        counter.update(value)
    return 1000 * (time.perf_counter() - start) / max(1, frames)


def plot_example(row, annotations, angles, reps, declared, path):
    signal = PRIMARY_ANGLE[int(row["exercise"])]
    t = np.arange(len(angles)) / FPS
    figure, axis = plt.subplots(figsize=(11, 3.2))
    for _, a in annotations.iterrows():
        axis.axvspan(a["start_s"] * declared / FPS, a["end_s"] * declared / FPS, color="#4c78a8", alpha=0.12)
        axis.axvline(a["start_s"] * declared / FPS, color="#4c78a8", lw=0.8)
    axis.plot(t, angles[signal], color="#222222", lw=1.2, label=signal)
    peaks = [r.peak for r in reps]
    axis.plot(t[peaks], angles[signal].to_numpy()[peaks], "o", color="#e45756", label="vârf detectat")
    true_count = int((~annotations["incomplete"]).sum())
    axis.set_title(f"{row['subject']} Es{row['exercise']}: {len(reps)} detectate, {true_count} adnotate (benzile albastre)", fontsize=11)
    axis.set_xlabel("secunde")
    axis.set_ylabel("grade")
    axis.legend(loc="upper right")
    figure.tight_layout()
    figure.savefig(path, dpi=110)
    plt.close(figure)


def best_lag(reference, moving):
    best, best_corr = 0, -np.inf
    for lag in range(-MAX_LAG, MAX_LAG + 1):
        corr = reference.corr(moving.shift(lag))
        if pd.notna(corr) and corr > best_corr:
            best, best_corr = lag, corr
    return best


def angle_errors(angles, kinect_angles, exercise):
    fill = lambda t: t.interpolate(limit=15, limit_area="inside")
    name = PRIMARY_ANGLE[exercise] if exercise in (1, 2, 5) else "trunk_tilt"
    lag = best_lag(fill(kinect_angles[name]), fill(angles[name]))
    shifted = angles.shift(lag).reindex(kinect_angles.index)
    result = {}
    for column in COMPARED_ANGLES:
        result[f"{column}_mae"] = (shifted[column] - kinect_angles[column]).abs().mean()
        result[f"{column}_corr"] = kinect_angles[column].corr(shifted[column])
    result["lag"] = lag
    return result


def peaks_in_annotations(reps, annotations, frames_per_second):
    """Câte repetări adnotate conțin exact un vârf detectat."""
    if annotations.empty:
        return np.nan
    peaks = np.array([r.peak for r in reps])
    hits = 0
    for _, a in annotations.iterrows():
        start, end = a["start_s"] * frames_per_second, a["end_s"] * frames_per_second
        hits += int(np.sum((peaks >= start) & (peaks <= end)) == 1)
    return hits / len(annotations)


def process_video(args):
    row, annotations = args
    exercise = int(row["exercise"])
    name = f"{row['subject']}_Es{exercise}"
    file = KEYPOINTS / f"{name}.npz"
    if not file.exists():
        return None
    data = np.load(file)
    image_kp, world_kp = data["image_kp"], data["world_kp"]
    out = {"video": name, "subject": row["subject"], "group": row["group"], "exercise": exercise,
           "frames": len(world_kp), "detected": float(np.mean(~np.isnan(world_kp[:, 11, 0]))),
           "true_reps": int((~annotations["incomplete"]).sum()), "true_reps_all": len(annotations)}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        signal = PRIMARY_ANGLE[exercise]
        prominence = REP_PROMINENCE[exercise]
        fps_declared = declared_fps(row)
        variants = {
            "raw": dict(use_quality=False, use_filter=False),
            "filter": dict(use_quality=False, use_filter=True),
            "quality_filter": dict(use_quality=True, use_filter=True),
        }
        for label, options in variants.items():
            angles, status, swaps = angles_from_mediapipe(image_kp, world_kp, **options)
            reps = find_reps(angles[signal].to_numpy(), FPS, prominence=prominence)
            out[f"reps_{label}"] = len(reps)
            out[f"peak_hit_{label}"] = peaks_in_annotations(reps, annotations, fps_declared)
            if pd.notna(row["skeleton_path"]) and row["use_skeleton"]:
                kinect_angles = compute_angles(named_joints(load_kinect(ROOT / row["skeleton_path"]), "kinect"))
                for key, value in angle_errors(angles, kinect_angles, exercise).items():
                    out[f"{key}_{label}"] = value
                if label == "quality_filter":
                    kinect_smooth = kinect_angles.interpolate(limit=15, limit_area="inside")
                    out["reps_kinect"] = len(find_reps(kinect_smooth[signal].to_numpy(), FPS, prominence=prominence))
            if status is not None:
                out["kept"] = float(np.mean(status == OK))
                out["swaps"] = swaps / max(1, len(status))
                for reason in pd.unique(status):
                    out[f"status_{reason}"] = float(np.mean(status == reason))
                out["rep_valid_min"] = min((r.valid_fraction for r in reps), default=np.nan)
        out["reps_live"] = live_count(image_kp, world_kp, exercise)
        out["chain_ms"] = chain_cost_ms(image_kp, world_kp, exercise)
        if row["use_skeleton"]:
            kinect_points = load_kinect(ROOT / row["skeleton_path"])
            cleaned = clean_sequence(image_kp, world_kp, FPS, mirrored=MIRRORED)[1]
            n = min(len(world_kp), len(kinect_points))
            out["wrist_x_corr_raw"] = side_agreement(world_kp[:n], kinect_points[:n])
            out["wrist_x_corr_fixed"] = side_agreement(cleaned[:n], kinect_points[:n])
        angles, _, _ = angles_from_mediapipe(image_kp, world_kp)
        reps = find_reps(angles[signal].to_numpy(), FPS, prominence=prominence)
        if row["subject"] in EXAMPLE_SUBJECTS and not annotations.empty:
            plot_example(row, annotations, angles, reps, fps_declared, OUT / f"{name}_reps.png")
    return out


def score(table, column):
    errors = (table[column] - table["true_reps"]).abs()
    return pd.Series({"videos": int(errors.notna().sum()), "mae": errors.mean(),
                      "exact_pct": 100 * (errors == 0).mean(), "within1_pct": 100 * (errors <= 1).mean()})


def report(results):
    results = results[results["true_reps"] > 0]
    columns = [c for c in ["reps_raw", "reps_filter", "reps_quality_filter", "reps_live", "reps_kinect"] if c in results]
    print("\nRepetări față de adnotări, pe variantă:")
    print(pd.DataFrame({c: score(results, c) for c in columns}).round(2).to_string())
    print("\nRepetări (verificare + netezire), pe exercițiu:")
    print(results.groupby("exercise").apply(lambda t: pd.concat(
        [score(t, "reps_quality_filter").add_prefix("offline_"), score(t, "reps_live")[["mae", "exact_pct"]].add_prefix("live_"),
         score(t.dropna(subset=["reps_kinect"]), "reps_kinect")[["mae", "exact_pct"]].add_prefix("kinect_"),
         pd.Series({"peak_hit": 100 * t["peak_hit_quality_filter"].mean()})]), include_groups=False).round(2).to_string())
    print("\nRepetări (verificare + netezire), pe grup:")
    print(results.groupby("group").apply(lambda t: score(t, "reps_quality_filter"), include_groups=False).round(2).to_string())
    print("\nMediană pe videoclip: eroare absolută față de Kinect (°) și corelație:")
    rows = {}
    for angle in COMPARED_ANGLES:
        for label in ["raw", "filter", "quality_filter"]:
            rows.setdefault(angle, {})[f"mae_{label}"] = results[f"{angle}_mae_{label}"].median()
            rows[angle][f"corr_{label}"] = results[f"{angle}_corr_{label}"].median()
    print(pd.DataFrame(rows).T.round(2).to_string())
    status = [c for c in results if c.startswith("status_")]
    print("\nLaturi: corelația încheieturii cu Kinect, pe același nume (mediană | medie):")
    if "wrist_x_corr_raw" in results:
        print(results[["wrist_x_corr_raw", "wrist_x_corr_fixed"]].agg(["median", "mean"]).round(3).to_string())
    print(f"\nCostul lanțului, fără model: {results['chain_ms'].median():.2f} ms/cadru")
    print("\nCe face verificarea (% cadre, medie pe videoclip):")
    print((100 * results[status + ["kept", "swaps"]].fillna(0).mean()).round(2).to_string())
    print("\nCadre păstrate, pe exercițiu (%):")
    print((100 * results.groupby("exercise")["kept"].mean()).round(1).to_string())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fold", type=int, default=1)
    args = parser.parse_args()
    index = pd.read_csv(INDEX)
    folds = subject_folds(index)
    annotations = load_annotations()
    rows = [r for r in index[index["use_rgb"]].to_dict("records") if folds[r["subject"]] == args.fold]
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(r, annotations[(annotations["subject"] == r["subject"]) & (annotations["exercise"] == r["exercise"])]) for r in rows]
    with ProcessPoolExecutor(8) as pool:
        results = [r for r in pool.map(process_video, jobs) if r is not None]
    results = pd.DataFrame(results)
    results.to_csv(OUT / f"results_fold{args.fold}.csv", index=False)
    print(f"Fold {args.fold}: {len(results)} videoclipuri")
    pd.set_option("display.width", 250, "display.max_columns", None)
    report(results)


if __name__ == "__main__":
    main()
