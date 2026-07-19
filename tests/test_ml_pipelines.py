"""
test_ml_pipelines.py - Unit and integration tests for ML pipelines
===================================================================
ID: TEST-ML-001
Requirement: Verify all four ML pipeline modules function correctly
             with synthetic data, including fallback behavior when
             optional dependencies (TensorFlow, XGBoost, PyTorch) are absent.
"""

import math
import pytest
import numpy as np
from datetime import datetime, timedelta
from typing import List
from pathlib import Path
import warnings

from src.cehsn import (
    FailureDataGenerator, FailureSample, LSTMTrainingPipeline, TrainingConfig,
    XGBoostRULPredictor, XGBConfig,
    RLResourceOptimizer, MissionState, SpaceMissionEnv, ResourceAllocation,
    FederatedAggregationServer, SimulatedSatelliteClient, ClientUpdate,
    MissionBenchmarkGenerator, MissionProfile, RULPredictor, HealthMetric,
    PredictiveMaintenanceEngine,
)


# ---------------------------------------------------------------------------
# LSTM pipeline tests
# ---------------------------------------------------------------------------

class TestLSTMPipeline:
    """Tests for lstm_training_pipeline.py"""

    def _make_samples(self, n_components=3, max_rul=100):
        gen = FailureDataGenerator()
        return gen.generate_component_dataset(
            "battery", n_components=n_components,
            max_rul_hours=max_rul, samples_per_hour=1.0,
        )

    def test_data_generator_creates_samples(self):
        samples = self._make_samples()
        assert len(samples) > 0
        assert all(isinstance(s, FailureSample) for s in samples)

    def test_data_generator_failure_events(self):
        samples = self._make_samples(n_components=5)
        failures = [s for s in samples if s.is_failure_event]
        assert len(failures) == 5

    def test_data_generator_rul_decreasing(self):
        gen = FailureDataGenerator()
        samples = gen.generate_component_dataset("battery", n_components=1, max_rul_hours=50)
        comp_samples = [s for s in samples if s.component_id == samples[0].component_id]
        ruls = [s.rul_hours for s in comp_samples]
        assert ruls[0] > ruls[-1]

    def test_train_returns_result(self):
        samples = self._make_samples(n_components=5)
        cfg = TrainingConfig(sequence_length=5, epochs=1, component_type="battery")
        pipe = LSTMTrainingPipeline(cfg)
        result = pipe.train(samples)
        assert result.test_rmse >= 0
        assert result.feature_names

    def test_predict_returns_non_negative(self):
        samples = self._make_samples(n_components=5)
        cfg = TrainingConfig(sequence_length=5, epochs=1)
        pipe = LSTMTrainingPipeline(cfg)
        pipe.train(samples)
        preds = pipe.predict(samples[:20])
        assert all(p >= 0 for p in preds)

    def test_empty_samples_handled(self):
        pipe = LSTMTrainingPipeline()
        result = pipe.train([])
        assert result.test_rmse == 0

    def test_solar_panel_profile_available(self):
        gen = FailureDataGenerator()
        samples = gen.generate_component_dataset("solar_panel", n_components=2)
        assert len(samples) > 0
        assert all("power_output_w" in s.features for s in samples)


# ---------------------------------------------------------------------------
# XGBoost pipeline tests
# ---------------------------------------------------------------------------

class TestXGBoostPipeline:
    """Tests for xgboost_pipeline.py"""

    def _make_samples(self):
        gen = FailureDataGenerator()
        return gen.generate_component_dataset("battery", n_components=5, max_rul_hours=100)

    def test_train_returns_result(self):
        samples = self._make_samples()
        pred = XGBoostRULPredictor(XGBConfig(n_iter_search=1, cv_folds=2))
        result = pred.train(samples, tune_hyperparams=False)
        assert result.n_features_engineered > 0

    def test_feature_engineering_expands_features(self):
        samples = self._make_samples()
        pred = XGBoostRULPredictor(XGBConfig(n_iter_search=1))
        result = pred.train(samples, tune_hyperparams=False)
        # Should have far more features than the 6 raw battery features
        assert result.n_features_engineered > 6

    def test_predict_after_train(self):
        samples = self._make_samples()
        pred = XGBoostRULPredictor(XGBConfig(n_iter_search=1))
        pred.train(samples, tune_hyperparams=False)
        preds = pred.predict(samples[:5])
        assert len(preds) == 5
        assert all(p >= 0 for p in preds)

    def test_empty_samples_returns_empty(self):
        pred = XGBoostRULPredictor()
        preds = pred.predict([])
        assert preds == []


# ---------------------------------------------------------------------------
# RL resource optimizer tests
# ---------------------------------------------------------------------------

