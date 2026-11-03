# Ghid de concepte – proiectul de kinetoterapie cu camera

Conceptele din planul proiectului, explicate simplu și în ordinea în care le folosești: de la camera care filmează până la graficul de progres. Graficele și desenele sunt în versiunea online a ghidului; aici fiecare apare ca o scurtă descriere.

## Harta ghidului

Ghidul urmează drumul datelor prin sistem: camera filmează, MediaPipe găsește scheletul, tu calculezi unghiuri, împarți mișcarea în repetări, le judeci și salvezi rezultatele.

1. **Uneltele:** Python, mediul virtual, librăriile. Săpt. 1.
2. **De la video la schelet:** pixeli, cadre, cele 33 de puncte MediaPipe. Săpt. 1–2.
3. **Netezirea:** cum scapi de tremuratul punctelor. Săpt. 2.
4. **Vectori și unghiuri:** cum transformi puncte în grade. Săpt. 2.
5. **Repetări din vârfuri:** cum numeri repetările automat. Săpt. 2.
6. **Măsurători pe repetare:** amplitudine, simetrie, tempo, netezime. Săpt. 2–4.
7. **Reguli și praguri:** cum decizi că o repetare e greșită. Săpt. 4.
8. **DTW:** cum compari cu o repetare corectă făcută în alt ritm. Săpt. 4.
9. **Învățare automată:** modele care învață scorul din exemple. Săpt. 6.
10. **Metrici de evaluare:** cât de bun e sistemul, în cifre. Săpt. 3 și 9–10.
11. **Repetabilitate și progres real:** ICC, SEM, MDC. Săpt. 8–10.
12. **Stocare și dashboard:** unde ajung rezultatele și cum le arăți. Săpt. 8.

## 1. Uneltele

O **librărie** e cod scris și testat de alții, pe care îl folosești în loc să-l scrii tu. Proiectul folosește Python pentru că aproape toate librăriile de vedere artificială și statistică sunt scrise pentru el.

**Mediul virtual** (`.venv`) e folderul în care stau librăriile acestui proiect, separat de restul calculatorului. Lista lor exactă o salvezi în `requirements.txt`, ca să poți reface același mediu pe laptop.

| Librărie | Ce face, pe scurt | Unde o folosești |
| --- | --- | --- |
| NumPy | Tablouri de numere și calcule rapide pe ele, de exemplu punctele unui cadru ca matrice 33 × 4 | Aproape peste tot: vectori, unghiuri, medii |
| OpenCV (`cv2`) | Deschide camera și fișierele video, citește cadre, desenează linii și text pe imagine | `webcam_test.py`, `extract_keypoints.py`, aplicația live |
| MediaPipe | Un model deja antrenat care găsește 33 de puncte ale corpului într-o imagine | `src/pose.py` |
| SciPy | Matematică științifică: filtre de netezire, găsirea vârfurilor, statistică | `filters.py`, `reps.py` |
| pandas | Tabele în cod, ca un Excel: rânduri, coloane, filtre, medii pe grupuri | Analiza rezultatelor, CSV-ul cu înregistrările |
| scikit-learn | Modele clasice de învățare automată, împărțirea datelor și metrici gata făcute | Scorul învățat, recunoașterea exercițiului, evaluarea |
| PyTorch | Rețele neuronale, de exemplu GRU | Doar comparația cu GRU, opțional |
| dtaidistance | DTW rapid | `reference.py` |
| pingouin | Statistică pentru cercetare, inclusiv ICC | Experimentul E5 |
| matplotlib | Grafice statice | Figurile din raport |
| Plotly | Grafice interactive: zoom, valoarea la trecerea cu mouse-ul | Dashboard-ul |
| Streamlit | Transformă un script Python într-o pagină web cu butoane și grafice | Dashboard-ul |
| PyYAML | Citește fișiere de configurare YAML, ușor de citit și de oameni | `exercises.yaml`, cu pragurile |
| sqlite3 | Bază de date într-un singur fișier; vine cu Python, nu se instalează | `storage.py` |
| Jupyter | Caiete în care rulezi cod pe bucăți și vezi imediat rezultatul și graficele | Explorarea dataset-urilor |

