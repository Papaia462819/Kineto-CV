"""E7: învață scorul clinic KIMORE (0–50) din mișcare, pe Kinect și pe MediaPipe.

Intrări: data/features/{kinect,mediapipe}_e7.csv (scripts/build_score_features.py)

Două moduri:
  python scripts/train_clinical_score.py           evaluează sistemul ales (src/clinical_score.py),
                                                    apoi îl antrenează pe tot și îl salvează
      → data/clinical_score/report.txt, predictions.csv; models/clinical_score_{sursa}.joblib + .json
  python scripts/train_clinical_score.py --search  runda 1: 36 de candidați pe exercițiu, aleși în bucla
                                                    interioară (de aici a pornit alegerea sistemului)
      → data/clinical_score/search/

Schema căutării (aceeași idee ca la E8):
- Doar execuțiile care au scor și date bune pe ambele surse, ca să comparăm corect Kinect cu MediaPipe.
- Validare imbricată pe persoane: bucla exterioară (5 grupe × 5 repetări) măsoară performanța pe persoane
  nevăzute; bucla interioară (4 grupe) alege grupul de măsurători, modelul și setările, doar din antrenare.
- Comparăm cu media (fără mișcare) și cu media grupului sănătos/pacient (care știe diagnosticul).
- Grupul, vârsta, sexul și calitatea filmării nu intră niciodată în model.

"""
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.cross_decomposition import PLSRegression
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.clinical_features import clinical_feature_names
from src.clinical_score import ClinicalScoreModel
from src.execution_features import FEATURE_NAMES, REPETITION_NAMES

FEATURES = ROOT / "data" / "features"
REPORT = ROOT / "data" / "clinical_score"
OUT = REPORT / "search"
MODELS = ROOT / "models"
SOURCES = ["kinect", "mediapipe"]
EXERCISES = [1, 2, 3, 4, 5]
TARGET = "score_total"
SCORE_RANGE = (0.0, 50.0)
OUTER_FOLDS, INNER_FOLDS, REPEATS = 5, 4, 5
MIN_VALID_S = 1.0
FEATURE_SETS = ["A", "B", "C", "ABC"]
MODEL_GRID = ([("ridge", dict(alpha=a)) for a in (10, 100, 1000, 10000)]
              + [("pls", dict(n_components=k)) for k in (1, 2, 3)]
              + [("forest", dict(min_samples_leaf=3, max_features=0.3)),
                 ("boosting", dict(n_estimators=150, learning_rate=0.03, max_depth=2, subsample=0.7))])
CANDIDATES = [(features, model, params) for features in FEATURE_SETS for model, params in MODEL_GRID]


def candidate_name(candidate):
    features, model, params = candidate
    return f"{features}|{model}|" + ",".join(f"{k}={v}" for k, v in params.items())


def load():
    """Aceleași execuții pentru ambele surse: scor prezent, MediaPipe cu cel puțin o secundă de date complete."""
    tables = {s: pd.read_csv(FEATURES / f"{s}_e7.csv") for s in SOURCES}
    keys = None
    for source, table in tables.items():
        good = table[TARGET].notna() & (table["valid_s"] >= MIN_VALID_S) & table[FEATURE_NAMES].notna().all(axis=1)
        good_keys = set(map(tuple, table.loc[good, ["subject", "exercise"]].to_numpy()))
        keys = good_keys if keys is None else keys & good_keys
    for source, table in tables.items():
        mask = [k in keys for k in map(tuple, table[["subject", "exercise"]].to_numpy())]
        tables[source] = table[mask].sort_values(["exercise", "subject"]).reset_index(drop=True)
    return tables


def columns(table, exercise, feature_set):
    groups = {"A": FEATURE_NAMES, "B": REPETITION_NAMES, "C": clinical_feature_names(exercise)}
    names = [c for g in feature_set for c in groups[g]]
    # O coloană fără nicio valoare (de ex. simetria la exercițiile fără pereche) nu poate ajuta.
    return [c for c in names if table[c].notna().any()]


