"""
Mission resource allocation optimizer for IoST core operations.

This module provides a deterministic, risk-aware allocation policy that maps
subsystem health and demand into actionable power/resource fractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import math


@dataclass(frozen=True)
class SubsystemState:
    """Normalized subsystem state used by the allocator."""

    name: str
    health_score: float  # 0..1
    demand_fraction: float  # 0..1 requested share of available budget
    criticality: float  # 0..1 mission criticality
    efficiency: float = 1.0  # >0, higher means better output per unit resource


@dataclass(frozen=True)
class AllocationPlan:
    """Allocator output with summary diagnostics."""

    allocations: Dict[str, float]  # Subsystem -> fraction in [0..1]
    reserve_fraction: float
    risk_index: float
    mission_utility: float


class MissionResourceAllocator:
    """
    Risk-constrained allocator for mission resources.

    The policy combines criticality, degradation pressure, and phase context
    to produce stable allocations under nominal and emergency conditions.
    """

    def __init__(self) -> None:
        self._phase_boosts: Dict[str, Dict[str, float]] = {
            "nominal": {
                "life_support": 0.10,
                "propulsion": 0.08,
                "communications": 0.08,
                "science": 0.20,
                "thermal": 0.10,
                "computing": 0.12,
            },
            "transit": {
                "life_support": 0.12,
                "propulsion": 0.18,
                "communications": 0.10,
                "science": 0.06,
                "thermal": 0.12,
                "computing": 0.10,
            },
            "emergency": {
                "life_support": 0.30,
                "propulsion": 0.10,
                "communications": 0.18,
                "science": 0.00,
                "thermal": 0.20,
                "computing": 0.07,
            },
        }

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _normalize_nonnegative(weights: Dict[str, float]) -> Dict[str, float]:
        total = sum(max(0.0, w) for w in weights.values())
        if total <= 0:
            count = max(1, len(weights))
            return {k: 1.0 / count for k in weights}
        return {k: max(0.0, w) / total for k, w in weights.items()}

    def recommend_allocation(
        self,
        subsystem_states: List[SubsystemState],
        crew_risk: float,
        mission_phase: str = "nominal",
    ) -> AllocationPlan:
        """
        Compute resource fractions for each subsystem plus reserve.

        Inputs:
        - subsystem_states: subsystem demand, health, and criticality states
        - crew_risk: normalized mission risk in [0..1]
        - mission_phase: nominal, transit, or emergency
        """
        if not subsystem_states:
            return AllocationPlan(allocations={}, reserve_fraction=1.0, risk_index=0.0, mission_utility=0.0)

        phase = mission_phase if mission_phase in self._phase_boosts else "nominal"
        risk = self._clamp(crew_risk, 0.0, 1.0)

        # Reserve grows with risk and fleet degradation to preserve maneuver margin.
        degradation = sum(1.0 - self._clamp(s.health_score, 0.0, 1.0) for s in subsystem_states) / len(subsystem_states)
        reserve_fraction = self._clamp(0.08 + 0.22 * risk + 0.10 * degradation, 0.06, 0.35)
        distributable = max(0.0, 1.0 - reserve_fraction)

        # Multi-factor urgency score per subsystem:
        # urgency = 0.45*criticality + 0.25*degradation + 0.20*demand_pressure + 0.10*phase_boost
        urgency: Dict[str, float] = {}
        for state in subsystem_states:
            health = self._clamp(state.health_score, 0.0, 1.0)
            criticality = self._clamp(state.criticality, 0.0, 1.0)
            efficiency = max(1e-3, state.efficiency)
            demand_pressure = self._clamp(state.demand_fraction / efficiency, 0.0, 2.0)
            phase_boost = self._phase_boosts[phase].get(state.name, 0.05)

            score = (
                0.45 * criticality
                + 0.25 * (1.0 - health)
                + 0.20 * demand_pressure
                + 0.10 * phase_boost
            )

            if state.name in {"life_support", "thermal", "communications"}:
                score += 0.20 * risk
            urgency[state.name] = score

        # Lower temperature during high-risk operations -> sharper prioritization.
        temperature = self._clamp(0.9 - 0.5 * risk, 0.28, 0.9)
        logits = {k: math.exp(v / temperature) for k, v in urgency.items()}
        normalized = self._normalize_nonnegative(logits)
        allocations = {k: distributable * v for k, v in normalized.items()}

        # Safety floors for mission-critical systems.
        floor_life = 0.22 + 0.10 * risk
        floor_thermal = 0.10 + 0.05 * risk
        floor_comms = 0.09 + 0.04 * risk
        floors = {
            "life_support": floor_life,
            "thermal": floor_thermal,
            "communications": floor_comms,
        }

        for name, floor in floors.items():
            if name in allocations:
                allocations[name] = max(allocations[name], floor)

        # During emergency-grade risk, cap science and redistribute remainder.
        if risk >= 0.70 and "science" in allocations:
            max_science = 0.04
            if allocations["science"] > max_science:
                reclaimed = allocations["science"] - max_science
                allocations["science"] = max_science
                for target in ("life_support", "thermal", "communications"):
                    if target in allocations:
                        allocations[target] += reclaimed / 3.0

        # Re-normalize allocations to distributable budget while preserving floors.
        floor_sum = sum(floors.get(k, 0.0) for k in allocations)
        if floor_sum > distributable:
            scale = distributable / floor_sum if floor_sum > 0 else 0.0
            allocations = {k: floors.get(k, 0.0) * scale for k in allocations}
        else:
            variable_keys = [k for k in allocations if k not in floors]
            fixed = sum(allocations[k] for k in allocations if k in floors)
            variable_target = max(0.0, distributable - fixed)
            variable_current = sum(allocations[k] for k in variable_keys)
            if variable_current > 0:
                ratio = variable_target / variable_current
                for k in variable_keys:
                    allocations[k] *= ratio

        total_alloc = sum(allocations.values())
        if total_alloc > 0:
            adjust = distributable / total_alloc
            for k in allocations:
                allocations[k] *= adjust

        # Utility captures weighted mission effectiveness under risk.
        utility = 0.0
        for state in subsystem_states:
            share = allocations.get(state.name, 0.0)
            health = self._clamp(state.health_score, 0.0, 1.0)
            criticality = self._clamp(state.criticality, 0.0, 1.0)
            efficiency = max(1e-3, state.efficiency)
            utility += share * criticality * health * efficiency

        risk_penalty = 0.20 * risk * max(0.0, 0.25 - allocations.get("life_support", 0.0))
        mission_utility = max(0.0, utility - risk_penalty)

        return AllocationPlan(
            allocations=allocations,
            reserve_fraction=reserve_fraction,
            risk_index=risk,
            mission_utility=mission_utility,
        )
