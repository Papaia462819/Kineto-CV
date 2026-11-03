"""Rulează MediaPipe Pose Landmarker pe câte un cadru și întoarce punctele ca matrice NumPy."""
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode

DEFAULT_MODEL = Path(__file__).resolve().parents[1] / "models" / "pose_landmarker_full.task"
N_LANDMARKS = 33

L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28


def _to_array(landmarks):
    return np.array([[p.x, p.y, p.z, p.visibility] for p in landmarks], dtype=np.float32)


class PoseEstimator:
    """Modelul se încarcă o singură dată; în modul VIDEO urmărește persoana de la un cadru la altul."""

    def __init__(self, model_path=DEFAULT_MODEL):
        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=RunningMode.VIDEO,
        )
        self._landmarker = PoseLandmarker.create_from_options(options)

    def process(self, frame_bgr, timestamp_ms):
        """Întoarce (image_kp, world_kp), matrice 33 × 4 (x, y, z, vizibilitate).

        Dacă nu e nicio persoană în cadru, matricele sunt pline de NaN.
        timestamp_ms trebuie să crească de la un cadru la altul.
        """
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)  # OpenCV citește BGR, MediaPipe vrea RGB
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, int(timestamp_ms))
        if not result.pose_landmarks:
            empty = np.full((N_LANDMARKS, 4), np.nan, dtype=np.float32)
            return empty, empty.copy()
        return _to_array(result.pose_landmarks[0]), _to_array(result.pose_world_landmarks[0])

    def close(self):
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
