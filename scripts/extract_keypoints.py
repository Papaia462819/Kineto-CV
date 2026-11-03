"""Extrage punctele MediaPipe dintr-un video și le salvează într-un fișier .npz.

Rulare: python scripts/extract_keypoints.py video.mp4 data/keypoints/video.npz --fps 30

La KIMORE dă --fps 30: videoclipurile declară 25 sau 24 fps, dar au fost filmate la ~30.
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pose import PoseEstimator


def extract_video(video_path, output_path, fps=None):
    """Salvează image_kp și world_kp (cadre × 33 × 4) și întoarce un mic rezumat."""
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise FileNotFoundError(f"Nu pot deschide {video_path}")
    fps = fps or capture.get(cv2.CAP_PROP_FPS)

    image_kp, world_kp = [], []
    start = time.perf_counter()
    with PoseEstimator() as estimator:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            image, world = estimator.process(frame, len(image_kp) * 1000 / fps)
            image_kp.append(image)
            world_kp.append(world)
    capture.release()
    elapsed = time.perf_counter() - start

    image_kp, world_kp = np.stack(image_kp), np.stack(world_kp)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, image_kp=image_kp, world_kp=world_kp, fps=fps)
    return {
        "frames": len(image_kp),
        "detected_pct": 100 * np.mean(~np.isnan(world_kp[:, 0, 0])),
        "processing_fps": len(image_kp) / elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("output")
    parser.add_argument("--fps", type=float, help="fps-ul real, dacă cel declarat de video e greșit")
    args = parser.parse_args()
    print(extract_video(args.video, args.output, args.fps))


if __name__ == "__main__":
    main()
