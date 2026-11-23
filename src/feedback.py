"""Feedback-ul live: reguli deterministe pe unghiuri și poziții, cu praguri calibrate pe KIMORE.

Nu intră în scorul clinic. Spune persoanei, în timpul exercițiului, ce să corecteze.

Fluxul, cadru cu cadru (aceeași logică e portată în Kotlin, android/.../pose/Feedback.kt):
1. Numărătoarea de 5 secunde: cadrele bune devin poziția de start (mediana fiecărei măsuri).
2. După start, fiecare cadru dă măsurile (frame_measures); la finalul unei repetări, RepCounter dă repetarea.
3. Regulile „rep” se verifică la fiecare repetare (sună la 2 din ultimele 3), regulile „hold” continuu
   (sună dacă abaterea de la start ține hold_s secunde). Dintre regulile care sună, se spune una singură:
   cea mai importantă care n-a fost spusă de curând.
"""
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.features import compute_angles

ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "config" / "feedback.json"
GOOD_JOB = "Bine, așa!"
HISTORY_S = 20.0  # cât din trecut se păstrează pentru repetarea în curs
ROTATIONS = {"shoulder_rotation", "pelvis_rotation"}  # unghiuri pe cerc: diferențele se calculează între -180° și 180°


def frame_measures(joints):
    """Măsurile pentru reguli, din articulații în axele comune ({nume: cadre × 3}). Întoarce {nume: cadre}.

    Unghiurile sunt în grade, distanțele în centimetri.
    """
    angles = compute_angles(joints)
    shoulders = (joints["shoulder_L"] + joints["shoulder_R"]) / 2
    hips = (joints["hip_L"] + joints["hip_R"]) / 2
    ankles = (joints["ankle_L"] + joints["ankle_R"]) / 2
    wrists = (joints["wrist_L"] + joints["wrist_R"]) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        knee_ratio = (joints["knee_L"][:, 0] - joints["knee_R"][:, 0]) / (joints["ankle_L"][:, 0] - joints["ankle_R"][:, 0])
    return {
        "shoulder": angles["shoulder_mean"].to_numpy(),  # unghiul braț–trunchi, media stânga/dreapta
        "shoulder_diff": (angles["shoulder_L"] - angles["shoulder_R"]).abs().to_numpy(),
        "elbow": np.fmin(angles["elbow_L"], angles["elbow_R"]).to_numpy(),  # cotul mai îndoit dintre cele două
        "tilt": angles["trunk_tilt"].to_numpy(),  # înclinarea laterală, pozitiv spre stânga persoanei
        "lean": angles["trunk_lean"].to_numpy(),  # aplecarea, pozitiv spre cameră (în față)
        "pelvis_shift": 100 * (hips[:, 0] - ankles[:, 0]),  # bazinul față de glezne, lateral
        "shoulder_rotation": angles["shoulder_rotation"].to_numpy(),
        "pelvis_rotation": angles["pelvis_rotation"].to_numpy(),
        "wrist_height": 100 * (wrists[:, 1] - shoulders[:, 1]),  # mâinile față de umeri, pe verticală
        "knee": angles["knee_flexion_mean"].to_numpy(),
        "knee_diff": (angles["knee_flexion_L"] - angles["knee_flexion_R"]).abs().to_numpy(),
        "knee_ratio": knee_ratio,  # distanța dintre genunchi / distanța dintre glezne (sub 1: genunchii se strâng)
    }


MEASURES = list(frame_measures({name: np.zeros((1, 3)) for name in [
    "shoulder_L", "shoulder_R", "elbow_L", "elbow_R", "wrist_L", "wrist_R", "hip_L", "hip_R",
    "knee_L", "knee_R", "ankle_L", "ankle_R"]}))


