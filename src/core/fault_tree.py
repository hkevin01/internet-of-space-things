"""
fault_tree.py - Probabilistic fault tree analysis for mission safety.

ID: CORE-039
Requirement: Given subsystem health scores, degradation rates, and a
             fault tree definition, compute the probability of mission-abort
             top events, identify minimal cut sets, and produce an FMEA table.
Purpose: Convert the continuous health/degradation outputs of the
         predictive-maintenance engine into actionable abort-risk scores
         that the resource allocator can use to adjust safety floors.
Rationale: Individual subsystem health scores are insufficient for system-level
           risk; life support at 70% health combined with thermal at 60% may
           produce a 90%+ abort probability through AND/OR gate combinations
           not visible in per-subsystem metrics alone.
Inputs: List[SubsystemHealthInput], FaultTreeDefinition, horizon_hours.
Outputs: FaultTreeResult with top_event_probability, minimal_cut_sets,
         FMEA table, risk classification.
Preconditions: All referenced event IDs appear in either basic events or gates.
Postconditions: top_event_probability in [0, 1].
Assumptions: Basic event failure probabilities are independent (no common-cause
             failure modelling in this version). Weibull hazard rate derived
             from health score and degradation rate.
Failure Modes: Unknown gate ID in tree definition raises KeyError.
               Circular gate references detected and raise ValueError.
Error Handling: Missing subsystem in inputs uses health=1.0 (healthy default).
Constraints: Gate count <= 1000; basic events <= 10000 for tractable
             minimal-cut-set enumeration.
Verification: tests/test_advanced_systems.py.
References: Vesely, W.E. "Fault Tree Handbook" NRC NUREG-0492, 1981.
            Stamatis, D.H. "Failure Mode and Effects Analysis" 2nd ed. 2003.
            Birnbaum, Z.W. "On the Importance of Different Components in a
            Multi-Component System" 1969.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class GateType(Enum):
    """
    ID: CORE-039-DS1
    Purpose: Boolean gate type in the fault tree.
    """
    AND = "AND"          # all children must fail
    OR = "OR"            # at least one child must fail
    VOTE = "VOTE"        # k-of-n children must fail


class RiskLevel(Enum):
    """
    ID: CORE-039-DS2
    Purpose: Qualitative risk classification bands.
    """
    NEGLIGIBLE = "NEGLIGIBLE"   # P < 1e-6
    LOW = "LOW"                 # 1e-6 <= P < 1e-3
    MEDIUM = "MEDIUM"           # 1e-3 <= P < 0.05
    HIGH = "HIGH"               # 0.05 <= P < 0.20
    CRITICAL = "CRITICAL"       # P >= 0.20


# ---------------------------------------------------------------------------
# Input/definition types
# ---------------------------------------------------------------------------

@dataclass
class SubsystemHealthInput:
    """
    ID: CORE-039-DS3
    Purpose: Snapshot of one subsystem's health for fault-tree leaf evaluation.

    Fields:
        subsystem_id     - matches the basic event IDs in the fault tree.
        health_score     - normalized health in [0, 1] (1 = fully healthy).
        degradation_rate - fractional health loss per hour [0, 1].
        anomaly_score    - optional anomaly detector output [0, 1].
        redundancy_level - number of independent redundant units (>= 1).
    """
    subsystem_id: str
    health_score: float
    degradation_rate: float = 0.0
    anomaly_score: float = 0.0
    redundancy_level: int = 1


@dataclass
class BasicEvent:
    """
    ID: CORE-039-DS4
    Purpose: Leaf node in the fault tree - maps to a subsystem failure mode.

    Fields:
        event_id        - unique identifier (must match SubsystemHealthInput.subsystem_id).
        description     - human-readable failure mode description.
        severity        - consequence severity if this event occurs [0, 1].
        detectable      - True if detectable by on-board monitoring.
        mitigation_cost - estimated resource cost (fraction of budget) to mitigate.
    """
    event_id: str
    description: str
    severity: float = 0.5
    detectable: bool = True
    mitigation_cost: float = 0.0


@dataclass
class FaultGate:
    """
    ID: CORE-039-DS5
    Purpose: Intermediate or top-level gate in the fault tree.

    Fields:
        gate_id     - unique identifier.
        gate_type   - AND, OR, or VOTE.
        children    - list of child gate_ids or basic event_ids.
        vote_k      - for VOTE gates: number of children that must fail.
        description - human-readable description of the failure scenario.
    """
    gate_id: str
    gate_type: GateType
    children: List[str]
    vote_k: int = 1
    description: str = ""


@dataclass
class FaultTreeDefinition:
    """
    ID: CORE-039-DS6
    Purpose: Complete fault tree specification.

    Fields:
        top_gate_id    - root gate whose probability is the mission abort risk.
        gates          - {gate_id: FaultGate}.
        basic_events   - {event_id: BasicEvent}.
    """
    top_gate_id: str
    gates: Dict[str, FaultGate]
    basic_events: Dict[str, BasicEvent]


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class FMEAEntry:
    """
    ID: CORE-039-DS7
    Purpose: One row of the Failure Mode and Effects Analysis table.
    """
    event_id: str
    description: str
    failure_probability: float
    severity: float
    risk_priority_number: float     # RPN = probability * severity * detectability_inverse
    birnbaum_importance: float      # sensitivity of top event to this basic event
    critical: bool                  # True if this event alone can cause top event
    recommended_action: str


@dataclass
class FaultTreeResult:
    """
    ID: CORE-039-DS8
    Purpose: Complete fault tree analysis output.

    Fields:
        top_event_probability   - P(mission abort) over horizon [0, 1].
        risk_level              - qualitative classification.
        subsystem_contributions - {event_id: conditional probability contribution}.
        minimal_cut_sets        - list of minimal sets of failures that cause top event.
        fmea_table              - FMEA rows sorted by RPN descending.
        gate_probabilities      - intermediate {gate_id: probability}.
        basic_event_probabilities - {event_id: probability}.
        horizon_hours           - evaluation horizon.
        dominant_failure_path   - description of most likely failure sequence.
    """
    top_event_probability: float
    risk_level: RiskLevel
    subsystem_contributions: Dict[str, float]
    minimal_cut_sets: List[List[str]]
    fmea_table: List[FMEAEntry]
    gate_probabilities: Dict[str, float]
    basic_event_probabilities: Dict[str, float]
    horizon_hours: float
    dominant_failure_path: str


# ---------------------------------------------------------------------------
# Hazard rate model
# ---------------------------------------------------------------------------

def _basic_event_probability(
    health: SubsystemHealthInput,
    horizon_hours: float,
) -> float:
    """
    ID: CORE-039-F1
    Purpose: Compute P(failure within horizon_hours) for a single subsystem
             using a Weibull-inspired constant-hazard-rate model.
    Rationale: P(fail | t) = 1 - exp(-lambda * t) where lambda is derived
               from current health and degradation rate:
               lambda = degradation_rate * (1 - health_score + anomaly_score)
               This ensures healthy systems have near-zero probability over
               short horizons and degrading systems escalate rapidly.
    Inputs:
        health       - SubsystemHealthInput snapshot.
        horizon_hours - mission planning horizon.
    Outputs: failure probability in [0, 1].
    Notes: For redundant systems (redundancy_level > 1), assume independent
           failures: P(all_fail) = P(single)^redundancy_level.
    """
    h = max(0.0, min(1.0, health.health_score))
    dr = max(0.0, min(1.0, health.degradation_rate))
    anomaly = max(0.0, min(1.0, health.anomaly_score))

    # Hazard rate: rises as health declines and degradation accelerates
    degradation_factor = dr + 0.5 * anomaly + 0.1 * (1.0 - h)
    # Minimum floor: any component has at least some tiny probability of failure
    lam = max(1e-9, degradation_factor) / max(0.01, h)

    # Clamp lambda to reasonable values (avoid numerical overflow)
    lam = min(lam, 10.0 / max(1.0, horizon_hours))

    p_single = 1.0 - math.exp(-lam * horizon_hours)
    p_single = max(0.0, min(1.0, p_single))

    # Redundant systems: all units must fail
    if health.redundancy_level > 1:
        return p_single ** health.redundancy_level
    return p_single


# ---------------------------------------------------------------------------
# Gate probability evaluation
# ---------------------------------------------------------------------------

def _evaluate_gate(
    gate_id: str,
    tree: FaultTreeDefinition,
    event_probs: Dict[str, float],
    gate_probs: Dict[str, float],
    visited: Set[str],
) -> float:
    """
    ID: CORE-039-F2
    Purpose: Recursively evaluate gate probability, caching results.
    Failure Modes: Circular references detected via visited set; raise ValueError.
    """
    if gate_id in gate_probs:
        return gate_probs[gate_id]
    if gate_id in visited:
        raise ValueError(f"Circular reference detected at gate '{gate_id}'")
    visited.add(gate_id)

    gate = tree.gates[gate_id]
    child_probs: List[float] = []
    for child_id in gate.children:
        if child_id in tree.basic_events:
            child_probs.append(event_probs.get(child_id, 0.0))
        elif child_id in tree.gates:
            child_probs.append(_evaluate_gate(child_id, tree, event_probs, gate_probs, visited))
        else:
            raise KeyError(f"Unknown child ID '{child_id}' in gate '{gate_id}'")

    if gate.gate_type == GateType.AND:
        p = 1.0
        for cp in child_probs:
            p *= cp
    elif gate.gate_type == GateType.OR:
        p = 1.0
        for cp in child_probs:
            p *= (1.0 - cp)
        p = 1.0 - p
    elif gate.gate_type == GateType.VOTE:
        k = max(1, gate.vote_k)
        n = len(child_probs)
        # Exact k-of-n probability via inclusion-exclusion (feasible for n <= ~20)
        p = _vote_probability(child_probs, k)
    else:
        raise ValueError(f"Unknown gate type: {gate.gate_type}")

    p = max(0.0, min(1.0, p))
    gate_probs[gate_id] = p
    visited.discard(gate_id)
    return p


def _vote_probability(child_probs: List[float], k: int) -> float:
    """
    ID: CORE-039-F3
    Purpose: Compute P(at least k of n independent events occur) using
             dynamic programming to avoid combinatorial explosion.
    Algorithm: DP table dp[i][j] = P(exactly j events among first i occur).
    Complexity: O(n^2) time, O(n) space.
    """
    n = len(child_probs)
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    # dp[j] = P(exactly j of events 0..i-1 have occurred)
    dp = [0.0] * (n + 1)
    dp[0] = 1.0
    for i, p in enumerate(child_probs):
        new_dp = [0.0] * (n + 1)
        for j in range(i + 2):
            if j > 0:
                new_dp[j] += dp[j - 1] * p
            if j <= i:
                new_dp[j] += dp[j] * (1.0 - p)
        dp = new_dp
    return sum(dp[k:])


# ---------------------------------------------------------------------------
# Minimal cut set enumeration
# ---------------------------------------------------------------------------

def _find_minimal_cut_sets(
    gate_id: str,
    tree: FaultTreeDefinition,
    max_order: int = 3,
) -> List[FrozenSet[str]]:
    """
    ID: CORE-039-F4
    Purpose: Find minimal cut sets (MCS) of the fault tree up to order max_order.
    Algorithm: MOCUS (Method for Obtaining Cut Sets) top-down expansion.
               Start with top gate; AND gates produce set union (same row);
               OR gates produce set union (separate rows).
    Complexity: Exponential in the number of OR gates; limited by max_order cutoff.
    Outputs: list of frozensets, each containing basic event IDs.
    """
    # Working set: list of sets (each set = one candidate cut set being built)
    working: List[FrozenSet[str]] = [frozenset()]

    def expand(gate_or_event_id: str, current_sets: List[FrozenSet[str]]) -> List[FrozenSet[str]]:
        if gate_or_event_id in tree.basic_events:
            # Leaf: add event to each set in current_sets
            return [cs | frozenset([gate_or_event_id]) for cs in current_sets]

        gate = tree.gates[gate_or_event_id]
        if gate.gate_type == GateType.AND:
            # AND: sequentially expand all children through each current set
            result = current_sets
            for child_id in gate.children:
                result = expand(child_id, result)
            return result
        elif gate.gate_type in (GateType.OR, GateType.VOTE):
            # OR: each child generates its own parallel branch
            # For VOTE k-of-n: approximate as OR of all k-combinations
            if gate.gate_type == GateType.VOTE:
                k = max(1, gate.vote_k)
                children = gate.children
                import itertools
                combos = list(itertools.combinations(children, k))
                result: List[FrozenSet[str]] = []
                for combo in combos:
                    branch = list(current_sets)
                    for child_id in combo:
                        branch = expand(child_id, branch)
                    result.extend(branch)
                return result
            else:
                result = []
                for child_id in gate.children:
                    result.extend(expand(child_id, list(current_sets)))
                return result
        return current_sets

    try:
        raw_sets = expand(gate_id, working)
    except (RecursionError, MemoryError):
        return []

    # Filter by max_order and minimalize
    filtered = [s for s in raw_sets if len(s) <= max_order]
    minimal = _minimize_cut_sets(filtered)
    return minimal


def _minimize_cut_sets(sets: List[FrozenSet[str]]) -> List[FrozenSet[str]]:
    """
    ID: CORE-039-H1
    Purpose: Remove non-minimal sets (supersets of other sets in the list).
    """
    sorted_sets = sorted(sets, key=len)
    minimal: List[FrozenSet[str]] = []
    for s in sorted_sets:
        if not any(m.issubset(s) and m != s for m in minimal):
            minimal.append(s)
    return minimal


# ---------------------------------------------------------------------------
# Birnbaum importance measure
# ---------------------------------------------------------------------------

def _birnbaum_importance(
    event_id: str,
    tree: FaultTreeDefinition,
    event_probs: Dict[str, float],
    top_prob: float,
    delta: float = 1e-4,
) -> float:
    """
    ID: CORE-039-F5
    Purpose: Compute the Birnbaum structural importance of a basic event:
             I_B(i) = P(top | event_i = 1) - P(top | event_i = 0).
    Rationale: Measures how sensitive the top event probability is to
               changes in this specific component's reliability.
    Algorithm: Finite difference approximation using a small probability delta.
    """
    orig = event_probs.get(event_id, 0.0)

    probs_hi = dict(event_probs)
    probs_hi[event_id] = min(1.0, orig + delta)
    gate_probs_hi: Dict[str, float] = {}
    p_hi = _evaluate_gate(tree.top_gate_id, tree, probs_hi, gate_probs_hi, set())

    probs_lo = dict(event_probs)
    probs_lo[event_id] = max(0.0, orig - delta)
    gate_probs_lo: Dict[str, float] = {}
    p_lo = _evaluate_gate(tree.top_gate_id, tree, probs_lo, gate_probs_lo, set())

    denom = 2.0 * delta
    return (p_hi - p_lo) / denom if denom > 1e-15 else 0.0


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def analyze_fault_tree(
    subsystem_health: List[SubsystemHealthInput],
    tree: FaultTreeDefinition,
    horizon_hours: float = 24.0,
    mcs_max_order: int = 3,
) -> FaultTreeResult:
    """
    ID: CORE-039-F6
    Purpose: Perform a complete probabilistic fault tree analysis:
             (a) compute basic event failure probabilities from health inputs,
             (b) evaluate gate probabilities bottom-up,
             (c) enumerate minimal cut sets,
             (d) compute Birnbaum importance for each basic event,
             (e) produce FMEA table sorted by risk priority number.
    Inputs:
        subsystem_health - list of current subsystem health snapshots.
        tree             - fault tree definition (gates + basic events).
        horizon_hours    - mission planning horizon for failure probabilities.
        mcs_max_order    - maximum cut set order for MCS enumeration.
    Outputs: FaultTreeResult.
    Preconditions: tree.top_gate_id must exist in tree.gates.
    Error Handling: Missing subsystem in health inputs defaults to healthy.
    """
    if tree.top_gate_id not in tree.gates:
        raise KeyError(f"Top gate '{tree.top_gate_id}' not found in tree.gates")

    # Build health lookup
    health_map: Dict[str, SubsystemHealthInput] = {h.subsystem_id: h for h in subsystem_health}

    # Compute basic event probabilities
    event_probs: Dict[str, float] = {}
    for event_id, event in tree.basic_events.items():
        h = health_map.get(event_id)
        if h is None:
            # Default: assume fully healthy
            h = SubsystemHealthInput(subsystem_id=event_id, health_score=1.0, degradation_rate=0.0)
        event_probs[event_id] = _basic_event_probability(h, horizon_hours)

    # Evaluate gate probabilities
    gate_probs: Dict[str, float] = {}
    top_prob = _evaluate_gate(tree.top_gate_id, tree, event_probs, gate_probs, set())

    # Risk level classification
    risk_level = _classify_risk(top_prob)

    # Minimal cut sets
    mcs_list = _find_minimal_cut_sets(tree.top_gate_id, tree, mcs_max_order)
    minimal_cut_sets = [sorted(mcs) for mcs in mcs_list]

    # Subsystem contributions (conditional top event given this event fails)
    contributions: Dict[str, float] = {}
    for event_id in tree.basic_events:
        probs_given_fail = dict(event_probs)
        probs_given_fail[event_id] = 1.0
        gp_temp: Dict[str, float] = {}
        p_given = _evaluate_gate(tree.top_gate_id, tree, probs_given_fail, gp_temp, set())
        contributions[event_id] = p_given

    # Birnbaum importance
    birnbaum: Dict[str, float] = {}
    for event_id in tree.basic_events:
        birnbaum[event_id] = _birnbaum_importance(event_id, tree, event_probs, top_prob)

    # Check which events are in any order-1 cut set (single point of failure)
    single_events: Set[str] = set()
    for mcs in mcs_list:
        if len(mcs) == 1:
            single_events |= mcs

    # FMEA table
    fmea: List[FMEAEntry] = []
    for event_id, event in tree.basic_events.items():
        p = event_probs[event_id]
        detectability_factor = 0.1 if event.detectable else 1.0   # lower = more detectable
        rpn = p * event.severity * detectability_factor * 1000.0   # scale to [0, 1000]
        action = _recommend_action(event_id, p, event.severity, event.mitigation_cost)
        fmea.append(FMEAEntry(
            event_id=event_id,
            description=event.description,
            failure_probability=p,
            severity=event.severity,
            risk_priority_number=rpn,
            birnbaum_importance=birnbaum.get(event_id, 0.0),
            critical=event_id in single_events,
            recommended_action=action,
        ))
    fmea.sort(key=lambda r: r.risk_priority_number, reverse=True)

    # Dominant failure path
    dominant = _describe_dominant_path(mcs_list, event_probs, tree)

    return FaultTreeResult(
        top_event_probability=top_prob,
        risk_level=risk_level,
        subsystem_contributions=contributions,
        minimal_cut_sets=minimal_cut_sets,
        fmea_table=fmea,
        gate_probabilities=gate_probs,
        basic_event_probabilities=event_probs,
        horizon_hours=horizon_hours,
        dominant_failure_path=dominant,
    )


def _classify_risk(p: float) -> RiskLevel:
    if p < 1e-6:
        return RiskLevel.NEGLIGIBLE
    if p < 1e-3:
        return RiskLevel.LOW
    if p < 0.05:
        return RiskLevel.MEDIUM
    if p < 0.20:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def _recommend_action(event_id: str, probability: float, severity: float, cost: float) -> str:
    if probability > 0.1 and severity > 0.7:
        return f"IMMEDIATE: Increase {event_id} allocation; schedule early maintenance."
    if probability > 0.05:
        return f"HIGH: Monitor {event_id} closely; prepare contingency plan."
    if probability > 0.01:
        return f"MEDIUM: Track {event_id} degradation trend; plan next maintenance window."
    return f"LOW: Routine monitoring of {event_id} sufficient."


def _describe_dominant_path(
    mcs_list: List[FrozenSet[str]],
    event_probs: Dict[str, float],
    tree: FaultTreeDefinition,
) -> str:
    if not mcs_list:
        return "No cut sets found within enumeration order limit."
    # Dominant path = MCS with highest joint probability
    def mcs_prob(mcs: FrozenSet[str]) -> float:
        p = 1.0
        for eid in mcs:
            p *= event_probs.get(eid, 0.0)
        return p
    dominant = max(mcs_list, key=mcs_prob)
    prob = mcs_prob(dominant)
    descriptions = [
        tree.basic_events[eid].description if eid in tree.basic_events else eid
        for eid in sorted(dominant)
    ]
    return f"P={prob:.2e}: {' AND '.join(descriptions)}"


# ---------------------------------------------------------------------------
# Convenience: build default mission fault tree from SubsystemState list
# ---------------------------------------------------------------------------

def default_mission_fault_tree(subsystem_names: Optional[List[str]] = None) -> FaultTreeDefinition:
    """
    ID: CORE-039-F7
    Purpose: Build a default mission-abort fault tree for an IoST satellite
             based on the standard subsystem set used by MissionResourceAllocator.
    Structure:
        MISSION_ABORT = OR(
            LIFE_SUPPORT_FAILURE,
            AND(THERMAL_FAILURE, POWER_FAILURE),
            AND(COMMS_FAILURE, COMPUTING_FAILURE),
        )
        LIFE_SUPPORT_FAILURE  = basic(life_support)
        THERMAL_FAILURE       = basic(thermal)
        POWER_FAILURE         = OR(basic(solar_panels), basic(battery))
        COMMS_FAILURE         = basic(communications)
        COMPUTING_FAILURE     = basic(computing)
    """
    names = subsystem_names or [
        "life_support", "thermal", "solar_panels", "battery",
        "communications", "computing", "propulsion",
    ]

    basic_events = {
        "life_support": BasicEvent("life_support", "Life support system failure", severity=1.0, detectable=True, mitigation_cost=0.35),
        "thermal":      BasicEvent("thermal",      "Thermal control failure",       severity=0.8, detectable=True, mitigation_cost=0.15),
        "solar_panels": BasicEvent("solar_panels", "Solar panel failure",            severity=0.6, detectable=True, mitigation_cost=0.10),
        "battery":      BasicEvent("battery",      "Battery failure",                severity=0.7, detectable=True, mitigation_cost=0.12),
        "communications": BasicEvent("communications", "Communications failure",     severity=0.5, detectable=True, mitigation_cost=0.10),
        "computing":    BasicEvent("computing",    "Onboard computer failure",       severity=0.7, detectable=True, mitigation_cost=0.08),
        "propulsion":   BasicEvent("propulsion",   "Propulsion system failure",      severity=0.4, detectable=True, mitigation_cost=0.12),
    }

    gates = {
        "POWER_FAILURE": FaultGate(
            gate_id="POWER_FAILURE", gate_type=GateType.OR,
            children=["solar_panels", "battery"],
            description="Any power generation or storage failure",
        ),
        "COMMS_COMPUTING_FAILURE": FaultGate(
            gate_id="COMMS_COMPUTING_FAILURE", gate_type=GateType.AND,
            children=["communications", "computing"],
            description="Simultaneous comms and computing loss",
        ),
        "THERMAL_POWER_FAILURE": FaultGate(
            gate_id="THERMAL_POWER_FAILURE", gate_type=GateType.AND,
            children=["thermal", "POWER_FAILURE"],
            description="Thermal failure compounded by power loss",
        ),
        "MISSION_ABORT": FaultGate(
            gate_id="MISSION_ABORT", gate_type=GateType.OR,
            children=["life_support", "THERMAL_POWER_FAILURE", "COMMS_COMPUTING_FAILURE"],
            description="Mission abort top event",
        ),
    }

    # Filter to only include basic events that exist
    kept = {k: v for k, v in basic_events.items() if k in names}
    return FaultTreeDefinition(
        top_gate_id="MISSION_ABORT",
        gates=gates,
        basic_events=kept,
    )
