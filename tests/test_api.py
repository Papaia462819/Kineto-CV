"""Serverul, cu un analizor fals: verifică drumul datelor, nu modelele (acelea au testele lor)."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

import src.api as api
from src.session import ExecutionResult


class FakeAnalyzer:
    score_error = 6.0

    def __init__(self, *_):
        self.calls = []

    def analyze(self, image_kp, world_kp, times, exercise, mirrored=False):
        self.calls.append((image_kp, world_kp, times, exercise, mirrored))
        return ExecutionResult(exercise, float(times[-1] - times[0]), 0.9, 2.0, 3, 80.0, 0.95, 41.5, 6.0, exercise,
                               0.9, [])


@pytest.fixture
def client(tmp_path, monkeypatch):
    fake = FakeAnalyzer()
    monkeypatch.setattr(api, "Analyzer", lambda *_: fake)
    app = api.create_app(db_path=tmp_path / "test.db", keypoints_dir=tmp_path / "sessions")
    with TestClient(app) as c:
        c.fake = fake
        c.tmp = tmp_path
        yield c


def add_patient(client):
    from src.storage import Storage
    storage = Storage(client.tmp / "test.db")
    pid = storage.add_patient("Test", 1970, "test", "Dr. Test")
    storage.set_plan(pid, 1, 10, 3)
    storage.close()
    return pid


def frame(t, present=True):
    values = list(np.linspace(0, 1, 132)) if present else None
    return {"t": t, "image": values, "world": values}


def test_health_and_exercises(client):
    assert client.get("/api/health").json()["ok"] is True
    assert [e["id"] for e in client.get("/api/exercises").json()] == [1, 2, 3, 4, 5]


def test_unknown_patient_is_404(client):
    assert client.get("/api/patients/99").status_code == 404


def test_upload_analyzes_and_stores_session(client):
    pid = add_patient(client)
    body = {"exercise": 1, "device": "test", "frames": [frame(0.0), frame(0.04, present=False), frame(0.08)]}
    session = client.post(f"/api/patients/{pid}/sessions", json=body).json()
    assert session["score"] == 41.5 and session["reps"] == 3 and session["warnings"] == []
    image_kp, _, times, exercise, mirrored = client.fake.calls[0]
    assert image_kp.shape == (3, 33, 4) and np.isnan(image_kp[1]).all() and not np.isnan(image_kp[0]).any()
    assert list(times) == [0.0, 0.04, 0.08] and exercise == 1 and mirrored is False
    assert (client.tmp / "sessions" / f"{session['id']}.npz").exists()
    assert client.get(f"/api/patients/{pid}/sessions").json()[0]["id"] == session["id"]


def test_bad_frames_are_rejected(client):
    pid = add_patient(client)
    short = {"exercise": 1, "frames": [{"t": 0.0, "image": [0.1] * 10, "world": [0.1] * 10}]}
    assert client.post(f"/api/patients/{pid}/sessions", json=short).status_code == 422
    backwards = {"exercise": 1, "frames": [frame(0.1), frame(0.0)]}
    assert client.post(f"/api/patients/{pid}/sessions", json=backwards).status_code == 422
    assert client.post(f"/api/patients/{pid}/sessions", json={"exercise": 7, "frames": []}).status_code == 422


def test_review_and_messages(client):
    pid = add_patient(client)
    session = client.post(f"/api/patients/{pid}/sessions", json={"exercise": 2, "frames": [frame(0), frame(1)]}).json()
    reviewed = client.post(f"/api/sessions/{session['id']}/review", json={"author": "Dr. Test", "text": "Bine"}).json()
    assert reviewed["review_text"] == "Bine"
    client.post(f"/api/patients/{pid}/messages", json={"author_role": "doctor", "author_name": "Dr", "text": "Salut"})
    messages = client.post(f"/api/patients/{pid}/messages",
                           json={"author_role": "patient", "author_name": "P", "text": "Mersi"}).json()
    assert [m["text"] for m in messages] == ["Salut", "Mersi"]
    assert client.post(f"/api/patients/{pid}/messages",
                       json={"author_role": "admin", "author_name": "x", "text": "y"}).status_code == 422
