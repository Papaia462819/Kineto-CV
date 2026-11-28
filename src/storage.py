"""Baza de date a aplicației (SQLite): pacienți, planul de exerciții, sesiuni, recenziile medicului, mesaje.

SQLite e un singur fișier (data/kineto.db), fără server separat. Punctele brute ale fiecărei sesiuni
stau lângă, în data/sessions/<id>.npz, ca să poată fi reanalizate cu un model nou.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "kineto.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    birth_year INTEGER,
    diagnosis TEXT,
    therapist TEXT,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plan (
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    exercise INTEGER NOT NULL,
    reps INTEGER NOT NULL,
    per_week INTEGER NOT NULL,
    PRIMARY KEY (patient_id, exercise)
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    created TEXT NOT NULL,
    exercise INTEGER NOT NULL,
    device TEXT,
    duration_s REAL, kept REAL, valid_s REAL, reps INTEGER, rom_mean REAL, rom_fatigue REAL,
    score REAL, score_error REAL, looks_like INTEGER, looks_like_p REAL,
    warnings TEXT NOT NULL DEFAULT '[]',
    feedback TEXT NOT NULL DEFAULT '{}',
    rep_details TEXT NOT NULL DEFAULT '[]',
    keypoints_path TEXT,
    review_text TEXT, review_author TEXT, review_created TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    created TEXT NOT NULL,
    author_role TEXT NOT NULL CHECK (author_role IN ('doctor', 'patient')),
    author_name TEXT NOT NULL,
    text TEXT NOT NULL,
    session_id INTEGER REFERENCES sessions(id)
);
"""
RESULT_FIELDS = ["duration_s", "kept", "valid_s", "reps", "rom_mean", "rom_fatigue", "score", "score_error",
                 "looks_like", "looks_like_p"]


def now():
    return datetime.now().isoformat(timespec="seconds")


class Storage:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI răspunde din mai multe fire; fiecare operație e scurtă și închisă.
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        # O bază mai veche nu are coloanele adăugate între timp: le adăugăm, fără să pierdem datele.
        columns = {row["name"] for row in self._db.execute("PRAGMA table_info(sessions)")}
        for name, default in [("feedback", "'{}'"), ("rep_details", "'[]'")]:
            if name not in columns:
                with self._db:
                    self._db.execute(f"ALTER TABLE sessions ADD COLUMN {name} TEXT NOT NULL DEFAULT {default}")

    def close(self):
        self._db.close()

    def _rows(self, sql, *args):
        return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def _write(self, sql, *args):
        with self._db:  # tranzacție: totul sau nimic
            return self._db.execute(sql, args).lastrowid

    # Pacienți
    def add_patient(self, name, birth_year=None, diagnosis=None, therapist=None):
        return self._write("INSERT INTO patients (name, birth_year, diagnosis, therapist, created) VALUES (?, ?, ?, ?, ?)",
                           name, birth_year, diagnosis, therapist, now())

    def set_plan(self, patient_id, exercise, reps, per_week):
        self._write("INSERT OR REPLACE INTO plan VALUES (?, ?, ?, ?)", patient_id, exercise, reps, per_week)

    def patient(self, patient_id):
        rows = self._rows("SELECT * FROM patients WHERE id = ?", patient_id)
        if not rows:
            return None
        patient = rows[0]
        patient["plan"] = self._rows("SELECT exercise, reps, per_week FROM plan WHERE patient_id = ? ORDER BY exercise",
                                     patient_id)
        return patient

    # Sesiuni
    def add_session(self, patient_id, result, device=None, keypoints_path=None, created=None):
        """result: dicționarul din ExecutionResult.to_dict() (feedback = {mesaj: de câte ori a fost spus live},
        rep_details = măsurile fiecărei repetări)."""
        return self._write(
            f"INSERT INTO sessions (patient_id, created, exercise, device, {', '.join(RESULT_FIELDS)}, warnings, "
            f"feedback, rep_details, keypoints_path) VALUES ({', '.join('?' * (len(RESULT_FIELDS) + 8))})",
            patient_id, created or now(), result["exercise"], device, *[result[f] for f in RESULT_FIELDS],
            json.dumps(result["warnings"], ensure_ascii=False),
            json.dumps(result.get("feedback") or {}, ensure_ascii=False),
            json.dumps(result.get("rep_details") or [], ensure_ascii=False), keypoints_path)

    def set_keypoints_path(self, session_id, path):
        self._write("UPDATE sessions SET keypoints_path = ? WHERE id = ?", str(path), session_id)

    def review_session(self, session_id, author, text, created=None):
        self._write("UPDATE sessions SET review_text = ?, review_author = ?, review_created = ? WHERE id = ?",
                    text, author, created or now(), session_id)

    @staticmethod
    def _session(row):
        row["warnings"] = json.loads(row["warnings"])
        row["feedback"] = json.loads(row["feedback"])
        row["rep_details"] = json.loads(row["rep_details"])
        row.pop("keypoints_path", None)  # e un drum pe server, nu interesează clientul
        return row

    def session(self, session_id):
        rows = self._rows("SELECT * FROM sessions WHERE id = ?", session_id)
        return self._session(rows[0]) if rows else None

    def sessions(self, patient_id, limit=50):
        rows = self._rows("SELECT * FROM sessions WHERE patient_id = ? ORDER BY created DESC, id DESC LIMIT ?",
                          patient_id, limit)
        return [self._session(r) for r in rows]

    # Mesaje
    def add_message(self, patient_id, author_role, author_name, text, session_id=None, created=None):
        return self._write("INSERT INTO messages (patient_id, created, author_role, author_name, text, session_id) "
                           "VALUES (?, ?, ?, ?, ?, ?)", patient_id, created or now(), author_role, author_name, text,
                           session_id)

    def messages(self, patient_id):
        return self._rows("SELECT * FROM messages WHERE patient_id = ? ORDER BY created, id", patient_id)
