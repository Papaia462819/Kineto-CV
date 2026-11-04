"""E8: recunoașterea exercițiului din mișcare, pe KIMORE: Random Forest sau regresie logistică.

Pentru fiecare sursă (kinect, mediapipe), separat:
1. Validare imbricată pe persoane: bucla exterioară (5 grupe × 5 repetări) estimează performanța;
   bucla interioară, doar pe datele de antrenare, alege tipul de model și setările lui, pragul de calitate
   pentru antrenare și regula de abținere.
2. Regula de abținere: modelul răspunde doar dacă execuția are destule cadre bune și dacă e destul de sigur.
   Criteriul, fixat dinainte: corect = +1, greșit = -1, abținere = 0.
3. Modelul final, antrenat pe toate datele cu setările alese, se salvează în models/.

Rulare: python scripts/train_exercise_classifier.py   (după build_execution_features.py)
Rezultate: data/exercise_classifier/
"""
import itertools
import json
import sys
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.execution_features import ANGLES, FEATURE_NAMES

FEATURES = ROOT / "data" / "features"
OUT = ROOT / "data" / "exercise_classifier"
MODELS = ROOT / "models"
SOURCES = ["kinect", "mediapipe"]
OUTER_FOLDS, INNER_FOLDS, REPEATS = 5, 4, 5
N_TREES = 300
MODEL_GRID = ([("random_forest", dict(max_features=m, min_samples_leaf=l)) for m in ("sqrt", 0.3) for l in (1, 3)]
              + [("logistic", dict(C=c)) for c in (0.1, 1.0, 10.0)])
TRAIN_MIN_KEPT = [0.0, 0.3, 0.5, 0.7]
GATE_KEPT = [0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
GATE_CONFIDENCE = [0.0, 0.4, 0.5, 0.6, 0.7]
MIN_VALID_S = 1.0  # sub o secundă de date nu există o execuție de clasificat


def load(source):
    table = pd.read_csv(FEATURES / f"{source}.csv")
    table["has_data"] = (table["valid_s"] >= MIN_VALID_S) & table[FEATURE_NAMES].notna().all(axis=1)
    return table.reset_index(drop=True)


def build_model(candidate, seed=0):
    """Random Forest nu are nevoie de scalare; regresia logistică da, ca toate măsurătorile să cântărească la fel."""
    kind, params = candidate
    if kind == "random_forest":
        return RandomForestClassifier(n_estimators=N_TREES, random_state=seed, n_jobs=1, **params)
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, **params))


def fit_predict(candidate, train_min_kept, train, test, seed=0):
    """Antrenează pe execuțiile de antrenare destul de bune; prezice probabilități pentru toate cele de test cu date."""
    use = train[train["has_data"] & (train["kept"] >= train_min_kept)]
    model = build_model(candidate, seed).fit(use[FEATURE_NAMES], use["exercise"])
    proba = np.full((len(test), 5), np.nan)
    has = test["has_data"].to_numpy()
    if has.any():
        proba[has] = model.predict_proba(test.loc[has, FEATURE_NAMES])
    return proba, model


def decide(proba, kept, gate_kept, gate_confidence):
    """Exercițiul prezis (1-5) sau 0 pentru „nu știu”."""
    best = np.nan_to_num(proba, nan=0.0)
    prediction = best.argmax(axis=1) + 1
    confidence = best.max(axis=1)
    answer = (kept >= gate_kept) & (confidence >= gate_confidence) & ~np.isnan(proba).any(axis=1)
    return np.where(answer, prediction, 0)


def net_score(decision, truth):
    answered = decision > 0
    return int(np.sum(decision[answered] == truth[answered]) - np.sum(decision[answered] != truth[answered]))


def splits(table, folds, seed):
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train, test in splitter.split(table, table["exercise"], table["subject"]):
        assert not set(table.loc[train, "subject"]) & set(table.loc[test, "subject"]), "persoană în ambele"
        yield train, test


def select(train, seed):
    """Bucla interioară: alege setările și regula de abținere doar din datele de antrenare."""
    truth = train["exercise"].to_numpy()
    kept = train["kept"].to_numpy()
    best = None
    for candidate, train_min in itertools.product(MODEL_GRID, TRAIN_MIN_KEPT):
        proba = np.full((len(train), 5), np.nan)
        for inner_train, inner_test in splits(train, INNER_FOLDS, seed):
            proba[inner_test], _ = fit_predict(candidate, train_min, train.iloc[inner_train], train.iloc[inner_test], seed)
        for gate_kept, gate_conf in itertools.product(GATE_KEPT, GATE_CONFIDENCE):
            score = net_score(decide(proba, kept, gate_kept, gate_conf), truth)
            # La egalitate preferăm regula care răspunde mai des (prag mai mic), apoi modelul mai simplu.
            key = (score, -gate_kept, -gate_conf)
            if best is None or key > best[0]:
                best = (key, dict(model=candidate, train_min_kept=train_min, gate_kept=gate_kept, gate_confidence=gate_conf))
    return best[1]


