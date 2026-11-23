"""Serverul aplicației (FastAPI): telefonul trimite punctele, serverul face analiza și păstrează datele.

Telefonul rulează MediaPipe și partea live. La finalul unei execuții trimite punctele brute și timpii;
serverul rulează exact lanțul din antrenare (src/session.py: Analyzer) și salvează sesiunea.

Endpoint-uri (toate sub /api):
    GET  /health                          serverul merge și modelele sunt încărcate
    GET  /exercises                       lista exercițiilor
    GET  /patients/{id}                   datele pacientului și planul de exerciții
    GET  /patients/{id}/sessions          sesiunile trecute, cele mai noi primele
    POST /patients/{id}/sessions          o înregistrare nouă → analiză → sesiunea salvată
    GET  /sessions/{id}                   o sesiune
    POST /sessions/{id}/review            recenzia medicului (pentru aplicația medicului, mai târziu)
    GET  /patients/{id}/messages          notițele și mesajele dintre medic și pacient
    POST /patients/{id}/messages          un mesaj nou

Prototip pentru rețeaua locală: fără autentificare și fără HTTPS. Înainte de date reale trebuie adăugate amândouă.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.session import Analyzer
from src.storage import ROOT, Storage

KEYPOINTS_DIR = ROOT / "data" / "sessions"
VALUES_PER_FRAME = 33 * 4  # 33 de puncte × (x, y, z, vizibilitate)
EXERCISES = [
    {"id": 1, "name": "Ridicarea brațelor", "description": "Brațele întinse urcă prin față deasupra capului și coboară."},
    {"id": 2, "name": "Înclinări laterale", "description": "Cu brațele sus, trunchiul se înclină spre stânga și spre dreapta."},
    {"id": 3, "name": "Rotația trunchiului", "description": "Cu bastonul ținut în față, la nivelul umerilor, trunchiul se rotește stânga-dreapta."},
    {"id": 4, "name": "Rotația pelvisului", "description": "Cu mâinile pe șolduri, pelvisul se rotește în plan orizontal."},
    {"id": 5, "name": "Genuflexiuni", "description": "Cu bastonul ținut în față, cobori în genuflexiune și urci."},
]


class Frame(BaseModel):
    t: float  # secunde de la începutul înregistrării
    image: list[float] | None = None  # 132 de valori: punctele din imagine (x, y în 0–1, z, vizibilitate)
    world: list[float] | None = None  # 132 de valori: punctele în metri, față de mijlocul șoldurilor


class Recording(BaseModel):
    exercise: int = Field(ge=1, le=5)
    mirrored: bool = False  # imaginea dată lui MediaPipe era în oglindă
    device: str | None = None
    feedback: dict[str, int] = {}  # mesajele de corectare spuse live, cu de câte ori (src/feedback.py)
    frames: list[Frame]


class Review(BaseModel):
    author: str
    text: str


class Message(BaseModel):
    author_role: Literal["doctor", "patient"]
    author_name: str
    text: str = Field(min_length=1)
    session_id: int | None = None


def recording_arrays(recording):
    """Lista de cadre → (image_kp, world_kp, timpi). Un cadru fără persoană devine NaN, ca în Python."""
    count = len(recording.frames)
    image = np.full((count, VALUES_PER_FRAME), np.nan, dtype=np.float32)
    world = np.full((count, VALUES_PER_FRAME), np.nan, dtype=np.float32)
    times = np.array([f.t for f in recording.frames], dtype=float)
    for k, frame in enumerate(recording.frames):
        if frame.image is None or frame.world is None:
            continue
        if len(frame.image) != VALUES_PER_FRAME or len(frame.world) != VALUES_PER_FRAME:
            raise HTTPException(422, f"cadrul {k}: astept {VALUES_PER_FRAME} de valori pentru image si world")
        image[k], world[k] = frame.image, frame.world
    if count > 1 and np.any(np.diff(times) <= 0):
        raise HTTPException(422, "timpii cadrelor trebuie sa creasca")
    return image.reshape(count, 33, 4), world.reshape(count, 33, 4), times


def create_app(db_path=None, models_dir=None, keypoints_dir=KEYPOINTS_DIR):
    state = {}

    @asynccontextmanager
    async def lifespan(_):
        # Modelele și baza de date se deschid o dată, la pornirea serverului.
        state["storage"] = Storage(db_path) if db_path else Storage()
        state["analyzer"] = Analyzer(models_dir) if models_dir else Analyzer()
        yield
        state["storage"].close()

    app = FastAPI(title="Kineto-CV", lifespan=lifespan)

    def storage():
        return state["storage"]

    def existing_patient(patient_id):
        patient = storage().patient(patient_id)
        if patient is None:
            raise HTTPException(404, "pacient inexistent")
        return patient

    @app.get("/api/health")
    def health():
        return {"ok": True, "models": "analyzer" in state, "score_error": state["analyzer"].score_error}

    @app.get("/api/exercises")
    def exercises():
        return EXERCISES

    @app.get("/api/patients/{patient_id}")
    def patient(patient_id: int):
        return existing_patient(patient_id)

    @app.get("/api/patients/{patient_id}/sessions")
    def sessions(patient_id: int):
        existing_patient(patient_id)
        return storage().sessions(patient_id)

    # `def`, nu `async def`: analiza ține procesorul ~1 s, iar FastAPI rulează funcțiile simple pe alt fir,
    # deci serverul răspunde între timp și altor cereri.
    @app.post("/api/patients/{patient_id}/sessions")
    def add_session(patient_id: int, recording: Recording):
        existing_patient(patient_id)
        image_kp, world_kp, times = recording_arrays(recording)
        result = state["analyzer"].analyze(image_kp, world_kp, times, recording.exercise, recording.mirrored)
        result.feedback = recording.feedback
        session_id = storage().add_session(patient_id, result.to_dict(), recording.device)
        path = Path(keypoints_dir) / f"{session_id}.npz"
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, image_kp=image_kp, world_kp=world_kp, times=times, exercise=recording.exercise,
                            mirrored=recording.mirrored)
        storage().set_keypoints_path(session_id, path)
        return storage().session(session_id)

    @app.get("/api/sessions/{session_id}")
    def session(session_id: int):
        found = storage().session(session_id)
        if found is None:
            raise HTTPException(404, "sesiune inexistenta")
        return found

    @app.post("/api/sessions/{session_id}/review")
    def review(session_id: int, body: Review):
        session(session_id)
        storage().review_session(session_id, body.author, body.text)
        return storage().session(session_id)

    @app.get("/api/patients/{patient_id}/messages")
    def messages(patient_id: int):
        existing_patient(patient_id)
        return storage().messages(patient_id)

    @app.post("/api/patients/{patient_id}/messages")
    def add_message(patient_id: int, body: Message):
        existing_patient(patient_id)
        storage().add_message(patient_id, body.author_role, body.author_name, body.text, body.session_id)
        return storage().messages(patient_id)

    return app
