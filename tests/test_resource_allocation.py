"""Tests for mission resource allocation optimizer."""

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.mission_control import MissionControl
from core.mission_resource_allocator import (
    MissionResourceAllocator,
    PhaseTraceSample,
    SubsystemState,
)


class _DummySink:
    def __init__(self):
        self.heartbeats = []

    def write_system_heartbeat(self, payload):
        self.heartbeats.append(dict(payload))


class TestMissionResourceAllocator:
    def test_allocation_respects_budget_and_reserve(self):
        allocator = MissionResourceAllocator()
        states = [
            SubsystemState("life_support", 0.92, 0.30, 1.0, 0.95),
            SubsystemState("propulsion", 0.80, 0.20, 0.75, 0.90),
            SubsystemState("communications", 0.88, 0.16, 0.85, 0.92),
            SubsystemState("science", 0.77, 0.24, 0.55, 0.98),
            SubsystemState("thermal", 0.83, 0.10, 0.90, 0.88),
            SubsystemState("computing", 0.74, 0.12, 0.60, 0.91),
        ]

        plan = allocator.recommend_allocation(states, crew_risk=0.35, mission_phase="nominal")

        total = sum(plan.allocations.values())
        assert 0.0 < plan.reserve_fraction < 1.0
        assert total == pytest.approx(1.0 - plan.reserve_fraction, abs=1e-6)
        assert plan.mission_utility > 0.0

    def test_high_risk_caps_science_and_boosts_safety(self):
        allocator = MissionResourceAllocator()
        states = [
            SubsystemState("life_support", 0.60, 0.35, 1.0, 0.90),
            SubsystemState("communications", 0.68, 0.15, 0.90, 0.90),
            SubsystemState("thermal", 0.62, 0.15, 0.92, 0.85),
            SubsystemState("science", 0.84, 0.30, 0.40, 0.99),
        ]

        plan = allocator.recommend_allocation(states, crew_risk=0.82, mission_phase="emergency")

        assert plan.allocations.get("science", 0.0) <= 0.04 + 1e-8
        assert plan.allocations.get("life_support", 0.0) >= 0.20
        assert plan.allocations.get("thermal", 0.0) >= 0.10
        assert plan.allocations.get("communications", 0.0) >= 0.09

    def test_predictive_maintenance_signals_increase_critical_share(self):
        allocator = MissionResourceAllocator()
        base_states = [
            SubsystemState("life_support", 0.80, 0.20, 0.90, 0.95, degradation_rate=0.02, anomaly_lead_time_hours=96.0),
            SubsystemState("science", 0.80, 0.22, 0.75, 0.95, degradation_rate=0.02, anomaly_lead_time_hours=96.0),
        ]
        stressed_states = [
            SubsystemState("life_support", 0.80, 0.20, 0.90, 0.95, degradation_rate=0.12, anomaly_lead_time_hours=8.0),
            SubsystemState("science", 0.80, 0.22, 0.75, 0.95, degradation_rate=0.02, anomaly_lead_time_hours=96.0),
        ]

        base = allocator.recommend_allocation(base_states, crew_risk=0.40, mission_phase="transit")
        stressed = allocator.recommend_allocation(stressed_states, crew_risk=0.40, mission_phase="transit")

        assert stressed.allocations["life_support"] > base.allocations["life_support"]

    def test_horizon_allocator_returns_valid_plan(self):
        allocator = MissionResourceAllocator()
        states = [
            SubsystemState("life_support", 0.78, 0.30, 1.0, 0.95, degradation_rate=0.08),
            SubsystemState("thermal", 0.73, 0.12, 0.88, 0.89, degradation_rate=0.06),
            SubsystemState("communications", 0.81, 0.18, 0.85, 0.91, degradation_rate=0.05),
            SubsystemState("science", 0.85, 0.25, 0.50, 0.99, degradation_rate=0.03),
        ]

        plan = allocator.recommend_horizon_allocation(
            subsystem_states=states,
            crew_risk=0.65,
            mission_phase="transit",
            horizon_steps=8,
            step_hours=1.0,
        )

        total = sum(plan.allocations.values())
        assert total == pytest.approx(1.0 - plan.reserve_fraction, abs=1e-6)
        assert 0.0 <= plan.mission_utility <= 1.0

    def test_learned_phase_penalty_matrices_affect_science_weight(self):
        allocator = MissionResourceAllocator()
        samples = [
            PhaseTraceSample("emergency", {"science": 0.28, "life_support": 0.22}, 0.92, 0.20),
            PhaseTraceSample("emergency", {"science": 0.30, "life_support": 0.20}, 0.88, 0.25),
            PhaseTraceSample("emergency", {"science": 0.26, "life_support": 0.23}, 0.90, 0.22),
        ]
        allocator.learn_phase_penalty_matrices(samples)

        states = [
            SubsystemState("science", 0.86, 0.28, 0.65, 0.98),
            SubsystemState("life_support", 0.80, 0.26, 0.95, 0.90),
            SubsystemState("thermal", 0.78, 0.18, 0.90, 0.87),
            SubsystemState("communications", 0.82, 0.17, 0.88, 0.90),
        ]
        plan = allocator.recommend_allocation(states, crew_risk=0.84, mission_phase="emergency")
        assert plan.allocations["science"] <= 0.04 + 1e-8

    def test_persistence_hook_writes_allocator_trends(self):
        sink = _DummySink()
        allocator = MissionResourceAllocator(metrics_sink=sink)
        states = [
            SubsystemState("life_support", 0.92, 0.3, 1.0),
            SubsystemState("communications", 0.87, 0.2, 0.9),
            SubsystemState("thermal", 0.86, 0.1, 0.9),
            SubsystemState("science", 0.85, 0.2, 0.5),
        ]
        allocator.recommend_allocation(states, crew_risk=0.35, mission_phase="nominal")
        allocator.recommend_horizon_allocation(states, crew_risk=0.35, mission_phase="nominal", horizon_steps=4)

        assert len(sink.heartbeats) >= 2
        assert any("allocator_utility" in hb for hb in sink.heartbeats)

    def test_formal_high_risk_safety_invariants(self):
        allocator = MissionResourceAllocator()
        rng = random.Random(20260720)

        for _ in range(120):
            risk = rng.uniform(0.80, 1.0)
            states = [
                SubsystemState("life_support", rng.uniform(0.45, 0.95), rng.uniform(0.15, 0.50), 1.0, rng.uniform(0.8, 1.0), degradation_rate=rng.uniform(0.0, 0.20), anomaly_lead_time_hours=rng.uniform(2.0, 72.0)),
                SubsystemState("thermal", rng.uniform(0.40, 0.95), rng.uniform(0.08, 0.25), 0.90, rng.uniform(0.75, 1.0), degradation_rate=rng.uniform(0.0, 0.15), anomaly_lead_time_hours=rng.uniform(2.0, 72.0)),
                SubsystemState("communications", rng.uniform(0.45, 0.95), rng.uniform(0.10, 0.30), 0.88, rng.uniform(0.8, 1.0), degradation_rate=rng.uniform(0.0, 0.16), anomaly_lead_time_hours=rng.uniform(2.0, 72.0)),
                SubsystemState("science", rng.uniform(0.55, 0.95), rng.uniform(0.05, 0.40), 0.45, rng.uniform(0.9, 1.0), degradation_rate=rng.uniform(0.0, 0.08), anomaly_lead_time_hours=rng.uniform(24.0, 168.0)),
            ]

            plan = allocator.recommend_allocation(states, crew_risk=risk, mission_phase="emergency")
            expected_life = 0.22 + 0.10 * risk
            expected_thermal = 0.10 + 0.05 * risk
            expected_comms = 0.09 + 0.04 * risk

            assert plan.allocations["life_support"] >= expected_life - 1e-8
            assert plan.allocations["thermal"] >= expected_thermal - 1e-8
            assert plan.allocations["communications"] >= expected_comms - 1e-8
            assert plan.allocations.get("science", 0.0) <= 0.04 + 1e-8


