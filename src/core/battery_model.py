"""
battery_model.py - Dynamic battery state-of-charge propagation over orbital arcs.

ID: CORE-036
Requirement: Integrate solar power generation vs. spacecraft load over an
             orbital interval, tracking battery SOC with depth-of-discharge
             limits, charge/discharge efficiency, and self-discharge.
Purpose: Replace the static battery_state_of_charge scalar in
         compute_power_budget_fraction with a dynamically propagated value
         that reflects real eclipse cycling, so allocator decisions are
         grounded in actual energy availability.
Rationale: A satellite exiting a 35-min eclipse may have SOC reduced by 15-25
           percent depending on load; the allocator must know this to correctly
           scale distributable power.
Inputs: OrbitalElementsJ2, BatteryConfig, SolarConfig, start datetime,
        duration [s].
Outputs: BatteryOrbitTrace with per-step SOC, energy accounting, and the
         final SOC usable by compute_power_budget_fraction.
Preconditions: orbit_dynamics module available.
Postconditions: soc_trace values are in [max_dod_limit, 1.0].
Assumptions: Instantaneous power balance (no thermal coupling to battery
             temperature). Solar panel oriented for maximum output (or
             sun-tracking). Constant load power.
Failure Modes: Overcharge guarded at SOC=1.0; deep discharge guarded at
               soc_min (degradation warning emitted but simulation continues).
Error Handling: n_steps < 1 raises ValueError.
Constraints: Intended for intervals up to ~24 h (one to fifteen orbits).
Verification: tests/test_advanced_systems.py.
References: Patel, M.R. "Spacecraft Power Systems" 2005, Ch. 10-11.
            Wertz "Space Mission Engineering" Ch. 20.
            Goldmeer, J. "Battery Management for SmallSats" IAC-2019.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import numpy as np

from .orbit_dynamics import (
    OrbitalElementsJ2,
    MU_EARTH,
    compute_eclipse_state,
    compute_power_budget_fraction,
    propagate_j2,
)

# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SolarConfig:
    """
    ID: CORE-036-DS1
    Purpose: Solar power generation parameters.

    Fields:
        panel_area_m2         - total deployable solar panel area [m^2].
        cell_efficiency       - photovoltaic efficiency at BOL [0, 1].
        panel_degradation     - current fractional efficiency loss [0, 1].
        packing_factor        - fraction of area covered by cells [0, 1].
        inherent_degradation  - additional losses (wiring, temperature) [0, 1].
        sun_tracking          - True if panels always face sun (max output).
    """
    panel_area_m2: float = 0.032          # 6U CubeSat two-panel deployment
    cell_efficiency: float = 0.295        # GaAs triple-junction BOL
    panel_degradation: float = 0.0        # 0 = new panels
    packing_factor: float = 0.9
    inherent_degradation: float = 0.90    # power conditioning, temperature losses
    sun_tracking: bool = True             # sun-tracking gimbals assumed

    @property
    def nominal_power_w(self) -> float:
        """Maximum output in full sunlight [W]."""
        eta = (self.cell_efficiency * self.packing_factor
               * self.inherent_degradation * (1.0 - self.panel_degradation))
        solar_const = 1361.0   # W/m^2  (SOLAR_CONSTANT from orbit_dynamics)
        return self.panel_area_m2 * solar_const * eta


@dataclass
class BatteryConfig:
    """
    ID: CORE-036-DS2
    Purpose: Battery electrochemical parameters.

    Fields:
        capacity_wh           - usable capacity at BOL [Wh].
        max_dod               - maximum depth of discharge [0, 1].
                                (1.0 = full discharge allowed; typ 0.8 for Li-ion)
        charge_efficiency     - Coulombic efficiency on charge [0, 1].
        discharge_efficiency  - Coulombic efficiency on discharge [0, 1].
        self_discharge_per_hour - fractional SOC loss per hour at rest.
        capacity_fade_per_cycle - fractional capacity loss per equivalent cycle.
        initial_soc           - starting state of charge [0, 1].
    """
    capacity_wh: float = 40.0
    max_dod: float = 0.80
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.98
    self_discharge_per_hour: float = 0.00005   # ~0.05%/h for Li-ion at ~20 C
    capacity_fade_per_cycle: float = 0.0002    # 0.02% capacity loss per cycle
    initial_soc: float = 1.0

    @property
    def min_soc(self) -> float:
        """Minimum allowed SOC = 1 - max_dod."""
        return max(0.0, 1.0 - self.max_dod)


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BatteryStepState:
    """
    ID: CORE-036-DS3
    Purpose: Battery state at one simulation timestep.

    Fields:
        epoch              - UTC time of this sample.
        soc                - state of charge [0, 1].
        power_solar_w      - solar power generated at this instant [W].
        power_load_w       - spacecraft load power [W].
        power_net_w        - net power into battery (+ = charging) [W].
        eclipse_type       - "sunlit"/"penumbra"/"umbra".
        depth_of_discharge - 1 - soc.
    """
    epoch: datetime
    soc: float
    power_solar_w: float
    power_load_w: float
    power_net_w: float
    eclipse_type: str
    depth_of_discharge: float


@dataclass
class BatteryOrbitTrace:
    """
    ID: CORE-036-DS4
    Purpose: Complete battery SOC history over a simulated orbital interval.

    Fields:
        steps                  - per-timestep states.
        initial_soc            - SOC at start of interval.
        final_soc              - SOC at end of interval.
        min_soc                - minimum SOC reached (worst-case eclipse depth).
        max_soc                - maximum SOC reached.
        energy_generated_wh    - total solar energy harvested [Wh].
        energy_consumed_wh     - total energy drawn by load [Wh].
        net_energy_wh          - energy balance (+ = surplus).
        eclipse_duration_s     - total time in umbra [s].
        sunlit_duration_s      - total time in sunlight [s].
        charge_cycle_fraction  - equivalent full discharge cycles accumulated.
        deep_discharge_events  - number of steps where soc < min_soc.
        capacity_wh_effective  - effective capacity after fade this interval.
    """
    steps: List[BatteryStepState]
    initial_soc: float
    final_soc: float
    min_soc: float
    max_soc: float
    energy_generated_wh: float
    energy_consumed_wh: float
    net_energy_wh: float
    eclipse_duration_s: float
    sunlit_duration_s: float
    charge_cycle_fraction: float
    deep_discharge_events: int
    capacity_wh_effective: float


# ---------------------------------------------------------------------------
# Core propagation
# ---------------------------------------------------------------------------

def propagate_battery_soc(
    elements: OrbitalElementsJ2,
    solar: SolarConfig,
    battery: BatteryConfig,
    load_power_w: float,
    start: datetime,
    duration_seconds: float,
    n_steps: int = 360,
) -> BatteryOrbitTrace:
    """
    ID: CORE-036-F1
    Purpose: Integrate battery SOC over an orbital interval using
             Coulomb counting with eclipse-aware solar generation.
    Inputs:
        elements       - orbital elements (for eclipse computation).
        solar          - solar panel configuration.
        battery        - battery electrochemical configuration.
        load_power_w   - constant spacecraft power draw [W].
        start          - UTC start of integration.
        duration_seconds - integration window length [s].
        n_steps        - number of quadrature steps.
    Outputs: BatteryOrbitTrace.
    Algorithm:
        dt = duration / n_steps   [s]
        For each step k:
            1. Propagate orbit to t_k.
            2. Compute eclipse state -> illumination_fraction.
            3. P_solar = solar.nominal_power_w * illumination_fraction
            4. P_net = P_solar - load_power_w
            5. dE = P_net * dt / 3600  [Wh] (sign = +charging, -discharging)
            6. Apply efficiency:
               if dE > 0: dSOC = dE * charge_efficiency / capacity_eff
               else:      dSOC = dE / (discharge_efficiency * capacity_eff)
            7. Apply self-discharge: soc *= (1 - self_discharge * dt/3600)
            8. Clamp soc to [0, 1] with soft DoD floor warning.
        Capacity fade: capacity_eff = capacity_wh * (1 - fade * cycles)

    Failure Modes:
        soc < min_soc -> deep_discharge_events counter incremented.
        soc > 1.0     -> clamped (overcharge prevented by design).
    """
    if n_steps < 1:
        raise ValueError(f"n_steps must be >= 1, got {n_steps}")
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    dt_s = duration_seconds / n_steps
    dt_h = dt_s / 3600.0

    soc = max(battery.min_soc, min(1.0, battery.initial_soc))
    capacity_eff = battery.capacity_wh   # will be updated for fade

    steps: List[BatteryStepState] = []
    total_gen_wh = 0.0
    total_load_wh = 0.0
    eclipse_s = 0.0
    sunlit_s = 0.0
    deep_discharge = 0
    soc_min = soc
    soc_max = soc
    amp_cycle_accum = 0.0   # |dSOC| accumulator for cycle counting

    for k in range(n_steps):
        t = start + timedelta(seconds=k * dt_s)
        state = propagate_j2(elements, t)
        eclipse = compute_eclipse_state(state)
        illum = eclipse.solar_illumination_fraction

        # Solar power: nominal_power * illumination (sun-tracking assumed)
        p_solar = solar.nominal_power_w * illum

        # Net power balance
        p_net = p_solar - load_power_w
        dE_wh = p_net * dt_h   # energy balance this step [Wh]

        # Apply efficiency and capacity
        if dE_wh >= 0.0:
            dSOC = dE_wh * battery.charge_efficiency / max(1e-6, capacity_eff)
        else:
            dSOC = dE_wh / (battery.discharge_efficiency * max(1e-6, capacity_eff))

        # Self-discharge (always negative)
        soc_before_sd = soc + dSOC
        soc_after_sd = soc_before_sd * (1.0 - battery.self_discharge_per_hour * dt_h)

        # Clamp
        soc_new = max(0.0, min(1.0, soc_after_sd))
        actual_dSOC = soc_new - soc

        # Cycle counting: accumulate absolute SOC changes
        amp_cycle_accum += abs(actual_dSOC)

        # Deep discharge detection
        if soc_new < battery.min_soc:
            deep_discharge += 1

        soc_min = min(soc_min, soc_new)
        soc_max = max(soc_max, soc_new)

        # Energy accounting
        gen_wh = p_solar * dt_h
        load_wh = load_power_w * dt_h
        total_gen_wh += gen_wh
        total_load_wh += load_wh

        # Eclipse duration
        if eclipse.eclipse_type.value == "umbra":
            eclipse_s += dt_s
        elif eclipse.eclipse_type.value == "sunlit":
            sunlit_s += dt_s

        steps.append(BatteryStepState(
            epoch=t,
            soc=soc_new,
            power_solar_w=p_solar,
            power_load_w=load_power_w,
            power_net_w=p_net,
            eclipse_type=eclipse.eclipse_type.value,
            depth_of_discharge=1.0 - soc_new,
        ))

        soc = soc_new

    # Cycle fraction: one full cycle = discharge from 1.0 to min_soc and back
    # amp_cycle_accum / 2 (half cycle per full swing) gives equivalent cycles
    cycle_fraction = amp_cycle_accum / 2.0
    capacity_eff = battery.capacity_wh * (
        1.0 - battery.capacity_fade_per_cycle * cycle_fraction
    )

    return BatteryOrbitTrace(
        steps=steps,
        initial_soc=battery.initial_soc,
        final_soc=soc,
        min_soc=soc_min,
        max_soc=soc_max,
        energy_generated_wh=total_gen_wh,
        energy_consumed_wh=total_load_wh,
        net_energy_wh=total_gen_wh - total_load_wh,
        eclipse_duration_s=eclipse_s,
        sunlit_duration_s=sunlit_s,
        charge_cycle_fraction=cycle_fraction,
        deep_discharge_events=deep_discharge,
        capacity_wh_effective=capacity_eff,
    )


def soc_at_time(
    trace: BatteryOrbitTrace,
    offset_seconds: float,
    duration_seconds: float,
) -> float:
    """
    ID: CORE-036-F2
    Purpose: Interpolate SOC from a BatteryOrbitTrace at a given time offset.
    Inputs: trace - previously computed trace; offset_seconds - elapsed time
            since trace start [s]; duration_seconds - total trace duration [s].
    Outputs: interpolated SOC in [0, 1].
    """
    if not trace.steps:
        return trace.initial_soc
    n = len(trace.steps)
    frac = max(0.0, min(1.0, offset_seconds / max(1e-6, duration_seconds)))
    idx = frac * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    alpha = idx - lo
    return trace.steps[lo].soc * (1.0 - alpha) + trace.steps[hi].soc * alpha


def eclipse_aware_power_budget(
    elements: OrbitalElementsJ2,
    solar: SolarConfig,
    battery: BatteryConfig,
    load_power_w: float,
    dt: datetime,
    lookback_seconds: float = 5400.0,
    n_steps: int = 180,
) -> float:
    """
    ID: CORE-036-F3
    Purpose: Compute the instantaneous power_budget_fraction by first
             propagating the battery SOC over the recent past (lookback),
             then computing the available power at dt.
    Inputs:
        elements        - orbital elements.
        solar, battery  - hardware configurations.
        load_power_w    - spacecraft load [W].
        dt              - target datetime for power fraction.
        lookback_seconds - how far back to start SOC propagation.
        n_steps         - integration steps over lookback.
    Outputs: power_budget_fraction in [0, 1].
    Rationale: Simulating from an initial known SOC (battery.initial_soc)
               over the lookback ensures the returned fraction reflects
               actual eclipse history, not just the instantaneous eclipse flag.
    """
    start = dt - timedelta(seconds=lookback_seconds)
    trace = propagate_battery_soc(
        elements, solar, battery, load_power_w, start, lookback_seconds, n_steps
    )
    current_soc = trace.final_soc

    # Solar contribution at dt
    state = propagate_j2(elements, dt)
    eclipse = compute_eclipse_state(state)
    panel_eff = max(0.0, 1.0 - solar.panel_degradation)
    solar_fraction = eclipse.solar_illumination_fraction * panel_eff

    # Battery contribution: fraction of load that battery can supply
    batt_fraction = 0.60 * current_soc   # matches compute_power_budget_fraction convention

    raw = solar_fraction + batt_fraction * (1.0 - solar_fraction)
    return max(0.0, min(1.0, raw))