class TestRLOptimizer:
    """Tests for rl_resource_optimizer.py"""

    def test_env_reset_returns_vector(self):
        env = SpaceMissionEnv(seed=0)
        obs = env.reset()
        assert obs.shape == (MissionState.n_obs(),)

    def test_env_step_returns_tuple(self):
        env = SpaceMissionEnv(seed=0)
        env.reset()
        action = np.zeros(ResourceAllocation.n_actions(), dtype=np.float32)
        obs, reward, done, info = env.step(action)
        assert obs.shape == (MissionState.n_obs(),)
        assert isinstance(reward, float)
        assert isinstance(done, bool)

    def test_resource_allocation_sums_to_one(self):
        action = np.array([1.0, 2.0, 0.5, 0.3, 1.5, 0.8], dtype=np.float32)
        alloc = ResourceAllocation.from_vector(action)
        total = (alloc.life_support + alloc.propulsion + alloc.communications +
                 alloc.science + alloc.thermal + alloc.computing)
        assert abs(total - 1.0) < 1e-5

    def test_mission_state_vector_length(self):
        s = MissionState(0.9,0.95,0.8,0.9,1,1,0.2,0.95,0.98,0.99,1.0,0.97,0.02,0.1)
        assert len(s.to_vector()) == MissionState.n_obs()

    def test_optimizer_train_returns_history(self):
        opt = RLResourceOptimizer(n_training_steps=512)
        hist = opt.train(verbose=False)
        assert "policy_loss" in hist
        assert "episode_returns" in hist

    def test_optimize_resources_returns_allocation(self):
        s = MissionState(0.9,0.95,0.8,0.9,1,1,0.2,0.95,0.98,0.99,1.0,0.97,0.02,0.1)
        opt = RLResourceOptimizer(n_training_steps=512)
        opt.train(verbose=False)
        alloc = opt.optimize_resources(s)
        assert isinstance(alloc, ResourceAllocation)
        assert 0 <= alloc.life_support <= 1

    def test_env_catastrophic_failure(self):
        """Mission terminates with low O2."""
        env = SpaceMissionEnv(seed=42)
        env.reset()
        # Force near-zero O2
        env._state.o2_level = 0.02
        action = np.ones(6, dtype=np.float32) * (-2)  # minimal life_support
        _, reward, done, info = env.step(action)
        assert done or env._state.o2_level < 0.1


# ---------------------------------------------------------------------------
# Federated learning server tests
# ---------------------------------------------------------------------------

class TestFederatedServer:
    """Tests for federated_aggregation_server.py"""

    def _make_server(self):
        server = FederatedAggregationServer(model_dir="/tmp/fed_test_pytest")
        weights = {
            "layer0": np.random.randn(16, 8).astype(np.float32),
            "layer1": np.random.randn(8, 1).astype(np.float32),
        }
        server.initialize_global_model(weights)
        return server, weights

    def _make_clients(self, server, n=5):
        clients = []
        for i in range(n):
            c = SimulatedSatelliteClient(f"SAT-{i:03d}", n_local_samples=100 + i * 20)
            server.register_client(c.client_id)
            c.receive_global_model(server.get_global_weights())
            clients.append(c)
        return clients

    def test_server_initializes(self):
        server, _ = self._make_server()
        status = server.get_status()
        assert status["status"] == "running"
        assert status["round"] == 0

    def test_submit_and_aggregate(self):
        server, _ = self._make_server()
        clients = self._make_clients(server, n=5)
        for c in clients:
            upd = c.train_local(round_number=0)
            accepted = server.submit_update(upd)
            assert accepted

        result = server.run_aggregation_round()
        assert result is not None
        assert result.n_clients_participated == 5
        assert result.round_number == 0

    def test_quorum_not_met(self):
        server, _ = self._make_server()
        clients = self._make_clients(server, n=2)
        for c in clients:
            upd = c.train_local(round_number=0)
            server.submit_update(upd)
        result = server.run_aggregation_round()
        assert result is None

    def test_stale_round_rejected(self):
        server, _ = self._make_server()
        c = SimulatedSatelliteClient("SAT-STALE", n_local_samples=100)
        server.register_client(c.client_id)
        c.receive_global_model(server.get_global_weights())
        upd = c.train_local(round_number=99)  # Wrong round
        accepted = server.submit_update(upd)
        assert not accepted

    def test_unregistered_client_rejected(self):
        server, _ = self._make_server()
        upd = ClientUpdate(
            client_id="UNKNOWN-SAT", round_number=0,
            gradients={"layer0": np.zeros((16, 8))},
            n_samples=100, loss=0.5,
        )
        accepted = server.submit_update(upd)
        assert not accepted

    def test_global_weights_update_after_round(self):
        server, init_weights = self._make_server()
        clients = self._make_clients(server, n=5)
        for c in clients:
            server.submit_update(c.train_local(round_number=0))

        server.run_aggregation_round()
        new_weights = server.get_global_weights()
        # Weights should have changed
        delta = sum(
            np.linalg.norm(new_weights[k] - init_weights[k])
            for k in init_weights
        )
        assert delta > 0

    def test_privacy_budget_tracked(self):
        server, _ = self._make_server()
        clients = self._make_clients(server, n=5)
        for c in clients:
            server.submit_update(c.train_local(round_number=0))
        server.run_aggregation_round()
        status = server.get_status()
        assert status["privacy_epsilon_used"] > 0

    def test_simulated_client_gradients_are_small(self):
        _, weights = self._make_server()
        c = SimulatedSatelliteClient("SAT-000", n_local_samples=200)
        c.receive_global_model(weights)
        upd = c.train_local(round_number=0)
        for g in upd.gradients.values():
            # Gradient norms should be small relative to weight magnitude
            assert np.linalg.norm(g) < np.linalg.norm(list(weights.values())[0]) * 0.5


