#!/usr/bin/env python3
"""
RiskPulse ML training pipeline — checklist items 1.8 + 2.1.

Run: `python ml/train.py` from the repo root (or `python train.py` from
inside ml/). Reads data/raw/{train_transaction,train_identity}.csv,
engineers 40+ features across the 5 required signal families, trains a
supervised classifier + an unsupervised anomaly detector, calibrates the
combined probability, computes real SHAP contributions, reports honest
test-set metrics, and dumps everything the backend needs into
backend/models/.

Pipeline
--------
1. Load + merge (data_loader.py) with memory-safe dtypes.
2. Feature engineering (features.py) — leak-free, chronological single pass.
3. Stratified train/test split (80/20). Train further split into
   train_core/calib (85/15) so calibration never sees SMOTE'd synthetic
   rows or the final test set.
4. SMOTE on train_core only (never on calib, never on test — that would be
   a leakage bug).
5. Supervised model: try XGBoost; if the wheel can't be loaded (a known
   macOS issue — the xgboost dylib needs libomp, normally via
   `brew install libomp`), fall back to
   sklearn.ensemble.GradientBoostingClassifier and say so loudly.
6. Unsupervised model: IsolationForest, fit on train_core's non-fraud rows
   only (standard anomaly-detection practice — model what "normal" looks
   like).
7. Combine supervised probability + normalized anomaly score
   (documented weighted average), then calibrate *that combined score*
   with isotonic regression fit on the held-out calib split.
8. SHAP TreeExplainer on the supervised model; sanity-checked against a
   sample of the test set.
9. Metrics (F1/precision/recall/FPR/confusion matrix) computed on the
   held-out test set using the calibrated combined score at the 0.5
   decision boundary — printed, logged, and written to
   backend/models/metrics.json.
10. Every artifact the API needs at serving time is joblib-dumped into
    backend/models/ (gitignored — trained weights never get committed).
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)  # allow `import feature_registry` etc. when run as a script

from data_loader import load_raw  # noqa: E402
from features import build_features, fit_categorical_encoders, _receiver_id_series  # noqa: E402
from feature_registry import get_feature_names, cold_start_defaults  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ml.train")

# Overridable via env for smoke-testing on a small CSV sample without
# touching the real 683MB dataset or clobbering real trained artifacts.
DATA_DIR = os.environ.get("RISKPULSE_DATA_DIR", os.path.join(REPO_ROOT, "data", "raw"))
MODELS_DIR = os.environ.get("RISKPULSE_MODELS_DIR", os.path.join(REPO_ROOT, "backend", "models"))

# ---- combination weights (documented precedence, checklist 2.1 / 2.4) ----
# Supervised model dominates (it's trained on real fraud labels); the
# Isolation Forest contributes a smaller correction for novel patterns
# that don't resemble anything in the labelled training data.
W_SUPERVISED = 0.85
W_ANOMALY = 0.15

RANDOM_STATE = 42
SMOTE_SAMPLING_STRATEGY = 0.20  # minority raised to 20% of majority in train_core only
DECISION_THRESHOLD_FOR_METRICS = 0.5


def try_import_xgboost():
    """Attempt to import XGBoost. On this dev machine (macOS, no Homebrew
    installed at all — verified via `command -v brew` returning nothing,
    so `brew install libomp` isn't a safe/straightforward one-liner here)
    the compiled xgboost wheel fails to dlopen libomp.dylib. We catch that
    specific failure mode and fall back cleanly rather than crashing the
    whole training run."""
    try:
        import xgboost as xgb  # noqa: F401
        # Smoke-test that the native library actually loads (import can
        # succeed while the C++ lib still fails to dlopen on first use).
        _ = xgb.XGBClassifier(n_estimators=1, max_depth=1).get_params()
        return xgb
    except Exception as e:  # noqa: BLE001 - deliberately broad, see docstring
        logger.warning(
            "XGBoost unavailable (%s: %s). Falling back to "
            "sklearn.ensemble.GradientBoostingClassifier as explicitly "
            "instructed. Root cause on this machine: the xgboost wheel "
            "needs libomp.dylib, and Homebrew itself is not installed "
            "(`brew` not on PATH), so `brew install libomp` is not a "
            "straightforward fix here without a much larger, unrequested "
            "system change. This is a real, documented limitation, not a "
            "silently-swallowed failure.",
            type(e).__name__, e,
        )
        return None


def build_receiver_domain_freq_table(df: pd.DataFrame, top_n: int = 500) -> dict:
    """Static receiver-domain -> population frequency lookup for online
    serving (the backend can't replay the whole training set per request).
    Unseen domains at serving time fall back to a documented default."""
    receiver_ids = _receiver_id_series(df)
    counts = receiver_ids.value_counts()
    total = len(receiver_ids)
    top = counts.head(top_n)
    table = {str(k): float(v) / total for k, v in top.items()}
    default = 1.0 / total  # treat an unseen domain like something seen once
    return {"table": table, "default": default}


def main() -> None:
    t0 = time.time()
    os.makedirs(MODELS_DIR, exist_ok=True)

    logger.info("=== RiskPulse ML training pipeline ===")
    logger.info("Data dir: %s", DATA_DIR)
    logger.info("Models output dir: %s", MODELS_DIR)

    # ---------------------------------------------------------------
    # 1. Load
    # ---------------------------------------------------------------
    df = load_raw(DATA_DIR)
    n_rows = len(df)
    fraud_rate = df["isFraud"].mean()
    logger.info("Loaded %d transactions. Fraud rate: %.4f (%d fraud)", n_rows, fraud_rate, int(df["isFraud"].sum()))

    # ---------------------------------------------------------------
    # 2. Feature engineering
    # ---------------------------------------------------------------
    encoders = fit_categorical_encoders(df)
    receiver_freq_table = build_receiver_domain_freq_table(df)
    X = build_features(df, encoders)
    y = df["isFraud"].to_numpy(dtype=np.int8)
    del df

    feature_names = get_feature_names()
    assert list(X.columns) == feature_names, "feature order mismatch with registry"
    logger.info("Feature matrix: %s", X.shape)

    # ---------------------------------------------------------------
    # 3. Stratified split: 80% train (further split into train_core/calib), 20% test
    # ---------------------------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE,
    )
    X_core, X_calib, y_core, y_calib = train_test_split(
        X_train, y_train, test_size=0.15, stratify=y_train, random_state=RANDOM_STATE,
    )
    logger.info(
        "Split sizes -> train_core=%d (fraud=%d), calib=%d (fraud=%d), test=%d (fraud=%d)",
        len(X_core), int(y_core.sum()), len(X_calib), int(y_calib.sum()), len(X_test), int(y_test.sum()),
    )

    # ---------------------------------------------------------------
    # 4. SMOTE — train_core only
    # ---------------------------------------------------------------
    from imblearn.over_sampling import SMOTE

    logger.info("Applying SMOTE (sampling_strategy=%.2f) to train_core only...", SMOTE_SAMPLING_STRATEGY)
    smote = SMOTE(sampling_strategy=SMOTE_SAMPLING_STRATEGY, random_state=RANDOM_STATE)
    X_core_res, y_core_res = smote.fit_resample(X_core, y_core)
    logger.info(
        "Post-SMOTE train_core: %d rows (fraud=%d, %.2f%%)",
        len(X_core_res), int(y_core_res.sum()), 100 * y_core_res.mean(),
    )

    # ---------------------------------------------------------------
    # 5. Supervised model
    # ---------------------------------------------------------------
    xgb = try_import_xgboost()
    if xgb is not None:
        model_type = "xgboost"
        scale_pos_weight = float((y_core_res == 0).sum() / max(1, (y_core_res == 1).sum()))
        clf = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=-1,
        )
        logger.info("Training XGBoost classifier...")
        clf.fit(X_core_res, y_core_res)
    else:
        model_type = "gradient_boosting"
        clf = GradientBoostingClassifier(
            n_estimators=120, max_depth=4, learning_rate=0.1,
            subsample=0.6, random_state=RANDOM_STATE, verbose=1,
        )
        logger.info(
            "Training sklearn GradientBoostingClassifier (XGBoost fallback). "
            "n_estimators=120 max_depth=4 subsample=0.6 — tuned down from a "
            "larger grid to fit a hackathon compute/time budget on this "
            "8GB, 8-core dev machine; SMOTE (not scale_pos_weight, which "
            "GradientBoostingClassifier doesn't expose) is the imbalance "
            "handling mechanism for this fallback path."
        )
        clf.fit(X_core_res, y_core_res)
    logger.info("Supervised model trained: %s", model_type)

    # ---------------------------------------------------------------
    # 6. Unsupervised anomaly model — fit on train_core's non-fraud rows only
    # ---------------------------------------------------------------
    logger.info("Training IsolationForest on train_core non-fraud rows...")
    iso = IsolationForest(
        n_estimators=100, contamination="auto", random_state=RANDOM_STATE, n_jobs=-1,
    )
    iso.fit(X_core[y_core == 0])

    def anomaly_risk(X_frame: pd.DataFrame, lo: float, hi: float) -> np.ndarray:
        raw = iso.score_samples(X_frame)  # lower = more anomalous
        norm = (raw - lo) / (hi - lo + 1e-9)
        norm = np.clip(norm, 0.0, 1.0)
        return 1.0 - norm  # invert: higher risk = more anomalous

    iso_scores_core = iso.score_samples(X_core)
    lo, hi = float(np.percentile(iso_scores_core, 1)), float(np.percentile(iso_scores_core, 99))
    logger.info("IsolationForest score normalization bounds: lo=%.4f hi=%.4f (1st/99th pct on train_core)", lo, hi)

    # ---------------------------------------------------------------
    # 7. Combine + calibrate (on the held-out calib split, never SMOTE'd)
    # ---------------------------------------------------------------
    def supervised_prob(X_frame: pd.DataFrame) -> np.ndarray:
        return clf.predict_proba(X_frame)[:, 1]

    def combined_raw(X_frame: pd.DataFrame) -> np.ndarray:
        return W_SUPERVISED * supervised_prob(X_frame) + W_ANOMALY * anomaly_risk(X_frame, lo, hi)

    combined_calib_raw = combined_raw(X_calib)
    logger.info("Fitting isotonic calibration on combined (supervised + anomaly) score, held-out calib split...")
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(combined_calib_raw, y_calib)

    # ---------------------------------------------------------------
    # 8. SHAP sanity check
    # ---------------------------------------------------------------
    import shap

    logger.info("Building SHAP TreeExplainer and sanity-checking on a sample of the test set...")
    explainer = shap.TreeExplainer(clf)
    sample_n = min(200, len(X_test))
    shap_sample = explainer.shap_values(X_test.iloc[:sample_n])
    shap_arr = shap_sample[1] if isinstance(shap_sample, list) else shap_sample
    assert shap_arr.shape[0] == sample_n and shap_arr.shape[1] == X.shape[1], "unexpected SHAP output shape"
    logger.info(
        "SHAP OK: produced per-transaction contributions for %d sample rows x %d features. "
        "Mean |SHAP| top-5 features: %s",
        sample_n, shap_arr.shape[1],
        {feature_names[i]: round(float(v), 4) for i, v in
         sorted(enumerate(np.abs(shap_arr).mean(axis=0)), key=lambda kv: -kv[1])[:5]},
    )

    # ---------------------------------------------------------------
    # 9. Honest test-set metrics
    # ---------------------------------------------------------------
    combined_test_raw = combined_raw(X_test)
    calibrated_test = calibrator.predict(combined_test_raw)
    y_pred = (calibrated_test >= DECISION_THRESHOLD_FOR_METRICS).astype(int)

    f1 = f1_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    logger.info("=== HELD-OUT TEST SET METRICS (honest, threshold=%.2f) ===", DECISION_THRESHOLD_FOR_METRICS)
    logger.info("F1        = %.4f", f1)
    logger.info("Precision = %.4f", precision)
    logger.info("Recall    = %.4f", recall)
    logger.info("FPR       = %.4f", fpr)
    logger.info("Confusion matrix [[TN FP][FN TP]] = [[%d %d][%d %d]]", tn, fp, fn, tp)
    print("\n=== RiskPulse — held-out test set metrics ===")
    print(f"Model type : {model_type}")
    print(f"F1         : {f1:.4f}")
    print(f"Precision  : {precision:.4f}")
    print(f"Recall     : {recall:.4f}")
    print(f"FPR        : {fpr:.4f}")
    print(f"Confusion matrix: TN={tn} FP={fp} FN={fn} TP={tp}\n")

    # ---------------------------------------------------------------
    # 10. Persist everything the backend needs
    # ---------------------------------------------------------------
    trained_at = datetime.now(timezone.utc).isoformat()
    version = "v_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    joblib.dump(clf, os.path.join(MODELS_DIR, "supervised_model.pkl"))
    joblib.dump(iso, os.path.join(MODELS_DIR, "isolation_forest.pkl"))
    joblib.dump(calibrator, os.path.join(MODELS_DIR, "calibrator.pkl"))
    joblib.dump(explainer, os.path.join(MODELS_DIR, "shap_explainer.pkl"))
    joblib.dump(encoders, os.path.join(MODELS_DIR, "categorical_encoders.pkl"))

    with open(os.path.join(MODELS_DIR, "feature_columns.json"), "w") as f:
        json.dump(feature_names, f, indent=2)
    with open(os.path.join(MODELS_DIR, "cold_start_defaults.json"), "w") as f:
        json.dump(cold_start_defaults(), f, indent=2)
    with open(os.path.join(MODELS_DIR, "receiver_domain_freq.json"), "w") as f:
        json.dump(receiver_freq_table, f)
    with open(os.path.join(MODELS_DIR, "anomaly_norm.json"), "w") as f:
        json.dump({"lo": lo, "hi": hi}, f)
    with open(os.path.join(MODELS_DIR, "combination_weights.json"), "w") as f:
        json.dump({"w_supervised": W_SUPERVISED, "w_anomaly": W_ANOMALY}, f)
    with open(os.path.join(MODELS_DIR, "version.json"), "w") as f:
        json.dump({
            "model_version": version,
            "trained_at": trained_at,
            "model_type": model_type,
            "n_features": len(feature_names),
            "n_train_rows": int(len(X_core_res)),
            "n_test_rows": int(len(X_test)),
            "dataset_rows_total": int(n_rows),
            "fraud_rate": float(fraud_rate),
            "decision_threshold_used_for_metrics": DECISION_THRESHOLD_FOR_METRICS,
        }, f, indent=2)
    with open(os.path.join(MODELS_DIR, "metrics.json"), "w") as f:
        json.dump({
            "model_version": version,
            "trained_at": trained_at,
            "model_type": model_type,
            "f1": float(f1),
            "precision": float(precision),
            "recall": float(recall),
            "false_positive_rate": float(fpr),
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "decision_threshold": DECISION_THRESHOLD_FOR_METRICS,
            "n_test_rows": int(len(X_test)),
            "test_fraud_count": int(y_test.sum()),
        }, f, indent=2)

    elapsed = time.time() - t0
    logger.info("All artifacts written to %s", MODELS_DIR)
    logger.info("Training pipeline complete in %.1f minutes.", elapsed / 60)


if __name__ == "__main__":
    main()
