"""Verifică punctele înainte de netezire: corectează laturile inversate și scoate cadrele aberante.

Aceeași clasă merge și live, cadru cu cadru, și pe înregistrări, prin clean_sequence.
Pragurile sunt alese pe subiecții de reglaj din KIMORE; vezi scripts/test_pipeline_kimore.py.
"""
from collections import deque

import numpy as np

OK, MISSING, LOW_VISIBILITY, UPSIDE_DOWN, BAD_BONES, BAD_TRUNK, JUMP = (
    "ok", "missing", "low_visibility", "upside_down", "bad_bones", "bad_trunk", "jump")

N_LANDMARKS = 33
ARMS = ([11, 13, 15, 17, 19, 21], [12, 14, 16, 18, 20, 22])
LEGS = ([23, 25, 27, 29, 31], [24, 26, 28, 30, 32])
FACE = ([1, 2, 3, 7, 9], [4, 5, 6, 8, 10])
SHOULDER_L, SHOULDER_R, HIP_L, HIP_R = 11, 12, 23, 24
CORE = [SHOULDER_L, SHOULDER_R, HIP_L, HIP_R]
BONES = [((11, 13), (12, 14)), ((13, 15), (14, 16)), ((23, 25), (24, 26)), ((25, 27), (26, 28))]
TRACKED = CORE + [13, 14, 15, 16, 25, 26, 27, 28]

MIN_VISIBILITY = 0.5
MAX_BONE_RATIO = 2.0  # de câte ori poate fi un os mai lung decât perechea lui
MAX_BONE_DEVIATION = 0.6  # abaterea unui os față de lungimea obișnuită, ca logaritm (0,6 ≈ de 1,8 ori)
MAX_TRUNK_DEVIATION = 0.5  # abaterea trunchiului din imagine față de mărimea obișnuită (0,5 ≈ de 1,65 ori)
MAX_IMAGE_SPEED = 3.0  # lățimi de imagine pe secundă
MIN_SIDE_GAP = 0.01  # sub această distanță în imagine, ordinea stânga/dreapta nu e sigură
REFERENCE_FRAMES = 150
MIN_REFERENCE_FRAMES = 15
REANCHOR_S = 1.0


def _swap(keypoints, group):
    left, right = group
    keypoints[left + right] = keypoints[right + left]


def _bone_lengths(world):
    pairs = np.array([p for bone in BONES for p in bone])
    return np.linalg.norm(world[pairs[:, 0], :3] - world[pairs[:, 1], :3], axis=1)


def _trunk_size(image):
    shoulders = image[[SHOULDER_L, SHOULDER_R], :2].mean(axis=0)
    hips = image[[HIP_L, HIP_R], :2].mean(axis=0)
    return float(np.linalg.norm(shoulders - hips))


