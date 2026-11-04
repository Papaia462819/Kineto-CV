"""Citește scheletul Kinect v2 din fișierele JointPosition*.csv ale KIMORE."""
from pathlib import Path

import numpy as np

N_JOINTS = 25


def load_kinect(path):
    """Întoarce cadre × 25 × 3 (x, y, z în metri). Rândurile goale (persoană nedetectată) devin NaN."""
    frames = []
    previous = None
    for line in Path(path).read_text(errors="replace").split("\n"):
        values = [v for v in line.strip().split(",") if v]
        if not values:
            frames.append(np.full((N_JOINTS, 3), np.nan))
            continue
        # Uneori Kinect vede mai multe corpuri pe același rând; păstrăm corpul cel mai apropiat de cadrul anterior.
        bodies = np.array(values, dtype=float).reshape(-1, N_JOINTS, 4)[:, :, :3]
        reference = previous if previous is not None else np.zeros(3)
        body = bodies[np.argmin(np.linalg.norm(bodies[:, 0] - reference, axis=1))]
        previous = body[0]
        frames.append(body)
    while frames and np.isnan(frames[-1]).all():
        frames.pop()
    return np.stack(frames) if frames else np.empty((0, N_JOINTS, 3))
