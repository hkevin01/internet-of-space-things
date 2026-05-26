"""
xgboost_pipeline.py - XGBoost Feature Engineering & Hyperparameter Tuning Pipeline
=====================================================================================
ID: ML-010
Requirement: Train an XGBoost gradient-boosted tree model for satellite component
             RUL prediction with full feature engineering, time-series cross-
             validation, and automated hyperparameter tuning via randomized search.
Purpose: Provide an interpretable, fast-inference alternative to LSTM that runs on
         minimal hardware without a GPU. XGBoost tree models produce SHAP-
         explainable feature importances useful for root-cause analysis.
Rationale: XGBoost achieves near-LSTM accuracy on structured telemetry with
           engineered features (rolling statistics, lag features, FFT magnitudes).
           Its inference latency (<1ms) suits hard real-time satellite control loops.
Inputs: List of FailureSample from lstm_training_pipeline or any compatible source.
Outputs: Trained XGBoostRULPredictor callable with best hyperparameters and metrics.
Preconditions: numpy available; xgboost and scikit-learn optional (fallback included).
Failure Modes: Degrades to median-based naive predictor when xgboost unavailable.
Verification: RMSE <= 80h on synthetic battery test set; hyperparameter search
              completes in < 5 min for n_iter=20, 5-fold time-series CV.
References: MDPI Applied Sciences 15(9):4898, XGBoost paper arXiv:1603.02754
"""

import logging
import random
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
    logger.info("XGBoost %s available.", xgb.__version__)
except ImportError:
    _XGB_AVAILABLE = False
    logger.warning(
        "xgboost not installed. XGBoostRULPredictor will use a median baseline. "
        "Install with: pip install xgboost>=2.0"
    )

try:
    from sklearn.model_selection import ParameterSampler, TimeSeriesSplit
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not found - simplified CV used.")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class XGBConfig:
    """
    ID: ML-010-A
    Purpose: XGBoost training configuration with hyperparameter search space.
    """
    # Fixed settings
    n_iter_search: int = 20          # Random search iterations
    cv_folds: int = 5                # TimeSeriesSplit folds
    early_stopping_rounds: int = 20
    eval_metric: str = "rmse"
    seed: int = 42

    # Hyperparameter search space
    param_space: Dict[str, Any] = field(default_factory=lambda: {
        "n_estimators":   [200, 400, 600, 800, 1000],
        "max_depth":      [3, 4, 5, 6, 7, 8],
        "learning_rate":  [0.01, 0.02, 0.05, 0.1, 0.15, 0.2],
        "subsample":      [0.6, 0.7, 0.8, 0.9, 1.0],
        "colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
        "min_child_weight": [1, 3, 5, 7, 10],
        "gamma":          [0, 0.1, 0.3, 0.5, 1.0],
        "reg_alpha":      [0, 0.01, 0.1, 1.0],
        "reg_lambda":     [0.1, 1.0, 5.0, 10.0],
    })

    # Feature engineering settings
    rolling_windows: List[int] = field(default_factory=lambda: [5, 10, 20, 50])
    lag_steps: List[int] = field(default_factory=lambda: [1, 3, 5, 10])
    n_fft_components: int = 5


@dataclass
class XGBTrainingResult:
    """
    ID: ML-010-B
    Purpose: Container for XGBoost training outcome and evaluation metrics.
    """
    best_params: Dict[str, Any]
    feature_names: List[str]
    train_rmse: float
    test_rmse: float
    test_mae: float
    test_r2: float
    feature_importances: Dict[str, float]
    cv_scores: List[float]
    n_features_engineered: int


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

