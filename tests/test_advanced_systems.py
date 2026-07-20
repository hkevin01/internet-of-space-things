"""
tests/test_advanced_systems.py
Tests for the four advanced algorithmic systems:
  1. Battery SOC propagation (battery_model.py)
  2. RAAN phasing optimizer (orbit_dynamics.py extension)
  3. Data volume model (data_volume_model.py)
  4. Fault tree analysis (fault_tree.py)

ID: TEST-CORE-036-039
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pytest

from src.core.orbit_dynamics import (
    OrbitalElementsJ2,
    R_EARTH,
    MU_EARTH,
    RAANPhasingPlan,
    compute_raan_phasing_plan,
    propagate_j2,
    compute_eclipse_state,
)
from src.core.battery_model import (
    BatteryConfig,
    BatteryOrbitTrace,
    BatteryStepState,
    SolarConfig,
    eclipse_aware_power_budget,
    propagate_battery_soc,
    soc_at_time,
)
from src.core.constellation_scheduler import (
    ConstellationSat,
    GroundStation,
    ScheduleEntryType,
    build_constellation_schedule,
)
from src.core.data_volume_model import (
    DataVolumeState,
    InstrumentProfile,
    buffer_fill_fractions_from_simulation,
    simulate_constellation_data_volume,
    simulate_data_volume,
)
from src.core.fault_tree import (
    BasicEvent,
    FaultGate,
    FaultTreeDefinition,
    FaultTreeResult,
    GateType,
    RiskLevel,
    SubsystemHealthInput,
    analyze_fault_tree,
    default_mission_fault_tree,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

EPOCH = datetime(2025, 6, 21, 12, 0, 0, tzinfo=timezone.utc)

ISS_LIKE = OrbitalElementsJ2(
    semi_major_axis=R_EARTH + 408.0, eccentricity=0.0002,
    inclination_deg=51.6, raan_deg=0.0, arg_perigee_deg=0.0,
    mean_anomaly_deg=0.0, epoch=EPOCH,
)

PERIOD_S = 2.0 * math.pi * math.sqrt(ISS_LIKE.semi_major_axis ** 3 / MU_EARTH)


# ===========================================================================
# 1. Battery SOC Propagation
# ===========================================================================

class TestBatteryModel:

    @pytest.fixture
    def default_solar(self) -> SolarConfig:
        return SolarConfig(
            panel_area_m2=0.032,
            cell_efficiency=0.295,
            panel_degradation=0.0,
            packing_factor=0.9,
            inherent_degradation=0.90,
        )

    @pytest.fixture
    def default_battery(self) -> BatteryConfig:
        return BatteryConfig(
            capacity_wh=40.0,
            max_dod=0.80,
            charge_efficiency=0.95,
            discharge_efficiency=0.98,
            initial_soc=1.0,
        )

    def test_trace_has_correct_steps(self, default_solar, default_battery) -> None:
        trace = propagate_battery_soc(
            ISS_LIKE, default_solar, default_battery,
            load_power_w=10.0, start=EPOCH, duration_seconds=PERIOD_S, n_steps=60,
        )
        assert len(trace.steps) == 60

    def test_soc_stays_in_range(self, default_solar, default_battery) -> None:
        trace = propagate_battery_soc(
            ISS_LIKE, default_solar, default_battery,
            load_power_w=8.0, start=EPOCH, duration_seconds=PERIOD_S * 3, n_steps=180,
        )
        for step in trace.steps:
            assert 0.0 <= step.soc <= 1.0, f"SOC {step.soc:.4f} out of [0,1] at {step.epoch}"

    def test_energy_balance_positive_surplus(self, default_solar, default_battery) -> None:
        # Load << solar generation -> net_energy should be positive (battery charges)
        solar = SolarConfig(panel_area_m2=0.10, cell_efficiency=0.30, packing_factor=0.9,
                            inherent_degradation=0.90, panel_degradation=0.0)
        trace = propagate_battery_soc(
            ISS_LIKE, solar, default_battery,
            load_power_w=5.0, start=EPOCH, duration_seconds=PERIOD_S, n_steps=60,
        )
        assert trace.energy_generated_wh > 0.0
        assert trace.energy_consumed_wh > 0.0

    def test_heavy_load_depletes_battery(self, default_solar, default_battery) -> None:
        # Load >> solar power -> SOC should drop from initial 1.0
        batt = BatteryConfig(capacity_wh=40.0, max_dod=0.80, initial_soc=1.0)
        trace = propagate_battery_soc(
            ISS_LIKE, default_solar, batt,
            load_power_w=100.0, start=EPOCH, duration_seconds=PERIOD_S, n_steps=60,
        )
        assert trace.final_soc < trace.initial_soc, "Heavy load should deplete battery"
        assert trace.min_soc < trace.initial_soc

    def test_eclipse_increases_discharge(self, default_solar, default_battery) -> None:
        # During eclipse solar=0, so battery must supply all load -> more discharge
        # Compare min_soc with zero load (no discharge possible in eclipse)
        trace_loaded = propagate_battery_soc(
            ISS_LIKE, default_solar, default_battery,
            load_power_w=15.0, start=EPOCH, duration_seconds=PERIOD_S, n_steps=60,
        )
        trace_idle = propagate_battery_soc(
            ISS_LIKE, default_solar, default_battery,
            load_power_w=0.0, start=EPOCH, duration_seconds=PERIOD_S, n_steps=60,
        )
        assert trace_loaded.min_soc <= trace_idle.min_soc

    def test_eclipse_duration_in_expected_range(self, default_solar, default_battery) -> None:
        trace = propagate_battery_soc(
            ISS_LIKE, default_solar, default_battery,
            load_power_w=10.0, start=EPOCH, duration_seconds=PERIOD_S, n_steps=90,
        )
        # ISS eclipse fraction ~35-40% of 92-min orbit -> 32-37 min
        eclipse_min = trace.eclipse_duration_s / 60.0
        assert 25.0 < eclipse_min < 50.0, (
            f"Eclipse duration {eclipse_min:.1f} min outside [25, 50] min range"
        )

    def test_cycle_fraction_positive(self, default_solar, default_battery) -> None:
        trace = propagate_battery_soc(
            ISS_LIKE, default_solar, default_battery,
            load_power_w=10.0, start=EPOCH, duration_seconds=PERIOD_S * 5, n_steps=90,
        )
        assert trace.charge_cycle_fraction > 0.0, "Battery cycling should produce non-zero cycles"

    def test_soc_at_time_interpolation(self, default_solar, default_battery) -> None:
        trace = propagate_battery_soc(
            ISS_LIKE, default_solar, default_battery,
            load_power_w=10.0, start=EPOCH, duration_seconds=PERIOD_S, n_steps=60,
        )
        soc_start = soc_at_time(trace, 0.0, PERIOD_S)
        soc_end = soc_at_time(trace, PERIOD_S, PERIOD_S)
        assert abs(soc_start - trace.steps[0].soc) < 0.01
        assert abs(soc_end - trace.steps[-1].soc) < 0.01

    def test_invalid_n_steps_raises(self, default_solar, default_battery) -> None:
        with pytest.raises(ValueError):
            propagate_battery_soc(ISS_LIKE, default_solar, default_battery,
                                   10.0, EPOCH, PERIOD_S, n_steps=0)

    def test_eclipse_aware_power_budget_in_range(self, default_solar, default_battery) -> None:
        pbf = eclipse_aware_power_budget(
            ISS_LIKE, default_solar, default_battery, 10.0, EPOCH,
            lookback_seconds=PERIOD_S, n_steps=60,
        )
        assert 0.0 <= pbf <= 1.0, f"eclipse_aware_power_budget {pbf:.4f} out of [0, 1]"

    def test_high_load_lowers_power_budget(self, default_solar) -> None:
        batt_low = BatteryConfig(capacity_wh=40.0, max_dod=0.8, initial_soc=0.4)
        batt_full = BatteryConfig(capacity_wh=40.0, max_dod=0.8, initial_soc=1.0)
        pbf_low = eclipse_aware_power_budget(
            ISS_LIKE, default_solar, batt_low, 10.0, EPOCH,
            lookback_seconds=PERIOD_S, n_steps=60,
        )
        pbf_full = eclipse_aware_power_budget(
            ISS_LIKE, default_solar, batt_full, 10.0, EPOCH,
            lookback_seconds=PERIOD_S, n_steps=60,
        )
        assert pbf_low <= pbf_full, "Lower initial SOC should not produce higher power budget"

    def test_nominal_power_property(self) -> None:
        solar = SolarConfig(panel_area_m2=0.032, cell_efficiency=0.295,
                            packing_factor=0.9, inherent_degradation=0.90)
        p = solar.nominal_power_w
        # 0.032 * 1361 * 0.295 * 0.9 * 0.9 ~ 11.1 W
        assert 5.0 < p < 20.0, f"nominal_power {p:.2f} W outside expected range"


# ===========================================================================
# 2. RAAN Phasing Optimizer
# ===========================================================================

class TestRAANPhasingOptimizer:

    def test_uniform_spacing_3_planes(self) -> None:
        plan = compute_raan_phasing_plan([0.0, 120.0, 240.0], ISS_LIKE)
        assert plan.n_planes == 3
        assert abs(plan.raan_spacing_deg - 120.0) < 1e-6

    def test_target_raans_span_360(self) -> None:
        plan = compute_raan_phasing_plan([0.0, 60.0, 120.0, 180.0, 240.0, 300.0], ISS_LIKE)
        assert plan.n_planes == 6
        assert abs(plan.raan_spacing_deg - 60.0) < 1e-6
        # Targets should cover the full 360 deg range
        spread = max(plan.target_raan_deg) - min(plan.target_raan_deg)
        assert spread >= 270.0, f"Target RAAN spread {spread:.1f} deg unexpectedly narrow"

    def test_already_phased_zero_delta(self) -> None:
        # When satellites are already at uniform spacing, delta should be small
        current = [0.0, 120.0, 240.0]
        plan = compute_raan_phasing_plan(current, ISS_LIKE, raan_ref_deg=0.0)
        # Delta should be close to zero (within numerical tolerance)
        for d in plan.delta_raan_deg:
            assert abs(d) < 0.5, f"Expected ~0 delta, got {d:.3f} deg"

    def test_phasing_duration_positive(self) -> None:
        current = [0.0, 80.0, 200.0]   # not uniformly spaced
        plan = compute_raan_phasing_plan(current, ISS_LIKE, raan_ref_deg=0.0)
        for t in plan.phasing_duration_days:
            assert t >= 0.0, f"Phasing duration {t:.3f} days must be non-negative"

    def test_deltav_positive(self) -> None:
        current = [0.0, 80.0, 200.0]
        plan = compute_raan_phasing_plan(current, ISS_LIKE)
        for dv in plan.maneuver_deltaV_m_per_s:
            assert dv >= 0.0, f"Delta-V {dv:.3f} m/s must be non-negative"

    def test_empty_returns_trivial(self) -> None:
        plan = compute_raan_phasing_plan([], ISS_LIKE)
        assert plan.n_planes == 0
        assert plan.maneuver_deltaV_m_per_s == []

    def test_single_returns_trivial(self) -> None:
        plan = compute_raan_phasing_plan([45.0], ISS_LIKE)
        assert plan.n_planes == 1
        assert plan.maneuver_deltaV_m_per_s == [0.0]

    def test_sat_ids_preserved(self) -> None:
        ids = ["ALPHA", "BETA", "GAMMA"]
        plan = compute_raan_phasing_plan([10.0, 130.0, 250.0], ISS_LIKE, sat_ids=ids)
        assert plan.sat_ids == ids

    def test_larger_delta_needs_more_dv_or_time(self) -> None:
        # Satellite needing 90-deg correction should have more dV than 5-deg correction
        plan_small = compute_raan_phasing_plan([0.0, 125.0, 245.0], ISS_LIKE, raan_ref_deg=0.0)
        plan_large = compute_raan_phasing_plan([0.0, 45.0, 90.0], ISS_LIKE, raan_ref_deg=0.0)
        max_dv_small = max(plan_small.maneuver_deltaV_m_per_s)
        max_dv_large = max(plan_large.maneuver_deltaV_m_per_s)
        # Combined metric: either more dV or longer phasing required
        max_time_small = max(plan_small.phasing_duration_days)
        max_time_large = max(plan_large.phasing_duration_days)
        assert max_dv_large + max_time_large >= max_dv_small + max_time_small - 0.1


# ===========================================================================
# 3. Data Volume Model
# ===========================================================================

@pytest.fixture
def two_sats_schedule():
    """Build a minimal constellation schedule for data volume tests."""
    sat1 = ConstellationSat(
        sat_id="DV-A",
        elements=OrbitalElementsJ2(
            semi_major_axis=R_EARTH + 550.0, eccentricity=0.001,
            inclination_deg=53.0, raan_deg=0.0, arg_perigee_deg=0.0,
            mean_anomaly_deg=0.0, epoch=EPOCH,
        ),
    )
    sat2 = ConstellationSat(
        sat_id="DV-B",
        elements=OrbitalElementsJ2(
            semi_major_axis=R_EARTH + 550.0, eccentricity=0.001,
            inclination_deg=53.0, raan_deg=0.0, arg_perigee_deg=0.0,
            mean_anomaly_deg=90.0, epoch=EPOCH,
        ),
    )
    station = GroundStation("central", 29.56, -95.09, 27.0, elevation_mask_deg=5.0)
    sched = build_constellation_schedule(
        [sat1, sat2], [station], EPOCH,
        search_duration_seconds=86400.0,
        time_step_seconds=15.0,
        include_isl=False,
    )
    return sched


class TestDataVolumeModel:

    def test_effective_rate_is_less_than_raw(self) -> None:
        inst = InstrumentProfile("cam", data_rate_mbps=100.0, duty_cycle=0.5, compression_ratio=2.0)
        assert inst.effective_rate_mbps < inst.data_rate_mbps

    def test_zero_instruments_no_generation(self, two_sats_schedule) -> None:
        state = simulate_data_volume(
            "DV-A", two_sats_schedule.entries, [],
            buffer_capacity_mb=10000.0, sim_start=EPOCH,
            sim_duration_seconds=3600.0, time_step_seconds=60.0,
        )
        assert state.total_generated_mb == 0.0
        assert state.buffer_fill_fraction == 0.0

    def test_buffer_fills_without_contacts(self) -> None:
        # Run with no contacts (pass empty schedule)
        inst = InstrumentProfile("cam", data_rate_mbps=10.0, duty_cycle=1.0, compression_ratio=1.0)
        state = simulate_data_volume(
            "DV-A", [],
            [inst], buffer_capacity_mb=10000.0, sim_start=EPOCH,
            sim_duration_seconds=3600.0, time_step_seconds=60.0,
        )
        assert state.total_generated_mb > 0.0
        assert state.total_downlinked_mb == 0.0
        assert state.buffer_fill_fraction > 0.0

    def test_buffer_capped_at_capacity(self) -> None:
        inst = InstrumentProfile("cam", data_rate_mbps=1000.0, duty_cycle=1.0, compression_ratio=1.0)
        state = simulate_data_volume(
            "DV-A", [],
            [inst], buffer_capacity_mb=100.0, sim_start=EPOCH,
            sim_duration_seconds=3600.0, time_step_seconds=60.0,
        )
        assert state.buffer_fill_fraction <= 1.0 + 1e-9
        assert state.overflow_events > 0, "Should detect overflow with fast fill and no contacts"

    def test_contacts_reduce_fill(self, two_sats_schedule) -> None:
        inst = InstrumentProfile("cam", data_rate_mbps=5.0, duty_cycle=1.0, compression_ratio=1.0)
        # With contacts
        state_with = simulate_data_volume(
            "DV-A", two_sats_schedule.entries, [inst],
            buffer_capacity_mb=100000.0, sim_start=EPOCH,
            sim_duration_seconds=86400.0, time_step_seconds=60.0,
        )
        # Without contacts
        state_without = simulate_data_volume(
            "DV-A", [], [inst],
            buffer_capacity_mb=100000.0, sim_start=EPOCH,
            sim_duration_seconds=86400.0, time_step_seconds=60.0,
        )
        assert state_with.total_downlinked_mb > 0.0
        assert state_with.buffer_fill_fraction <= state_without.buffer_fill_fraction

    def test_constellation_simulation_covers_all_sats(self, two_sats_schedule) -> None:
        instruments = {
            "DV-A": [InstrumentProfile("cam_a", 10.0)],
            "DV-B": [InstrumentProfile("cam_b", 10.0)],
        }
        results = simulate_constellation_data_volume(
            two_sats_schedule.entries, instruments,
            sim_start=EPOCH, sim_duration_seconds=86400.0, time_step_seconds=60.0,
        )
        assert "DV-A" in results
        assert "DV-B" in results

    def test_fill_fractions_in_range(self, two_sats_schedule) -> None:
        instruments = {
            "DV-A": [InstrumentProfile("cam", 10.0, duty_cycle=0.5)],
            "DV-B": [InstrumentProfile("cam", 10.0, duty_cycle=0.5)],
        }
        results = simulate_constellation_data_volume(
            two_sats_schedule.entries, instruments,
            sim_start=EPOCH, sim_duration_seconds=86400.0,
        )
        fills = buffer_fill_fractions_from_simulation(results)
        for sat_id, frac in fills.items():
            assert 0.0 <= frac <= 1.0, f"{sat_id}: fill fraction {frac:.4f} out of [0,1]"

    def test_buffer_fill_feeds_scheduler(self, two_sats_schedule) -> None:
        """End-to-end: simulate fills -> inject into next schedule iteration."""
        instruments = {"DV-A": [InstrumentProfile("cam", 5.0)],
                       "DV-B": [InstrumentProfile("cam", 5.0)]}
        results = simulate_constellation_data_volume(
            two_sats_schedule.entries, instruments, sim_start=EPOCH,
            sim_duration_seconds=43200.0,
        )
        fills = buffer_fill_fractions_from_simulation(results)
        # Inject fills into a new schedule build (comms urgency should reflect fill)
        sats = [
            ConstellationSat("DV-A", OrbitalElementsJ2(
                R_EARTH+550, 0.001, 53.0, 0.0, 0.0, 0.0, EPOCH)),
            ConstellationSat("DV-B", OrbitalElementsJ2(
                R_EARTH+550, 0.001, 53.0, 0.0, 0.0, 90.0, EPOCH)),
        ]
        station = GroundStation("central", 29.56, -95.09, 27.0)
        new_sched = build_constellation_schedule(
            sats, [station], EPOCH + timedelta(hours=12),
            search_duration_seconds=43200.0,
            time_step_seconds=15.0,
            buffer_fill_fractions=fills,
            include_isl=False,
        )
        for sat_id, demand in new_sched.comms_demand_fractions.items():
            assert 0.0 <= demand <= 1.0

    def test_keep_trace_populates_steps(self) -> None:
        inst = InstrumentProfile("cam", 1.0)
        state = simulate_data_volume(
            "DV-A", [], [inst], 1000.0, EPOCH, 600.0, time_step_seconds=60.0, keep_trace=True,
        )
        assert len(state.steps) == 10  # 600 s / 60 s = 10 steps

    def test_downlink_utilization_in_range(self, two_sats_schedule) -> None:
        inst = InstrumentProfile("cam", 10.0)
        state = simulate_data_volume(
            "DV-A", two_sats_schedule.entries, [inst],
            buffer_capacity_mb=100000.0, sim_start=EPOCH,
            sim_duration_seconds=86400.0,
        )
        assert 0.0 <= state.downlink_utilization <= 1.0


# ===========================================================================
# 4. Fault Tree Analysis Engine
# ===========================================================================

@pytest.fixture
def minimal_tree() -> FaultTreeDefinition:
    """Simple OR tree: abort if life_support OR (thermal AND power) fails."""
    return FaultTreeDefinition(
        top_gate_id="ABORT",
        gates={
            "THERMAL_POWER": FaultGate("THERMAL_POWER", GateType.AND, ["thermal", "power"]),
            "ABORT": FaultGate("ABORT", GateType.OR, ["life_support", "THERMAL_POWER"]),
        },
        basic_events={
            "life_support": BasicEvent("life_support", "LS failure", severity=1.0, detectable=True),
            "thermal": BasicEvent("thermal", "Thermal failure", severity=0.8, detectable=True),
            "power": BasicEvent("power", "Power failure", severity=0.6, detectable=True),
        },
    )


class TestFaultTree:

    def test_healthy_system_low_probability(self, minimal_tree) -> None:
        health = [
            SubsystemHealthInput("life_support", 0.99, degradation_rate=0.0),
            SubsystemHealthInput("thermal", 0.99, degradation_rate=0.0),
            SubsystemHealthInput("power", 0.99, degradation_rate=0.0),
        ]
        result = analyze_fault_tree(health, minimal_tree, horizon_hours=24.0)
        assert result.top_event_probability < 0.10, (
            f"Healthy system abort prob {result.top_event_probability:.4f} too high"
        )

    def test_degraded_system_higher_probability(self, minimal_tree) -> None:
        health_good = [SubsystemHealthInput(sid, 0.99) for sid in ["life_support", "thermal", "power"]]
        health_bad = [SubsystemHealthInput(sid, 0.2, degradation_rate=0.5) for sid in ["life_support", "thermal", "power"]]
        result_good = analyze_fault_tree(health_good, minimal_tree, horizon_hours=24.0)
        result_bad = analyze_fault_tree(health_bad, minimal_tree, horizon_hours=24.0)
        assert result_bad.top_event_probability > result_good.top_event_probability

    def test_and_gate_lower_than_or(self) -> None:
        events = {
            "A": BasicEvent("A", "Event A", 0.5),
            "B": BasicEvent("B", "Event B", 0.5),
        }
        and_tree = FaultTreeDefinition(
            top_gate_id="TOP",
            gates={"TOP": FaultGate("TOP", GateType.AND, ["A", "B"])},
            basic_events=events,
        )
        or_tree = FaultTreeDefinition(
            top_gate_id="TOP",
            gates={"TOP": FaultGate("TOP", GateType.OR, ["A", "B"])},
            basic_events=events,
        )
        health = [SubsystemHealthInput("A", 0.7, 0.1), SubsystemHealthInput("B", 0.7, 0.1)]
        r_and = analyze_fault_tree(health, and_tree, 24.0)
        r_or = analyze_fault_tree(health, or_tree, 24.0)
        assert r_and.top_event_probability <= r_or.top_event_probability, (
            "AND gate probability must be <= OR gate probability for same inputs"
        )

    def test_vote_gate_between_and_or(self) -> None:
        """2-of-3 VOTE gate probability should be between AND-3 and OR-3."""
        events = {
            "A": BasicEvent("A", "A"), "B": BasicEvent("B", "B"), "C": BasicEvent("C", "C")
        }
        and3 = FaultTreeDefinition("T", {"T": FaultGate("T", GateType.AND, ["A","B","C"])}, events)
        or3  = FaultTreeDefinition("T", {"T": FaultGate("T", GateType.OR,  ["A","B","C"])}, events)
        v2of3 = FaultTreeDefinition("T", {"T": FaultGate("T", GateType.VOTE, ["A","B","C"], vote_k=2)}, events)
        health = [SubsystemHealthInput(k, 0.7, 0.1) for k in ["A","B","C"]]
        p_and = analyze_fault_tree(health, and3, 24.0).top_event_probability
        p_or  = analyze_fault_tree(health, or3,  24.0).top_event_probability
        p_v   = analyze_fault_tree(health, v2of3, 24.0).top_event_probability
        assert p_and <= p_v <= p_or, f"VOTE p={p_v:.4f} not between AND p={p_and:.4f} and OR p={p_or:.4f}"

    def test_probability_in_range(self, minimal_tree) -> None:
        health = [SubsystemHealthInput(s, 0.6, 0.2) for s in ["life_support","thermal","power"]]
        result = analyze_fault_tree(health, minimal_tree, 24.0)
        assert 0.0 <= result.top_event_probability <= 1.0

    def test_default_mission_tree_works(self) -> None:
        tree = default_mission_fault_tree()
        health = [
            SubsystemHealthInput("life_support", 0.9, 0.01),
            SubsystemHealthInput("thermal", 0.85, 0.02),
            SubsystemHealthInput("solar_panels", 0.92, 0.005),
            SubsystemHealthInput("battery", 0.88, 0.01),
            SubsystemHealthInput("communications", 0.91, 0.008),
            SubsystemHealthInput("computing", 0.95, 0.005),
        ]
        result = analyze_fault_tree(health, tree, 24.0)
        assert 0.0 <= result.top_event_probability <= 1.0
        assert isinstance(result.risk_level, RiskLevel)

    def test_fmea_table_sorted_by_rpn(self, minimal_tree) -> None:
        health = [SubsystemHealthInput(s, 0.7, 0.1) for s in ["life_support","thermal","power"]]
        result = analyze_fault_tree(health, minimal_tree, 24.0)
        rpns = [row.risk_priority_number for row in result.fmea_table]
        assert rpns == sorted(rpns, reverse=True), "FMEA table must be sorted by RPN descending"

    def test_minimal_cut_sets_found(self, minimal_tree) -> None:
        health = [SubsystemHealthInput(s, 0.7, 0.1) for s in ["life_support","thermal","power"]]
        result = analyze_fault_tree(health, minimal_tree, 24.0)
        assert len(result.minimal_cut_sets) > 0

    def test_life_support_is_single_point_failure(self, minimal_tree) -> None:
        health = [SubsystemHealthInput(s, 0.7, 0.1) for s in ["life_support","thermal","power"]]
        result = analyze_fault_tree(health, minimal_tree, 24.0)
        # life_support OR gate -> single point of failure
        ls_entries = [r for r in result.fmea_table if r.event_id == "life_support"]
        assert len(ls_entries) == 1
        assert ls_entries[0].critical is True

    def test_redundant_system_lower_probability(self) -> None:
        tree = default_mission_fault_tree()
        health_single = [SubsystemHealthInput("life_support", 0.7, 0.2, redundancy_level=1)]
        health_dual   = [SubsystemHealthInput("life_support", 0.7, 0.2, redundancy_level=2)]
        r1 = analyze_fault_tree(health_single + [SubsystemHealthInput(s, 0.95, 0.0) for s in
              ["thermal","solar_panels","battery","communications","computing"]], tree, 24.0)
        r2 = analyze_fault_tree(health_dual   + [SubsystemHealthInput(s, 0.95, 0.0) for s in
              ["thermal","solar_panels","battery","communications","computing"]], tree, 24.0)
        assert r2.top_event_probability <= r1.top_event_probability, (
            "Redundant life support should reduce abort probability"
        )

    def test_missing_top_gate_raises(self) -> None:
        bad_tree = FaultTreeDefinition(
            top_gate_id="NONEXISTENT",
            gates={}, basic_events={},
        )
        with pytest.raises(KeyError):
            analyze_fault_tree([], bad_tree, 24.0)

    def test_missing_health_defaults_healthy(self, minimal_tree) -> None:
        # Omit health inputs -> should default to healthy (low probability)
        result = analyze_fault_tree([], minimal_tree, 24.0)
        assert result.top_event_probability < 0.05

    def test_subsystem_contributions_in_range(self, minimal_tree) -> None:
        health = [SubsystemHealthInput(s, 0.7, 0.1) for s in ["life_support","thermal","power"]]
        result = analyze_fault_tree(health, minimal_tree, 24.0)
        for event_id, contrib in result.subsystem_contributions.items():
            assert 0.0 <= contrib <= 1.0, f"{event_id} contribution {contrib:.4f} out of [0,1]"

    def test_risk_classification_critical_for_all_failed(self) -> None:
        tree = default_mission_fault_tree()
        health = [SubsystemHealthInput(s, 0.05, 1.0) for s in
                  ["life_support","thermal","solar_panels","battery","communications","computing"]]
        result = analyze_fault_tree(health, tree, 48.0)
        assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_birnbaum_importance_positive(self, minimal_tree) -> None:
        health = [SubsystemHealthInput(s, 0.7, 0.1) for s in ["life_support","thermal","power"]]
        result = analyze_fault_tree(health, minimal_tree, 24.0)
        for row in result.fmea_table:
            assert row.birnbaum_importance >= 0.0, (
                f"{row.event_id} Birnbaum importance {row.birnbaum_importance:.6f} < 0"
            )

    def test_fault_tree_abort_risk_feeds_allocator(self, minimal_tree) -> None:
        """End-to-end: use abort risk as crew_risk input to allocator."""
        from src.core.mission_resource_allocator import MissionResourceAllocator, SubsystemState
        health = [SubsystemHealthInput(s, 0.65, 0.15) for s in ["life_support","thermal","power"]]
        result = analyze_fault_tree(health, minimal_tree, 24.0)
        crew_risk = min(1.0, result.top_event_probability)
        alloc = MissionResourceAllocator()
        states = [
            SubsystemState("life_support", 0.65, 0.3, 1.0),
            SubsystemState("thermal", 0.65, 0.2, 0.9),
            SubsystemState("computing", 0.9, 0.1, 0.4),
        ]
        plan = alloc.recommend_allocation(states, crew_risk=crew_risk)
        assert 0.0 <= plan.allocations["life_support"] <= 1.0
        assert plan.risk_index == crew_risk
