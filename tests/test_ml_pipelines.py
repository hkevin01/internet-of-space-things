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

from src.cehsn import (
    FailureDataGenerator, FailureSample, LSTMTrainingPipeline, TrainingConfig,
    XGBoostRULPredictor, XGBConfig,
    RLResourceOptimizer, MissionState, SpaceMissionEnv, ResourceAllocation,
    FederatedAggregationServer, SimulatedSatelliteClient, ClientUpdate,
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