def outer_fold(table, train_index, test_index, repeat, fold):
    train, test = table.iloc[train_index].reset_index(drop=True), table.iloc[test_index].reset_index(drop=True)
    choice = select(train, seed=1000 + repeat)
    proba, model = fit_predict(choice["model"], choice["train_min_kept"], train, test, seed=repeat)
    decision = decide(proba, test["kept"].to_numpy(), choice["gate_kept"], choice["gate_confidence"])
    ungated = decide(proba, test["kept"].to_numpy(), 0.0, 0.0)

    # Importanța pe unghi: amestecăm cele 6 coloane ale unui unghi deodată și vedem cât scade acuratețea.
    importance = {}
    usable = test[test["has_data"]]
    if repeat == 0 and len(usable):
        base = accuracy_score(usable["exercise"], model.predict(usable[FEATURE_NAMES]))
        rng = np.random.default_rng(fold)
        for angle in ANGLES:
            columns = [c for c in FEATURE_NAMES if c.startswith(angle + "__")]
            shuffled = usable[FEATURE_NAMES].copy()
            shuffled[columns] = shuffled[columns].to_numpy()[rng.permutation(len(shuffled))]
            importance[angle] = base - accuracy_score(usable["exercise"], model.predict(shuffled))

    # Comparații: ghicitul celei mai frecvente clase și un model liniar simplu, fără prag.
    train_data = train[train["has_data"]]
    dummy = DummyClassifier(strategy="most_frequent").fit(train_data[FEATURE_NAMES], train_data["exercise"])
    linear = make_pipeline(SimpleImputer(), StandardScaler(), LogisticRegression(max_iter=5000))
    linear.fit(train_data[FEATURE_NAMES], train_data["exercise"])
    has = test["has_data"].to_numpy()
    dummy_pred = np.zeros(len(test), dtype=int)
    linear_pred = np.zeros(len(test), dtype=int)
    if has.any():
        dummy_pred[has] = dummy.predict(test.loc[has, FEATURE_NAMES])
        linear_pred[has] = linear.predict(test.loc[has, FEATURE_NAMES])

    rows = test[["subject", "group", "exercise", "kept", "valid_s", "has_data"]].copy()
    rows["repeat"], rows["fold"] = repeat, fold
    rows["decision"], rows["ungated"] = decision, ungated
    rows["confidence"] = np.nan_to_num(proba, nan=0.0).max(axis=1)
    rows["dummy"], rows["linear"] = dummy_pred, linear_pred
    return rows, {**choice, "repeat": repeat, "fold": fold}, importance


def metrics(rows, column):
    truth, prediction = rows["exercise"].to_numpy(), rows[column].to_numpy()
    answered = prediction > 0
    return {
        "coverage": answered.mean(),
        "accuracy_answered": accuracy_score(truth[answered], prediction[answered]) if answered.any() else np.nan,
        "accuracy_all": np.mean(prediction == truth),  # „nu știu” contează ca greșit
        "balanced_accuracy_answered": balanced_accuracy_score(truth[answered], prediction[answered]) if answered.any() else np.nan,
        "macro_f1_answered": f1_score(truth[answered], prediction[answered], average="macro") if answered.any() else np.nan,
        "net_score_per_execution": net_score(prediction, truth) / len(truth),
    }


def by_repeat(rows, column):
    table = pd.DataFrame([metrics(group, column) for _, group in rows.groupby("repeat")])
    return table.mean().round(3).astype(str) + " ± " + table.std().round(3).astype(str)


def plot_confusion(rows, source, column):
    answered = rows[rows[column] > 0]
    matrix = confusion_matrix(answered["exercise"], answered[column], labels=[1, 2, 3, 4, 5], normalize="true")
    figure, axis = plt.subplots(figsize=(5, 4.3))
    image = axis.imshow(matrix, cmap="Blues", vmin=0, vmax=1)
    for i, j in itertools.product(range(5), range(5)):
        axis.text(j, i, f"{100 * matrix[i, j]:.0f}", ha="center", va="center", color="white" if matrix[i, j] > 0.5 else "black")
    axis.set_xticks(range(5), [f"Es{k}" for k in range(1, 6)])
    axis.set_yticks(range(5), [f"Es{k}" for k in range(1, 6)])
    axis.set_xlabel("prezis")
    axis.set_ylabel("adevărat")
    axis.set_title(f"{source}, regresie logistică: % din fiecare exercițiu", fontsize=10)
    figure.colorbar(image)
    figure.tight_layout()
    figure.savefig(OUT / f"{source}_confusion.png", dpi=110)
    plt.close(figure)


