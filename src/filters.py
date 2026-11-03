"""Netezirea punctelor: Savitzky-Golay pentru înregistrări, One Euro pentru aplicația live.

Filtrele reduc tremuratul mic. Cadrele complet greșite trebuie scoase înainte, de quality.py.
"""
import numpy as np
from scipy.signal import savgol_filter

DEFAULT_WINDOW = 15
DEFAULT_POLYORDER = 3
MAX_GAP = 15  # cadre; la 30 fps, o jumătate de secundă


def fill_gaps(x, max_gap=MAX_GAP):
    """Completează liniar golurile scurte dintre valori. Golurile lungi și capetele rămân NaN."""
    x = np.array(x, dtype=float)
    missing = np.isnan(x)
    if missing.all() or not missing.any():
        return x
    known = np.flatnonzero(~missing)
    for left, right in zip(known[:-1], known[1:]):
        if 1 < right - left <= max_gap + 1:
            x[left:right + 1] = np.linspace(x[left], x[right], right - left + 1)
    return x


def _runs(valid):
    """Întoarce (început, sfârșit) pentru fiecare secvență continuă de valori True."""
    edges = np.flatnonzero(np.diff(np.concatenate([[False], valid, [False]]).astype(int)))
    return zip(edges[::2], edges[1::2])


def savgol(x, window=DEFAULT_WINDOW, polyorder=DEFAULT_POLYORDER, max_gap=MAX_GAP):
    """Netezește o curbă pe bucăți continue, ca să nu amestece date de o parte și de alta a unui gol lung.

    O bucată mai scurtă decât fereastra rămâne nenetezită, pentru că filtrul nu are destule puncte.
    """
    x = fill_gaps(x, max_gap)
    for start, end in _runs(~np.isnan(x)):
        if end - start >= window:
            x[start:end] = savgol_filter(x[start:end], window, polyorder)
    return x


def smooth_keypoints(keypoints, window=DEFAULT_WINDOW, polyorder=DEFAULT_POLYORDER, max_gap=MAX_GAP):
    """Aplică Savitzky-Golay pe fiecare coordonată a fiecărui punct (cadre × puncte × 4).

    Coloana de vizibilitate nu e o poziție, deci nu se netezește.
    """
    smoothed = np.array(keypoints, dtype=float)
    for point in range(smoothed.shape[1]):
        for axis in range(3):
            smoothed[:, point, axis] = savgol(smoothed[:, point, axis], window, polyorder, max_gap)
    return smoothed


class OneEuroFilter:
    """Filtru live: netezește mult când punctul stă și puțin când se mișcă repede.

    min_cutoff: mai mic = mai neted în repaus. beta: mai mare = întârziere mai mică în mișcare.
    Valorile implicite sunt reglate pe world_kp din KIMORE, în metri: la 30 fps, tremuratul scade
    cam la jumătate, iar întârzierea e de aproximativ 2 cadre.
    Primește una sau mai multe valori deodată, de exemplu toată matricea de puncte a unui cadru.
    """

    def __init__(self, min_cutoff=1.0, beta=0.5, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self):
        self._x = None
        self._dx = None
        self._t = None

    @staticmethod
    def _alpha(cutoff, dt):
        return 1.0 / (1.0 + 1.0 / (2.0 * np.pi * cutoff * dt))

    def __call__(self, x, t):
        """x este valoarea la momentul t, în secunde. Un cadru lipsă repornește filtrul."""
        x = np.asarray(x, dtype=float)
        if np.isnan(x).any():
            self.reset()
            return x.copy()
        if self._x is None:
            self._x, self._dx, self._t = x.copy(), np.zeros_like(x), t
            return x.copy()
        dt = t - self._t
        if dt <= 0:
            raise ValueError("Timpul trebuie să crească de la un cadru la altul")
        dx = (x - self._x) / dt
        self._dx = self._dx + self._alpha(self.d_cutoff, dt) * (dx - self._dx)
        cutoff = self.min_cutoff + self.beta * np.abs(self._dx)
        self._x = self._x + self._alpha(cutoff, dt) * (x - self._x)
        self._t = t
        return self._x.copy()
