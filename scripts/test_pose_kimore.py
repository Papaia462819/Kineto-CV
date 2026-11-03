"""Testul de la pasul 4: MediaPipe pe 10 videoclipuri KIMORE, comparat cu scheletul Kinect.

Alege 2 videoclipuri din fiecare grup și acoperă fiecare exercițiu de 2 ori.
Rezultate în data/pose_test/: summary.csv, angles.csv, un grafic și o planșă cu scheletul per video.
Rulare: python scripts/test_pose_kimore.py
"""
import sys
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
from extract_keypoints import extract_video

INDEX = ROOT / "data" / "kimore" / "index.csv"
KEYPOINTS = ROOT / "data" / "keypoints" / "kimore"
OUT = ROOT / "data" / "pose_test"

FPS = 30
MAX_LAG = 30  # cadre; destul pentru decalajul video–schelet, sub durata unei repetări
UNSIGNED = ["shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "knee_L", "knee_R"]
MIN_RANGE = 20  # grade; un unghi care abia se mișcă nu spune nimic despre potrivirea curbelor
MIN_VISIBILITY = 0.5

# Aceleași articulații în cele două sisteme: 33 de puncte MediaPipe, 25 de puncte Kinect v2.
MP = dict(ls=11, rs=12, le=13, re=14, lw=15, rw=16, lh=23, rh=24, lk=25, rk=26, la=27, ra=28)
KI = dict(ls=4, rs=8, le=5, re=9, lw=6, rw=10, lh=12, rh=16, lk=13, rk=17, la=14, ra=18)
BONES = [("ls", "rs"), ("ls", "le"), ("le", "lw"), ("rs", "re"), ("re", "rw"), ("ls", "lh"), ("rs", "rh"),
         ("lh", "rh"), ("lh", "lk"), ("lk", "la"), ("rh", "rk"), ("rk", "ra")]


def pick_videos(index):
    candidates = index[index["use_rgb"] & index["use_skeleton"] & index["notes"].isna()]
    picks = []
    for k, group in enumerate(list(candidates["group"].unique()) * 2):
        exercise = (k % 5 + 2 * (k // 5)) % 5 + 1  # la a doua trecere, fiecare grup primește alt exercițiu
        options = candidates[(candidates["group"] == group) & (candidates["exercise"] == exercise)]
        picks.append(options.sample(1, random_state=42).iloc[0])
    return pd.DataFrame(picks)


def load_kinect(path):
    """Rândurile goale (persoană nedetectată) devin NaN, ca să nu se decaleze numerotarea."""
    frames = []
    previous = None
    for line in Path(path).read_text(errors="replace").split("\n"):
        values = [v for v in line.strip().split(",") if v]
        if not values:
            frames.append(np.full((25, 3), np.nan))
            continue
        # Uneori Kinect vede mai multe corpuri pe același rând; păstrăm corpul cel mai apropiat de cadrul anterior.
        bodies = np.array(values, dtype=float).reshape(-1, 25, 4)[:, :, :3]
        reference = previous if previous is not None else np.array([0.0, 0.0, 0.0])
        body = bodies[np.argmin(np.linalg.norm(bodies[:, 0] - reference, axis=1))]
        previous = body[0]
        frames.append(body)
    while frames and np.isnan(frames[-1]).all():
        frames.pop()
    return np.stack(frames)


def joints(points, mapping):
    return {name: points[:, i, :3] for name, i in mapping.items()}


def angle(a, b, c):
    v1, v2 = a - b, c - b
    cos = np.sum(v1 * v2, axis=1) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1))
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def top_view_rotation(j):
    """Rotația liniei umerilor față de linia șoldurilor, văzută de sus (planul x–z)."""
    shoulders = j["rs"] - j["ls"]
    hips = j["rh"] - j["lh"]
    diff = np.arctan2(shoulders[:, 2], shoulders[:, 0]) - np.arctan2(hips[:, 2], hips[:, 0])
    return np.degrees(np.arctan2(np.sin(diff), np.cos(diff)))


def pelvis_rotation(j):
    """Orientarea liniei șoldurilor față de cameră, văzută de sus. O linie n-are sens, deci -90°..90°."""
    hips = j["rh"] - j["lh"]
    return np.degrees(np.arctan(hips[:, 2] / hips[:, 0]))


def trunk_tilt(j):
    """Înclinarea trunchiului față de verticală, în planul imaginii (x–y)."""
    trunk = (j["ls"] + j["rs"]) / 2 - (j["lh"] + j["rh"]) / 2
    return np.degrees(np.arctan2(trunk[:, 0], np.abs(trunk[:, 1])))


def all_angles(j):
    return pd.DataFrame({
        "shoulder_L": angle(j["le"], j["ls"], j["lh"]),
        "shoulder_R": angle(j["re"], j["rs"], j["rh"]),
        "elbow_L": angle(j["ls"], j["le"], j["lw"]),
        "elbow_R": angle(j["rs"], j["re"], j["rw"]),
        "knee_L": angle(j["lh"], j["lk"], j["la"]),
        "knee_R": angle(j["rh"], j["rk"], j["ra"]),
        "trunk_tilt": trunk_tilt(j),
        "trunk_rotation": top_view_rotation(j),
        "pelvis_rotation": pelvis_rotation(j),
    })


def to_kinect_axes(world_kp, x_sign=1.0):
    """MediaPipe are y în jos, Kinect în sus. Sensul lui x se măsoară per video (vezi x_agreement)."""
    return world_kp[:, :, :3] * np.array([x_sign, -1.0, 1.0])


def x_agreement(mp_joints, kinect_joints, lag):
    """Corelația coordonatelor x față de mijlocul șoldurilor: pozitivă = același sens al axei."""
    a, b = [], []
    n = len(next(iter(kinect_joints.values())))
    mp_center = (mp_joints["lh"][:, 0] + mp_joints["rh"][:, 0]) / 2
    ki_center = (kinect_joints["lh"][:, 0] + kinect_joints["rh"][:, 0]) / 2
    for name in ["lw", "rw", "le", "re", "ls", "rs"]:
        a.append(pd.Series(mp_joints[name][:, 0] - mp_center).shift(lag).reindex(range(n)))
        b.append(pd.Series(kinect_joints[name][:, 0] - ki_center))
    return pd.concat(a, ignore_index=True).corr(pd.concat(b, ignore_index=True))


def fill_gaps(series):
    return series.interpolate(limit=15, limit_area="inside")


def best_lag(a, b):
    """Decalajul (în cadre) la care cele două curbe se potrivesc cel mai bine."""
    best, best_corr = 0, -np.inf
    for lag in range(-MAX_LAG, MAX_LAG + 1):
        corr = a.corr(b.shift(lag))
        if pd.notna(corr) and corr > best_corr:
            best, best_corr = lag, corr
    return best


def find_alignment(mp_angles, kinect_angles):
    """Decalajul după unghiul fără semn care se mișcă cel mai mult în Kinect."""
    candidates = kinect_angles[UNSIGNED].apply(fill_gaps)
    main = (candidates.quantile(0.95) - candidates.quantile(0.05)).idxmax()
    return best_lag(candidates[main], fill_gaps(mp_angles[main])), main


def compare(mp_angles, kinect_angles, lag):
    mp_angles = mp_angles.apply(fill_gaps)
    kinect_angles = kinect_angles.apply(fill_gaps)
    ranges = kinect_angles.quantile(0.95) - kinect_angles.quantile(0.05)
    shifted = mp_angles.shift(lag)
    rows = []
    for name in kinect_angles.columns:
        diff = (shifted[name] - kinect_angles[name]).abs()
        rows.append({
            "angle": name,
            "kinect_range": ranges[name],
            "moving": ranges[name] >= MIN_RANGE,
            "corr": kinect_angles[name].corr(shifted[name]),
            "mean_abs_diff": diff.mean(),
        })
    return pd.DataFrame(rows), shifted


def contact_sheet(row, image_kp, path, n=6):
    """Șase cadre din video, cu scheletul desenat peste ele, ca să verificăm cu ochii."""
    capture = cv2.VideoCapture(str(ROOT / row["rgb_path"]))
    tiles = []
    for i in np.linspace(0, len(image_kp) - 1, n + 2, dtype=int)[1:-1]:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, frame = capture.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        points = image_kp[i]
        if not np.isnan(points[0, 0]):
            for a, b in BONES:
                pa = tuple(int(v) for v in points[MP[a], :2] * (w, h))
                pb = tuple(int(v) for v in points[MP[b], :2] * (w, h))
                cv2.line(frame, pa, pb, (0, 255, 0), 2)
            for name, j in MP.items():
                color = (0, 0, 255) if name.startswith("l") else (255, 128, 0)
                cv2.circle(frame, tuple(int(v) for v in points[j, :2] * (w, h)), 4, color, -1)
        tiles.append(cv2.resize(frame, (480, 270)))
    capture.release()
    rows = [np.hstack(tiles[k:k + 3]) for k in range(0, len(tiles), 3)]
    cv2.imwrite(str(path), np.vstack(rows))


def plot_curves(row, table, shifted, kinect_angles, lag, path):
    moving = table.sort_values("kinect_range", ascending=False).head(4)
    fig, axes = plt.subplots(len(moving), 1, figsize=(10, 2.2 * len(moving)), sharex=True, squeeze=False)
    for ax, (_, r) in zip(axes[:, 0], moving.iterrows()):
        t = np.arange(len(kinect_angles)) / FPS
        ax.plot(t, kinect_angles[r["angle"]], color="#1f77b4", label="Kinect")
        ax.plot(t, shifted[r["angle"]].reindex(kinect_angles.index), color="#ff7f0e", label="MediaPipe")
        ax.set_ylabel("grade")
        ax.set_title(f"{r['angle']}: corelație {r['corr']:.2f}, diferență {r['mean_abs_diff']:.1f}°", fontsize=10)
    axes[0, 0].legend(loc="upper right")
    axes[-1, 0].set_xlabel("secunde")
    fig.suptitle(f"{row['subject']} Es{row['exercise']} ({row['group']}), decalaj {lag} cadre")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    index = pd.read_csv(INDEX)
    summary, details = [], []
    for _, row in pick_videos(index).iterrows():
        name = f"{row['subject']}_Es{row['exercise']}"
        npz = KEYPOINTS / f"{name}.npz"
        info = extract_video(ROOT / row["rgb_path"], npz, fps=FPS)
        print(f"{name}: {info['frames']} cadre, detectie {info['detected_pct']:.1f}%, "
              f"{info['processing_fps']:.1f} cadre/s", flush=True)

        data = np.load(npz)
        world_kp, image_kp = data["world_kp"], data["image_kp"]
        visibility = np.nanmean(world_kp[:, list(MP.values()), 3], axis=0)

        kinect = load_kinect(ROOT / row["skeleton_path"])
        kinect_joints = joints(kinect, KI)
        kinect_angles = all_angles(kinect_joints)
        raw_joints = joints(to_kinect_axes(world_kp), MP)
        lag, main_angle = find_alignment(all_angles(raw_joints), kinect_angles)
        x_corr = x_agreement(raw_joints, kinect_joints, lag)
        mp_joints = joints(to_kinect_axes(world_kp, np.sign(x_corr)), MP)
        table, shifted = compare(all_angles(mp_joints), kinect_angles, lag)

        # Dacă video-ul ar fi în oglindă, umărul stâng s-ar potrivi cu cel drept din Kinect.
        same = table.set_index("angle").loc[["shoulder_L", "shoulder_R"], "corr"].mean()
        swapped = np.mean([kinect_angles["shoulder_L"].corr(shifted["shoulder_R"]),
                           kinect_angles["shoulder_R"].corr(shifted["shoulder_L"])])

        moving = table[table["moving"]]
        summary.append({
            "video": name, "group": row["group"], "exercise": row["exercise"],
            "frames": info["frames"], "kinect_frames": len(kinect),
            "detected_pct": round(info["detected_pct"], 1),
            "mean_visibility": round(float(np.nanmean(visibility)), 2),
            "low_visibility_joints": ",".join(n for n, v in zip(MP, visibility) if v < MIN_VISIBILITY),
            "lag_frames": lag, "main_angle": main_angle, "x_corr": round(x_corr, 2),
            "corr_median": round(moving["corr"].median(), 2),
            "diff_median": round(moving["mean_abs_diff"].median(), 1),
            "shoulder_corr_same_side": round(same, 2), "shoulder_corr_swapped": round(swapped, 2),
            "processing_fps": round(info["processing_fps"], 1),
        })
        details.append(table.assign(video=name, exercise=row["exercise"]))
        contact_sheet(row, image_kp, OUT / f"{name}_skeleton.jpg")
        plot_curves(row, table, shifted, kinect_angles, lag, OUT / f"{name}_curves.png")

    summary = pd.DataFrame(summary)
    details = pd.concat(details).round(2)
    summary.to_csv(OUT / "summary.csv", index=False)
    details.to_csv(OUT / "angles.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", None)
    print(summary.to_string())
    moving = details[details["moving"]]
    print(moving.groupby("angle")[["corr", "mean_abs_diff"]].median().join(moving.groupby("angle").size().rename("n")))


if __name__ == "__main__":
    main()