def build_model(model, params, seed=0):
    if model == "mean":
        return DummyRegressor()
    if model == "ridge":
        estimator = Ridge(**params)
    elif model == "pls":
        estimator = PLSRegression(scale=False, **params)
    elif model == "forest":
        estimator = RandomForestRegressor(n_estimators=150, random_state=seed, n_jobs=1, **params)
    elif model == "boosting":
        estimator = GradientBoostingRegressor(random_state=seed, **params)
    else:
        raise ValueError(model)
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), estimator)


def fit_predict(candidate, train, test, exercise, seed=0):
    features, model, params = candidate
    names = columns(train, exercise, features)
    estimator = build_model(model, params, seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        estimator.fit(train[names], train[TARGET])
        prediction = np.ravel(estimator.predict(test[names]))
    return np.clip(prediction, *SCORE_RANGE)


def splits(table, folds, seed):
    """Grupe pe persoane, echilibrate pe nivelul scorului (4 trepte), ca fiecare grupă să aibă scoruri variate."""
    strata = pd.qcut(table[TARGET].rank(method="first"), 4, labels=False)
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train, test in splitter.split(table, strata, groups=table["subject"]):
        assert not set(table["subject"].iloc[train]) & set(table["subject"].iloc[test])
        yield train, test


def inner_scores(train, exercise, seed):
    """MAE pe bucla interioară pentru fiecare candidat. Folosește doar datele de antrenare."""
    errors = {candidate_name(c): [] for c in CANDIDATES}
    for inner_train, inner_test in splits(train, INNER_FOLDS, seed):
        fit, check = train.iloc[inner_train], train.iloc[inner_test]
        for candidate in CANDIDATES:
            prediction = fit_predict(candidate, fit, check, exercise, seed)
            errors[candidate_name(candidate)].append(mean_absolute_error(check[TARGET], prediction))
    return {name: float(np.mean(values)) for name, values in errors.items()}


def outer_fold(source, table, exercise, repeat, fold, train_index, test_index):
    train, test = table.iloc[train_index], table.iloc[test_index]
    seed = 1000 * repeat + fold
    scores = inner_scores(train, exercise, seed)
    chosen = min(CANDIDATES, key=lambda c: scores[candidate_name(c)])
    out = test[["subject", "group", "population", "exercise", "kept", TARGET]].copy()
    out["source"], out["repeat"], out["fold"] = source, repeat, fold
    out["chosen"] = candidate_name(chosen)
    out["nested"] = fit_predict(chosen, train, test, exercise, seed)
    out["baseline_mean"] = train[TARGET].mean()
    # Referință care știe diagnosticul: media scorurilor din antrenare pentru grupul persoanei.
    out["baseline_population"] = test["population"].map(train.groupby("population")[TARGET].mean())
    # Fiecare candidat fix, fără alegere: arată care setare e bună și cât de stabilă e.
    for candidate in CANDIDATES:
        out[candidate_name(candidate)] = fit_predict(candidate, train, test, exercise, seed)
    return out


def metrics(frame, column):
    truth, prediction = frame[TARGET].to_numpy(), frame[column].to_numpy()
    row = {"mae": mean_absolute_error(truth, prediction),
           "spearman": spearmanr(truth, prediction)[0] if np.ptp(prediction) > 0 else np.nan}
    patient = frame["population"] == "patient"
    if patient.any() and (~patient).any():
        row["auc_patient"] = roc_auc_score(~patient, prediction)
        sub = frame[patient]
        row["spearman_patients"] = spearmanr(sub[TARGET], sub[column])[0] if np.ptp(sub[column]) > 0 else np.nan
    return row


def by_repeat(rows, column):
    """O valoare pe repetare, apoi media și abaterea: cât de stabil e rezultatul la o altă împărțire."""
    per_repeat = pd.DataFrame([metrics(group, column) for _, group in rows.groupby("repeat")])
    return per_repeat.mean(), per_repeat.std()


def evaluate(tables):
    jobs = []
    for source in SOURCES:
        for exercise in EXERCISES:
            table = tables[source][tables[source]["exercise"] == exercise].reset_index(drop=True)
            for repeat in range(REPEATS):
                for fold, (train, test) in enumerate(splits(table, OUTER_FOLDS, seed=repeat)):
                    jobs.append(delayed(outer_fold)(source, table, exercise, repeat, fold, train, test))
    print(f"{len(jobs)} grupe exterioare x {len(CANDIDATES)} candidati, in paralel...")
    return pd.concat(Parallel(n_jobs=-1, verbose=0)(jobs), ignore_index=True)


def final_model(source, table, exercise):
    """Aceeași procedură ca în bucla exterioară, pe toate datele: alegerea pe 4 grupe, apoi antrenarea pe tot."""
    scores = inner_scores(table, exercise, seed=0)
    chosen = min(CANDIDATES, key=lambda c: scores[candidate_name(c)])
    features, model, params = chosen
    names = columns(table, exercise, features)
    estimator = build_model(model, params)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        estimator.fit(table[names], table[TARGET])
    path = OUT / f"model_{source}_Es{exercise}"
    joblib.dump(estimator, path.with_suffix(".joblib"))
    path.with_suffix(".json").write_text(json.dumps({
        "source": source, "exercise": exercise, "target": TARGET, "candidate": candidate_name(chosen),
        "features": names, "score_range": SCORE_RANGE, "train_executions": len(table),
        "inner_mae": scores[candidate_name(chosen)]}, indent=2), encoding="utf-8")
    return candidate_name(chosen)


def search():
    OUT.mkdir(parents=True, exist_ok=True)
    tables = load()
    rows = evaluate(tables)
    rows.to_csv(OUT / "predictions.csv", index=False)

    lines, summary, candidates = [], [], []
    for (source, exercise), group in rows.groupby(["source", "exercise"]):
        for column in ["baseline_mean", "baseline_population", "nested"] + [candidate_name(c) for c in CANDIDATES]:
            mean, std = by_repeat(group, column)
            record = {"source": source, "exercise": exercise, "model": column, **mean.add_suffix("").to_dict(),
                      **std.add_suffix("_std").to_dict()}
            (summary if column in ("baseline_mean", "baseline_population", "nested") else candidates).append(record)
    summary, candidates = pd.DataFrame(summary), pd.DataFrame(candidates)
    summary.to_csv(OUT / "summary.csv", index=False)
    candidates.to_csv(OUT / "candidates.csv", index=False)

    lines.append(f"Executii: {len(tables['kinect'])} (aceleasi pe ambele surse), "
                 f"{tables['kinect']['subject'].nunique()} persoane; tinta {TARGET} 0-50")
    lines.append(tables["kinect"].groupby("exercise").size().to_string())
    for source in SOURCES:
        lines.append(f"\n===== {source}: validare imbricata, {REPEATS} repetari x {OUTER_FOLDS} grupe =====")
        part = summary[summary["source"] == source]
        lines.append(part.pivot(index="exercise", columns="model", values="mae").round(2).to_string())
        lines.append("Spearman (nested): " + ", ".join(
            f"Es{r.exercise} {r.spearman:.2f}±{r.spearman_std:.2f}" for r in part[part.model == "nested"].itertuples()))
        lines.append("Spearman doar pacienti (nested): " + ", ".join(
            f"Es{r.exercise} {r.spearman_patients:.2f}" for r in part[part.model == "nested"].itertuples()))
        lines.append("AUC sanatos/pacient (nested): " + ", ".join(
            f"Es{r.exercise} {r.auc_patient:.2f}" for r in part[part.model == "nested"].itertuples()))
        chosen = rows[rows["source"] == source].drop_duplicates(["exercise", "repeat", "fold"])
        lines.append("Alegeri ale buclei interioare (de cate ori din 25):")
        for exercise, group in chosen.groupby("exercise"):
            lines.append(f"  Es{exercise}: " + ", ".join(f"{k} {v}" for k, v in group["chosen"].value_counts().head(4).items()))
        best = candidates[candidates["source"] == source].sort_values("mae").groupby("exercise").head(3)
        lines.append("Cei mai buni candidati ficsi (fara alegere, optimist):")
        lines.append(best[["exercise", "model", "mae", "mae_std", "spearman"]].round(2).to_string(index=False))
        by_set = candidates[candidates["source"] == source].assign(features=lambda d: d.model.str.split("|").str[0])
        lines.append("Cel mai bun MAE pe grup de masuratori:")
        lines.append(by_set.groupby(["exercise", "features"])["mae"].min().unstack().round(2).to_string())

    mp = rows[(rows["source"] == "mediapipe")].copy()
    mp["residual"] = mp["nested"] - mp[TARGET]
    lines.append("\n===== Verificari MediaPipe =====")
    lines.append(f"Spearman(eroare, kept) = {spearmanr(mp['residual'], mp['kept'])[0]:.2f}; "
                 f"Spearman(|eroare|, kept) = {spearmanr(mp['residual'].abs(), mp['kept'])[0]:.2f}")
    mp["kept_band"] = pd.cut(mp["kept"], [0, 0.5, 0.9, 1.01], labels=["<50%", "50-90%", ">=90%"])
    lines.append(mp.groupby("kept_band", observed=True).apply(
        lambda g: pd.Series({"executii": len(g) / REPEATS, "mae": (g["nested"] - g[TARGET]).abs().mean()})).round(2).to_string())
    lines.append(mp.groupby("group").apply(
        lambda g: pd.Series({"mae": (g["nested"] - g[TARGET]).abs().mean(), "bias": (g["nested"] - g[TARGET]).mean()})).round(2).to_string())

    lines.append("\n===== Ce ar alege bucla interioara pe toate datele =====")
    for source in SOURCES:
        for exercise in EXERCISES:
            table = tables[source][tables[source]["exercise"] == exercise].reset_index(drop=True)
            lines.append(f"{source} Es{exercise}: {final_model(source, table, exercise)}")
    report = "\n".join(lines)
    (OUT / "report.txt").write_text(report, encoding="utf-8")
    print(report)


# ---------------------------------------------------------------- sistemul ales

def subject_splits(table, seed):
    """Toate execuțiile unei persoane stau în aceeași grupă; grupele sunt echilibrate pe nivelul scorului."""
    level = table.groupby("subject")[TARGET].transform("mean")
    strata = pd.qcut(level.rank(method="dense"), 4, labels=False)
    splitter = StratifiedGroupKFold(n_splits=OUTER_FOLDS, shuffle=True, random_state=seed)
    for train, test in splitter.split(table, strata, groups=table["subject"]):
        assert not set(table["subject"].iloc[train]) & set(table["subject"].iloc[test])
        yield train, test


def reference_per_exercise(train, test):
    """Referință: un singur gradient boosting pe exercițiu, pe A+B+C (cel mai bun candidat fix din runda 1)."""
    candidate = ("ABC", "boosting", dict(n_estimators=150, learning_rate=0.03, max_depth=2, subsample=0.7))
    out = np.full(len(test), np.nan)
    for exercise in EXERCISES:
        mask = (test["exercise"] == exercise).to_numpy()
        out[mask] = fit_predict(candidate, train[train["exercise"] == exercise], test[mask], exercise)
    return out


def evaluate_fold(source, table, repeat, fold, train_index, test_index):
    train, test = table.iloc[train_index], table.iloc[test_index]
    out = test[["subject", "group", "population", "exercise", "kept", TARGET]].copy()
    out["source"], out["repeat"], out["fold"] = source, repeat, fold
    out["model"] = ClinicalScoreModel(seed=repeat).fit(train).predict(test)
    out["one_boosting_per_exercise"] = reference_per_exercise(train, test)
    out["baseline_mean"] = test["exercise"].map(train.groupby("exercise")[TARGET].mean())
    means = train.groupby(["exercise", "population"])[TARGET].mean()
    out["baseline_population"] = [means[(e, p)] for e, p in zip(test["exercise"], test["population"])]
    return out


def score_table(rows, column):
    """Măsurile pe fiecare (repetare, exercițiu); apoi media pe exercițiu și media ± abaterea între repetări."""
    per = pd.DataFrame([{"repeat": r, "exercise": e, **metrics(g, column)}
                        for (r, e), g in rows.groupby(["repeat", "exercise"])])
    by_exercise = per.groupby("exercise").mean().drop(columns="repeat")
    overall = per.groupby("repeat").mean().drop(columns="exercise")
    return by_exercise, overall.mean(), overall.std()


def main():
    if "--search" in sys.argv:
        return search()
    REPORT.mkdir(parents=True, exist_ok=True)
    tables = load()
    jobs = [delayed(evaluate_fold)(source, tables[source], repeat, fold, train, test)
            for source in SOURCES for repeat in range(REPEATS)
            for fold, (train, test) in enumerate(subject_splits(tables[source], seed=repeat))]
    rows = pd.concat(Parallel(n_jobs=-1)(jobs), ignore_index=True)
    rows.to_csv(REPORT / "predictions.csv", index=False)

    columns = ["baseline_mean", "baseline_population", "one_boosting_per_exercise", "model"]
    lines = [f"Executii: {len(tables['kinect'])} (aceleasi pe ambele surse), {tables['kinect']['subject'].nunique()} "
             f"persoane; tinta {TARGET} 0-50; {REPEATS} repetari x {OUTER_FOLDS} grupe pe persoane",
             "baseline_mean = media scorurilor din antrenare (nu se uita la miscare)",
             "baseline_population = media grupului sanatos/pacient (stie diagnosticul; aplicatia nu il stie)",
             "one_boosting_per_exercise = cel mai bun model simplu din runda 1; model = sistemul ales"]
    for source in SOURCES:
        part = rows[rows["source"] == source]
        lines.append(f"\n===== {source} =====")
        mae, summary = {}, []
        for column in columns:
            by_exercise, mean, std = score_table(part, column)
            mae[column] = by_exercise["mae"]
            summary.append({"model": column, **{k: f"{mean[k]:.2f} +- {std[k]:.2f}" for k in mean.index}})
        lines.append("Eroare medie (MAE, puncte de scor) pe exercitiu:")
        lines.append(pd.DataFrame(mae).round(2).to_string())
        lines.append("Pe toate exercitiile (medie +- abatere intre repetari):")
        lines.append(pd.DataFrame(summary).set_index("model").to_string())

    mp = rows[rows["source"] == "mediapipe"].copy()
    mp["error"] = mp["model"] - mp[TARGET]
    lines.append("\n===== Verificari pe MediaPipe (sistemul ales) =====")
    lines.append(f"Depinde eroarea de calitatea filmarii? Spearman(|eroare|, kept) = "
                 f"{spearmanr(mp['error'].abs(), mp['kept'])[0]:.2f}")
    mp["kept_band"] = pd.cut(mp["kept"], [0, 0.5, 0.9, 1.01], labels=["<50%", "50-90%", ">=90%"], right=False)
    lines.append(mp.groupby("kept_band", observed=True)[["error"]].apply(lambda g: pd.Series({
        "executii": len(g) / REPEATS, "mae": g["error"].abs().mean()})).round(2).to_string())
    lines.append("Pe grup (bias > 0 = scor prezis prea mare):")
    lines.append(mp.groupby("group")[["error", TARGET]].apply(lambda g: pd.Series({
        "executii": len(g) / REPEATS, "scor_real": g[TARGET].mean(), "mae": g["error"].abs().mean(),
        "bias": g["error"].mean()})).round(2).to_string())

    MODELS.mkdir(exist_ok=True)
    lines.append(f"\n===== Modele finale, antrenate pe toate cele {len(tables['kinect'])} executii =====")
    for source in SOURCES:
        model = ClinicalScoreModel(seed=0).fit(tables[source])
        path = MODELS / f"clinical_score_{source}"
        joblib.dump(model, path.with_suffix(".joblib"))
        _, mean, _ = score_table(rows[rows["source"] == source], "model")
        path.with_suffix(".json").write_text(json.dumps({
            "source": source, "target": TARGET, "score_range": SCORE_RANGE, "exercises": EXERCISES,
            "train_executions": len(tables[source]), "cv_mae": round(float(mean["mae"]), 2),
            "cv_spearman": round(float(mean["spearman"]), 2),
            "system": "media dintre un model comun (A+B, gradient boosting) si modelele pe exercitiu "
                      "(A+B+C: gradient boosting, random forest, ridge)"}, indent=2), encoding="utf-8")
        lines.append(str(path.with_suffix(".joblib").relative_to(ROOT)))
    report = "\n".join(lines)
    (REPORT / "report.txt").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
