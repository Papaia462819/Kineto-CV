"""Test live: camera (sau un video), scheletul MediaPipe, verificarea cadrelor și numărătoarea.

Rulare:
    python scripts/webcam_test.py --list                 # ce camere vede Windows
    python scripts/webcam_test.py --camera 1 --exercise 1
    python scripts/webcam_test.py --video clip.mp4 --exercise 2

Taste: q = ieșire, m = imaginea e/nu e în oglindă, r = repetările de la zero.
Punctele stângi ale persoanei sunt roșii, cele drepte albastre: dacă îți ridici mâna stângă,
trebuie să se miște punctele roșii. Dacă se mișcă cele albastre, apasă m.
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features import PRIMARY_ANGLE, REP_PROMINENCE, compute_angles, named_joints
from src.filters import OneEuroFilter
from src.pose import PoseEstimator
from src.quality import OK, QualityChecker
from src.reps import RepCounter

BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
         (23, 25), (25, 27), (24, 26), (26, 28)]
LEFT = [11, 13, 15, 23, 25, 27]
RIGHT = [12, 14, 16, 24, 26, 28]
RED, BLUE, GREEN, GREY, WHITE = (60, 60, 230), (230, 140, 40), (80, 200, 80), (150, 150, 150), (255, 255, 255)


def list_cameras(n=6):
    for index in range(n):
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        ok, frame = capture.read() if capture.isOpened() else (False, None)
        print(f"camera {index}: " + (f"merge, {frame.shape[1]}x{frame.shape[0]}" if ok else "nu"))
        capture.release()


def draw(frame, image_kp, status):
    h, w = frame.shape[:2]
    if np.isnan(image_kp[11, 0]):
        return
    pixel = lambda i: (int(image_kp[i, 0] * w), int(image_kp[i, 1] * h))
    for a, b in BONES:
        cv2.line(frame, pixel(a), pixel(b), GREEN if status == OK else GREY, 3)
    for indices, color in ((LEFT, RED), (RIGHT, BLUE)):
        for i in indices:
            cv2.circle(frame, pixel(i), 6, color, -1)


def text(frame, lines):
    for k, line in enumerate(lines):
        y = 30 + 30 * k
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, WHITE, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--video", help="un fișier video în loc de cameră")
    parser.add_argument("--exercise", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--mirrored", action="store_true", help="imaginea vine deja în oglindă")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--max-frames", type=int, help="oprește după atâtea cadre (pentru test)")
    parser.add_argument("--no-window", action="store_true", help="fără fereastră, doar rezumatul (pentru test)")
    args = parser.parse_args()
    if args.list:
        list_cameras()
        return

    capture = cv2.VideoCapture(args.video) if args.video else cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not capture.isOpened():
        sys.exit("Nu pot deschide camera sau videoclipul. Incearca --list.")
    video_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0

    mirrored = args.mirrored
    signal = PRIMARY_ANGLE[args.exercise]
    checker = QualityChecker(mirrored=mirrored)
    smoother = OneEuroFilter()
    counter = RepCounter(30.0, prominence=REP_PROMINENCE[args.exercise])
    start = time.perf_counter()
    frames, kept, model_ms = 0, 0, []
    fps_shown, last_tick = 0.0, start

    with PoseEstimator() as estimator:
        while True:
            ok, frame = capture.read()
            if not ok or (args.max_frames and frames >= args.max_frames):
                break
            now = time.perf_counter()
            # Camera dă timpul real; un video se redă cu fps-ul lui.
            t = frames / video_fps if args.video else now - start
            tick = time.perf_counter()
            image_kp, world_kp = estimator.process(frame, t * 1000)
            model_ms.append(1000 * (time.perf_counter() - tick))
            image_kp, world_kp, status = checker.update(image_kp, world_kp)
            frames += 1
            kept += status == OK

            world = np.array(world_kp)
            world[:, :3] = smoother(world_kp[:, :3], t)
            value = compute_angles(named_joints(world[None], "mediapipe", mirrored))[signal].iloc[0]
            counter.update(value)

            fps_shown = 0.9 * fps_shown + 0.1 / max(now - last_tick, 1e-6)
            last_tick = now
            if args.no_window:
                continue
            draw(frame, image_kp, status)
            text(frame, [
                f"Es{args.exercise} {signal}: {'-' if np.isnan(value) else f'{value:.0f} grade'}",
                f"repetari: {counter.count}",
                f"cadru: {status}   FPS: {fps_shown:.0f}   model: {model_ms[-1]:.0f} ms",
                f"oglinda: {'da' if mirrored else 'nu'} (m)   rosu = stanga ta",
            ])
            cv2.imshow("Kineto-CV - webcam test", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("m"):
                mirrored = not mirrored
                checker = QualityChecker(mirrored=mirrored)
            if key == ord("r"):
                counter = RepCounter(30.0, prominence=REP_PROMINENCE[args.exercise])

    capture.release()
    cv2.destroyAllWindows()
    elapsed = time.perf_counter() - start
    if frames:
        # Textul afișat în consolă rămâne fără diacritice: consola Windows nu le poate scrie pe toate.
        print(f"{frames} cadre, {frames / elapsed:.1f} cadre/s, model {np.median(model_ms):.1f} ms/cadru (mediana), "
              f"cadre bune {100 * kept / frames:.0f}%, laturi corectate {checker.swaps}, repetari {counter.count}")


if __name__ == "__main__":
    main()