**Cum se leagă între ele:** OpenCV citește cadrul, MediaPipe găsește punctele, NumPy calculează unghiurile, SciPy le netezește și găsește repetările, scikit-learn învață scorul, SQLite salvează rezultatele, iar Streamlit le arată.

## 2. De la video la schelet

Pentru calculator, un video e doar un șir lung de numere. MediaPipe transformă fiecare cadru în 33 de puncte, iar de aici încolo lucrezi doar cu ele.

**Imaginea.** O imagine e o grilă de pixeli, iar fiecare pixel are trei numere între 0 și 255, câte unul pentru albastru, verde și roșu. OpenCV ține culorile în ordinea BGR, MediaPipe le vrea în RGB, de aceea `pose.py` le convertește înainte.

**Video-ul.** Un video e un șir de imagini numite cadre. La 30 de cadre pe secundă (fps) vine un cadru la fiecare 33 ms, așa că o repetare de 3 secunde înseamnă cam 90 de cadre, adică 90 de măsurători.

**Estimarea pozei.** MediaPipe e o rețea neuronală deja antrenată. Primește un cadru și întoarce 33 de puncte (repere), fiecare cu patru numere: x, y, z și vizibilitatea. În modul VIDEO urmărește persoana de la un cadru la altul, în loc s-o caute de la zero de fiecare dată.

*Desen în ghidul online: scheletul cu punctele numerotate (11/12 umeri, 13/14 coate, 15/16 încheieturi, 23/24 șolduri, 25/26 genunchi, 27/28 glezne). Stânga persoanei apare în dreapta imaginii.*

Primești aceleași puncte în două feluri:

- **În imagine:** x și y între 0 și 1, ca procent din lățimea și înălțimea cadrului. Originea e în colțul stânga-sus, iar y crește în jos. Sunt bune pentru desenat scheletul peste video.
- **În metri („world”):** x, y, z în metri, cu originea în mijlocul șoldurilor. Sunt bune pentru unghiuri, pentru că nu depind de cât de departe stai de cameră.

**Vizibilitatea** e un număr între 0 și 1 care spune cât de sigur e modelul că punctul se vede. Sub 0,5, punctul e probabil ascuns și nu te bazezi pe el. „Stânga” înseamnă stânga persoanei, nu a ecranului.

**O limită de ținut minte:** x și y se văd direct în imagine, dar z (adâncimea) e ghicită de model dintr-o singură imagine. De aceea mișcările spre cameră sau dinspre ea se măsoară mai slab.

```python
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28
```

**În proiect:** `src/pose.py` primește un cadru și întoarce două matrice 33 × 4, `image_kp` și `world_kp`. `extract_keypoints.py` le salvează pentru fiecare cadru într-un fișier `.npz`.

## 3. Zgomot și netezire

Punctele MediaPipe tremură puțin de la un cadru la altul, chiar dacă stai nemișcat. Netezirea păstrează mișcarea reală, care e lentă și lină, și taie tremuratul, care e rapid și haotic.

**De ce tremură.** Modelul estimează punctele pe fiecare cadru cu o mică eroare, de câțiva pixeli. Pentru un unghi, asta înseamnă salturi de câteva grade între cadre. Tremuratul ăsta se numește **zgomot**.

**Media mobilă** e cea mai simplă metodă: fiecare valoare devine media ultimelor N valori. Rămâne în urma mișcării, iar vârfurile ies mai joase decât în realitate. A doua e gravă aici, pentru că amplitudinea e chiar ce măsori.

**Savitzky–Golay** potrivește o curbă mică (un polinom de grad 2 sau 3) pe o fereastră de puncte din jurul fiecărei valori și ia valoarea curbei. Păstrează forma vârfurilor mult mai bine. Are nevoie și de punctele de după, deci îl folosești offline, pe înregistrări.

*Grafic în ghidul online: pe o repetare simulată, media mobilă de 0,5 s coboară vârful cu ~5° și îl întârzie cu ~0,2 s; Savitzky–Golay rămâne aproape de mișcarea reală.*

