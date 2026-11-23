"""O execuție în aplicație: urmărirea live, cadru cu cadru, și analiza de la final, cu scorul clinic.

Nu știe nimic despre cameră sau fereastră: primește puncte MediaPipe și timpi, întoarce numere și mesaje.
Așa, aceeași logică poate fi folosită de aplicația de pe laptop, de un server sau de teste.

Live (LiveSession): verificare → netezire One Euro → unghiul principal → numărarea repetărilor.
La final (Analyzer): exact lanțul din antrenare (scripts/build_score_features.py), pe punctele brute
înregistrate, apoi modelele salvate: scorul clinic (E7) și recunoașterea exercițiului (E8).
"""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.clinical_features import clinical_summary
from src.execution_features import (FEATURE_NAMES, joints_from_mediapipe, repetition_summary, summarize,
                                    valid_seconds)
from src.feedback import RULES_FILE, FeedbackEngine, RepTimes, frame_measures, load_rules
from src.features import PRIMARY_ANGLE, REP_PROMINENCE, compute_angles, named_joints
from src.filters import OneEuroFilter
from src.quality import JUMP, LOW_VISIBILITY, MISSING, OK, QualityChecker
from src.reps import RepCounter

MODELS = Path(__file__).resolve().parents[1] / "models"
ANALYSIS_FPS = 30.0  # modelele au învățat pe KIMORE, filmat la 30 de cadre pe secundă
MIN_VALID_S = 1.0  # ca la antrenare: sub o secundă de cadre complete nu dăm scor
MIN_DURATION_S = 5.0
LOW_KEPT = 0.5  # sub jumătate de cadre bune, eroarea pe KIMORE a crescut de la ~5,6 la ~7,3 puncte
COUNTDOWN_S = 5.0  # numărătoarea de la start: persoana stă nemișcată, cadrele devin poziția de start
# Unghiul principal al exercițiului (PRIMARY_ANGLE) printre măsurile regulilor (src/feedback.py).
PRIMARY_MEASURE = {"shoulder_mean": "shoulder", "trunk_tilt": "tilt", "shoulder_rotation": "shoulder_rotation",
                   "knee_flexion_mean": "knee"}
CLASSIFIER_DOUBT = 0.6  # avertizăm doar dacă alt exercițiu e mult mai probabil

STATUS_MESSAGES = {
    OK: "",
    MISSING: "Nu te vad: intra in cadru",
    LOW_VISIBILITY: "Nu te vad intreg: departeaza-te de camera",
    JUMP: "Miscare prea brusca sau detectie gresita",
}
OTHER_STATUS_MESSAGE = "Detectie nesigura: stai cu fata la camera, tot corpul in cadru"


def feature_row(joints, exercise, fps=ANALYSIS_FPS):
    """Rândul de numere al unei execuții (A + B + C), identic cu cel din tabelele de antrenare."""
    angles = compute_angles(joints)
    return {"exercise": exercise, "valid_s": valid_seconds(angles, fps), **summarize(angles, fps),
            **repetition_summary(angles, exercise, fps), **clinical_summary(joints, exercise, fps)}


def resample(times, *arrays, fps=ANALYSIS_FPS):
    """Aduce o înregistrare la `fps` cadre pe secundă, pe baza timpului fiecărui cadru.

    Camera nu dă un ritm fix (15–30 de cadre pe secundă, după lumină și procesor), dar netezirea,
    viteza și distanța dintre repetări sunt calculate în cadre de 1/30 s. Fiecare cadru nou e
    interpolat liniar între cele două cadre vecine; dacă unul din ele lipsește (NaN), lipsește și cel nou.
    """
    times = np.asarray(times, dtype=float)
    if len(times) < 2:
        return arrays
    count = int(np.floor((times[-1] - times[0]) * fps + 1e-6)) + 1
    grid = times[0] + np.arange(count) / fps
    right = np.clip(np.searchsorted(times, grid, side="right"), 1, len(times) - 1)
    left = right - 1
    weight = np.clip((grid - times[left]) / np.maximum(times[right] - times[left], 1e-9), 0, 1)
    result = []
    for array in arrays:
        w = weight.reshape(-1, *[1] * (array.ndim - 1))
        mixed = (1 - w) * array[left] + w * array[right]
        mixed = np.where(w == 0, array[left], np.where(w == 1, array[right], mixed))
        result.append(mixed.astype(array.dtype))
    return tuple(result)


