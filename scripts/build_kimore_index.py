"""Construiește data/kimore/index.csv: un rând pentru fiecare execuție KIMORE (persoană × exercițiu).

Datele brute nu se modifică. Toate deciziile despre fișierele cu probleme stau aici.
Rulare: python scripts/build_kimore_index.py
"""
import re
import warnings
from pathlib import Path

import openpyxl
import pandas as pd

warnings.filterwarnings("ignore", module="openpyxl")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "kimore" / "raw"
RGB = ROOT / "data" / "kimore" / "rgb"
OUT = ROOT / "data" / "kimore" / "index.csv"

GROUPS = ["CG/Expert", "CG/NotExpert", "GPP/BackPain", "GPP/Parkinson", "GPP/Stroke"]
EXERCISES = range(1, 6)  # Es6 apare doar la NE_ID1 și NE_ID2 și nu e unul din cele 5 exerciții
TIMESTAMP = re.compile(r"\d{6}_\d{6}")
COPY = re.compile(r"\(\d+\)")
MIN_TRACKED = 0.7  # sub acest procent de cadre cu persoană detectată, execuția primește o notă


def read_excel_row(path):
    """Întoarce rândul de date al unui fișier Excel, ca dicționar coloană -> valoare."""
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = list(sheet.iter_rows(values_only=True))
    return {str(h).strip(): v for h, v in zip(rows[0], rows[1]) if h is not None}


def subject_rows(subject_dir, prefix):
    """Citește fișierele Excel ale persoanei, de la toate exercițiile.

    Păstrează doar rândurile cu ID-ul persoanei: unele foldere conțin fișiere ale altcuiva.
    Întoarce (rândurile bune, câte fișiere are în total).
    """
    paths = list(subject_dir.glob(f"Es[1-5]/**/{prefix}*.xlsx"))
    rows = [read_excel_row(p) for p in paths]
    return [r for r in rows if r.get("Subject ID") == subject_dir.name], len(paths)


def score(rows, kind, exercise):
    """Caută scorul în toate fișierele persoanei; aceeași persoană nu poate avea două valori."""
    column = f"clinical {kind} Ex#{exercise}"
    values = {r[column] for r in rows if isinstance(r.get(column), (int, float))}
    if len(values) > 1:
        raise ValueError(f"Scoruri diferite pentru {rows[0]['Subject ID']}, {column}: {values}")
    return values.pop() if values else None


def timestamp(path):
    match = TIMESTAMP.search(path.name)
    return match.group(0) if match else None


def originals(paths):
    """Copiile „(1)” dublează originalul; le folosim doar dacă originalul lipsește."""
    kept = [p for p in paths if not COPY.search(p.name)]
    return kept or paths


def count_frames(path):
    """Numără rândurile CSV. Rândurile goale sunt cadre fără persoană detectată de Kinect."""
    lines = path.read_text(errors="replace").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return len(lines), sum(1 for line in lines if line.strip())


def relative(path):
    return path.relative_to(ROOT).as_posix() if path else None


def index_execution(group, subject_dir, exercise, score_rows, score_files, info):
    subject = subject_dir.name
    es_dir = subject_dir / f"Es{exercise}"
    rgb_dir = RGB / group / subject / f"Es{exercise}"

    rgb_paths = sorted(rgb_dir.glob("**/*.mp4"))  # singurul .mxf dublează un .mp4
    if len(rgb_paths) > 1:
        raise ValueError(f"Mai multe videoclipuri în {rgb_dir}")
    rgb = rgb_paths[0] if rgb_paths else None

    # La încercări multiple alegem înregistrarea care are video; altfel, ultima.
    skeletons = originals(sorted(es_dir.glob("**/JointPosition*.csv")))
    stamps = {timestamp(p) for p in skeletons}
    chosen = timestamp(rgb) if rgb and timestamp(rgb) in stamps else max(stamps, default=None)
    skeleton = next((p for p in skeletons if timestamp(p) == chosen), None)
    times = originals(sorted(es_dir.glob(f"**/TimeStamp{chosen}*.csv"))) if chosen else []
    frames, tracked = count_frames(skeleton) if skeleton else (None, None)

    total = score(score_rows, "TS", exercise)
    has_score = total is not None
    notes = []
    if not has_score:
        notes.append("missing_score" if score_rows or not score_files else "wrong_score_file")
    if not skeleton:
        notes.append("no_skeleton")
    if not rgb:
        notes.append("no_rgb")
    if len(stamps) > 1:
        notes.append("multiple_takes")
    if skeleton and tracked / frames < MIN_TRACKED:
        notes.append("low_tracking")

    return {
        "subject": subject,
        "group": group.split("/")[1],
        "population": "healthy" if group.startswith("CG") else "patient",
        "exercise": exercise,
        "score_total": total,
        "score_po": score(score_rows, "PO", exercise),
        "score_cf": score(score_rows, "CF", exercise),
        "age": info.get("Age"),
        "gender": info.get("Gender"),
        "skeleton_path": relative(skeleton),
        "timestamp_path": relative(times[0]) if times else None,
        "rgb_path": relative(rgb),
        "skeleton_frames": frames,
        "tracked_frames": tracked,
        "use_skeleton": bool(skeleton and has_score),
        "use_rgb": bool(rgb and has_score),
        "notes": ";".join(notes),
    }


def main():
    rows = []
    for group in GROUPS:
        for subject_dir in sorted((RAW / group).iterdir()):
            score_rows, score_files = subject_rows(subject_dir, "ClinicalAssessment")
            info_rows, _ = subject_rows(subject_dir, "SuppInfo")
            info = info_rows[0] if info_rows else {}
            for exercise in EXERCISES:
                rows.append(index_execution(group, subject_dir, exercise, score_rows, score_files, info))

    index = pd.DataFrame(rows)
    index.to_csv(OUT, index=False)

    print(f"{OUT.relative_to(ROOT)}: {len(index)} linii, {index['subject'].nunique()} persoane")
    print(index.groupby("exercise")[["use_skeleton", "use_rgb"]].sum())
    print(f"Total: schelet {index['use_skeleton'].sum()}, RGB {index['use_rgb'].sum()}")
    print(index["notes"].str.split(";").explode().value_counts().drop("", errors="ignore"))


if __name__ == "__main__":
    main()
