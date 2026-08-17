"""
Loads the trained model artifacts once (FastAPI lifespan event) and
exposes scoring + SHAP explanation. Combines the supervised classifier's
probability with the IsolationForest anomaly score using the same
documented weighted-average precedence as ml/train.py, then applies the
same isotonic calibrator fit at training time — this is what "genuine
train/serve parity" means here: the exact same artifacts, the exact same
combination formula, just called once per request instead of once per
batch.
"""
from __future__ import annotations

import json
import logging
import os

import joblib
import numpy as np
import pandas as pd

from . import ml_path  # noqa: F401
from feature_registry import get_feature_names  # noqa: E402

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    pass


class ModelService:
    def __init__(self, model_dir: str) -> None:
        self.model_dir = model_dir
        self.loaded = False
        self.model_version = "unloaded"
        self.feature_names = get_feature_names()

        self.supervised_model = None
        self.isolation_forest = None
        self.calibrator = None
        self.shap_explainer = None
        self.encoders: dict | None = None
        self.receiver_freq: dict | None = None
        self.anomaly_norm: dict | None = None
        self.combination_weights: dict | None = None

    def load(self) -> None:
        d = self.model_dir
        required = [
            "supervised_model.pkl", "isolation_forest.pkl", "calibrator.pkl",
            "shap_explainer.pkl", "categorical_encoders.pkl", "feature_columns.json",
            "receiver_domain_freq.json", "anomaly_norm.json", "combination_weights.json",
            "version.json",
        ]
        missing = [f for f in required if not os.path.exists(os.path.join(d, f))]
        if missing:
            logger.warning(
                "Model artifacts missing (%s) — the API will start but /api/v1/score "
                "will fall back to a rule-based scorer until `python ml/train.py` has "
                "been run. This is a deliberate resilience fallback (checklist 2.10), "
                "not a crash.",
                missing,
            )
            self.loaded = False
            return

        self.supervised_model = joblib.load(os.path.join(d, "supervised_model.pkl"))
        self.isolation_forest = joblib.load(os.path.join(d, "isolation_forest.pkl"))
        self.calibrator = joblib.load(os.path.join(d, "calibrator.pkl"))
        self.shap_explainer = joblib.load(os.path.join(d, "shap_explainer.pkl"))
        self.encoders = joblib.load(os.path.join(d, "categorical_encoders.pkl"))

        with open(os.path.join(d, "feature_columns.json")) as f:
            saved_cols = json.load(f)
        if saved_cols != self.feature_names:
            logger.warning("Saved feature_columns.json differs from the current feature_registry order!")
            self.feature_names = saved_cols

        with open(os.path.join(d, "receiver_domain_freq.json")) as f:
            self.receiver_freq = json.load(f)
        with open(os.path.join(d, "anomaly_norm.json")) as f:
            self.anomaly_norm = json.load(f)
        with open(os.path.join(d, "combination_weights.json")) as f:
            self.combination_weights = json.load(f)
        with open(os.path.join(d, "version.json")) as f:
            version_info = json.load(f)
            self.model_version = version_info.get("model_version", "unknown")

        self.loaded = True
        logger.info("ModelService loaded model_version=%s", self.model_version)

    def _anomaly_risk(self, X: pd.DataFrame) -> np.ndarray:
        lo, hi = self.anomaly_norm["lo"], self.anomaly_norm["hi"]
        raw = self.isolation_forest.score_samples(X)
        norm = np.clip((raw - lo) / (hi - lo + 1e-9), 0.0, 1.0)
        return 1.0 - norm

    def score(self, X: pd.DataFrame) -> tuple[float, dict]:
        """Returns (calibrated_risk_score, debug_components)."""
        if not self.loaded:
            raise ModelNotLoadedError("Model artifacts not loaded")

        supervised_prob = float(self.supervised_model.predict_proba(X)[:, 1][0])
        anomaly_risk = float(self._anomaly_risk(X)[0])
        w_s = self.combination_weights["w_supervised"]
        w_a = self.combination_weights["w_anomaly"]
        combined_raw = w_s * supervised_prob + w_a * anomaly_risk
        calibrated = float(self.calibrator.predict([combined_raw])[0])
        calibrated = max(0.0, min(1.0, calibrated))

        return calibrated, {
            "supervised_prob": supervised_prob,
            "anomaly_risk": anomaly_risk,
            "combined_raw": combined_raw,
            "calibrated": calibrated,
        }

    def explain(self, X: pd.DataFrame, top_k: int = 8) -> dict[str, float]:
        """Real per-transaction SHAP contributions from the TreeExplainer
        fit at training time on the supervised model."""
        if not self.loaded:
            raise ModelNotLoadedError("Model artifacts not loaded")
        shap_values = self.shap_explainer.shap_values(X)
        arr = shap_values[1] if isinstance(shap_values, list) else shap_values
        row = arr[0]
        contributions = {name: float(val) for name, val in zip(self.feature_names, row)}
        top = dict(sorted(contributions.items(), key=lambda kv: -abs(kv[1]))[:top_k])
        return top


_singleton: ModelService | None = None


def get_model_service(model_dir: str | None = None) -> ModelService:
    global _singleton
    if _singleton is None:
        from .config import get_settings

        _singleton = ModelService(model_dir or get_settings().model_dir)
    return _singleton