# ---------------------------------------------------------------------------
# Predictive maintenance calibration tests
# ---------------------------------------------------------------------------

class TestPredictiveMaintenanceCalibration:
    """Tests for mission-calibrated RUL and benchmark dataset generation."""

    def test_benchmark_generator_creates_time_series(self):
        gen = MissionBenchmarkGenerator(seed=7)
        profile = MissionProfile(
            mission_name="mars_transfer",
            radiation_factor=1.8,
            thermal_cycling_factor=1.4,
            duty_cycle=0.85,
        )
        dataset = gen.generate_component_dataset(
            component_type="battery",
            mission_profile=profile,
            n_components=3,
            horizon_hours=72,
            step_hours=6,
        )

        assert len(dataset) == 3
        first_series = next(iter(dataset.values()))
        assert len(first_series) == 13  # 0..72 in 6h steps
        assert first_series[0].value >= first_series[-1].value

    def test_mission_calibration_increases_rate_under_stress(self):
        gen = MissionBenchmarkGenerator(seed=13)
        profile = MissionProfile(
            mission_name="deep_space_high_stress",
            radiation_factor=2.0,
            thermal_cycling_factor=1.5,
            duty_cycle=0.9,
            communication_latency_factor=1.4,
            shadowing_factor=1.3,
        )
        dataset = gen.generate_component_dataset(
            component_type="battery",
            mission_profile=profile,
            n_components=2,
            horizon_hours=240,
            step_hours=12,
            noise_std=0.2,
        )

        predictor = RULPredictor()
        predictor.register_mission_profile(profile)
        history = list(dataset.values())[0]

        result = predictor.calibrate_component_for_mission(
            component_type="battery",
            mission_name=profile.mission_name,
            historical_data=history,
        )

        assert result.calibrated_degradation_rate > result.baseline_degradation_rate
        assert 0.35 <= result.confidence <= 0.9

    def test_mission_aware_rul_is_lower_for_high_stress_profile(self):
        predictor = RULPredictor()
        profile = MissionProfile(
            mission_name="lunar_surface_ops",
            radiation_factor=1.7,
            thermal_cycling_factor=1.6,
            duty_cycle=0.85,
        )
        predictor.register_mission_profile(profile)

        now = datetime(2026, 1, 1)
        hist: List[HealthMetric] = []
        for i in range(8):
            ts = now + timedelta(hours=i * 24)
            hist.append(
                HealthMetric(
                    metric_name="health_score",
                    value=100.0 - i * 2.2,
                    unit="score",
                    timestamp=ts,
                )
            )

        predictor.calibrate_component_for_mission("battery", profile.mission_name, hist)

        base_rul, _ = predictor.predict_rul(
            component_id="bat-1",
            component_type="battery",
            current_metrics={"health_score": 80.0},
            historical_data=hist,
            mission_name=None,
        )
        stressed_rul, _ = predictor.predict_rul(
            component_id="bat-1",
            component_type="battery",
            current_metrics={"health_score": 80.0},
            historical_data=hist,
            mission_name=profile.mission_name,
        )

        assert stressed_rul < base_rul


class _DummyMetricSink:
    def __init__(self):
        self.predictions = []
        self.heartbeats = []

    def write_ml_prediction(self, model_type, component_id, component_type, rul_hours, confidence):
        self.predictions.append({
            "model_type": model_type,
            "component_id": component_id,
            "component_type": component_type,
            "rul_hours": rul_hours,
            "confidence": confidence,
        })

    def write_system_heartbeat(self, metrics):
        self.heartbeats.append(dict(metrics))