def load_rules(exercise, path=RULES_FILE):
    """Regulile exercițiului și setările comune, din config/feedback.json (scris de calibrare)."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    return config["settings"], config["exercises"][str(exercise)] + config["general"]


@dataclass
class RepTimes:
    """O repetare, în secunde: începutul (valea), vârful, momentul anunțului; amplitudinea în grade."""
    start: float
    peak: float
    end: float
    amplitude: float


@dataclass
class FeedbackEngine:
    rules: list
    settings: dict
    baseline: dict | None = None
    trace: dict = field(default_factory=dict)  # valorile măsurate pe regulă (pentru calibrare)
    counts: dict = field(default_factory=dict)  # de câte ori a sunat fiecare regulă (pentru rezumat)

    def __post_init__(self):
        self.rules = [r for r in self.rules if r.get("enabled", True)]
        self._history = deque()  # (t, măsuri)
        self._recent = {r["id"]: deque(maxlen=3) for r in self.rules}  # greșit/corect la ultimele repetări
        self._held_since = {}
        self._spoken_at = {}
        self._last_message_t = -np.inf
        self._last_rep_t = None
        self._amplitudes = []
        self._corrected = set()  # reguli care au sunat și așteaptă un „Bine, așa!”

    # Poziția de start
    def set_baseline(self, frames):
        """frames: lista de măsuri din numărătoare (doar cadrele bune). Mediana fiecărei măsuri."""
        values = {m: [f[m] for f in frames if np.isfinite(f.get(m, np.nan))] for m in MEASURES}
        self.baseline = {m: float(np.median(v)) if v else np.nan for m, v in values.items()}

    def _value(self, rule, raw):
        if rule.get("relative") and self.baseline is not None:
            difference = raw - self.baseline[rule["measure"]]
            if rule["measure"] in ROTATIONS:
                difference = (difference + 180) % 360 - 180
            return difference
        return raw

    # Pe cadru
    def update(self, t, measures, rep=None):
        """measures: {măsură: valoare} pentru un cadru bun, sau None pentru un cadru respins.
        rep: RepTimes dacă tocmai s-a încheiat o repetare. Întoarce mesajul de spus sau None."""
        if self._last_rep_t is None:
            self._last_rep_t = t
        if measures is not None:
            self._history.append((t, measures))
        while self._history and self._history[0][0] < t - HISTORY_S:
            self._history.popleft()

        alerts = []
        for rule in self.rules:
            kind = rule["kind"]
            if kind == "hold":
                alerts += self._check_hold(rule, t, measures)
            elif kind == "idle":
                if t - self._last_rep_t >= rule["threshold"]:
                    alerts.append(rule)
                    self._last_rep_t = t  # următorul îndemn abia după încă o pauză întreagă
        if rep is not None:
            self._last_rep_t = t
            self._amplitudes.append(rep.amplitude)
            for rule in self.rules:
                alerts += self._check_rep(rule, rep)
        return self._choose(t, alerts)

    def _check_hold(self, rule, t, measures):
        if measures is None or self.baseline is None:
            self._held_since.pop(rule["id"], None)
            return []
        deviation = abs(self._value(rule, measures[rule["measure"]]))
        if not np.isfinite(deviation):
            return []
        self.trace.setdefault(rule["id"], []).append((t, deviation))
        if "threshold" not in rule or deviation <= rule["threshold"]:
            self._held_since.pop(rule["id"], None)
            return []
        since = self._held_since.setdefault(rule["id"], t)
        return [rule] if t - since >= self.settings["hold_s"] else []

    def _rep_stat(self, rule, rep):
        window = [(t, m[rule["measure"]]) for t, m in self._history if rep.start <= t <= rep.end]
        window = [(t, v) for t, v in window if np.isfinite(v)]
        if not window:
            return np.nan
        times = np.array([t for t, _ in window])
        values = np.array([self._value(rule, v) for _, v in window])
        stat = rule["stat"]
        if stat == "peak":
            return float(values[np.argmin(np.abs(times - rep.peak))])
        if stat == "min":
            return float(values.min())
        if stat == "max":
            return float(values.max())
        if stat == "range":
            return float(values.max() - values.min())
        if len(self._amplitudes) < 2:
            return np.nan  # prima repetare pornește din centru: „cealaltă parte” nu e încă o înclinare reală
        # Mișcări stânga-dreapta: valea repetării e o parte, vârful e cealaltă (față de start, cu semn).
        one_side = float(values[np.argmin(np.abs(times - rep.peak))])
        other_side = float(-values[np.argmin(np.abs(times - rep.start))])
        if stat == "both_sides":
            return min(one_side, other_side)
        if stat == "sides_diff":
            return abs(one_side - other_side)
        raise ValueError(f"stat necunoscut: {stat}")

    def _check_rep(self, rule, rep):
        kind = rule["kind"]
        if kind == "rep":
            value = self._rep_stat(rule, rep)
            if not np.isfinite(value):
                return []
            self.trace.setdefault(rule["id"], []).append((rep.end, value))
            if "threshold" not in rule:
                return []
            wrong = value < rule["threshold"] if rule["bad"] == "low" else value > rule["threshold"]
        elif kind == "too_fast":
            self.trace.setdefault(rule["id"], []).append((rep.end, rep.peak - rep.start))
            if "threshold" not in rule:
                return []
            wrong = rep.peak - rep.start < rule["threshold"]
        elif kind == "fatigue":
            first = self._amplitudes[:3]
            wrong = len(self._amplitudes) > 3 and rep.amplitude < rule["threshold"] * float(np.mean(first))
        else:
            return []
        recent = self._recent[rule["id"]]
        recent.append(wrong)
        if wrong:
            return [rule] if sum(recent) >= 2 else []
        if rule["id"] in self._corrected and not any(list(recent)[-2:]) and len(recent) >= 2:
            self._corrected.discard(rule["id"])
            return [{"id": "good_job", "priority": 4, "message": GOOD_JOB}]
        return []

    def _choose(self, t, alerts):
        if not alerts or t - self._last_message_t < self.settings["gap_s"]:
            return None
        fresh = [a for a in alerts if t - self._spoken_at.get(a["message"], -np.inf) >= self.settings["repeat_s"]]
        if not fresh:
            return None
        rule = min(fresh, key=lambda a: a["priority"])
        self._spoken_at[rule["message"]] = t
        self._last_message_t = t
        if rule["id"] != "good_job":
            self.counts[rule["id"]] = self.counts.get(rule["id"], 0) + 1
            if rule.get("kind") == "rep":
                self._corrected.add(rule["id"])
        return rule["message"]

    def summary(self):
        """{mesaj: de câte ori a fost spus}, pentru rezultatul sesiunii."""
        messages = {r["id"]: r["message"] for r in self.rules}
        return {messages[k]: v for k, v in sorted(self.counts.items(), key=lambda kv: -kv[1])}
