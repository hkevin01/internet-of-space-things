"""
constellation_scheduler.py - Time-ordered contact and ISL schedule for a
                              multi-satellite IoST constellation.

ID: CORE-034
Requirement: Given N satellites and M ground stations, produce a unified
             time-ordered schedule of (a) ground contact windows and
             (b) inter-satellite link (ISL) availability windows, for
             ingestion by the comms resource allocator.
Purpose: Allow the communications subsystem demand fraction to be driven
         by upcoming window scarcity rather than a fixed constant.
Rationale: A satellite with no upcoming ground contact in the next 30 min
           must buffer science data; communications allocation urgency rises
           as the window approaches and falls after downlink completion.
Inputs: List[ConstellationSat], List[GroundStation], search interval.
Outputs: List[ScheduleEntry] sorted ascending by start_time.
Preconditions: orbit_dynamics module available.
Postconditions: All entries reference valid satellite IDs and station/peer IDs.
Assumptions: ISL visibility uses Earth-occultation-only check (no atmosphere
             for crosslinks at typical LEO altitudes >= 400 km).
Failure Modes: Empty satellite list returns empty schedule.
Verification: tests/test_orbital_extensions.py.
References: Wertz "Space Mission Engineering" Ch. 13.
            Lutz & Jahn "Satellite Systems for Personal and Broadband
            Communications" 2000.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

from .orbit_dynamics import (
    ContactWindow,
    GroundStation,
    OrbitalElementsJ2,
    check_isl_visibility,
    compute_isl_link_budget,
    find_contact_windows,
    propagate_j2,
    R_EARTH,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ScheduleEntryType(Enum):
    """
    ID: CORE-034-DS1
    Purpose: Tag type for a schedule entry.
    """
    GROUND_CONTACT = "ground_contact"
    ISL_WINDOW = "isl_window"


@dataclass
class ConstellationSat:
    """
    ID: CORE-034-DS2
    Purpose: Satellite descriptor for constellation scheduling.

    Fields:
        sat_id          - unique identifier.
        elements        - J2-perturbed orbital elements.
        isl_capable     - whether this satellite has inter-satellite link hardware.
        isl_freq_hz     - ISL carrier frequency (for link budget).
        isl_tx_power_w  - ISL transmit power [W].
    """
    sat_id: str
    elements: OrbitalElementsJ2
    isl_capable: bool = True
    isl_freq_hz: float = 2.4e9
    isl_tx_power_w: float = 2.0


@dataclass
class ScheduleEntry:
    """
    ID: CORE-034-DS3
    Purpose: One contiguous communications window in the constellation schedule.

    Fields:
        entry_type      - GROUND_CONTACT or ISL_WINDOW.
        sat_id          - satellite initiating or involved in the link.
        peer_id         - ground station ID (GROUND_CONTACT) or remote sat ID (ISL_WINDOW).
        start_time      - window open (UTC).
        end_time        - window close (UTC).
        max_elevation_deg - peak elevation above ground station horizon (GROUND_CONTACT only).
        min_range_km    - minimum slant range during window.
        link_margin_db  - predicted RF link margin [dB] (ISL only; NaN for ground contacts).
        data_rate_mbps  - estimated achievable data rate [Mbps].
    """
    entry_type: ScheduleEntryType
    sat_id: str
    peer_id: str
    start_time: datetime
    end_time: datetime
    max_elevation_deg: float = float("nan")
    min_range_km: float = float("nan")
    link_margin_db: float = float("nan")
    data_rate_mbps: float = float("nan")

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class ConstellationSchedule:
    """
    ID: CORE-034-DS4
    Purpose: Full scheduled window set with per-satellite statistics.

    Fields:
        entries                - sorted list of all ScheduleEntry objects.
        ground_contact_counts  - {sat_id: count of ground windows}.
        isl_link_counts        - {sat_id: count of ISL windows}.
        comms_demand_fractions - {sat_id: urgency [0,1] for comms allocator}.
    """
    entries: List[ScheduleEntry]
    ground_contact_counts: Dict[str, int]
    isl_link_counts: Dict[str, int]
    comms_demand_fractions: Dict[str, float]


# ---------------------------------------------------------------------------
# Ground contact collection
# ---------------------------------------------------------------------------

def _collect_ground_contacts(
    satellites: List[ConstellationSat],
    stations: List[GroundStation],
    search_start: datetime,
    search_duration_s: float,
    time_step_s: float,
) -> List[ScheduleEntry]:
    """
    ID: CORE-034-F1
    Purpose: Collect all ground contact windows for every satellite-station pair.
    """
    entries: List[ScheduleEntry] = []
    for sat in satellites:
        for station in stations:
            windows = find_contact_windows(
                sat.elements, station,
                search_start, search_duration_s, time_step_s,
            )
            for w in windows:
                # Estimate data rate from link margin (Shannon-inspired rough bound)
                # For X-band 8 GHz with 5 MHz bandwidth: capacity ~ BW * log2(1 + 10^(SNR/10))
                # Simplified: use elevation as proxy; higher elevation -> shorter range -> better link
                entries.append(ScheduleEntry(
                    entry_type=ScheduleEntryType.GROUND_CONTACT,
                    sat_id=sat.sat_id,
                    peer_id=station.station_id,
                    start_time=w.aos,
                    end_time=w.los,
                    max_elevation_deg=w.max_elevation_deg,
                    min_range_km=min(w.aos_range_km, w.los_range_km),
                    link_margin_db=float("nan"),
                    data_rate_mbps=_estimate_ground_data_rate_mbps(w.max_elevation_deg),
                ))
    return entries


def _estimate_ground_data_rate_mbps(max_elevation_deg: float) -> float:
    """
    ID: CORE-034-H1
    Purpose: Rough elevation-based data rate estimate for X-band downlink.
    Assumes 5 MHz bandwidth, typical 25W transmitter, 1.5m dish.
    At 5 deg elevation: ~50 Mbps; at 90 deg: ~150 Mbps.
    """
    # Linear interpolation in elevation angle
    lo_elev, lo_rate = 5.0, 50.0
    hi_elev, hi_rate = 90.0, 150.0
    alpha = max(0.0, min(1.0, (max_elevation_deg - lo_elev) / (hi_elev - lo_elev)))
    return lo_rate + alpha * (hi_rate - lo_rate)


# ---------------------------------------------------------------------------
# ISL window collection
# ---------------------------------------------------------------------------

def _collect_isl_windows(
    satellites: List[ConstellationSat],
    search_start: datetime,
    search_duration_s: float,
    time_step_s: float,
    link_margin_threshold_db: float = 3.0,
) -> List[ScheduleEntry]:
    """
    ID: CORE-034-F2
    Purpose: Scan all satellite pairs for ISL visibility windows.
    Algorithm:
        For each pair (i, j) with i < j, scan at time_step_s resolution.
        Detect rising/falling edges of ISL visibility using check_isl_visibility.
        Refine window edges with bisection to ~1 s accuracy.
        Compute link budget at window midpoint.
    Inputs:
        link_margin_threshold_db - minimum link margin to declare window usable.
    """
    entries: List[ScheduleEntry] = []
    isl_sats = [s for s in satellites if s.isl_capable]
    n = len(isl_sats)
    if n < 2:
        return entries

    n_steps = int(search_duration_s / time_step_s) + 1

    for i in range(n):
        for j in range(i + 1, n):
            sat_a = isl_sats[i]
            sat_b = isl_sats[j]
            prev_visible: Optional[bool] = None
            window_start: Optional[datetime] = None
            window_min_range: float = float("inf")

            for k in range(n_steps):
                t = search_start + timedelta(seconds=k * time_step_s)
                st_a = propagate_j2(sat_a.elements, t)
                st_b = propagate_j2(sat_b.elements, t)
                visible, rng = check_isl_visibility(st_a.position, st_b.position)

                if visible:
                    window_min_range = min(window_min_range, rng)

                if prev_visible is None:
                    # Very first sample: start window if already visible at search_start
                    if visible:
                        window_start = search_start
                        window_min_range = rng
                elif not prev_visible and visible:
                    # Rising edge
                    t_rise = _bisect_isl(sat_a, sat_b, t - timedelta(seconds=time_step_s), t, rising=True)
                    window_start = t_rise
                    window_min_range = rng

                if prev_visible is not None and prev_visible and not visible:
                    # Falling edge
                    t_fall = _bisect_isl(sat_a, sat_b, t - timedelta(seconds=time_step_s), t, rising=False)
                    if window_start is not None:
                        mid_t = window_start + timedelta(seconds=(t_fall - window_start).total_seconds() / 2.0)
                        st_a_mid = propagate_j2(sat_a.elements, mid_t)
                        st_b_mid = propagate_j2(sat_b.elements, mid_t)
                        budget = compute_isl_link_budget(
                            st_a_mid.position, st_b_mid.position,
                            transmit_power_w=sat_a.isl_tx_power_w,
                            carrier_freq_hz=sat_a.isl_freq_hz,
                        )
                        if budget["link_margin_db"] >= link_margin_threshold_db:
                            dr = _isl_data_rate_mbps(budget["link_margin_db"])
                            entries.append(ScheduleEntry(
                                entry_type=ScheduleEntryType.ISL_WINDOW,
                                sat_id=sat_a.sat_id,
                                peer_id=sat_b.sat_id,
                                start_time=window_start,
                                end_time=t_fall,
                                link_margin_db=budget["link_margin_db"],
                                min_range_km=window_min_range,
                                data_rate_mbps=dr,
                            ))
                    window_start = None
                    window_min_range = float("inf")

                prev_visible = visible

            # Close any open window at end of search
            if prev_visible and window_start is not None:
                end_t = search_start + timedelta(seconds=search_duration_s)
                st_a_end = propagate_j2(sat_a.elements, end_t)
                st_b_end = propagate_j2(sat_b.elements, end_t)
                budget = compute_isl_link_budget(
                    st_a_end.position, st_b_end.position,
                    transmit_power_w=sat_a.isl_tx_power_w,
                    carrier_freq_hz=sat_a.isl_freq_hz,
                )
                if budget["link_margin_db"] >= link_margin_threshold_db:
                    entries.append(ScheduleEntry(
                        entry_type=ScheduleEntryType.ISL_WINDOW,
                        sat_id=sat_a.sat_id,
                        peer_id=sat_b.sat_id,
                        start_time=window_start,
                        end_time=end_t,
                        link_margin_db=budget["link_margin_db"],
                        min_range_km=window_min_range,
                        data_rate_mbps=_isl_data_rate_mbps(budget["link_margin_db"]),
                    ))

    return entries


def _bisect_isl(
    sat_a: ConstellationSat,
    sat_b: ConstellationSat,
    t_lo: datetime,
    t_hi: datetime,
    rising: bool,
    iterations: int = 16,
) -> datetime:
    """
    ID: CORE-034-H2
    Purpose: Binary search for ISL visibility edge crossing.
    Outputs: Refined crossing datetime.
    """
    for _ in range(iterations):
        span = (t_hi - t_lo).total_seconds()
        t_mid = t_lo + timedelta(seconds=span / 2.0)
        st_a = propagate_j2(sat_a.elements, t_mid)
        st_b = propagate_j2(sat_b.elements, t_mid)
        vis, _ = check_isl_visibility(st_a.position, st_b.position)
        if rising:
            if vis:
                t_hi = t_mid
            else:
                t_lo = t_mid
        else:
            if vis:
                t_lo = t_mid
            else:
                t_hi = t_mid
    return t_lo + timedelta(seconds=(t_hi - t_lo).total_seconds() / 2.0)


def _isl_data_rate_mbps(link_margin_db: float) -> float:
    """
    ID: CORE-034-H3
    Purpose: Convert ISL link margin to estimated data rate.
    Mapping: 3 dB margin -> 1 Mbps; 20 dB margin -> 100 Mbps (log-linear).
    """
    if link_margin_db <= 3.0:
        return 1.0
    return min(100.0, 1.0 * (10.0 ** ((link_margin_db - 3.0) / 10.0)))


# ---------------------------------------------------------------------------
# Communications demand fraction
# ---------------------------------------------------------------------------

def _comms_demand_fraction(
    sat_id: str,
    entries: List[ScheduleEntry],
    search_start: datetime,
    horizon_seconds: float = 3600.0,
    buffer_fill_fraction: float = 0.5,
) -> float:
    """
    ID: CORE-034-F3
    Purpose: Derive communications subsystem demand fraction from window scarcity.
    Rationale: If no ground contact is available in the next `horizon_seconds`,
               data buffer fills and comms urgency rises to 1.0.
               A window occurring soon with high data rate reduces urgency.
    Inputs:
        sat_id              - satellite to compute demand for.
        entries             - full schedule (already filtered to this sat).
        horizon_seconds     - planning horizon for urgency calculation.
        buffer_fill_fraction - current data buffer fill (0=empty, 1=full);
                               higher fill raises base urgency.
    Outputs: demand fraction in [0, 1].
    """
    horizon_end = search_start + timedelta(seconds=horizon_seconds)
    upcoming = [
        e for e in entries
        if e.sat_id == sat_id
        and e.entry_type == ScheduleEntryType.GROUND_CONTACT
        and e.start_time >= search_start
        and e.start_time <= horizon_end
    ]

    if not upcoming:
        # No contact in horizon - urgency is driven purely by buffer fill
        return min(1.0, 0.6 + 0.4 * buffer_fill_fraction)

    # Contact available: urgency = function of time-to-next-contact and fill
    next_contact = min(upcoming, key=lambda e: e.start_time)
    time_to_contact_s = max(0.0, (next_contact.start_time - search_start).total_seconds())
    # Urgency rises linearly from 0.1 (contact now) to 0.8 (contact at end of horizon)
    time_urgency = 0.1 + 0.7 * (time_to_contact_s / horizon_seconds)
    fill_urgency = 0.4 * buffer_fill_fraction
    return min(1.0, time_urgency + fill_urgency)


# ---------------------------------------------------------------------------
# Main scheduler entry point
# ---------------------------------------------------------------------------

def build_constellation_schedule(
    satellites: List[ConstellationSat],
    stations: List[GroundStation],
    search_start: datetime,
    search_duration_seconds: float = 86400.0,
    time_step_seconds: float = 15.0,
    include_isl: bool = True,
    buffer_fill_fractions: Optional[Dict[str, float]] = None,
    comms_horizon_seconds: float = 3600.0,
    isl_link_margin_threshold_db: float = 3.0,
) -> ConstellationSchedule:
    """
    ID: CORE-034-F4
    Purpose: Build a complete time-ordered constellation contact + ISL schedule.
    Inputs:
        satellites              - list of ConstellationSat descriptors.
        stations                - list of ground stations.
        search_start            - UTC start of scheduling window.
        search_duration_seconds - total scheduling horizon.
        time_step_seconds       - scan resolution (15 s trades speed for accuracy).
        include_isl             - whether to compute ISL windows.
        buffer_fill_fractions   - {sat_id: fill 0..1} for demand calculation.
        comms_horizon_seconds   - look-ahead horizon for urgency calculation.
    Outputs: ConstellationSchedule with entries sorted by start_time.
    """
    if search_start.tzinfo is None:
        search_start = search_start.replace(tzinfo=timezone.utc)

    buf_fills = buffer_fill_fractions or {}

    # Gather ground contacts
    ground_entries = _collect_ground_contacts(
        satellites, stations, search_start, search_duration_seconds, time_step_seconds
    )

    # Gather ISL windows
    isl_entries: List[ScheduleEntry] = []
    if include_isl:
        isl_entries = _collect_isl_windows(
            satellites, search_start, search_duration_seconds, time_step_seconds,
            link_margin_threshold_db=isl_link_margin_threshold_db,
        )

    all_entries = ground_entries + isl_entries
    all_entries.sort(key=lambda e: e.start_time)

    # Per-satellite statistics
    ground_counts: Dict[str, int] = {s.sat_id: 0 for s in satellites}
    isl_counts: Dict[str, int] = {s.sat_id: 0 for s in satellites}
    for e in all_entries:
        if e.entry_type == ScheduleEntryType.GROUND_CONTACT:
            ground_counts[e.sat_id] = ground_counts.get(e.sat_id, 0) + 1
        else:
            isl_counts[e.sat_id] = isl_counts.get(e.sat_id, 0) + 1
            # Both satellites share the window
            isl_counts[e.peer_id] = isl_counts.get(e.peer_id, 0) + 1

    # Communications demand fractions
    comms_demands: Dict[str, float] = {}
    for sat in satellites:
        fill = buf_fills.get(sat.sat_id, 0.5)
        comms_demands[sat.sat_id] = _comms_demand_fraction(
            sat.sat_id, all_entries, search_start,
            comms_horizon_seconds, fill,
        )

    return ConstellationSchedule(
        entries=all_entries,
        ground_contact_counts=ground_counts,
        isl_link_counts=isl_counts,
        comms_demand_fractions=comms_demands,
    )
