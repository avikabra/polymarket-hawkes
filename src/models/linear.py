"""Linear baseline model — Ridge regression via sklearn RidgeCV."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import joblib
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold

class LinearModel:
    """Ridge regression wrapper. fit(X, y) then predict(X)."""
    def __init__(self, alphas=None, cv: int = 5):
        if alphas is None:
            alphas = np.logspace(-4, 4, 50)
        self._ridge = RidgeCV(
            alphas=alphas,
            cv=KFold(n_splits=cv, shuffle=False),
            fit_intercept=True,
        )
        self.alpha_: float | None = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LinearModel":
        self._ridge.fit(X, y)
        self.alpha_ = float(self._ridge.alpha_)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self._ridge.predict(X).astype(np.float64)

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, str(path))

    @classmethod
    def load(cls, path: str | Path) -> "LinearModel":
        return joblib.load(str(path))