def evaluate(source):
    table = load(source)
    jobs = [(train, test, repeat, fold) for repeat in range(REPEATS)
            for fold, (train, test) in enumerate(splits(table, OUTER_FOLDS, seed=repeat))]
    results = Parallel(n_jobs=-1)(delayed(outer_fold)(table, *job) for job in jobs)
    rows = pd.concat([r[0] for r in results], ignore_index=True)
    choices = pd.DataFrame([r[1] for r in results])
    importance = pd.DataFrame([r[2] for r in results if r[2]]).mean().sort_values(ascending=False)
    rows.to_csv(OUT / f"{source}_predictions.csv", index=False)

    print(f"\n===== {source}: {len(table)} executii, {table['subject'].nunique()} persoane, "
          f"{(~table['has_data']).sum()} fara date =====")
    summary = pd.DataFrame({
        "model ales + regula": by_repeat(rows, "decision"),
        "model ales, raspunde mereu": by_repeat(rows, "ungated"),
        "model liniar, raspunde mereu": by_repeat(rows, "linear"),
        "cea mai frecventa clasa": by_repeat(rows, "dummy"),
    })
    print(summary.to_string())
    choices["model"] = choices["model"].astype(str)
    print("\nAlegerile buclei interioare (din 25):")
    for column in ["model", "train_min_kept", "gate_kept", "gate_confidence"]:
        print(f"  {column}: {choices[column].value_counts().to_dict()}")

    first = rows[rows["repeat"] == 0].copy()
    first["band"] = pd.cut(first["kept"], [-0.01, 0.5, 0.9, 1.01], labels=["<50%", "50-90%", ">=90%"])
    print("\nRepetarea 0, pe calitatea detectiei (fara regula de abtinere):")
    print(first.groupby("band", observed=True).apply(
        lambda g: pd.Series({"executii": len(g), "acuratete": np.mean(g["ungated"] == g["exercise"])}),
        include_groups=False).round(3).to_string())
    print("\nRepetarea 0, pe grup (cu regula):")
    print(first.groupby("group").apply(lambda g: pd.Series(metrics(g, "decision"))[["coverage", "accuracy_answered"]],
                                        include_groups=False).round(3).to_string())
    print("\nImportanta pe unghi (cat scade acuratetea cand unghiul e amestecat):")
    print(importance.round(3).to_string())
    plot_confusion(rows[rows["repeat"] == 0], source, "linear")
    simple = rows[(rows["repeat"] == 0) & (rows["linear"] > 0)]
    print("\nMatricea de confuzie, regresie logistica simpla, repetarea 0:")
    print(pd.DataFrame(confusion_matrix(simple["exercise"], simple["linear"], labels=[1, 2, 3, 4, 5]),
                       index=[f"Es{k}" for k in range(1, 6)], columns=[f"Es{k}" for k in range(1, 6)]).to_string())
    print("\nRegresie logistica simpla, pe grup si pe calitate (repetarea 0):")
    print(first.groupby("group").apply(lambda g: pd.Series(metrics(g, "linear"))[["coverage", "accuracy_answered"]],
                                        include_groups=False).round(3).to_string())
    print(first[first["has_data"]].groupby("band", observed=True).apply(
        lambda g: pd.Series({"executii cu date": len(g), "acuratete": np.mean(g["linear"] == g["exercise"])}),
        include_groups=False).round(3).to_string())
    answered = rows[(rows["repeat"] == 0) & (rows["decision"] > 0)]
    print("\nMatricea de confuzie, repetarea 0 (randuri = adevarat):")
    print(pd.DataFrame(confusion_matrix(answered["exercise"], answered["decision"], labels=[1, 2, 3, 4, 5]),
                       index=[f"Es{k}" for k in range(1, 6)], columns=[f"Es{k}" for k in range(1, 6)]).to_string())
    return table, summary, rows


SIMPLE = dict(model=("logistic", dict(C=1.0)), train_min_kept=0.0, gate_kept=0.0, gate_confidence=0.0)


def final_model(source, table, rows):
    """Strategia cu cel mai bun scor net la testul exterior, antrenată apoi pe toate datele.

    Se compară doar două strategii fixate dinainte: reglajul imbricat și regresia logistică simplă,
    fără reglaj și fără abținere (în afară de execuțiile fără date).
    """
    truth = rows["exercise"].to_numpy()
    nested = net_score(rows["decision"].to_numpy(), truth)
    simple = net_score(rows["linear"].to_numpy(), truth)
    choice = SIMPLE if simple >= nested else select(table, seed=4242)
    print(f"\nScor net la testul exterior: reglaj imbricat {nested}, regresie logistica simpla {simple}")
    use = table[table["has_data"] & (table["kept"] >= choice["train_min_kept"])]
    model = build_model(choice["model"], seed=0).fit(use[FEATURE_NAMES], use["exercise"])
    MODELS.mkdir(exist_ok=True)
    joblib.dump(model, MODELS / f"exercise_classifier_{source}.joblib")
    info = {"source": source, "features": FEATURE_NAMES, "trained_on": int(len(use)), **choice,
            "rule": "raspunde doar daca kept >= gate_kept si increderea >= gate_confidence"}
    (MODELS / f"exercise_classifier_{source}.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"\nModel final {source}: {info['model']}, antrenat pe {len(use)} executii, "
          f"prag antrenare {choice['train_min_kept']}, raspunde daca kept >= {choice['gate_kept']} "
          f"si increderea >= {choice['gate_confidence']}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220, "display.max_columns", None)
    summaries = {}
    for source in SOURCES:
        table, summaries[source], rows = evaluate(source)
        final_model(source, table, rows)
    pd.concat(summaries, names=["source"]).to_csv(OUT / "summary.csv")


if __name__ == "__main__":
    main()