**One Euro** e filtrul pentru live, care nu poate aștepta punctele viitoare. Netezește puternic când mișcarea e lentă și slab când e rapidă. Are doi parametri:

- `min_cutoff`: cât netezește în repaus. Mai mic înseamnă mai neted.
- `beta`: cât de repede renunță la netezire când te miști. Mai mare înseamnă întârziere mai mică.

Le reglezi în doi pași: stai pe loc și scazi `min_cutoff` până dispare tremuratul, apoi te miști repede și crești `beta` până scheletul nu mai rămâne în urmă.

**Compromisul de reținut:** orice filtru live alege între netezime și întârziere. Offline nu ai problema asta.

**În proiect:** `filters.py` conține ambele filtre. Pe înregistrări folosești `scipy.signal.savgol_filter(x, window_length=15, polyorder=3)`, cu o fereastră de număr impar de cadre. În aplicația live folosești One Euro, fie din pachetul `OneEuroFilter`, fie scris de tine în vreo 30 de linii.

## 4. Vectori și unghiuri

Un unghi articular se calculează din trei puncte: articulația din mijloc și câte un punct pe fiecare segment.

**Vectorul** e o săgeată de la un punct la altul: de la cot la umăr, vectorul e umăr minus cot. **Lungimea** lui se calculează cu Pitagora.

**Produsul scalar** înmulțește componentele pereche și le adună:

```text
a · b = ax·bx + ay·by + az·bz = |a| · |b| · cos θ
θ = arccos( a · b / (|a| · |b|) )
```

Cosinusul e 1 când vectorii merg în aceeași direcție (0°), 0 când sunt perpendiculari (90°) și −1 când sunt opuși (180°).

**Exemplu numeric (desen în ghidul online):** cot (0; 0), umăr (0; −0,30), încheietură (0,20; 0,15). a = (0; −0,30), b = (0,20; 0,15), a · b = −0,045, |a| = 0,30, |b| = 0,25, cos θ = −0,6, θ = arccos(−0,6) ≈ 127°.

```python
def angle(a, b, c):
    """Unghiul în punctul b, între segmentele b→a și b→c, în grade."""
    v1, v2 = a - b, c - b
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
```

`np.clip` e acolo pentru că rotunjirile pot da 1,0000001, iar arccos nu e definit peste 1.

Unghiurile din proiect:

- **Cotul:** umăr–cot–încheietură (11–13–15). Aproape 180° cu brațul întins.
- **Genunchiul:** șold–genunchi–gleznă (23–25–27). **Flexia** genunchiului e 180° minus acest unghi: 0° în picioare, ~90° la o genuflexiune adâncă.
- **Umărul:** între braț (umăr→cot) și trunchi (umăr→șold). 0° cu brațul pe lângă corp, 180° cu brațul sus.
- **Înclinarea trunchiului:** între linia mijloc-șolduri→mijloc-umeri și verticală. Telefonul trebuie să stea drept.
- **Rotația trunchiului:** între linia umerilor și linia șoldurilor, privite de sus. Depinde aproape numai de z.

### Ce vede bine o cameră frontală

| Mișcarea | Exemple | Precizie cu camera în față |
| --- | --- | --- |
| Stânga–dreapta și sus–jos, în planul imaginii | Brațele ridicate lateral, înclinarea laterală a trunchiului, genunchii care cad spre interior | Bună: folosește x și y |
| Spre cameră sau dinspre ea | Brațele ridicate prin față, aplecarea trunchiului în față, genunchii care ies în față la genuflexiune | Medie: depinde de z |
| Rotații în jurul axei verticale | Rotația trunchiului, rotația bazinului | Slabă: aproape numai z |

Experimentul E1 îți spune cât de mare e eroarea; dacă iese mare, soluția e o cameră laterală sau la 45° pentru acel exercițiu.

**În proiect:** `features.py` calculează pe fiecare cadru unghiurile principale ale exercițiului, din `world_kp`.