class QualityChecker:
    """Primește câte un cadru și întoarce (image_kp, world_kp, stare).

    Un cadru respins vine înapoi plin de NaN. Laturile inversate sunt doar schimbate la loc.

    facing_camera: persoana stă cu fața la cameră, deci ordinea laturilor se vede din geometrie.
        Altfel, de exemplu cu camera laterală, laturile se decid după continuitatea cu cadrul anterior.
    mirrored: imaginea dată modelului e în oglindă, cum sunt videoclipurile KIMORE. În aplicație,
        modelul primește imaginea neoglindită; oglindirea e doar pentru afișare.
    upright: persoana stă în picioare, deci umerii trebuie să fie deasupra șoldurilor.
    reference: (lungimi de oase, mărimea trunchiului) cunoscute dinainte, de exemplu mediana clipului.
    """

    def __init__(self, fps=30.0, facing_camera=True, mirrored=False, upright=True, reference=None,
                 min_visibility=MIN_VISIBILITY, max_bone_ratio=MAX_BONE_RATIO,
                 max_bone_deviation=MAX_BONE_DEVIATION, max_trunk_deviation=MAX_TRUNK_DEVIATION,
                 max_image_speed=MAX_IMAGE_SPEED):
        self.fps = fps
        self.facing_camera = facing_camera
        self.mirrored = mirrored
        self.upright = upright
        self.min_visibility = min_visibility
        self.max_bone_ratio = max_bone_ratio
        self.max_bone_deviation = max_bone_deviation
        self.max_trunk_deviation = max_trunk_deviation
        self.max_image_speed = max_image_speed
        self.reanchor_frames = int(REANCHOR_S * fps)
        self.fixed_reference = reference
        self.swaps = 0
        self._bones = deque(maxlen=REFERENCE_FRAMES)
        self._trunks = deque(maxlen=REFERENCE_FRAMES)
        self._last = None  # ultimul cadru acceptat din imagine
        self._since_last = 0
        self._rejected_in_a_row = 0

    def _reference(self):
        if self.fixed_reference is not None:
            return self.fixed_reference
        if len(self._bones) < MIN_REFERENCE_FRAMES:
            return None
        return np.median(self._bones, axis=0), float(np.median(self._trunks))

    def _fix_group(self, image, world, group, left_index, right_index):
        wrong = False
        if self.facing_camera:
            gap = image[left_index, 0] - image[right_index, 0]
            gap = -gap if self.mirrored else gap
            wrong = gap < -MIN_SIDE_GAP
        elif self._last is not None:
            left, right = group
            same = np.nansum(np.linalg.norm(image[left + right, :2] - self._last[left + right, :2], axis=1))
            crossed = np.nansum(np.linalg.norm(image[left + right, :2] - self._last[right + left, :2], axis=1))
            wrong = crossed < 0.5 * same
        if wrong:
            _swap(image, group)
            _swap(world, group)
        return wrong

    def _fix_sides(self, image, world):
        arms = self._fix_group(image, world, ARMS, SHOULDER_L, SHOULDER_R)
        legs = self._fix_group(image, world, LEGS, HIP_L, HIP_R)
        if arms:
            _swap(image, FACE)
            _swap(world, FACE)
        self.swaps += int(arms or legs)

    def _judge(self, image, world):
        if np.nanmin(world[CORE, 3]) < self.min_visibility:
            return LOW_VISIBILITY
        if self.upright and image[[SHOULDER_L, SHOULDER_R], 1].mean() >= image[[HIP_L, HIP_R], 1].mean():
            return UPSIDE_DOWN  # y crește în jos în imagine
        lengths = _bone_lengths(world)
        for k in range(len(BONES)):
            left, right = lengths[2 * k], lengths[2 * k + 1]
            if max(left, right) > self.max_bone_ratio * min(left, right):
                return BAD_BONES
        reference = self._reference()
        if reference is not None:
            bones, trunk = reference
            if np.max(np.abs(np.log(lengths / bones))) > self.max_bone_deviation:
                return BAD_BONES
            if abs(np.log(_trunk_size(image) / trunk)) > self.max_trunk_deviation:
                return BAD_TRUNK
        if self._last is not None:
            moved = np.linalg.norm(image[TRACKED, :2] - self._last[TRACKED, :2], axis=1).max()
            if moved * self.fps / self._since_last > self.max_image_speed:
                return JUMP
        return OK

    def update(self, image_kp, world_kp):
        self._since_last += 1
        image, world = np.array(image_kp, dtype=float), np.array(world_kp, dtype=float)
        if np.isnan(world[CORE, :3]).any() or np.isnan(image[CORE, :2]).any():
            return np.full_like(image, np.nan), np.full_like(world, np.nan), MISSING

        self._fix_sides(image, world)
        status = self._judge(image, world)
        if status in (JUMP, BAD_TRUNK) or (status == BAD_BONES and self.fixed_reference is None):
            # Dacă se respinge totul o secundă întreagă, poate s-a schimbat ceva real, nu cadrul e greșit:
            # persoana s-a apropiat sau s-a mutat. Repornim referința ca să nu respingem la nesfârșit.
            self._rejected_in_a_row += 1
            if self._rejected_in_a_row >= self.reanchor_frames and self.fixed_reference is None:
                self._bones.clear()
                self._trunks.clear()
                self._last = None
                status = self._judge(image, world)
        elif status == OK:
            self._rejected_in_a_row = 0
        if status != OK:
            return np.full_like(image, np.nan), np.full_like(world, np.nan), status

        self._rejected_in_a_row = 0
        self._bones.append(_bone_lengths(world))
        self._trunks.append(_trunk_size(image))
        self._last = image
        self._since_last = 0
        return image, world, OK


def clip_reference(image_kp, world_kp, upright=True):
    """Mediana clipului: lungimile oaselor și mărimea trunchiului, pentru verificarea offline."""
    present = ~np.isnan(world_kp[:, CORE, :3]).any(axis=(1, 2))
    if upright:
        # Scheletele răsturnate nu au voie să strice referința.
        with np.errstate(invalid="ignore"):
            present &= image_kp[:, [SHOULDER_L, SHOULDER_R], 1].mean(axis=1) < image_kp[:, [HIP_L, HIP_R], 1].mean(axis=1)
    if not present.any():
        return None
    pairs = np.array([p for bone in BONES for p in bone])
    lengths = np.linalg.norm(world_kp[present][:, pairs[:, 0], :3] - world_kp[present][:, pairs[:, 1], :3], axis=2)
    shoulders = image_kp[present][:, [SHOULDER_L, SHOULDER_R], :2].mean(axis=1)
    hips = image_kp[present][:, [HIP_L, HIP_R], :2].mean(axis=1)
    return np.median(lengths, axis=0), float(np.median(np.linalg.norm(shoulders - hips, axis=1)))


def clean_sequence(image_kp, world_kp, fps=30.0, **options):
    """Verifică un clip întreg. Întoarce (image_kp, world_kp, stări, câte cadre au avut laturile corectate)."""
    reference = clip_reference(image_kp, world_kp, options.get("upright", True))
    checker = QualityChecker(fps=fps, reference=reference, **options)
    results = [checker.update(i, w) for i, w in zip(image_kp, world_kp)]
    images, worlds, status = zip(*results) if results else ([], [], [])
    return np.array(images), np.array(worlds), np.array(status), checker.swaps
