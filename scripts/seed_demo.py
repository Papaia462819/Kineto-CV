"""Umple baza de date cu un pacient demo, ca aplicația să aibă ce arăta de la început.

Pacientul e fictiv. Sesiunile lui trecute sunt analize reale ale unor execuții KIMORE
(punctele MediaPipe din data/keypoints/kimore), datate în urmă cu câteva zile, iar recenziile și notițele
medicului sunt scrise de mână, ca exemplu.

Rulare:
    python scripts/seed_demo.py           # adaugă pacientul demo dacă baza e goală
    python scripts/seed_demo.py --reset   # șterge baza și o reface de la zero
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.session import Analyzer
from src.storage import DEFAULT_DB, Storage

KEYPOINTS = ROOT / "data" / "keypoints" / "kimore"
DOCTOR = "Dr. Demo (kinetoterapeut)"
# (zile în urmă, înregistrarea KIMORE, recenzia medicului sau None)
PAST_SESSIONS = [
    (9, "B_ID7_Es1", "Amplitudine bună la ridicarea brațelor. Păstrează trunchiul drept, fără să te lași pe spate."),
    (7, "B_ID7_Es2", "Înclinările sunt corecte, dar mai lente ar fi mai bine: 2–3 secunde pe fiecare parte."),
    (4, "B_ID7_Es5", None),
    (2, "B_ID6_Es1", None),
]
MESSAGES = [
    (10, "doctor", DOCTOR, "Bun venit! Planul pentru primele două săptămâni: exercițiile 1, 2 și 5, de 3 ori pe săptămână. "
                           "Oprește-te dacă apare durere ascuțită."),
    (8, "patient", "Pacient Demo", "Mulțumesc! La înclinări simt o ușoară tensiune pe partea dreaptă, e normal?"),
    (7, "doctor", DOCTOR, "Da, o tensiune ușoară e normală la început. Nu forța amplitudinea; o creștem treptat."),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if args.reset and DEFAULT_DB.exists():
        DEFAULT_DB.unlink()
    storage = Storage()
    if storage.patient(1) is not None:
        print("Baza are deja pacientul 1. Pentru o baza noua: --reset")
        return

    patient = storage.add_patient("Pacient Demo", 1968, "Lombalgie cronică (date demonstrative)", DOCTOR)
    for exercise, reps, per_week in [(1, 10, 3), (2, 10, 3), (5, 8, 3)]:
        storage.set_plan(patient, exercise, reps, per_week)

    analyzer = Analyzer()
    today = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    for days, name, review in PAST_SESSIONS:
        data = np.load(KEYPOINTS / f"{name}.npz")
        exercise = int(name[-1])
        times = np.arange(len(data["image_kp"])) / 30.0
        result = analyzer.analyze(data["image_kp"], data["world_kp"], times, exercise, mirrored=True)
        created = (today - timedelta(days=days)).isoformat(timespec="seconds")
        session = storage.add_session(patient, result.to_dict(), device="KIMORE (demo)", created=created)
        if review:
            storage.review_session(session, DOCTOR, review,
                                   (today - timedelta(days=days - 1)).isoformat(timespec="seconds"))
        print(f"sesiune {session}: Es{exercise}, scor {result.score:.1f}, repetari {result.reps}")
    for days, role, author, text in MESSAGES:
        storage.add_message(patient, role, author, text, created=(today - timedelta(days=days)).isoformat(timespec="seconds"))
    storage.close()
    print(f"Pacientul demo are id-ul {patient}. Baza: {DEFAULT_DB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
