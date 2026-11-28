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
| `src/session.py` | o execuție în aplicație: urmărirea live și analiza de la final, cu scorul |
| `scripts/app.py` | aplicația pe laptop: camera sau video, repetările live, scorul la final |
| `src/feedback.py` | feedback-ul live: reguli pe unghiuri și poziții (regulile și pragurile: `config/feedback.json`) |
| `src/storage.py` | baza de date SQLite: pacienți, plan, sesiuni, recenziile medicului, mesaje |
| `src/api.py` | serverul pentru telefon (FastAPI): primește punctele, rulează analiza, păstrează datele |
| `android/` | aplicația Android (Kotlin): MediaPipe și partea live pe telefon, scorul de la server |

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
python scripts/app.py --camera 0 --exercise 1             # aplicația: SPAȚIU start/stop, apoi scorul
python scripts/app.py --video clip.mp4 --exercise 1 --mirrored   # pe un video (KIMORE e în oglindă)
```

## Telefon + server

```
telefon (Kotlin): camera → MediaPipe → repetări live ──puncte brute──► laptop (Python): src/session.py → scor
```

Pe laptop:

```
python scripts/seed_demo.py --reset           # o dată: baza de date cu un pacient demo
python scripts/run_server.py                  # afișează adresa de pus în aplicație
```

Pe telefon: deschide folderul `android/` în Android Studio și rulează aplicația (modelul MediaPipe se copiază
automat din `models/`). În aplicație, la Profil → Avansat → Conexiunea cu serverul, pune adresa afișată de server
și apasă „Testează conexiunea”. Telefonul și laptopul trebuie să fie în aceeași rețea Wi-Fi; prima dată, Windows
întreabă dacă Python are voie în rețea: „Rețele private”. Pe emulatorul din Android Studio merge și adresa
`http://10.0.2.2:8000` (emulatorul vede laptopul la această adresă).

Prototip: fără autentificare și fără HTTPS, doar pentru rețeaua de acasă și date demonstrative.

Pașii pe KIMORE, în ordine (datele se pun în `data/kimore/`):

```
python scripts/build_kimore_index.py          # indexul execuțiilor și al scorurilor
python scripts/extract_keypoints.py ...       # punctele MediaPipe din videoclipuri
python scripts/test_pipeline_kimore.py        # test: repetări și unghiuri față de Kinect
python scripts/build_execution_features.py    # tabelele pentru recunoașterea exercițiului
python scripts/train_exercise_classifier.py
python scripts/build_score_features.py        # tabelele pentru scorul clinic
python scripts/train_clinical_score.py
python scripts/calibrate_feedback.py          # pragurile regulilor de feedback live → config/feedback.json
python scripts/export_android_fixtures.py     # datele pentru testele Kotlin (după orice schimbare în codul live)
```

## Date

Folderele `data/` și `models/` nu sunt în git. Dataset-ul KIMORE are licența lui și se descarcă separat.
