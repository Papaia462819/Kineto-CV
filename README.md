# Kineto-CV

Evaluarea exercițiilor de kinetoterapie cu o cameră obișnuită: proiect de master în telemedicină.

Din video, aplicația găsește punctele corpului (MediaPipe), le verifică și le netezește, calculează unghiurile,
numără repetările și estimează scorul clinic al exercițiului (0–50, ca în dataset-ul KIMORE).

## Cum funcționează

```
camera / video → MediaPipe (33 de puncte) → verificare → netezire → unghiuri → repetări
                                                                         └→ rezumat → scor clinic
```

| Fișier | Ce face |
|---|---|
| `src/pose.py` | rulează MediaPipe pe un cadru |
| `src/quality.py` | respinge cadrele aberante (schelet răsturnat, oase deformate, salturi) și corectează stânga/dreapta |
| `src/filters.py` | netezire: Savitzky–Golay (offline) și One Euro (live) |
| `src/features.py` | unghiurile articulațiilor, cadru cu cadru |
| `src/reps.py` | găsirea repetărilor (offline și live) |
| `src/execution_features.py` | rezumatul unei execuții: statistici pe unghiuri (A) și pe repetări (B) |
| `src/clinical_features.py` | mărimile clinicienilor KIMORE, traduse din MATLAB (C) |
| `src/clinical_score.py` | modelul de scor clinic |

## Rezultate pe KIMORE (validare pe persoane nevăzute)

- Numărarea repetărilor: eroare medie de 1,6 repetări; pe filmările bune, 61% exact și 88% cu cel mult o repetare diferență.
- Recunoașterea exercițiului: 94% cu MediaPipe, 97% cu Kinect.
- Scorul clinic (0–50): eroare medie de 6,0 puncte cu MediaPipe, 5,2 cu Kinect; ghicitul mediei greșește cu 8,1.

## Instalare

Ai nevoie de Python 3.13.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Modelul MediaPipe (`pose_landmarker_full.task`) se descarcă de pe site-ul MediaPipe și se pune în `models/`.

## Rulare

```
python -m pytest                              # testele
python scripts/webcam_test.py --list          # camerele disponibile
python scripts/webcam_test.py --camera 0 --exercise 1
```

Pașii pe KIMORE, în ordine (datele se pun în `data/kimore/`):

```
python scripts/build_kimore_index.py          # indexul execuțiilor și al scorurilor
python scripts/extract_keypoints.py ...       # punctele MediaPipe din videoclipuri
python scripts/test_pipeline_kimore.py        # test: repetări și unghiuri față de Kinect
python scripts/build_execution_features.py    # tabelele pentru recunoașterea exercițiului
python scripts/train_exercise_classifier.py
python scripts/build_score_features.py        # tabelele pentru scorul clinic
python scripts/train_clinical_score.py
```

## Date

Folderele `data/` și `models/` nu sunt în git. Dataset-ul KIMORE are licența lui și se descarcă separat.