## 5. Unghiul ca semnal: găsirea repetărilor

Dacă desenezi unghiul principal în timp, fiecare repetare apare ca un deal. Numărarea repetărilor devine găsirea vârfurilor.

**Semnal** înseamnă o mărime măsurată în timp. **Vârful** e momentul de amplitudine maximă al unei repetări, iar **văile** dinainte și de după el sunt începutul și sfârșitul ei.

Nu orice ridicătură e o repetare. Le filtrezi cu două reguli:

- **Proeminența minimă:** cât trebuie să iasă un vârf deasupra văii din jurul lui. O repetare reală iese cu zeci de grade, o tresărire cu câteva.
- **Distanța minimă:** câte cadre trebuie să treacă între două vârfuri. La 30 fps pui cel puțin 30 de cadre, ca să nu numeri de două ori un vârf cu două cocoașe.

*Grafic în ghidul online: 5 genuflexiuni simulate; `find_peaks` le găsește pe toate 5 (proeminență ~90°) și ignoră o mișcare mică de ~9°.*

Netezești semnalul înainte, altfel zgomotul face vârfuri false. **Live,** știi că un vârf a fost vârf abia când unghiul începe să scadă, deci feedback-ul vine la sfârșitul repetării.

**În proiect:** `reps.py` folosește `scipy.signal.find_peaks(unghi, prominence=20, distance=30)`. Începutul și sfârșitul fiecărei repetări sunt minimele dintre vârfuri.

## 6. Măsurători pe repetare

După ce ai împărțit mișcarea în repetări, rezumi fiecare repetare în câteva numere. Pe ele se bazează feedback-ul, graficele de progres și scorul învățat.

*Grafic în ghidul online: o genuflexiune cu amplitudine 93°, urcare 1,4 s, coborâre 1,0 s.*

- **Amplitudinea** (ROM): maximul minus minimul unghiului principal în repetare. Principala măsură a recuperării.
- **Simetria:** diferența dintre amplitudinea părții stângi și a celei drepte.
- **Tempoul:** cât durează urcarea și coborârea, în secunde.
- **Netezimea:** viteza e cât se schimbă unghiul pe secundă, accelerația e cât se schimbă viteza, iar **jerk**-ul e cât de brusc se schimbă accelerația. Mișcare lină = jerk mic.
- **Compensarea:** o articulație care se mișcă deși n-ar trebui, măsurată ca valoarea maximă a acelui unghi în timpul repetării.

**Derivatele în cod:** `np.gradient(unghi, 1/fps)`, aplicat o dată pentru viteză, de două ori pentru accelerație, de trei ori pentru jerk. Fiecare derivată amplifică zgomotul, deci netezirea contează și mai mult. Normalizezi jerk-ul după durată și amplitudine.

**În proiect:** `features.py` scoate pentru fiecare repetare un rând cu aceste numere, folosit de reguli, baza de date și, agregat pe execuție, de modelul învățat.

## 7. Reguli și praguri

O regulă de formă e un „dacă–atunci”: dacă flexia maximă a genunchiului e sub un prag, mesajul e „coboară mai jos”. Pragul îl calculezi din repetările corecte.

**Media (μ)** e valoarea tipică. **Abaterea standard (σ)** spune cât de împrăștiate sunt valorile. Cam 95% din valori cad între μ − 2σ și μ + 2σ, deci cu pragul la μ − 2σ o repetare corectă cade sub el rar, cam o dată la 40.

*Grafic în ghidul online: 30 de repetări corecte (μ ≈ 98°, σ ≈ 6°) și 12 prea puțin adânci; pragul μ − 2σ ≈ 86° prinde 11 din 12 și dă o alarmă falsă din 30.*

**Compromisul:** un prag mai strict prinde mai multe greșeli, dar dă și mai multe alarme false.

Ce mărimi verifici la fiecare exercițiu iei din caracteristicile definite de medici în KIMORE (folderul `Script`); valorile le calibrezi pe repetările tale corecte. Pragurile și mesajele stau într-un fișier YAML, nu în cod:

```yaml
squat:
  main_angle: knee_flexion
  checks:
    - name: depth
      metric: rom
      min: 86
      message: "Coboară mai jos"
    - name: trunk_lean
      metric: max_trunk_lean
      max: 35
      message: "Ține spatele mai drept"
```

**În proiect:** `rules.py` citește `configs/exercises.yaml`, compară măsurătorile fiecărei repetări cu pragurile și întoarce mesajele de afișat. Pragurile din exemplu sunt ilustrative.

## 8. DTW: compararea cu o repetare de referință

Repetarea pacientului și cea de referință au ritmuri diferite. Comparate cadru cu cadru, ies diferențe mari chiar dacă forma e aceeași.

**DTW** (Dynamic Time Warping) leagă fiecare moment dintr-o curbă de momentul cel mai asemănător din cealaltă, păstrând ordinea. **Distanța DTW** e suma diferențelor de-a lungul acestor legături: mică înseamnă aceeași formă, chiar dacă ritmul diferă.

*Desen în ghidul online: o repetare de referință de 2 s și una a pacientului de 3 s; diferența medie e 37° cadru cu cadru și 1,7° după aliniere.*

Legăturile se găsesc cu un tabel al diferențelor dintre toate perechile de cadre și drumul cel mai ieftin dintr-un colț în celălalt (programare dinamică).

**Ce obții:** un scor de asemănare cu referința și momentul cu cea mai mare abatere, pentru feedback precis.

**De ținut minte:** DTW ignoră intenționat viteza, deci tempoul îl măsori separat; împarte distanța la lungimea drumului; pune o fereastră care limitează cât de departe în timp pot fi două momente legate.

**În proiect:** `reference.py` folosește `dtaidistance`: `dtw.distance(repetare, referinta, window=20)` și `dtw.warping_path(repetare, referinta)`. Referința e o repetare corectă de-a ta din sesiunea 1.

## 9. Învățare automată

La reguli scrii tu logica; la învățare automată, modelul o deduce din exemple. În proiect: prezici scorul clinic din KIMORE și recunoști ce exercițiu se face.

- **Exemplu:** o execuție a unui exercițiu.
- **Caracteristici:** numerele care descriu exemplul (măsurătorile din secțiunea 6, agregate pe execuție).
- **Țintă:** un număr (scorul 0–50) înseamnă **regresie**; o categorie (numele exercițiului) înseamnă **clasificare**.
- **Antrenare:** modelul își ajustează parametrii până când predicțiile se apropie de ținte.

Modelele:

- **Regresia liniară:** scorul e o sumă ponderată a caracteristicilor. **Ridge** penalizează ponderile mari, deci e mai stabilă cu puține exemple.
- **Arborele de decizie:** întrebări da/nu. **Random Forest** = sute de arbori care votează. **Gradient boosting** = arbori adăugați pe rând, fiecare corectând greșelile celor dinainte.
- **GRU:** rețea neuronală care citește secvența cadru cu cadru. Are nevoie de multe date; doar pentru comparație.

**Supraînvățarea:** modelul memorează exemplele în loc să învețe regula. Singura apărare e testarea pe date nevăzute.

**Validarea încrucișată:** împarți datele în k bucăți, antrenezi pe k − 1, testezi pe cea rămasă și rotești.

**Validarea pe subiecți** e regula de aur: dacă aceeași persoană apare și în antrenare, și în test, modelul o recunoaște și cifrele ies prea bune. Împarte pe persoane.

*Desen în ghidul online: împărțirea aleatorie (fiecare persoană apare și în test) față de împărțirea pe subiecți (o persoană e doar în test).*

```python
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, cross_val_predict

# X = caracteristicile, y = scorurile clinice, subiect = cine a făcut fiecare execuție
pred = cross_val_predict(Ridge(alpha=1.0), X, y, groups=subiect, cv=GroupKFold(n_splits=5))
```

**În proiect:** în `learned/` antrenezi Ridge și gradient boosting pentru scor, Random Forest pentru recunoașterea exercițiului, toate validate pe subiecți.

