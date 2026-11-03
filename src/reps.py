"""Găsește repetările într-o curbă de unghi: fiecare vârf destul de înalt e o repetare."""
from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks

from src.filters import _runs, fill_gaps

DEFAULT_PROMINENCE = 20.0  # grade
MIN_DISTANCE_S = 1.0
MAX_GAP_S = 0.5
EDGE_FRACTION = 0.10  # repetarea începe și se termină la 10% din amplitudine deasupra văii


@dataclass
class Rep:
    start: int
    peak: int
    end: int
    amplitude: float
    valid_fraction: float = 1.0  # câte cadre din repetare au date măsurate, nu completate


def _edge(values, peak, valley, step):
    """Se depărtează de vârf până ajunge aproape de vale, ca pauza de repaus să nu intre în repetare."""
    threshold = values[valley] + EDGE_FRACTION * (values[peak] - values[valley])
    i = peak
    while i != valley and values[i] > threshold:
        i += step
    return i


def find_reps(signal, fps, prominence=DEFAULT_PROMINENCE, min_distance_s=MIN_DISTANCE_S):
    """Varianta offline: vede toată curba. Golurile lungi despart curba, deci nu există repetări peste ele."""
    measured = np.asarray(signal, dtype=float)
    filled = fill_gaps(measured, int(MAX_GAP_S * fps))
    reps = []
    for run_start, run_end in _runs(~np.isnan(filled)):
        values = filled[run_start:run_end]
        peaks, _ = find_peaks(values, prominence=prominence, distance=max(1, int(min_distance_s * fps)))
        for k, peak in enumerate(peaks):
            left_bound = peaks[k - 1] if k else 0
            right_bound = peaks[k + 1] if k + 1 < len(peaks) else len(values) - 1
            left_valley = left_bound + int(np.argmin(values[left_bound:peak + 1]))
            right_valley = peak + int(np.argmin(values[peak:right_bound + 1]))
            start = _edge(values, peak, left_valley, -1)
            end = _edge(values, peak, right_valley, 1)
            lowest = min(values[left_valley], values[right_valley])
            reps.append(Rep(
                start=run_start + start,
                peak=run_start + peak,
                end=run_start + end,
                amplitude=float(values[peak] - lowest),
                valid_fraction=float(np.mean(~np.isnan(measured[run_start + start:run_start + end + 1]))),
            ))
    return reps


class RepCounter:
    """Varianta live: primește câte o valoare și anunță repetarea când unghiul a coborât destul de la vârf.

    Nu poate ști mai devreme că un vârf a fost vârf, deci anunțul vine cu o mică întârziere.
    La anunț, `end` este cadrul curent. `min_distance_s` are același rol ca la varianta offline.
    """

    def __init__(self, fps, prominence=DEFAULT_PROMINENCE, min_distance_s=MIN_DISTANCE_S, max_gap_s=2.0):
        self.fps = fps
        self.prominence = prominence
        self.min_distance = int(min_distance_s * fps)
        self.max_gap = int(max_gap_s * fps)
        self.count = 0
        self._i = -1
        self._last_valid = None
        self._last_peak = None
        self._reset_state()

    def _reset_state(self):
        self._rising = False
        self._valley = (None, np.inf)
        self._top = (None, -np.inf)
        self._valid = 0

    def update(self, value):
        """Întoarce un Rep când tocmai s-a încheiat o repetare, altfel None."""
        self._i += 1
        if value is None or np.isnan(value):
            if self._last_valid is not None and self._i - self._last_valid > self.max_gap:
                self._reset_state()
            return None
        self._last_valid = self._i
        self._valid += 1

        if not self._rising:
            if value < self._valley[1]:
                self._valley = (self._i, value)
                self._valid = 1
            elif value - self._valley[1] >= self.prominence:
                self._rising = True
                self._top = (self._i, value)
            return None

        if value > self._top[1]:
            self._top = (self._i, value)
            return None
        if self._top[1] - value < self.prominence:
            return None

        far_enough = self._last_peak is None or self._top[0] - self._last_peak >= self.min_distance
        rep = None
        if far_enough:
            self.count += 1
            self._last_peak = self._top[0]
            length = self._i - self._valley[0] + 1
            rep = Rep(self._valley[0], self._top[0], self._i, float(self._top[1] - self._valley[1]),
                      min(1.0, self._valid / length))
        self._rising = False
        self._valley = (self._i, value)
        self._top = (None, -np.inf)
        self._valid = 1
        return rep