@dataclass
class LiveState:
    status: str  # starea cadrului, din src/quality.py
    message: str  # ce îi spunem persoanei despre poziție ("" dacă totul e bine)
    angle: float  # unghiul principal al exercițiului, în grade (NaN dacă nu se vede)
    reps: int
    new_rep: object = None  # un Rep, când tocmai s-a încheiat o repetare
    countdown: float | None = None  # secundele rămase din numărătoare (None după ea)
    feedback: str | None = None  # un mesaj de spus acum (regulile din src/feedback.py)


class LiveSession:
    """Primește cadrele pe rând, dă starea live și păstrează punctele brute pentru analiza de la final.

    Primele `countdown_s` secunde sunt numărătoarea: persoana stă nemișcată, iar cadrele bune devin poziția
    de start pentru reguli. Repetările și regulile pornesc după ea. Punctele brute se înregistrează de la început.
    """

    def __init__(self, exercise, mirrored=False, fps=ANALYSIS_FPS, countdown_s=COUNTDOWN_S, rules_path=RULES_FILE):
        self.exercise = exercise
        self.mirrored = mirrored
        self.angle_name = PRIMARY_ANGLE[exercise]
        self.countdown_s = countdown_s
        self._checker = QualityChecker(fps=fps, mirrored=mirrored)
        self._smoother = OneEuroFilter()
        self._counter = RepCounter(fps, prominence=REP_PROMINENCE[exercise])
        self._counter_times = []  # timpul fiecărui cadru dat numărătorului (repetările vin ca indici)
        settings, rules = load_rules(exercise, rules_path)
        self.feedback = FeedbackEngine(rules, settings)
        self._start_frames = []
        self._image, self._world, self._times = [], [], []

    def update(self, image_kp, world_kp, t):
        """t: timpul cadrului, în secunde."""
        self._image.append(np.array(image_kp))
        self._world.append(np.array(world_kp))
        self._times.append(float(t))

        _, world, status = self._checker.update(image_kp, world_kp)
        measures = None
        if status == OK:
            smooth = np.array(world)
            smooth[:, :3] = self._smoother(world[:, :3], t)
            values = frame_measures(named_joints(smooth[None], "mediapipe", self.mirrored))
            measures = {name: float(v[0]) for name, v in values.items()}
        else:
            self._smoother.reset()
        message = STATUS_MESSAGES.get(status, OTHER_STATUS_MESSAGE)

        remaining = self.countdown_s - (t - self._times[0])
        if remaining > 0:
            if measures is not None:
                self._start_frames.append(measures)
            return LiveState(status, message, np.nan, 0, countdown=remaining)
        if self.feedback.baseline is None:
            self.feedback.set_baseline(self._start_frames)

        angle = measures[PRIMARY_MEASURE[self.angle_name]] if measures is not None else np.nan
        self._counter_times.append(float(t))
        rep = self._counter.update(angle)
        rep_times = None
        if rep is not None:
            times = self._counter_times
            rep_times = RepTimes(times[rep.start], times[rep.peak], times[rep.end], rep.amplitude)
        said = self.feedback.update(float(t), measures, rep_times)
        return LiveState(status, message, float(angle), self._counter.count, rep, feedback=said)

    @property
    def duration_s(self):
        return self._times[-1] - self._times[0] if len(self._times) > 1 else 0.0

    def recording(self):
        """(image_kp, world_kp, timpi): cadre × 33 × 4, cadre × 33 × 4, cadre."""
        if not self._times:
            empty = np.empty((0, 33, 4), dtype=np.float32)
            return empty, empty.copy(), np.empty(0)
        return np.stack(self._image), np.stack(self._world), np.array(self._times)