## 10. Cum măsori cât de bun e sistemul

**MAE** (eroarea medie absolută): media diferențelor dintre ce măsori și adevăr, fără semn. Erori de 4°, 6°, 2° și 8° dau MAE = 5°.

### Detecția greșelilor: matricea de confuzie

Exemplu cu 100 de repetări, dintre care 40 cu greșeală:

| | Sistemul zice: greșeală | Sistemul zice: corect |
| --- | --- | --- |
| **În realitate: greșeală** (40) | 34, prinse corect | 6, ratate |
| **În realitate: corect** (60) | 5, alarme false | 55, lăsate corect în pace |

- **Precizia:** din alarmele date, câte erau reale? 34 din 39 = 87%.
- **Recall:** din greșelile reale, câte au fost prinse? 34 din 40 = 85%.
- **F1:** cele două combinate, aici 86%.
- **Acuratețea:** 89 din 100. Poate păcăli când greșelile sunt rare.

Un prag mai strict crește recall-ul și scade precizia.

### Compararea cu clinicienii

- **Spearman (ρ):** dacă ordinea execuțiilor după scorul tău e aceeași ca după scorul clinic. 1 = identică, −1 = inversă, 0 = fără legătură.
- **AUC:** cât de bine separă scorul sănătoșii de pacienți. 0,5 = la întâmplare, 1 = perfect.

| Metrica | Întrebarea | Experimentul |
| --- | --- | --- |
| MAE în grade | Cât greșesc unghiurile? | E1 |
| Procent de repetări numărate corect | Numără bine? | E2 |
| Precizie, recall, F1 | Prinde greșelile fără alarme false? | E3, E10 |
| Spearman, MAE pe scor, AUC | Se potrivește cu clinicienii? | E7 |
| Acuratețe, matrice de confuzie | Recunoaște exercițiul? | E8 |

**În proiect:** `sklearn.metrics` (`mean_absolute_error`, `precision_score`, `recall_score`, `f1_score`, `confusion_matrix`, `roc_auc_score`) și `scipy.stats.spearmanr`.

## 11. Repetabilitate și progres real

Aceeași persoană măsurată de două ori dă numere puțin diferite. Cât de mare trebuie să fie o schimbare ca să fie progres, nu zgomot?

1. **ICC:** ce parte din variația măsurătorilor vine din diferențele reale dintre oameni și ce parte din zgomot. 0 la 1; sub 0,5 slab, 0,5–0,75 moderat, 0,75–0,9 bun, peste 0,9 excelent.
2. **SEM:** zgomotul în grade.
3. **MDC:** pragul de la care o diferență între două sesiuni e reală, cu 95% încredere.

```text
SEM = SD × √(1 − ICC)
MDC95 = 1,96 × √2 × SEM
```

**Exemplu:** SD = 12°, ICC = 0,90 → SEM ≈ 3,8°, MDC ≈ 10,5°. Amplitudinea trebuie să crească cu peste 10,5° față de prima sesiune ca să fie progres real.

*Grafic în ghidul online: 6 sesiuni ipotetice (92°, 95°, 99°, 104°, 107°, 111°); abia din sesiunea 4 creșterea depășește MDC.*

Un protocol de filmare mai riguros scade zgomotul, crește ICC și micșorează MDC.

**În proiect:** în E5 calculezi ICC cu `pingouin.intraclass_corr` (coloanele persoană, set, amplitudine; tipul ICC2), apoi SEM și MDC, care ajunge pe graficele din dashboard.

## 12. Stocare și dashboard

**SQLite** ține toată baza într-un singur fișier (`data/rehab.db`), fără server. **SQL** e limbajul cu care pui și scoți date. Datele stau în tabele legate prin ID-uri: pacient → sesiuni → repetări.

```sql
CREATE TABLE patient (id INTEGER PRIMARY KEY, code TEXT);
CREATE TABLE session (id INTEGER PRIMARY KEY, patient_id INTEGER REFERENCES patient(id),
                      date TEXT, exercise TEXT);
CREATE TABLE repetition (id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES session(id),
                         n INTEGER, rom REAL, asymmetry REAL, duration_s REAL, errors TEXT);
```