class TestPredictiveMaintenanceLiveFlow:
    """Integration-style tests for mission-calibrated live telemetry flow."""

    def test_mission_context_and_coupled_degradation_applied(self):
        sink = _DummyMetricSink()
        engine = PredictiveMaintenanceEngine(metrics_sink=sink)
        profile = MissionProfile("lunar_ops", radiation_factor=1.5, duty_cycle=0.8)
        engine.register_mission_profile(profile)
        engine.bind_mission_profile_to_satellite("SAT-1", "lunar_ops")

        t0 = datetime(2026, 1, 1, 0, 0, 0)
        # Seed battery telemetry first, then avionics receives coupling penalty.
        for k in range(6):
            engine.process_telemetry(
                satellite_id="SAT-1",
                component_id="battery-1",
                component_type="battery",
                metrics={"health_score": 95.0 - k * 2.0, "temperature_c": 48.0},
                current_time=t0 + timedelta(hours=2 * k),
            )

        event = engine.process_telemetry(
            satellite_id="SAT-1",
            component_id="avionics-1",
            component_type="avionics",
            metrics={"health_score": 92.0, "power_rail_v": 4.7},
            current_time=t0 + timedelta(hours=12),
        )

        assert event is None or event.component_id == "avionics-1"
        status = engine.component_status["avionics-1"]
        assert status.health_score < 92.0  # coupled penalty should reduce effective health
        assert sink.predictions  # prediction persistence hook used

    def test_drift_monitor_triggers_recalibration(self):
        sink = _DummyMetricSink()
        engine = PredictiveMaintenanceEngine(
            metrics_sink=sink,
            drift_window=4,
            drift_threshold=0.4,
            auto_recalibration_min_points=6,
        )
        profile = MissionProfile("mars_long", radiation_factor=1.8, thermal_cycling_factor=1.4)
        engine.register_mission_profile(profile)
        engine.bind_mission_profile_to_component("battery-2", "mars_long")

        t0 = datetime(2026, 2, 1, 0, 0, 0)
        for k in range(12):
            engine.process_telemetry(
                satellite_id="SAT-2",
                component_id="battery-2",
                component_type="battery",
                metrics={"health_score": 100.0 - k * 3.5, "temperature_c": 44.0},
                current_time=t0 + timedelta(hours=6 * k),
            )

        # Recalibration outputs should be persisted as heartbeat records.
        assert any("pm_calibration_rate" in hb for hb in sink.heartbeats)
        assert len(engine.calibration_history.get("battery-2", [])) >= 1

    def test_scorecard_metrics_persisted(self):
        sink = _DummyMetricSink()
        engine = PredictiveMaintenanceEngine(metrics_sink=sink)
        profile = MissionProfile("geo_station", radiation_factor=1.2, duty_cycle=0.75)
        engine.register_mission_profile(profile)
        engine.bind_mission_profile_to_satellite("SAT-3", "geo_station")

        t0 = datetime(2026, 3, 1, 0, 0, 0)
        for k in range(24):
            engine.process_telemetry(
                satellite_id="SAT-3",
                component_id="radiator-1",
                component_type="radiator",
                metrics={"health_score": 98.0 - k * 1.4, "temperature_c": 68.0},
                current_time=t0 + timedelta(hours=4 * k),
            )

        scorecard = engine.get_component_scorecard(
            satellite_id="SAT-3",
            component_id="radiator-1",
            component_type="radiator",
            current_time=t0 + timedelta(hours=100),
        )
        assert scorecard.n_predictions > 0
        assert scorecard.n_calibrations >= 0
        assert any("pm_rul_mae_h" in hb for hb in sink.heartbeats)

    def test_warning_ceiling_for_predictive_flow(self):
        engine = PredictiveMaintenanceEngine()
        profile = MissionProfile("warn_test")
        engine.register_mission_profile(profile)
        engine.bind_mission_profile_to_satellite("SAT-W", "warn_test")
        t0 = datetime(2026, 4, 1, 0, 0, 0)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            for k in range(10):
                engine.process_telemetry(
                    satellite_id="SAT-W",
                    component_id="battery-W",
                    component_type="battery",
                    metrics={"health_score": 100.0 - k * 2.0, "temperature_c": 40.0},
                    current_time=t0 + timedelta(hours=k),
                )

        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(dep_warnings) <= 2


def test_cehsn_sources_have_no_utcnow_calls():
    cehsn_dir = Path(__file__).resolve().parents[1] / "src" / "cehsn"
    offenders = []
    for py_file in cehsn_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "utcnow(" in text:
            offenders.append(py_file.name)
    assert not offenders, f"Found forbidden utcnow usage in: {offenders}"
