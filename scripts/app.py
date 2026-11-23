"""Aplicația Kineto-CV, prima versiune: camera (sau un video), urmărirea live și scorul la final.

Rulare:
    python scripts/app.py --exercise 1                     # camera 0
    python scripts/app.py --camera 1 --exercise 5
    python scripts/app.py --video clip.mp4 --exercise 2 --mirrored   # de ex. un video KIMORE
    python scripts/app.py --video clip.mp4 --exercise 2 --mirrored --no-window   # doar rezultatul

Cu camera:
    SPAȚIU  pornește înregistrarea execuției; încă un SPAȚIU o oprește și o analizează
    r       renunță la înregistrarea curentă      m  imaginea e/nu e în oglindă (doar înainte de start)
    q       ieșire
Cu un video, înregistrarea ține de la primul la ultimul cadru.

Fiecare execuție analizată se salvează în data/sessions/<data>_Es<n>/: punctele brute (keypoints.npz)
și rezultatul (result.json). Mai târziu, de aici se umple baza de date și dashboard-ul.
"""
import argparse
import json
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pose import PoseEstimator
from src.quality import MISSING, OK
from src.session import Analyzer, LiveSession

SESSIONS = ROOT / "data" / "sessions"
EXERCISE_NAMES = {1: "Ridicarea bratelor", 2: "Inclinari laterale", 3: "Rotatia trunchiului",
                  4: "Rotatia pelvisului", 5: "Genuflexiuni"}
BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24),
         (23, 25), (25, 27), (24, 26), (26, 28)]
LEFT, RIGHT = [11, 13, 15, 23, 25, 27], [12, 14, 16, 24, 26, 28]
RED, BLUE, GREEN, GREY, WHITE, YELLOW = (60, 60, 230), (230, 140, 40), (80, 200, 80), (150, 150, 150), \
    (255, 255, 255), (0, 220, 255)
REP_BANNER_S = 2.0
FEEDBACK_S = 3.0  # cât stă mesajul de corectare pe ecran


