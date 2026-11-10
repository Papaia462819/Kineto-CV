"""Modelul de scor clinic (E7): din rândul-rezumat al unei execuții, un scor KIMORE 0–50.

Scorul final e media a două păreri:
1. Un model comun pentru toate exercițiile (gradient boosting), antrenat pe toate execuțiile, pe grupurile A și B
   (aceleași nume la orice exercițiu) plus exercițiul ca indicator. Vede de 5 ori mai multe date.
2. Un model pe exercițiu, pe grupurile A, B și C (C diferă de la un exercițiu la altul): media dintre
   gradient boosting, random forest și ridge. Trei modele diferite greșesc diferit, iar media le liniștește.

De ce așa: pe KIMORE, combinația a avut eroarea cea mai mică și cea mai stabilă între împărțiri
(vezi scripts/train_clinical_score.py și data/clinical_score/report.txt).
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.clinical_features import clinical_feature_names
from src.execution_features import FEATURE_NAMES, REPETITION_NAMES

EXERCISES = [1, 2, 3, 4, 5]
SCORE_RANGE = (0.0, 50.0)
POOLED_COLUMNS = FEATURE_NAMES + [c for c in REPETITION_NAMES if c != "rep__asymmetry"]


def _pipeline(estimator):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), estimator)


def _boosting(seed, n_estimators=150, max_depth=2):
    return _pipeline(GradientBoostingRegressor(n_estimators=n_estimators, learning_rate=0.03, max_depth=max_depth,
                                               subsample=0.7, random_state=seed))


def _per_exercise_models(seed):
    return [_boosting(seed),
            _pipeline(RandomForestRegressor(n_estimators=150, min_samples_leaf=3, max_features=0.3,
                                            random_state=seed, n_jobs=1)),
            _pipeline(Ridge(alpha=100))]


def per_exercise_columns(exercise):
    return FEATURE_NAMES + REPETITION_NAMES + clinical_feature_names(exercise)


def _pooled_matrix(table):
    indicator = pd.DataFrame({f"exercise_{e}": (table["exercise"] == e).astype(float) for e in EXERCISES},
                             index=table.index)
    return pd.concat([table[POOLED_COLUMNS], indicator], axis=1)


class ClinicalScoreModel:
    def __init__(self, seed=0):
        self.seed = seed
        self.pooled = None
        self.per_exercise = {}  # exercițiu → (coloane, [modele])

    def fit(self, table, target="score_total"):
        """table: un rând pe execuție, cu coloanele A, B, C, `exercise` și scorul."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.pooled = _boosting(self.seed, n_estimators=300, max_depth=3)
            self.pooled.fit(_pooled_matrix(table), table[target])
            for exercise, part in table.groupby("exercise"):
                # O coloană fără nicio valoare (de ex. simetria la exercițiile fără pereche) nu poate ajuta.
                columns = [c for c in per_exercise_columns(exercise) if part[c].notna().any()]
                models = _per_exercise_models(self.seed)
                for model in models:
                    model.fit(part[columns], part[target])
                self.per_exercise[int(exercise)] = (columns, models)
        return self

    def predict(self, table):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pooled = self.pooled.predict(_pooled_matrix(table))
            own = np.full(len(table), np.nan)
            for exercise, part in table.groupby("exercise"):
                columns, models = self.per_exercise[int(exercise)]
                position = table.index.get_indexer(part.index)
                own[position] = np.mean([m.predict(part[columns]) for m in models], axis=0)
        return np.clip((pooled + own) / 2, *SCORE_RANGE)