```sql
SELECT s.date, AVG(r.rom) AS rom
FROM repetition r JOIN session s ON r.session_id = s.id
WHERE s.patient_id = 1 AND s.exercise = 'squat'
GROUP BY s.id ORDER BY s.date;
```

`JOIN` lipește rândurile din două tabele după ID, `GROUP BY` face câte o medie pe sesiune. `pd.read_sql(query, conn)` dă rezultatul ca tabel pandas.

**Streamlit** transformă un script Python într-o pagină web (`st.selectbox`, `st.plotly_chart`; rulezi `streamlit run dashboard/app.py`). **Plotly** face graficele interactive. În baza de date folosești coduri precum P01, nu nume.

**În proiect:** `storage.py` creează tabelele și salvează rândurile la sfârșitul fiecărei sesiuni, iar `dashboard/app.py` le citește și desenează graficele, cu pragul MDC.

## Glosar

| Termen | Pe scurt | Secțiunea |
| --- | --- | --- |
| Abatere standard (σ) | Cât de împrăștiate sunt valorile în jurul mediei | 7 |
| Amplitudine (ROM) | Maximul minus minimul unghiului într-o repetare | 6 |
| AUC | Cât de bine separă un scor două grupuri; 0,5 = la întâmplare, 1 = perfect | 10 |
| Cadru, fps | O imagine din video; câte imagini pe secundă | 2 |
| Caracteristici | Numerele care descriu un exemplu pentru model | 9 |
| Compensare | O articulație care se mișcă ca să „ajute”, deși n-ar trebui | 6 |
| Coordonate „world” | Poziția punctelor în metri, cu originea în mijlocul șoldurilor | 2 |
| DTW | Compară două curbe după ce le aliniază în timp | 8 |
| F1 | Precizia și recall-ul combinate | 10 |
| Flexie | Cât e îndoită o articulație; la genunchi, 180° minus unghiul | 4 |
| ICC | Ce parte din variație e reală și ce parte e zgomot | 11 |
| Jerk | Cât de brusc se schimbă accelerația | 6 |
| MAE | Eroarea medie, fără semn | 10 |
| MDC | Cea mai mică schimbare care e sigur reală | 11 |
| Medie mobilă | Netezire prin media ultimelor N valori | 3 |
| One Euro | Filtru de netezire pentru live, adaptat la viteză | 3 |
| Precizie | Din alarmele date, câte erau reale | 10 |
| Produs scalar | Dă unghiul dintre doi vectori | 4 |
| Proeminență | Cât iese un vârf deasupra văii din jurul lui | 5 |
| Recall | Din greșelile reale, câte au fost prinse | 10 |
| Ridge | Regresie liniară care penalizează ponderile mari | 9 |
| Savitzky–Golay | Netezire offline care păstrează forma vârfurilor | 3 |
| SEM | Zgomotul măsurării, în grade | 11 |
| Spearman (ρ) | Cât de bine se potrivește ordinea a două clasamente | 10 |
| Supraînvățare | Modelul memorează exemplele în loc să învețe regula | 9 |
| Validare pe subiecți | Persoanele din test nu apar în antrenare | 9 |
| Vizibilitate | Cât de sigur e modelul că punctul se vede | 2 |
| Zgomot | Tremuratul aleator al măsurătorilor | 3 |

## De citit mai departe

- [MediaPipe Pose Landmarker pentru Python](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python)
- [1€ Filter, articolul original](https://direction.bordeaux.inria.fr/~roussel/publications/2012-CHI-one-euro-filter.pdf) (Casiez, Roussel, Vogel, CHI 2012)
- [Implementări One Euro, inclusiv în Python](https://github.com/casiez/OneEuroFilter)
- [scipy.signal.find_peaks](https://docs.scipy.org/doc/scipy-1.10.1/reference/generated/scipy.signal.find_peaks.html)
- [KIMORE dataset](https://vrai.dii.univpm.it/content/kimore-dataset)