class XGBFeatureEngineer:
    """
    ID: ML-011
    Requirement: Engineer a rich feature set from raw telemetry for XGBoost:
      1. Rolling statistics (mean, std, min, max, skewness) per sensor.
      2. Lag features (values at t-1, t-3, t-5, t-10 timesteps).
      3. Rate-of-change features (delta between consecutive readings).
      4. FFT magnitude of the top-n frequency components per sensor.
      5. Cross-feature interactions (ratios of key sensor pairs).
    Purpose: Transform raw sensor readings into structured features that capture
             both instantaneous state and temporal trend information - compensating
             for the lack of recurrent state in tree models.
    Side Effects: Stores column order for inference-time consistency.
    Failure Modes: NaN values from partial windows are zero-filled.
    """

    def __init__(self, config: XGBConfig):
        self.config = config
        self.raw_feature_names: List[str] = []
        self.engineered_feature_names: List[str] = []
        self._fitted = False

    def fit_transform(
        self, raw_features: np.ndarray, feature_names: List[str]
    ) -> np.ndarray:
        """
        ID: ML-011-A
        Requirement: Fit feature column names and compute all engineered features.
        Inputs:
          - raw_features: shape (n_samples, n_raw_features) float32 array
          - feature_names: column labels for raw_features
        Outputs: Engineered feature matrix shape (n_samples, n_engineered_features).
        """
        self.raw_feature_names = feature_names
        eng = self._compute_features(raw_features)
        self.engineered_feature_names = self._build_names(feature_names, raw_features.shape)
        self._fitted = True
        return eng

    def transform(self, raw_features: np.ndarray) -> np.ndarray:
        """
        ID: ML-011-B
        Purpose: Apply same feature engineering to new samples at inference time.
        Preconditions: fit_transform() called first.
        """
        if not self._fitted:
            raise RuntimeError("Call fit_transform() before transform().")
        return self._compute_features(raw_features)

    def _compute_features(self, X: np.ndarray) -> np.ndarray:
        """
        ID: ML-011-C
        Purpose: Core feature computation. All features concatenated column-wise.
        """
        n, f = X.shape
        parts: List[np.ndarray] = [X]  # Raw features always first

        # ---- Rolling statistics ----
        for w in self.config.rolling_windows:
            if w >= n:
                w = max(1, n - 1)
            for stat in ("mean", "std", "min", "max"):
                rolled = self._rolling(X, w, stat)
                parts.append(rolled)

            # Rolling skewness (3rd standardized moment)
            parts.append(self._rolling_skew(X, w))

        # ---- Lag features ----
        for lag in self.config.lag_steps:
            if lag < n:
                lagged = np.vstack([np.zeros((lag, f)), X[:-lag]])
                parts.append(lagged)

        # ---- Rate-of-change ----
        delta = np.vstack([np.zeros((1, f)), np.diff(X, axis=0)])
        parts.append(delta)
        # Second derivative (acceleration of change)
        delta2 = np.vstack([np.zeros((1, f)), np.diff(delta, axis=0)])
        parts.append(delta2)

        # ---- FFT frequency magnitudes ----
        n_fft = self.config.n_fft_components
        fft_feats = np.zeros((n, f * n_fft), dtype=np.float32)
        for col in range(f):
            fft_vals = np.abs(np.fft.rfft(X[:, col]))
            # rfft may produce fewer than n_fft+1 components on short signals
            available = min(n_fft, len(fft_vals) - 1)
            top_k = np.zeros(n_fft, dtype=np.float32)
            if available > 0:
                top_k[:available] = fft_vals[1: available + 1]
            # Broadcast same FFT values to all rows (global property of signal)
            fft_feats[:, col * n_fft: (col + 1) * n_fft] = top_k
        parts.append(fft_feats)

        # ---- Cross-feature ratios (all pairs with safety clamp) ----
        ratio_cols: List[np.ndarray] = []
        for i in range(f):
            for j in range(i + 1, f):
                denom = np.where(np.abs(X[:, j]) > 1e-6, X[:, j], 1e-6)
                ratio_cols.append((X[:, i] / denom).reshape(-1, 1))
        if ratio_cols:
            parts.append(np.hstack(ratio_cols))

        result = np.hstack(parts)
        # Replace NaN/Inf from rolling std on constant signals
        result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
        return result.astype(np.float32)

    # ---- Internal helpers ----

    def _rolling(self, X: np.ndarray, w: int, stat: str) -> np.ndarray:
        """
        ID: ML-011-D
        Purpose: Compute causal rolling statistic without future leakage.
        """
        n, f = X.shape
        out = np.zeros_like(X)
        for i in range(n):
            start = max(0, i - w + 1)
            window = X[start: i + 1]
            if stat == "mean":
                out[i] = window.mean(axis=0)
            elif stat == "std":
                out[i] = window.std(axis=0) if len(window) > 1 else 0.0
            elif stat == "min":
                out[i] = window.min(axis=0)
            elif stat == "max":
                out[i] = window.max(axis=0)
        return out

    def _rolling_skew(self, X: np.ndarray, w: int) -> np.ndarray:
        """
        ID: ML-011-E
        Purpose: Compute causal rolling skewness (3rd standardized moment).
        """
        n, f = X.shape
        out = np.zeros_like(X)
        for i in range(n):
            start = max(0, i - w + 1)
            window = X[start: i + 1]
            if len(window) < 3:
                continue
            mu = window.mean(axis=0)
            sigma = window.std(axis=0)
            sigma = np.where(sigma > 1e-8, sigma, 1e-8)
            skew = ((window - mu) ** 3).mean(axis=0) / (sigma ** 3)
            out[i] = skew
        return out

    def _build_names(self, raw_names: List[str], shape: Tuple[int, int]) -> List[str]:
        """
        ID: ML-011-F
        Purpose: Build descriptive column names for the engineered feature matrix.
        """
        names: List[str] = list(raw_names)
        f = shape[1]
        for w in self.config.rolling_windows:
            for stat in ("mean", "std", "min", "max"):
                names += [f"{n}_roll{w}_{stat}" for n in raw_names]
            names += [f"{n}_roll{w}_skew" for n in raw_names]
        for lag in self.config.lag_steps:
            names += [f"{n}_lag{lag}" for n in raw_names]
        names += [f"{n}_delta1" for n in raw_names]
        names += [f"{n}_delta2" for n in raw_names]
        for col_name in raw_names:
            for k in range(self.config.n_fft_components):
                names.append(f"{col_name}_fft_c{k+1}")
        for i in range(f):
            for j in range(i + 1, f):
                names.append(f"{raw_names[i]}_div_{raw_names[j]}")
        return names


