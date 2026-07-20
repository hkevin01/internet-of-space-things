"""
data_volume_model.py - Onboard data buffer fill vs. contact window integration.

ID: CORE-038
Requirement: Given a schedule of ground contacts and a set of science
             instruments, simulate the onboard data buffer fill fraction
             over time and feed it back to build_constellation_schedule.
Purpose: Replace the static buffer_fill_fractions scalar with a dynamically
         simulated value so comms urgency correctly rises as the buffer fills
         between contacts and falls after successful downlinks.
Rationale: Science instruments at 10-100 Mbps fill a 64 GB buffer in hours;
           without this feedback the comms allocator has no awareness of
           imminent overflow risk.
Inputs: List[InstrumentProfile], List[ScheduleEntry], buffer capacity,
        simulation start/duration.
Outputs: DataVolumeState per satellite with buffer_fill_fraction for
         immediate injection into build_constellation_schedule.
Preconditions: constellation_scheduler module available.
Postconditions: buffer_fill_fraction in [0, 1]; overflow_events >= 0.
Assumptions: Instruments run at constant data rate * duty_cycle.
             Downlink fills at min(available_channel_rate, buffer_fill_rate).
             ISL transfer can pre-position data to a satellite with upcoming
             ground contact (optional relay mode).
Failure Modes: Contact window with data_rate_mbps = NaN treated as 0.
Error Handling: Empty instrument list returns zero-fill trace.
Constraints: Intended for same time range as the constellation schedule.
Verification: tests/test_advanced_systems.py.
References: Wertz "Space Mission Engineering" Ch. 13.
            Del Monte, L. "Onboard Data Management for Earth Observation
            Satellites" Acta Astronautica 2010.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .constellation_scheduler import ScheduleEntry, ScheduleEntryType


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class InstrumentProfile:
    """
    ID: CORE-038-DS1
    Purpose: Science instrument data production parameters.

    Fields:
        instrument_id   - unique name.
        data_rate_mbps  - raw data rate when active [Mbps].
        duty_cycle      - fraction of time instrument is producing data [0, 1].
        compression_ratio - on-board lossless compression factor (>= 1.0).
        priority        - scheduling priority [0, 1]; higher = downlinked first.
    """
    instrument_id: str
    data_rate_mbps: float
    duty_cycle: float = 1.0
    compression_ratio: float = 1.5
    priority: float = 0.5

    @property
    def effective_rate_mbps(self) -> float:
        """Net data accumulation rate after compression [Mbps]."""
        return self.data_rate_mbps * self.duty_cycle / max(1e-3, self.compression_ratio)


@dataclass
class BufferStep:
    """
    ID: CORE-038-DS2
    Purpose: Buffer state at one simulation timestep.
    """
    epoch: datetime
    fill_mb: float
    fill_fraction: float
    generation_rate_mbps: float
    downlink_rate_mbps: float
    overflow: bool


@dataclass
class DataVolumeState:
    """
    ID: CORE-038-DS3
    Purpose: Complete data volume simulation result for one satellite.

    Fields:
        sat_id               - satellite identifier.
        buffer_fill_fraction - fill fraction at END of simulation [0, 1].
        buffer_capacity_mb   - total buffer capacity [MB].
        total_generated_mb   - total data generated during interval [MB].
        total_downlinked_mb  - total data downlinked during interval [MB].
        total_relayed_mb     - data forwarded via ISL relay [MB].
        overflow_events      - number of timesteps where buffer >= 100%.
        downlink_utilization - fraction of available contact capacity used.
        average_fill_fraction - time-averaged buffer fill fraction.
        steps                - per-timestep trace (populated if keep_trace=True).
    """
    sat_id: str
    buffer_fill_fraction: float
    buffer_capacity_mb: float
    total_generated_mb: float
    total_downlinked_mb: float
    total_relayed_mb: float
    overflow_events: int
    downlink_utilization: float
    average_fill_fraction: float
    steps: List[BufferStep] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_data_volume(
    sat_id: str,
    schedule_entries: List[ScheduleEntry],
    instruments: List[InstrumentProfile],
    buffer_capacity_mb: float,
    sim_start: datetime,
    sim_duration_seconds: float,
    initial_fill_mb: float = 0.0,
    time_step_seconds: float = 60.0,
    keep_trace: bool = False,
    relay_entries: Optional[List[ScheduleEntry]] = None,
) -> DataVolumeState:
    """
    ID: CORE-038-F1
    Purpose: Simulate onboard data buffer fill over a scheduling interval
             for one satellite, integrating science data generation against
             contact-window downlink capacity.
    Inputs:
        sat_id              - satellite to simulate.
        schedule_entries    - full constellation schedule (all satellites).
        instruments         - list of instruments on this satellite.
        buffer_capacity_mb  - total buffer size [MB].
        sim_start           - UTC start of simulation.
        sim_duration_seconds - simulation length [s].
        initial_fill_mb     - buffer fill at sim_start [MB].
        time_step_seconds   - integration timestep [s].
        keep_trace          - if True, populate DataVolumeState.steps.
        relay_entries       - optional ISL relay windows where data can be
                              offloaded to a relay satellite for later downlink.
    Outputs: DataVolumeState.
    Algorithm:
        dt = time_step_seconds [s]
        For each step:
            1. Compute generation rate = sum(effective_rate_mbps for active instruments).
            2. Check if current time falls inside a ground contact window for sat_id.
               If yes: downlink_rate = entry.data_rate_mbps.
            3. Check ISL relay windows.
            4. Net: fill += (generation - downlink - relay) * dt / 1.0e6
               (rates in Mbps; dt in seconds -> result in Mb; /8 for MB)
            5. Clamp fill to [0, buffer_capacity].
    Notes:
        data_rate_mbps in ScheduleEntry is Megabits/s; buffer in MB (Megabytes).
        Conversion: 1 MB = 8 Mb, so: d_fill_MB = rate_Mbps * dt_s / 8.
    """
    if sim_start.tzinfo is None:
        sim_start = sim_start.replace(tzinfo=timezone.utc)

    # Filter entries for this satellite's downlinks
    downlink_windows: List[ScheduleEntry] = [
        e for e in schedule_entries
        if e.sat_id == sat_id and e.entry_type == ScheduleEntryType.GROUND_CONTACT
    ]
    relay_windows: List[ScheduleEntry] = [
        e for e in (relay_entries or [])
        if e.sat_id == sat_id and e.entry_type == ScheduleEntryType.ISL_WINDOW
    ]

    n_steps = max(1, int(sim_duration_seconds / time_step_seconds))
    dt_s = sim_duration_seconds / n_steps

    fill_mb = max(0.0, min(buffer_capacity_mb, initial_fill_mb))
    total_gen = 0.0
    total_dl = 0.0
    total_relay = 0.0
    overflow_n = 0
    available_contact_mb = 0.0
    used_contact_mb = 0.0
    fill_accum = 0.0
    steps: List[BufferStep] = []

    # Generation rate (constant)
    gen_rate_mbps = sum(inst.effective_rate_mbps for inst in instruments)

    for k in range(n_steps):
        t = sim_start + timedelta(seconds=k * dt_s)
        t_end = t + timedelta(seconds=dt_s)

        # Downlink rate: find active ground contact window at time t
        dl_rate_mbps = 0.0
        for w in downlink_windows:
            if w.start_time <= t < w.end_time:
                rate = w.data_rate_mbps
                if math.isnan(rate):
                    rate = 0.0
                dl_rate_mbps = max(dl_rate_mbps, rate)
        # ISL relay offload
        relay_rate_mbps = 0.0
        for w in relay_windows:
            if w.start_time <= t < w.end_time:
                rate = w.data_rate_mbps
                if math.isnan(rate):
                    rate = 0.0
                relay_rate_mbps = max(relay_rate_mbps, rate)

        # Account for available vs used contact capacity
        if dl_rate_mbps > 0:
            available_contact_mb += dl_rate_mbps * dt_s / 8.0

        # Net fill change [MB] in this step
        gen_mb = gen_rate_mbps * dt_s / 8.0
        dl_mb = min(fill_mb + gen_mb, dl_rate_mbps * dt_s / 8.0)
        relay_mb = min(max(0.0, fill_mb + gen_mb - dl_mb), relay_rate_mbps * dt_s / 8.0)

        fill_mb = fill_mb + gen_mb - dl_mb - relay_mb
        overflow = fill_mb > buffer_capacity_mb
        if overflow:
            overflow_n += 1
        fill_mb = max(0.0, min(buffer_capacity_mb, fill_mb))

        total_gen += gen_mb
        total_dl += dl_mb
        total_relay += relay_mb
        used_contact_mb += dl_mb
        fill_accum += fill_mb / max(1e-9, buffer_capacity_mb)

        if keep_trace:
            steps.append(BufferStep(
                epoch=t,
                fill_mb=fill_mb,
                fill_fraction=fill_mb / max(1e-9, buffer_capacity_mb),
                generation_rate_mbps=gen_rate_mbps,
                downlink_rate_mbps=dl_rate_mbps,
                overflow=overflow,
            ))

    dl_utilization = used_contact_mb / max(1e-9, available_contact_mb) if available_contact_mb > 0 else 0.0

    return DataVolumeState(
        sat_id=sat_id,
        buffer_fill_fraction=fill_mb / max(1e-9, buffer_capacity_mb),
        buffer_capacity_mb=buffer_capacity_mb,
        total_generated_mb=total_gen,
        total_downlinked_mb=total_dl,
        total_relayed_mb=total_relay,
        overflow_events=overflow_n,
        downlink_utilization=min(1.0, dl_utilization),
        average_fill_fraction=fill_accum / n_steps,
        steps=steps,
    )


def simulate_constellation_data_volume(
    schedule_entries: List[ScheduleEntry],
    satellite_instruments: Dict[str, List[InstrumentProfile]],
    buffer_capacity_mb: float = 65536.0,   # 64 GB default
    sim_start: Optional[datetime] = None,
    sim_duration_seconds: float = 86400.0,
    time_step_seconds: float = 60.0,
    initial_fill_fractions: Optional[Dict[str, float]] = None,
    keep_trace: bool = False,
) -> Dict[str, DataVolumeState]:
    """
    ID: CORE-038-F2
    Purpose: Simulate data volume for all satellites in a constellation and
             return a {sat_id: DataVolumeState} dict suitable for
             injecting buffer_fill_fractions into build_constellation_schedule.
    Inputs:
        schedule_entries       - full constellation schedule.
        satellite_instruments  - {sat_id: List[InstrumentProfile]}.
        buffer_capacity_mb     - per-satellite buffer size [MB].
        sim_start              - UTC sim start; inferred from schedule if None.
        sim_duration_seconds   - simulation horizon [s].
        time_step_seconds      - integration resolution [s].
        initial_fill_fractions - {sat_id: fraction} starting fill; default 0.
        keep_trace             - populate per-step trace lists.
    Outputs: {sat_id: DataVolumeState}.
    """
    if sim_start is None:
        times = [e.start_time for e in schedule_entries if e.start_time is not None]
        sim_start = min(times) if times else datetime.now(tz=timezone.utc)
    if sim_start.tzinfo is None:
        sim_start = sim_start.replace(tzinfo=timezone.utc)

    sat_ids = list(satellite_instruments.keys())
    fills_in = initial_fill_fractions or {}
    isl_relay = [e for e in schedule_entries if e.entry_type == ScheduleEntryType.ISL_WINDOW]

    results: Dict[str, DataVolumeState] = {}
    for sat_id in sat_ids:
        init_fill_mb = fills_in.get(sat_id, 0.0) * buffer_capacity_mb
        state = simulate_data_volume(
            sat_id=sat_id,
            schedule_entries=schedule_entries,
            instruments=satellite_instruments[sat_id],
            buffer_capacity_mb=buffer_capacity_mb,
            sim_start=sim_start,
            sim_duration_seconds=sim_duration_seconds,
            initial_fill_mb=init_fill_mb,
            time_step_seconds=time_step_seconds,
            keep_trace=keep_trace,
            relay_entries=isl_relay,
        )
        results[sat_id] = state
    return results


def buffer_fill_fractions_from_simulation(
    dv_states: Dict[str, "DataVolumeState"],
) -> Dict[str, float]:
    """
    ID: CORE-038-F3
    Purpose: Extract the current buffer_fill_fraction per satellite for
             direct injection into build_constellation_schedule's
             buffer_fill_fractions parameter.
    Inputs: dv_states - output of simulate_constellation_data_volume.
    Outputs: {sat_id: fill_fraction}.
    """
    return {sat_id: state.buffer_fill_fraction for sat_id, state in dv_states.items()}
