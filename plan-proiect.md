# Plan proiect – Evaluarea exercițiilor de kinetoterapie cu camera

Plan scris pe 4 octombrie 2026. Termen de predare: 20 decembrie 2026.

## Stare actuală (1 noiembrie 2026)

- Mediul real: Python 3.13 și MediaPipe 1.0.1 într-un `.venv`, merg. Planul de mai jos zice Python 3.11; rămâi pe 3.13 cât timp merge.
- Repo-ul real e `C:\Kineto-CV` (în plan apare ca `rehab-cv/`).
- Scripturile de pornire: `src/pose.py` (MediaPipe Tasks, mod VIDEO, întoarce `image_kp` și `world_kp`, matrice 33 × 4), `scripts/webcam_test.py`, `scripts/extract_keypoints.py` (salvează `.npz` în `data/keypoints/`).
- KIMORE descărcat fără RGB; RGB-ul se primește după semnarea EULA. KERAAL, grupurile 1A și 2A, descărcat.
- Corectură: ridicarea brațelor prin față și adâncimea genuflexiunii depind de z, deci precizia cu camera frontală e medie, nu „bine”. Decizia (cameră frontală, laterală sau la 45°) se ia după experimentul E1.

## Rezumat

Construiești un sistem care urmărește cu o cameră obișnuită exercițiile de kinetoterapie, dă feedback live pe fiecare repetare și arată progresul de la o sesiune la alta. Predarea e pe 20 decembrie, iar 21–23 decembrie rămân buffer.

Ce predai la final:

- **Aplicația live:** camera, scheletul desenat, contorul de repetări și mesaje de corectare.
- **Dashboard-ul de progres:** grafice pe sesiuni, cu pragul de la care o schimbare e progres real.
- **Raportul:** precizia unghiurilor, detecția greșelilor, repetabilitatea și acordul cu scorurile clinicienilor.
- **Video demo și prezentarea.**

Ordinea e aleasă ca partea riscantă, aplicația live, să meargă devreme: primul demo e pe 8 noiembrie. Din 29 noiembrie nu mai intră funcții noi, doar experimente și raport.

## Ce îți trebuie

Echipamentul e ieftin; cel mai greu de obținut sunt voluntarii.

| Ce | La ce folosește | Observații |
| --- | --- | --- |
| Laptop cu webcam | Rulează tot sistemul | MediaPipe merge în timp real pe CPU; pentru antrenări mai mari ai Google Colab |
| Telefon + trepied | Camera fixă, imagine mai bună decât webcam-ul | Îl folosești ca webcam (DroidCam, Camo) sau filmezi direct pe el |
| Goniometru | Adevărul de referință pentru unghiurile brațelor și genunchilor | Unul de plastic e suficient |
| Aplicația phyphox pe un telefon | Adevărul de referință pentru înclinarea și rotația trunchiului (giroscop) | Doar pentru validare (E1), nu în produsul final |
| Bandă adezivă + ruletă | Marcaje pe podea pentru trepied și pentru picioarele persoanei | Esențial pentru ca sesiunile să fie comparabile |
| Spațiu de ~3 × 3 m | Tot corpul în cadru | Fundal simplu, lumină difuză, haine mulate |

**Oameni:**

- **3–5 voluntari** pentru filmarea din 16–22 noiembrie, cam 1,5 ore fiecare.
- **Opțional, un kinetoterapeut pentru o oră:** validează lista de greșeli per exercițiu și, ideal, notează câteva înregistrări.

**Ce să recapitulezi:** unghiul dintre doi vectori (produs scalar, arccos), filtre de netezire, detecția vârfurilor, o rețea GRU în PyTorch (doar pentru comparații), DTW, corelație Spearman, MAE, precizie și recall, ICC.

## Setup mediu de lucru

