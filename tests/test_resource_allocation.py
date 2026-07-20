"""Tests for mission resource allocation optimizer."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.mission_control import MissionControl
from core.mission_resource_allocator import MissionResourceAllocator, SubsystemState


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
