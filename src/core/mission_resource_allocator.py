"""
Mission resource allocation optimizer for IoST core operations.

This module provides a deterministic, risk-aware allocation policy that maps
subsystem health and demand into actionable power/resource fractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import math


@dataclass(frozen=True)
class SubsystemState:
    """Normalized subsystem state used by the allocator."""

    name: str
    health_score: float  # 0..1
    demand_fraction: float  # 0..1 requested share of available budget
    criticality: float  # 0..1 mission criticality
    efficiency: float = 1.0  # >0, higher means better output per unit resource
    degradation_rate: float = 0.0  # normalized health loss per hour in [0..1]
    anomaly_lead_time_hours: Optional[float] = None  # higher lead-time usually means lower urgency


@dataclass(frozen=True)
class AllocationPlan:
    """Allocator output with summary diagnostics."""

    allocations: Dict[str, float]  # Subsystem -> fraction in [0..1]
    reserve_fraction: float
    risk_index: float
    mission_utility: float


@dataclass(frozen=True)
class PhaseTraceSample:
    """Simulation trace sample for phase-specific penalty learning."""

    mission_phase: str
    allocations: Dict[str, float]
    crew_risk: float
    mission_utility: float


class MissionResourceAllocator:
    """
    Risk-constrained allocator for mission resources.

    The policy combines criticality, degradation pressure, and phase context
    to produce stable allocations under nominal and emergency conditions.
    """

    def __init__(self, metrics_sink: Optional[Any] = None) -> None:
        self.metrics_sink = metrics_sink
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
        self._phase_penalty_matrices: Dict[str, Dict[str, float]] = {
            "nominal": {},
            "transit": {},
            "emergency": {},
            "eva": {},
        }

    def set_metrics_sink(self, metrics_sink: Optional[Any]) -> None:
        """Attach or replace sink used for allocation trend persistence."""
        self.metrics_sink = metrics_sink

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

    @staticmethod
    def _phase_norm(phase: str) -> str:
        if phase in {"nominal", "transit", "emergency", "eva"}:
            return phase
        return "nominal"

    @staticmethod
    def _phase_code(phase: str) -> float:
        table = {"nominal": 0.0, "transit": 1.0, "eva": 2.0, "emergency": 3.0}
        return table.get(phase, 0.0)

    @staticmethod
    def _lead_time_urgency_factor(lead_time_hours: Optional[float]) -> float:
        if lead_time_hours is None:
            return 0.0
        clamped = max(0.0, min(168.0, lead_time_hours))
        return max(0.0, 1.0 - clamped / 168.0)

    def learn_phase_penalty_matrices(self, trace_samples: List[PhaseTraceSample]) -> Dict[str, Dict[str, float]]:
        """
        Learn phase-specific allocation penalties from simulation traces.

        Penalty per phase/subsystem is proportional to how often allocation
        coincides with poor outcomes: high crew risk and low mission utility.
        """
        if not trace_samples:
            return self._phase_penalty_matrices

        accum: Dict[str, Dict[str, float]] = {}
        counts: Dict[str, Dict[str, float]] = {}
        for sample in trace_samples:
            phase = self._phase_norm(sample.mission_phase)
            accum.setdefault(phase, {})
            counts.setdefault(phase, {})

            outcome_stress = self._clamp(sample.crew_risk, 0.0, 1.0) * (1.0 - self._clamp(sample.mission_utility, 0.0, 1.0))
            for subsystem, share in sample.allocations.items():
                s = max(0.0, float(share))
                accum[phase][subsystem] = accum[phase].get(subsystem, 0.0) + outcome_stress * s
                counts[phase][subsystem] = counts[phase].get(subsystem, 0.0) + s

        learned: Dict[str, Dict[str, float]] = {"nominal": {}, "transit": {}, "emergency": {}, "eva": {}}
        for phase, subsystem_scores in accum.items():
            for subsystem, value in subsystem_scores.items():
                denom = max(1e-6, counts[phase].get(subsystem, 0.0))
                learned_penalty = self._clamp(value / denom, 0.0, 0.5)
                learned[phase][subsystem] = learned_penalty

        self._phase_penalty_matrices = learned
        return self._phase_penalty_matrices

    def recommend_horizon_allocation(
        self,
        subsystem_states: List[SubsystemState],
        crew_risk: float,
        mission_phase: str = "nominal",
        horizon_steps: int = 6,
        step_hours: float = 1.0,
    ) -> AllocationPlan:
        """
        Horizon-aware model-predictive allocation over a short forecast window.

        This approximates MPC by solving one-step allocations across forecasted
        health/risk states, then returning a weighted aggregate first-action plan.
        """
        steps = max(1, int(horizon_steps))
        dt = max(0.1, float(step_hours))
        base_phase = self._phase_norm(mission_phase)

        simulated_states = list(subsystem_states)
        simulated_risk = self._clamp(crew_risk, 0.0, 1.0)
        plans: List[AllocationPlan] = []

        for t in range(steps):
            plan = self.recommend_allocation(simulated_states, simulated_risk, base_phase, persist=False)
            plans.append(plan)

            updated: List[SubsystemState] = []
            for state in simulated_states:
                share = plan.allocations.get(state.name, 0.0)
                # Higher share slows net health loss; low share accelerates decay.
                effective_decay = max(0.0, state.degradation_rate * (1.20 - 0.70 * share))
                next_health = self._clamp(state.health_score - effective_decay * dt, 0.0, 1.0)
                updated.append(
                    SubsystemState(
                        name=state.name,
                        health_score=next_health,
                        demand_fraction=state.demand_fraction,
                        criticality=state.criticality,
                        efficiency=state.efficiency,
                        degradation_rate=state.degradation_rate,
                        anomaly_lead_time_hours=state.anomaly_lead_time_hours,
                    )
                )
            simulated_states = updated

            avg_health = sum(s.health_score for s in simulated_states) / max(1, len(simulated_states))
            simulated_risk = self._clamp(simulated_risk + 0.07 * (1.0 - avg_health), 0.0, 1.0)

        discounts = [0.85 ** i for i in range(len(plans))]
        z = sum(discounts) if discounts else 1.0
        discounts = [d / z for d in discounts]

        blended_alloc: Dict[str, float] = {}
        for weight, plan in zip(discounts, plans):
            for subsystem, share in plan.allocations.items():
                blended_alloc[subsystem] = blended_alloc.get(subsystem, 0.0) + weight * share

        reserve = sum(w * p.reserve_fraction for w, p in zip(discounts, plans))
        utility = sum(w * p.mission_utility for w, p in zip(discounts, plans))
        risk_index = sum(w * p.risk_index for w, p in zip(discounts, plans))

        final_plan = AllocationPlan(
            allocations=blended_alloc,
            reserve_fraction=reserve,
            risk_index=risk_index,
            mission_utility=utility,
        )
        self._persist_plan(final_plan, base_phase, mode="horizon_mpc")
        return final_plan

    def recommend_allocation(
        self,
        subsystem_states: List[SubsystemState],
        crew_risk: float,
        mission_phase: str = "nominal",
        persist: bool = True,
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

        phase = self._phase_norm(mission_phase)
        risk = self._clamp(crew_risk, 0.0, 1.0)

        floors = self._floors_for_risk(risk)
        floor_sum = sum(floors.values())

        # Reserve grows with risk and fleet degradation to preserve maneuver margin.
        degradation = sum(1.0 - self._clamp(s.health_score, 0.0, 1.0) for s in subsystem_states) / len(subsystem_states)
        reserve_candidate = self._clamp(0.08 + 0.22 * risk + 0.10 * degradation, 0.06, 0.35)
        max_reserve_for_safety = max(0.0, 1.0 - floor_sum - 0.01)
        reserve_fraction = min(reserve_candidate, max_reserve_for_safety)
        reserve_fraction = self._clamp(reserve_fraction, 0.0, 0.35)
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
            maintenance_pressure = self._clamp(state.degradation_rate, 0.0, 1.0)
            lead_urgency = self._lead_time_urgency_factor(state.anomaly_lead_time_hours)
            learned_penalty = self._phase_penalty_matrices.get(phase, {}).get(state.name, 0.0)

            score = (
                0.38 * criticality
                + 0.20 * (1.0 - health)
                + 0.16 * demand_pressure
                + 0.08 * phase_boost
                + 0.12 * maintenance_pressure
                + 0.10 * lead_urgency
                - 0.10 * learned_penalty
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

        # Re-normalize allocations as floor + extra terms.
        present_floor_sum = sum(floors.get(k, 0.0) for k in allocations)
        remaining_budget = max(0.0, distributable - present_floor_sum)

        extras: Dict[str, float] = {}
        for name, share in allocations.items():
            floor_val = floors.get(name, 0.0)
            extras[name] = max(0.0, share - floor_val)

        extras_total = sum(extras.values())
        if extras_total > 0.0:
            scale = remaining_budget / extras_total
            for name in extras:
                extras[name] *= scale
        else:
            for name in extras:
                extras[name] = 0.0

        allocations = {
            name: floors.get(name, 0.0) + extras.get(name, 0.0)
            for name in allocations
        }

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

        plan = AllocationPlan(
            allocations=allocations,
            reserve_fraction=reserve_fraction,
            risk_index=risk,
            mission_utility=mission_utility,
        )
        if persist:
            self._persist_plan(plan, phase, mode="single_step")
        return plan

    def _floors_for_risk(self, risk: float) -> Dict[str, float]:
        return {
            "life_support": 0.22 + 0.10 * risk,
            "thermal": 0.10 + 0.05 * risk,
            "communications": 0.09 + 0.04 * risk,
        }

    def _persist_plan(self, plan: AllocationPlan, mission_phase: str, mode: str) -> None:
        if self.metrics_sink is None:
            return
        if not hasattr(self.metrics_sink, "write_system_heartbeat"):
            return

        payload: Dict[str, Any] = {
            "allocator_mode": mode,
            "allocator_phase": mission_phase,
            "allocator_phase_code": self._phase_code(mission_phase),
            "allocator_reserve": float(plan.reserve_fraction),
            "allocator_risk": float(plan.risk_index),
            "allocator_utility": float(plan.mission_utility),
            "allocator_timestamp_s": float(datetime.now().timestamp()),
        }
        for subsystem, share in plan.allocations.items():
            payload[f"allocator_{subsystem}"] = float(share)

        try:
            self.metrics_sink.write_system_heartbeat(payload)
        except Exception:
            # Allocation feedback persistence must never interrupt mission decisions.
            pass