1. Python și Git instalate.
2. Mediul virtual și pachetele:

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   Linux/macOS: source .venv/bin/activate
pip install mediapipe opencv-python numpy scipy pandas scikit-learn matplotlib plotly streamlit pyyaml dtaidistance pingouin jupyter
# torch se instalează separat, doar când e nevoie de GRU
```

3. Modelul Pose Landmarker în `models/`:

```bash
curl.exe -L -o models\pose_landmarker_full.task https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task
```

4. Scripturile de verificare: `scripts/webcam_test.py` (camera, scheletul, FPS-ul) și `scripts/extract_keypoints.py` (video în `.npz`). Dacă modelul full e prea lent live, treci pe lite doar pentru aplicație.
5. `data/`, `models/*.task` și `.venv/` în `.gitignore`: videoclipurile cu oameni și dataset-urile nu ajung pe GitHub.

| Pachet | Rol |
| --- | --- |
| mediapipe | Detectarea scheletului (33 de puncte 3D) |
| opencv-python | Camera, citirea video, desenarea pe ecran |
| scipy | Filtre de netezire, detecția vârfurilor |
| scikit-learn | Modele simple, validare încrucișată |
| torch | GRU pentru comparații |
| dtaidistance | DTW |
| pingouin | ICC pentru repetabilitate |
| streamlit + plotly | Dashboard-ul de progres |

Structura repo-ului:

```text
Kineto-CV/
├── configs/exercises.yaml   # praguri și mesaje per exercițiu
├── data/                    # nu intră în git
│   ├── kimore/  keraal/
│   ├── raw/                 # videoclipurile tale
│   └── keypoints/           # fișierele .npz extrase
├── models/                  # modelul MediaPipe, modelele antrenate
├── src/
│   ├── capture.py           # cameră sau fișier video, aceeași interfață
│   ├── pose.py              # MediaPipe -> puncte 3D
│   ├── filters.py           # One Euro, Savitzky-Golay
│   ├── features.py          # unghiuri, simetrie, viteze
│   ├── reps.py              # segmentarea în repetări
│   ├── rules.py             # verificările de formă
│   ├── reference.py         # comparația DTW
│   ├── learned/             # recunoaștere exercițiu, scor învățat
│   ├── storage.py           # SQLite
│   └── app.py               # aplicația live
├── dashboard/app.py         # Streamlit
├── scripts/                 # extragere, experimente
├── notebooks/
└── reports/figures/
```

**Regula de bază:** același cod procesează video înregistrat și camera live. Așa evaluezi totul pe înregistrări și faci demo-ul live fără cod separat.

Dezvoltarea și antrenarea se fac pe PC; laptopul doar rulează aplicația pentru prezentare (git + același `requirements.txt`, căi relative cu `pathlib`, indexul camerei în config).

## Datele

Lucrezi pe cele 5 exerciții din KIMORE, ca să ai scoruri clinice reale pe care să validezi sistemul. Înregistrările tale dau adevărul de referință, voluntarii dau generalizarea, iar KERAAL aduce pacienți reali.

### Dataset-uri publice

| Dataset | Ce conține | Cum îl folosești | Acces |
| --- | --- | --- | --- |
| [KIMORE](https://vrai.dii.univpm.it/content/kimore-dataset) | 78 de subiecți (44 sănătoși, 34 cu disfuncții motorii), 5 exerciții pentru dureri lombare, Kinect v2 (depth, schelet; RGB la cerere), caracteristici definite de medici și un scor clinic 0–50 per execuție, ~70 de execuții per exercițiu | Scorul învățat, separarea sănătos/pacient, punctul de plecare pentru praguri | Google Drive (folderele CG și GPP; fiecare execuție are `Raw`, `Label`, `Script`). RGB după EULA semnat |
| [KERAAL](https://keraal.enstb.org/KeraalDataset.html) | 12 pacienți și 9 sănătoși, 3 exerciții (ascunderea feței, întinderea flancului, rotația trunchiului), video RGB anonimizat, schelet Kinect și BlazePose (același model ca MediaPipe), greșeli adnotate de medic cu partea corpului și intervalul de timp | Progres pe pacienți reali: grupul 1A are înregistrări de la începutul și din a doua jumătate a programului. Plus test extern pentru greșeli | CC BY-NC-SA; grupurile 1A și 2A |
| [UI-PRMD](https://pmc.ncbi.nlm.nih.gov/articles/PMC5773117/) | 10 subiecți sănătoși, 10 exerciții, execuții corecte și incorecte, Vicon + Kinect | Rezervă | Download direct |

În KIMORE, toate repetările unei persoane au același scor clinic, deci scorul învățat se face pe execuție, nu pe repetare.

### Exercițiile

| Exercițiu | Unghiul principal (pentru progres) | Greșeli verificate | Cât de bine se măsoară frontal |
| --- | --- | --- | --- |
| 1. Ridicarea brațelor | Flexia umărului, stânga și dreapta | Coate îndoite, asimetrie, aplecarea trunchiului | Bine dacă brațele urcă lateral; medie dacă urcă prin față |
| 2. Înclinarea laterală a trunchiului cu brațele întinse | Flexia laterală a trunchiului | Brațe neîntinse, aplecare în față, bazinul se deplasează | Bine |
| 3. Rotația trunchiului | Rotația liniei umerilor față de bazin | Bazinul se rotește odată cu trunchiul, aplecare | Medie: depinde de adâncimea estimată |
| 4. Rotația bazinului în plan transversal | Rotația liniei șoldurilor | Trunchiul se mișcă odată cu bazinul | Slab: doar scor învățat, trecut la limitări |
| 5. Genuflexiune | Flexia genunchiului și a șoldului | Adâncime insuficientă, trunchi prea aplecat, genunchi spre interior | Medie pentru adâncime (depinde de z), bine pentru genunchii spre interior |

Greșelile din tabel sunt punctul de plecare; le confirmi cu caracteristicile definite de medici în articolul KIMORE (folderul `Script`) și, dacă îl ai, cu kinetoterapeutul.

### Protocolul de filmare

- Telefonul pe trepied la ~1 m înălțime și 2,5–3 m distanță, frontal (ca în KIMORE), tot corpul în cadru.
- Același telefon, aceeași rezoluție, același fps și aceeași orientare la toate sesiunile; fără wide/ultra-wide, filtre sau încadrare automată.
- Marcaje cu bandă pe podea pentru trepied și picioare; aceeași poziție la fiecare sesiune.
- 1080p sau 720p la 30 fps, lumină difuză, fundal simplu, haine mulate.
- **Etichete prin design:** fiecare clip conține o singură condiție și numele fișierului o spune, de exemplu `p02_ex5_err-depth_t1.mp4`.
- Un CSV cu persoana, exercițiul, condiția, unghiul de referință și observații.

### Sesiunea 1: tu (19–25 octombrie)

- 10 repetări corecte per exercițiu: referința pentru DTW și pentru praguri.
- 10 repetări pentru fiecare greșeală din tabel.
- Poziții statice măsurate: brațul la 30°, 60°, 90°, 120° și 150° și genunchiul la 4–5 unghiuri, cu goniometrul; trunchiul înclinat și rotit, cu telefonul pe piept și phyphox.

### Sesiunea 2: voluntari (16–22 noiembrie)

Pentru fiecare persoană, cam 1,5 ore:

- Execuții corecte și cu greșeli, ca la sesiunea 1, 5–10 repetări fiecare.
- **Repetabilitate:** același set de 3 ori, cu trepiedul mutat și pus înapoi între seturi.
- **Recuperare simulată:** exercițiul la 25%, 50%, 75% și 100% din amplitudinea maximă, tratate ca 4 sesiuni. Plus o variantă cu compensare, de exemplu aplecarea trunchiului ca să „câștige” amplitudine.

### Acordul voluntarilor

Un formular de o pagină, semnat înainte de filmare: scopul (proiect de master), ce se filmează, că datele stau local, că fețele sunt blurate în raport și în demo și că se pot retrage oricând.

## Arhitectura sistemului

Un singur pipeline duce de la cameră la dashboard: fiecare repetare e măsurată o dată și folosită de două ori, pentru feedback live și pentru progres.

```text
Cameră -> Pose (MediaPipe, 33 de puncte 3D) -> Netezire + unghiuri -> Recunoaștere exercițiu
       -> Segmentare în repetări (vârfurile unghiului principal)
       -> Măsurători | Reguli de formă | Comparație DTW | Scor învățat (KIMORE)
       -> Feedback live (schelet, contor, mesaje)
       -> Stocare sesiune (SQLite) -> Dashboard progres (grafice pe sesiuni, cu pragul MDC)
```

Deciziile pe module:

- **Pose:** folosești coordonatele 3D „world” ale MediaPipe (în metri, centrate pe bazin), nu pe cele din imagine; depind mai puțin de distanța și unghiul camerei.
- **Netezire:** filtrul One Euro live, pentru că reduce tremuratul fără întârziere mare; Savitzky–Golay offline.
- **Unghiuri:** unghiul dintre două segmente prin produs scalar, de exemplu umăr–cot față de umăr–șold la ridicarea brațelor.
- **Recunoaștere:** întâi Random Forest pe ferestre de unghiuri, GRU doar dacă nu ajunge. În aplicație, pacientul alege exercițiul din plan, iar recunoașterea confirmă că face exercițiul corect.
- **Segmentare:** unghiul principal netezit, cu `scipy.signal.find_peaks` (prag de proeminență și distanță minimă între vârfuri).
- **Măsurători:** amplitudinea, diferența stânga/dreapta, durata de urcare și coborâre, netezimea (jerk normalizat).
- **Reguli:** praguri în `configs/exercises.yaml`, fiecare cu mesajul ei. Pornești de la caracteristicile definite de medici în KIMORE și le calibrezi pe repetările tale corecte (de exemplu media minus 2 abateri standard). Feedback-ul apare la finalul fiecărei repetări, ca să nu clipească.
- **DTW:** distanța dintre curba unghiurilor și referință, plus momentul în care repetarea deviază cel mai tare.
- **Scor învățat:** aceleași măsurători, agregate pe execuție, intră într-un model simplu (ridge sau gradient boosting), validat pe subiecți (`GroupKFold`). GRU doar ca comparație, pentru că KIMORE are doar ~70 de execuții per exercițiu.
- **Stocare și dashboard:** SQLite cu tabelele pacient, sesiune și repetare; Streamlit + Plotly pentru grafice, cu pragul MDC.
- **Producție (mai târziu, în afara proiectului):** logica rămâne bazată doar pe keypoints și regulile în YAML, ca să poată fi portată pe telefon (MediaPipe are SDK Android, iOS și web).

## Plan de evaluare

Zece experimente, fiecare răspunde la o întrebare din raport. Primele șase sunt obligatorii, restul vin dacă rămâne timp.

| # | Întrebarea | Date | Metrica | Prioritate |
| --- | --- | --- | --- | --- |
| E1 | Cât de precise sunt unghiurile? | Sesiunea 1: poziții statice cu goniometru și phyphox | Eroarea medie absolută, în grade, per articulație | Obligatoriu |
| E2 | Numără corect repetările? | Sesiunile 1 și 2 | Procentul de repetări numărate corect | Obligatoriu |
| E3 | Prinde greșelile? | Clipurile cu greșeli intenționate, sesiunile 1 și 2 | Precizie și recall per tip de greșeală | Obligatoriu |
| E4 | Merge în timp real? | Aplicația live pe laptop | FPS și latența până la feedback, în ms | Obligatoriu |
| E5 | De la ce mărime o schimbare e progres real? | Repetabilitatea, sesiunea 2 | ICC, SEM, MDC | Obligatoriu |
| E6 | Arată progresul? | Recuperarea simulată, sesiunea 2 | Ordinea corectă a celor 4 niveluri, schimbări peste MDC, compensarea semnalată | Obligatoriu |
| E7 | Se potrivește cu clinicienii? | KIMORE | Corelație Spearman și MAE față de scorul clinic; separarea sănătos/pacient (AUC) | Recomandat |
| E8 | Recunoaște exercițiul? | KIMORE + înregistrările tale | Acuratețe, matrice de confuzie | Recomandat |
| E9 | Vede progresul la pacienți reali? | KERAAL 1A: începutul vs a doua jumătate a programului, la întinderea flancului și rotația trunchiului | Diferența metricilor între cele două perioade | Recomandat |
| E10 | Prinde greșelile adnotate de medic? | KERAAL 1A și 2A | Acuratețe pe tipuri de greșeli | Opțional |

Pragul de progres real (MDC) vine din repetabilitate:

```text
SEM = SD × √(1 − ICC)
MDC95 = 1,96 × √2 × SEM
```

O schimbare mai mică decât MDC poate fi doar zgomot de măsurare, așa că dashboard-ul o marchează ca progres doar peste acest prag.

E1–E6 sunt pe oameni sănătoși care simulează; scrii asta explicit în raport. E7 și E9 sunt singurele pe pacienți reali.

Fiecare experiment e un script în `scripts/` care regenerează tabelul și graficul lui. Dacă schimbi ceva în pipeline, reiei totul cu o comandă.

## Calendar pe săptămâni

Unsprezece săptămâni plus trei zile de buffer. Milestone-uri: 18 oct, 25 oct, 1 nov, **8 nov (demo live pe 2 exerciții)**, **29 nov (feature freeze)**, 13 dec (rezultate finale), **20 dec (predare)**.

### Săpt. 1 · 5–11 oct · Setup și date

- [x] Descarcă KIMORE; dacă lipsește RGB-ul, scrie autorilor în aceeași zi
- [x] Descarcă KERAAL, grupurile 1A și 2A
- [ ] Setup-ul mediului, `webcam_test.py` și `extract_keypoints.py`
- [ ] Citește articolul KIMORE: exercițiile și caracteristicile definite de medici
- [ ] Cumpără goniometrul și trepiedul; instalează phyphox
- [ ] Roagă 3–5 voluntari și fixează datele pentru 16–22 noiembrie
- [ ] Opțional: caută un kinetoterapeut

### Săpt. 2 · 12–18 oct · Unghiuri și repetări

- [ ] `filters.py`: One Euro și Savitzky–Golay
- [ ] `features.py`: unghiurile principale pentru cele 5 exerciții
- [ ] `reps.py`: segmentarea pe vârfuri
- [ ] Filmează-te informal, 10 repetări per exercițiu, și verifică graficele

**Milestone 18 oct:** dintr-un video ies repetările numărate și unghiurile pe grafic.

### Săpt. 3 · 19–25 oct · Sesiunea 1 de filmare

- [ ] Marcajele pe podea și protocolul scris
- [ ] Filmarea: corect, greșeli, poziții statice cu goniometrul și phyphox
- [ ] Extrage keypoints pentru toate clipurile
- [ ] Rulează E1; dacă un exercițiu iese prost, schimbi unghiul camerei acum, nu în noiembrie

**Milestone 25 oct:** știi eroarea de unghi pentru fiecare articulație.

### Săpt. 4 · 26 oct – 1 nov · Formă și referință

- [ ] `exercises.yaml` cu praguri și mesaje
- [ ] `rules.py` și `reference.py` (DTW)
- [ ] Verifică regulile pe clipurile cu greșeli
- [ ] Scrie secțiunea Date din raport

**Milestone 1 nov:** evaluarea completă merge offline pe înregistrările tale.

### Săpt. 5 · 2–8 nov · Aplicația live

- [ ] `app.py`: scheletul, contorul, unghiul curent și mesajele pe ecran
- [ ] Măsoară FPS-ul și latența (E4)
- [ ] Testează rularea pe laptop

**Milestone 8 nov:** demo live pe 2 exerciții.

### Săpt. 6 · 9–15 nov · Modele învățate

- [ ] Măsurătorile pe KIMORE (pe RGB cu MediaPipe sau pe scheletul Kinect)
- [ ] Scorul învățat: ridge și gradient boosting, validare pe subiecți, Spearman și MAE
- [ ] Recunoașterea exercițiului (Random Forest)
- [ ] Live pe încă un exercițiu

### Săpt. 7 · 16–22 nov · Sesiunea 2 cu voluntari

- [ ] Filmarea: corect și greșeli, repetabilitate (3 seturi), recuperare simulată (4 niveluri), compensare
- [ ] Extrage keypoints
- [ ] Live pe toate exercițiile care au trecut de E1

### Săpt. 8 · 23–29 nov · Stocare și dashboard

- [ ] `storage.py` cu SQLite
- [ ] Dashboard-ul Streamlit: grafice pe sesiuni pentru fiecare exercițiu
- [ ] MDC din repetabilitate (E5), pus pe grafice
- [ ] Scrie secțiunea Metodă

**Milestone 29 nov: feature freeze.** De aici, doar experimente, corecturi și raport.

### Săpt. 9–10 · 30 nov – 13 dec · Experimente

- [ ] E1–E6, apoi E7–E9 dacă e timp, fiecare ca script care regenerează tabelul și graficul
- [ ] Analiza erorilor: unde și de ce greșește sistemul
- [ ] Scrie Rezultatele pe măsură ce ies

**Milestone 13 dec:** toate rezultatele sunt finale.

### Săpt. 11 · 14–20 dec · Raport și demo

- [ ] Raportul complet: introducere, lucrări similare, limitări, concluzii
- [ ] Video demo cu fețele blurate
- [ ] Slide-urile
- [ ] README și curățenie în cod

**Milestone 20 dec: predare.** 21–23 decembrie rămân buffer.

## Priorități, riscuri și planuri de rezervă

Dacă rămâi în urmă, tai de jos în sus: opționalele primele, apoi recomandatele.

- **Obligatoriu:** pipeline-ul pose, unghiuri și repetări; regulile de formă cu feedback; aplicația live pe cel puțin 3 exerciții; stocarea și dashboard-ul; experimentele E1–E6.
- **Recomandat:** live pe toate 5 exercițiile, comparația DTW, scorul învățat pe KIMORE (E7), recunoașterea exercițiului (E8), progresul pe pacienții KERAAL (E9).
- **Opțional:** greșelile adnotate din KERAAL (E10), camera la 45° pentru genuflexiune, un al doilea model de pose pentru comparație.

| Risc | Semnal de alarmă | Plan B |
| --- | --- | --- |
| RGB-ul KIMORE nu vine | Niciun link după trimiterea EULA | Folosești scheletul Kinect: mapezi articulațiile comune și calculezi aceleași unghiuri |
| Unghiurile ies imprecise frontal | E1 arată erori mari la un exercițiu | Cameră laterală sau la 45° pentru acel exercițiu, sau îl scoți din urmărirea progresului |
| Rotațiile (exercițiile 3 și 4) se măsoară slab | Erori mari la trunchi în E1 | Le păstrezi doar pentru scorul învățat și le treci la limitări |
| Aplicația live nu e stabilă | Pe 8 nov nu merge demo-ul pe 2 exerciții | Live doar pe 3 exerciții bune; restul rămân evaluate offline |
| Voluntarii nu pot în noiembrie | Nicio dată fixată până pe 1 nov | 2–3 persoane ajung; repetabilitatea o faci și pe tine |
| Idei noi pe parcurs | Orice funcție nouă după 29 nov | O scrii la „Lucrări viitoare” în raport, nu în cod |

## Livrabile finale și raportul

Pe 20 decembrie predai:

- [ ] Repo-ul cu cod curat și un README care spune cum rulezi aplicația și dashboard-ul
- [ ] Aplicația live
- [ ] Dashboard-ul de progres, populat cu recuperarea simulată
- [ ] Raportul
- [ ] Un video demo de 2–3 minute, cu fețele blurate
- [ ] Prezentarea

Structura raportului:

1. Introducere: telereabilitarea și problema exercițiilor făcute acasă fără supraveghere
2. Lucrări similare: KIMORE, KERAAL și metodele de evaluare
3. Datele: dataset-urile publice și protocolul tău de filmare
4. Metoda: pipeline-ul, modul cu modul
5. Experimente și rezultate: E1–E10
6. Limitări: oameni sănătoși care simulează, o singură cameră, eșantion mic, nu e un instrument de diagnostic
7. Concluzii și lucrări viitoare

Scrii secțiunile Date și Metodă la finalul fiecărei faze, nu în decembrie.