# ---------------------------------------------------------------------------
# Hyperparameter tuning
# ---------------------------------------------------------------------------

class XGBHyperparamTuner:
    """
    ID: ML-012
    Requirement: Perform randomized hyperparameter search over the XGBConfig
                 param_space using time-series cross-validation to prevent
                 future data leakage. Select params minimizing mean CV RMSE.
    Purpose: Automated search prevents manual trial-and-error and ensures
             robustness of model performance across different failure modes.
    Side Effects: Logs each trial's CV RMSE; may take several minutes.
    """

    def __init__(self, config: XGBConfig):
        self.config = config
        self.best_params: Dict[str, Any] = {}
        self.cv_scores: List[float] = []

    def search(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        ID: ML-012-A
        Requirement: Run n_iter_search random trials; return best params.
        Inputs:
          - X: engineered feature matrix (n_samples, n_features)
          - y: RUL labels in hours (n_samples,)
        Outputs: dict of best XGBoost hyperparameters.
        """
        if not _XGB_AVAILABLE:
            logger.warning("XGBoost unavailable - returning default params.")
            return {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.1}

        # Subsample parameter combinations
        param_list = list(ParameterSampler(
            self.config.param_space,
            n_iter=self.config.n_iter_search,
            random_state=self.config.seed,
        )) if _SKLEARN_AVAILABLE else [
            {k: random.choice(v) for k, v in self.config.param_space.items()}
            for _ in range(self.config.n_iter_search)
        ]

        best_rmse = float("inf")
        best_p: Dict[str, Any] = {}

        for trial_idx, params in enumerate(param_list):
            cv_rmse = self._cv_score(X, y, params)
            self.cv_scores.append(cv_rmse)
            logger.debug("Trial %02d/%02d RMSE=%.2f params=%s",
                         trial_idx + 1, len(param_list), cv_rmse, params)
            if cv_rmse < best_rmse:
                best_rmse = cv_rmse
                best_p = dict(params)

        self.best_params = best_p
        logger.info(
            "Hyperparameter search done. Best CV RMSE=%.2f, params=%s",
            best_rmse, best_p,
        )
        return best_p

    def _cv_score(
        self, X: np.ndarray, y: np.ndarray, params: Dict[str, Any]
    ) -> float:
        """
        ID: ML-012-B
        Purpose: Score a parameter set using time-series k-fold cross-validation.
        Returns: Mean RMSE across folds (hours).
        """
        n = len(X)
        fold_size = n // (self.config.cv_folds + 1)
        rmses: List[float] = []

        for fold in range(1, self.config.cv_folds + 1):
            split = fold * fold_size
            if split >= n:
                break
            X_tr, y_tr = X[:split], y[:split]
            X_vl, y_vl = X[split: split + fold_size], y[split: split + fold_size]
            if len(X_vl) == 0:
                continue

            model = xgb.XGBRegressor(
                **params,
                early_stopping_rounds=self.config.early_stopping_rounds,
                eval_metric=self.config.eval_metric,
                verbosity=0,
                random_state=self.config.seed,
            )
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_vl, y_vl)],
                verbose=False,
            )
            preds = model.predict(X_vl)
            rmse = float(np.sqrt(np.mean((preds - y_vl) ** 2)))
            rmses.append(rmse)

        return float(np.mean(rmses)) if rmses else float("inf")


# ---------------------------------------------------------------------------
# Main XGBoost RUL predictor
# ---------------------------------------------------------------------------

class XGBoostRULPredictor:
    """
    ID: ML-010
    Requirement: Full XGBoost RUL prediction pipeline - feature engineering,
                 hyperparameter tuning, training, evaluation, and inference.
    Purpose: Production-ready XGBoost predictor for satellite component RUL.
    Preconditions: FailureSample list from lstm_training_pipeline.py.
    Postconditions: Trained model callable via predict(); metrics available.
    Failure Modes: Falls back to median prediction when xgboost is unavailable.
    Verification: RMSE and MAE reported on held-out test set after training.
    """

    def __init__(self, config: Optional[XGBConfig] = None):
        self.config = config or XGBConfig()
        self.feature_engineer = XGBFeatureEngineer(self.config)
        self.tuner = XGBHyperparamTuner(self.config)
        self._model: Any = None
        self._median_fallback: float = 500.0
        self._raw_feature_names: List[str] = []

    def train(
        self,
        samples: List[Any],
        tune_hyperparams: bool = True,
    ) -> XGBTrainingResult:
        """
        ID: ML-013
        Requirement: Full training: split, engineer, optionally tune, train, evaluate.
        Inputs:
          - samples: FailureSample list (min 200 recommended)
          - tune_hyperparams: if True, run randomized CV search first
        Outputs: XGBTrainingResult with metrics and feature importances.
        """
        if not samples:
            return XGBTrainingResult(
                best_params={}, feature_names=[], train_rmse=0,
                test_rmse=0, test_mae=0, test_r2=0,
                feature_importances={}, cv_scores=[], n_features_engineered=0,
            )

        # Extract raw feature matrix and labels
        feat_names = sorted(samples[0].features.keys())
        self._raw_feature_names = feat_names
        X_raw = np.array(
            [[s.features[f] for f in feat_names] for s in samples],
            dtype=np.float32,
        )
        y = np.array([s.rul_hours for s in samples], dtype=np.float32)

        # Component-level train/test split (no leakage)
        comp_ids = list({s.component_id for s in samples})
        random.shuffle(comp_ids)
        n_test = max(1, int(len(comp_ids) * 0.2))
        test_ids = set(comp_ids[:n_test])

        idx_train = [i for i, s in enumerate(samples) if s.component_id not in test_ids]
        idx_test = [i for i, s in enumerate(samples) if s.component_id in test_ids]

        X_raw_train, y_train = X_raw[idx_train], y[idx_train]
        X_raw_test, y_test = X_raw[idx_test], y[idx_test]

        # Feature engineering
        X_eng_train = self.feature_engineer.fit_transform(X_raw_train, feat_names)
        X_eng_test = self.feature_engineer.transform(X_raw_test)

        self._median_fallback = float(np.median(y_train))

        if not _XGB_AVAILABLE:
            return XGBTrainingResult(
                best_params={}, feature_names=feat_names,
                train_rmse=float(np.std(y_train)),
                test_rmse=float(np.std(y_test)),
                test_mae=float(np.std(y_test)),
                test_r2=0.0,
                feature_importances={},
                cv_scores=[],
                n_features_engineered=X_eng_train.shape[1],
            )

        # Hyperparameter search
        best_params = {}
        cv_scores: List[float] = []
        if tune_hyperparams and len(X_eng_train) > 100:
            best_params = self.tuner.search(X_eng_train, y_train)
            cv_scores = self.tuner.cv_scores
        else:
            best_params = {
                "n_estimators": 400, "max_depth": 5,
                "learning_rate": 0.05, "subsample": 0.8,
                "colsample_bytree": 0.8, "min_child_weight": 5,
                "gamma": 0.1, "reg_alpha": 0.1, "reg_lambda": 1.0,
            }

        # Final training on full train set
        n_val = max(10, int(len(X_eng_train) * 0.1))
        X_val_final, y_val_final = X_eng_train[-n_val:], y_train[-n_val:]
        X_tr_final, y_tr_final = X_eng_train[:-n_val], y_train[:-n_val]

        model = xgb.XGBRegressor(
            **best_params,
            early_stopping_rounds=self.config.early_stopping_rounds,
            eval_metric=self.config.eval_metric,
            verbosity=0,
            random_state=self.config.seed,
        )
        model.fit(
            X_tr_final, y_tr_final,
            eval_set=[(X_val_final, y_val_final)],
            verbose=False,
        )
        self._model = model

        # Evaluation metrics
        train_preds = model.predict(X_eng_train)
        test_preds = model.predict(X_eng_test)

        def _rmse(a, b):
            return float(np.sqrt(np.mean((a - b) ** 2)))

        def _r2(a, b):
            ss_res = np.sum((b - a) ** 2)
            ss_tot = np.sum((b - b.mean()) ** 2)
            return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        train_rmse = _rmse(train_preds, y_train)
        test_rmse = _rmse(test_preds, y_test)
        test_mae = float(np.mean(np.abs(test_preds - y_test)))
        test_r2 = _r2(test_preds, y_test)

        # Feature importance (gain-based)
        eng_names = self.feature_engineer.engineered_feature_names
        importances = dict(zip(
            eng_names[:len(model.feature_importances_)],
            [float(x) for x in model.feature_importances_],
        ))
        top_feats = sorted(importances.items(), key=lambda x: -x[1])[:10]
        logger.info(
            "XGBoost training complete | train_RMSE=%.1f test_RMSE=%.1f "
            "test_MAE=%.1f test_R2=%.3f | Top features: %s",
            train_rmse, test_rmse, test_mae, test_r2,
            [(n[:30], f"{v:.4f}") for n, v in top_feats],
        )

        return XGBTrainingResult(
            best_params=best_params,
            feature_names=eng_names,
            train_rmse=train_rmse,
            test_rmse=test_rmse,
            test_mae=test_mae,
            test_r2=test_r2,
            feature_importances=importances,
            cv_scores=cv_scores,
            n_features_engineered=X_eng_train.shape[1],
        )

    def predict(self, samples: List[Any]) -> List[float]:
        """
        ID: ML-014
        Requirement: Predict RUL hours for new samples using trained model.
        Inputs: samples - FailureSample list (at least 1 sample).
        Outputs: list of predicted RUL hours.
        Preconditions: train() called successfully.
        Error Handling: Returns median fallback list when model unavailable.
        """
        if not samples:
            return []
        feat_names = self._raw_feature_names or sorted(samples[0].features.keys())
        X_raw = np.array(
            [[s.features.get(f, 0.0) for f in feat_names] for s in samples],
            dtype=np.float32,
        )
        X_eng = self.feature_engineer.transform(X_raw)

        if _XGB_AVAILABLE and self._model is not None:
            return [float(max(0.0, v)) for v in self._model.predict(X_eng)]
        return [self._median_fallback] * len(samples)