@dataclass
class ExecutionResult:
    exercise: int
    duration_s: float
    kept: float  # partea de cadre care au trecut verificarea
    valid_s: float  # secunde cu toate unghiurile măsurate
    reps: int
    rom_mean: float  # amplitudinea medie a repetărilor, în grade, pe unghiul principal
    rom_fatigue: float  # amplitudinea ultimelor repetări / a primelor (sub 1 = amplitudinea scade)
    score: float | None  # scorul clinic estimat, 0–50; None dacă datele nu ajung
    score_error: float  # eroarea medie a modelului pe persoane nevăzute (KIMORE)
    looks_like: int | None  # exercițiul recunoscut din mișcare
    looks_like_p: float | None
    warnings: list = field(default_factory=list)
    feedback: dict = field(default_factory=dict)  # {mesaj de corectare: de câte ori a fost spus live}

    def to_dict(self):
        return {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in asdict(self).items()}


class Analyzer:
    """Încarcă modelele o singură dată și analizează execuții întregi."""

    def __init__(self, models_dir=MODELS):
        models_dir = Path(models_dir)
        self.score_model = joblib.load(models_dir / "clinical_score_mediapipe.joblib")
        info = json.loads((models_dir / "clinical_score_mediapipe.json").read_text(encoding="utf-8"))
        self.score_error = float(info["cv_mae"])
        classifier = models_dir / "exercise_classifier_mediapipe.joblib"
        self.classifier = joblib.load(classifier) if classifier.exists() else None

    def features(self, image_kp, world_kp, times, exercise, mirrored=False):
        """Rândul de numere (A + B + C) și partea de cadre păstrate."""
        image_kp, world_kp = resample(times, image_kp, world_kp)
        joints, kept = joints_from_mediapipe(image_kp, world_kp, ANALYSIS_FPS, mirrored)
        return feature_row(joints, exercise), kept

    def analyze(self, image_kp, world_kp, times, exercise, mirrored=False):
        duration = float(times[-1] - times[0]) if len(times) > 1 else 0.0
        warnings = []
        if len(times) < 2:
            return ExecutionResult(exercise, duration, 0.0, 0.0, 0, np.nan, np.nan, None, self.score_error,
                                   None, None, ["Nu s-a inregistrat nimic"])
        row, kept = self.features(image_kp, world_kp, times, exercise, mirrored)
        table = pd.DataFrame([row])

        complete = table[FEATURE_NAMES].notna().all(axis=1).iloc[0]
        score = None
        if row["valid_s"] >= MIN_VALID_S and complete:
            score = float(self.score_model.predict(table)[0])
        else:
            warnings.append("Prea putine cadre bune: nu pot estima scorul")

        looks_like = looks_like_p = None
        if self.classifier is not None and score is not None:  # pe prea puține cadre ar ghici
            proba = self.classifier.predict_proba(table[FEATURE_NAMES])[0]
            best = int(np.argmax(proba))
            looks_like, looks_like_p = int(self.classifier.classes_[best]), float(proba[best])
            if looks_like != exercise and looks_like_p >= CLASSIFIER_DOUBT:
                warnings.append(f"Miscarea seamana mai mult cu exercitiul {looks_like} ({looks_like_p:.0%})")

        if duration < MIN_DURATION_S:
            warnings.append(f"Inregistrare scurta ({duration:.0f} s)")
        if kept < LOW_KEPT:
            warnings.append(f"Doar {kept:.0%} din cadre au fost bune: scorul e mai putin sigur")
        if row["rep__count"] == 0:
            warnings.append("Nu am gasit nicio repetare")
        return ExecutionResult(exercise, duration, kept, float(row["valid_s"]), int(row["rep__count"]),
                               float(row["rep__rom_mean"]), float(row["rep__rom_fatigue"]), score,
                               self.score_error, looks_like, looks_like_p, warnings)