def plain(text):
    """Fără diacritice: fontul OpenCV și consola Windows nu le pot scrie pe toate."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def draw_skeleton(frame, image_kp, ok):
    h, w = frame.shape[:2]
    if np.isnan(image_kp[11, 0]):
        return
    pixel = lambda i: (int(image_kp[i, 0] * w), int(image_kp[i, 1] * h))
    for a, b in BONES:
        cv2.line(frame, pixel(a), pixel(b), GREEN if ok else GREY, 3)
    for indices, color in ((LEFT, RED), (RIGHT, BLUE)):
        for i in indices:
            cv2.circle(frame, pixel(i), 6, color, -1)


def put_lines(frame, lines, top=30, scale=0.8):
    """Text cu contur negru, ca să se vadă pe orice fundal. Fontul OpenCV nu are diacritice."""
    for k, item in enumerate(lines):
        line, color = item if isinstance(item, tuple) else (item, WHITE)
        y = top + int(34 * scale / 0.8) * k
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4)
        cv2.putText(frame, line, (12, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2)


def result_lines(result):
    lines = [(f"Es{result.exercise} {EXERCISE_NAMES[result.exercise]}: rezultat", YELLOW)]
    if result.score is not None:
        lines.append((f"Scor estimat: {result.score:.0f} / 50  (eroare tipica +-{result.score_error:.0f})", GREEN))
    lines += [f"Repetari: {result.reps}",
              f"Amplitudine medie: {'-' if np.isnan(result.rom_mean) else f'{result.rom_mean:.0f} grade'}",
              f"Durata: {result.duration_s:.0f} s, cadre bune: {result.kept:.0%}"]
    if not np.isnan(result.rom_fatigue):
        lines.append(f"Amplitudine la final fata de inceput: {result.rom_fatigue:.0%}")
    lines += [(f"! {w}", (80, 160, 255)) for w in result.warnings]
    if result.feedback:
        lines.append(("Observatii in timpul exercitiului:", YELLOW))
        lines += [f"  {plain(message)} (x{count})" for message, count in result.feedback.items()]
    return lines


def save_session(session, result, frame_size):
    image_kp, world_kp, times = session.recording()
    folder = SESSIONS / f"{datetime.now():%Y%m%d_%H%M%S}_Es{session.exercise}"
    folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(folder / "keypoints.npz", image_kp=image_kp, world_kp=world_kp, times=times,
                        exercise=session.exercise, mirrored=session.mirrored)
    info = {"time": datetime.now().isoformat(timespec="seconds"), "frame_size": frame_size, **result.to_dict()}
    (folder / "result.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    return folder


def show_result(frame, result, wait):
    panel = (0.35 * frame).astype(np.uint8)
    put_lines(panel, result_lines(result) + ["", "orice tasta: inapoi   q: iesire"], top=40, scale=0.7)
    cv2.imshow("Kineto-CV", panel)
    return cv2.waitKey(0 if wait else 1) & 0xFF


def print_result(result, folder):
    # Consola Windows nu scrie toate diacriticele, deci textul rămâne fără ele.
    for line in result_lines(result):
        print(line[0] if isinstance(line, tuple) else line)
    print(f"Salvat in {folder.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--video", help="un fisier video in loc de camera")
    parser.add_argument("--exercise", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--mirrored", action="store_true", help="imaginea vine deja in oglinda (ex. KIMORE)")
    parser.add_argument("--no-window", action="store_true", help="fara fereastra (doar cu --video)")
    parser.add_argument("--countdown", type=float, default=5.0, help="secundele de stat nemiscat de la start")
    args = parser.parse_args()
    if args.no_window and not args.video:
        sys.exit("--no-window merge doar cu --video")

    capture = cv2.VideoCapture(args.video) if args.video else cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not capture.isOpened():
        sys.exit("Nu pot deschide camera sau videoclipul. Vezi: python scripts/webcam_test.py --list")
    video_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    analyzer = Analyzer()  # modelele se încarcă o dată, la pornire
    print(f"Es{args.exercise} {EXERCISE_NAMES[args.exercise]}. Modele incarcate.")

    mirrored = args.mirrored
    new_session = lambda: LiveSession(args.exercise, mirrored, countdown_s=args.countdown)
    session = new_session() if args.video else None  # un video se înregistrează tot
    start, frames, fps_shown, last_tick = time.perf_counter(), 0, 0.0, time.perf_counter()
    banner, banner_until = "", 0.0
    said, said_until = "", 0.0

    def finish(last_frame):
        nonlocal session
        result = analyzer.analyze(*session.recording(), args.exercise, session.mirrored)
        result.feedback = session.feedback.summary()
        folder = save_session(session, result, list(last_frame.shape[1::-1]))
        print_result(result, folder)
        session = None
        return result

    with PoseEstimator() as estimator:
        frame = None
        while True:
            ok, new_frame = capture.read()
            if not ok:
                if args.video and session is not None and frame is not None:
                    result = finish(frame)
                    if not args.no_window:
                        show_result(frame, result, wait=True)
                break
            frame = new_frame
            now = time.perf_counter()
            # Camera dă timpul real; un video se redă cu fps-ul lui. MediaPipe vrea timpi crescători.
            t = frames / video_fps if args.video else now - start
            frames += 1
            image_kp, world_kp = estimator.process(frame, t * 1000)

            if session is not None:
                state = session.update(image_kp, world_kp, t)
                status, message = state.status, state.message
                if state.new_rep is not None:
                    banner, banner_until = f"Repetarea {state.reps}: {state.new_rep.amplitude:.0f} grade", now + REP_BANNER_S
                if state.feedback:
                    said, said_until = plain(state.feedback), now + FEEDBACK_S
                    print(f"[{t:5.1f} s] {said}")
            else:
                # Înainte de start: doar verificăm că persoana se vede, ca să se poată așeza.
                visible = not np.isnan(image_kp[[11, 12, 23, 24, 27, 28], 0]).any()
                status, message = (OK, "Te vad intreg. SPATIU = start") if visible else \
                    (MISSING, "Asaza-te: tot corpul in cadru")

            fps_shown = 0.9 * fps_shown + 0.1 / max(now - last_tick, 1e-6)
            last_tick = now
            if args.no_window:
                continue

            draw_skeleton(frame, image_kp, status == OK)
            if not args.video and not mirrored:
                # Persoana se vede ca în oglindă, dar modelul a primit imaginea neîntoarsă.
                frame = cv2.flip(frame, 1)
            if session is not None:
                lines = [f"Es{args.exercise} {EXERCISE_NAMES[args.exercise]}   inregistrez {session.duration_s:.0f} s",
                         (f"Repetari: {state.reps}", GREEN),
                         f"{session.angle_name}: {'-' if np.isnan(state.angle) else f'{state.angle:.0f} grade'}"]
            else:
                lines = [f"Es{args.exercise} {EXERCISE_NAMES[args.exercise]}   pregatire",
                         f"oglinda: {'da' if mirrored else 'nu'} (m)   rosu = stanga ta"]
            if message:
                lines.append((message, (80, 160, 255)))
            if now < banner_until:
                lines.append((banner, YELLOW))
            put_lines(frame, lines)
            put_lines(frame, [f"FPS {fps_shown:.0f}"], top=frame.shape[0] - 15, scale=0.6)
            h, w = frame.shape[:2]
            if session is not None and state.countdown is not None:
                # Numărătoarea: mare, în mijloc. Acum se memorează poziția de start.
                number = str(int(np.ceil(state.countdown)))
                cv2.putText(frame, number, (w // 2 - 60, h // 2 + 60), cv2.FONT_HERSHEY_SIMPLEX, 6, (0, 0, 0), 18)
                cv2.putText(frame, number, (w // 2 - 60, h // 2 + 60), cv2.FONT_HERSHEY_SIMPLEX, 6, WHITE, 8)
                put_lines(frame, [("Stai nemiscat", YELLOW)], top=h // 2 + 120, scale=1.0)
            elif session is not None and now < said_until:
                put_lines(frame, [(said, YELLOW)], top=h - 60, scale=1.1)
            cv2.imshow("Kineto-CV", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if args.video:
                continue
            if key == ord(" "):
                if session is None:
                    session, banner_until, said_until = new_session(), 0.0, 0.0
                else:
                    if show_result(frame, finish(frame), wait=True) == ord("q"):
                        break
            elif key == ord("r") and session is not None:
                session = None
            elif key == ord("m") and session is None:
                mirrored = not mirrored

    capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