class TestMissionControlAllocationBridge:
    def test_mission_control_returns_allocator_plan(self):
        mc = MissionControl("allocation-test")
        result = mc.recommend_resource_allocation(
            subsystem_metrics=[
                {
                    "name": "life_support",
                    "health_score": 0.91,
                    "demand_fraction": 0.34,
                    "criticality": 1.0,
                    "efficiency": 0.95,
                },
                {
                    "name": "science",
                    "health_score": 0.88,
                    "demand_fraction": 0.25,
                    "criticality": 0.52,
                    "efficiency": 0.98,
                },
            ],
            crew_risk=0.45,
            mission_phase="transit",
        )

        assert "allocations" in result
        assert "reserve_fraction" in result
        assert "mission_utility" in result
        assert result["allocations"]["life_support"] > 0.0

    def test_bridge_supports_predictive_signals_and_horizon_mpc(self):
        mc = MissionControl("allocation-bridge-horizon")
        result = mc.recommend_resource_allocation(
            subsystem_metrics=[
                {"name": "life_support", "health_score": 0.82, "demand_fraction": 0.33, "criticality": 1.0, "efficiency": 0.95},
                {"name": "science", "health_score": 0.84, "demand_fraction": 0.28, "criticality": 0.55, "efficiency": 0.99},
                {"name": "communications", "health_score": 0.80, "demand_fraction": 0.16, "criticality": 0.90, "efficiency": 0.92},
                {"name": "thermal", "health_score": 0.79, "demand_fraction": 0.14, "criticality": 0.92, "efficiency": 0.90},
            ],
            predictive_signals={
                "life_support": {"degradation_rate": 0.10, "anomaly_lead_time_hours": 6.0},
                "science": {"degradation_rate": 0.01, "anomaly_lead_time_hours": 100.0},
            },
            crew_risk=0.78,
            mission_phase="emergency",
            use_horizon_mpc=True,
            horizon_steps=6,
        )

        assert result["mode"] == "horizon_mpc"
        assert result["allocations"]["life_support"] > result["allocations"]["science"]

    def test_phase_penalty_learning_via_mission_control_bridge(self):
        mc = MissionControl("allocation-penalty-learning")
        matrices = mc.learn_phase_penalty_matrices(
            [
                {
                    "mission_phase": "eva",
                    "allocations": {"science": 0.30, "life_support": 0.22, "thermal": 0.18},
                    "crew_risk": 0.86,
                    "mission_utility": 0.32,
                },
                {
                    "mission_phase": "eva",
                    "allocations": {"science": 0.26, "life_support": 0.24, "thermal": 0.17},
                    "crew_risk": 0.82,
                    "mission_utility": 0.35,
                },
            ]
        )

        assert "eva" in matrices
        assert matrices["eva"].get("science", 0.0) > 0.0
