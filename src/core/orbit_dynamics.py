"""
orbit_dynamics.py - J2-perturbed orbital propagation, eclipse detection,
                    ground station contact windows, and power-budget coupling.

ID: CORE-030
Requirement: Provide accurate-enough orbital state for resource scheduling -
             specifically (a) J2-secular position/velocity at arbitrary future
             times, (b) illumination fraction per orbit, (c) upcoming ground
             contact intervals, and (d) a scalar power_budget_fraction that
             the MissionResourceAllocator can consume directly.
Purpose: Replace the first-order Keplerian stub in satellite_manager.py with a
         physically consistent propagator that feeds downstream systems with
         eclipse-aware power budgets and comms-window schedules.
Rationale: LEO orbits precess ~7 deg/day in RAAN and ~3.5 deg/day in AoP due
           to J2; ignoring this makes contact windows drift by tens of minutes
           per day and makes power estimates wrong by up to 30-40 percent during
           near-terminator orbits.
Inputs: OrbitalElementsJ2 (Keplerian + epoch), GroundStation (geodetic),
        mission datetime.
Outputs: EciState, EclipseState, ContactWindow list, power_budget_fraction.
Preconditions: numpy available.
Postconditions: Allocations calling power_budget_fraction see a value in [0, 1].
Assumptions: Point-mass Earth + J2 only (no drag, no third-body). Sun modelled
             with low-precision solar ephemeris (< 1 deg error).
Side Effects: None - all functions are pure unless a metrics_sink is attached.
Failure Modes: Kepler solver convergence checked; degenerate circular orbits
               handled by bypassing eccentric-anomaly when e < 1e-9.
Error Handling: ValueError raised on physically impossible input (e >= 1, a <= 0).
Constraints: Suitable for LEO/MEO over propagation horizons up to ~7 days
             without higher-order perturbations.
Verification: Test suite in tests/test_orbit_dynamics.py.
References: Vallado, D.A. "Fundamentals of Astrodynamics and Applications" 4th ed.
            Montenbruck & Gill "Satellite Orbits" 2000.
            Meeus "Astronomical Algorithms" Ch. 27 (solar ephemeris).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

MU_EARTH: float = 398600.4418          # km^3 / s^2  (GM)
R_EARTH: float = 6378.137              # km           (WGS-84 equatorial radius)
F_EARTH: float = 1.0 / 298.257223563  # WGS-84 flattening
E2_EARTH: float = 2 * F_EARTH - F_EARTH ** 2  # first eccentricity squared
J2: float = 1.08262668e-3              # dimensionless
R_SUN: float = 696_000.0              # km
AU_KM: float = 149_597_870.7          # km  (1 AU)
C_LIGHT: float = 299_792.458          # km/s
EARTH_ROTATION_RATE: float = 7.292115e-5  # rad/s  (omega_earth)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OrbitalElementsJ2:
    """
    ID: CORE-030-DS1
    Keplerian elements at epoch for J2-perturbed propagation.
    All angles in degrees, distances in km.

    Preconditions: 0 <= eccentricity < 1; semi_major_axis > R_EARTH.
    """
    semi_major_axis: float        # a  [km]
    eccentricity: float           # e  [0, 1)
    inclination_deg: float        # i  [deg]
    raan_deg: float               # Omega, right ascension of ascending node [deg]
    arg_perigee_deg: float        # omega [deg]
    mean_anomaly_deg: float       # M0 [deg] at epoch
    epoch: datetime               # UTC epoch

    def __post_init__(self) -> None:
        if self.eccentricity >= 1.0 or self.eccentricity < 0.0:
            raise ValueError(f"Eccentricity must be in [0, 1); got {self.eccentricity}")
        if self.semi_major_axis <= R_EARTH:
            raise ValueError(
                f"semi_major_axis {self.semi_major_axis} km is below Earth's surface"
            )


@dataclass
class EciState:
    """
    ID: CORE-030-DS2
    Earth-Centered Inertial (ECI) position and velocity at a given epoch.
    Units: km and km/s.
    """
    position: np.ndarray   # shape (3,) km
    velocity: np.ndarray   # shape (3,) km/s
    epoch: datetime


class EclipseType(Enum):
    """
    ID: CORE-030-DS3
    Shadow regime of the satellite.
    """
    SUNLIT = "sunlit"
    PENUMBRA = "penumbra"
    UMBRA = "umbra"


@dataclass
class EclipseState:
    """
    ID: CORE-030-DS4
    Illumination state and derived power fraction.

    solar_illumination_fraction:
        1.0  - fully sunlit
        0.0  - deep umbra
        (0, 1) - partial penumbra (linear approximation of occultation disc)
    """
    eclipse_type: EclipseType
    solar_illumination_fraction: float   # [0, 1]
    sun_elevation_deg: float             # elevation of Sun above satellite local horizon [deg]
    epoch: datetime

    @property
    def is_eclipse(self) -> bool:
        return self.eclipse_type != EclipseType.SUNLIT


@dataclass
class GroundStation:
    """
    ID: CORE-030-DS5
    Ground station geodetic position.

    latitude_deg:  [-90, 90]
    longitude_deg: [-180, 180]
    altitude_m: metres above WGS-84 ellipsoid
    elevation_mask_deg: minimum elevation for usable contact (typ. 5-10 deg)
    """
    station_id: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0
    elevation_mask_deg: float = 5.0
    downlink_freq_hz: float = 8.0e9     # X-band default


@dataclass
class ContactWindow:
    """
    ID: CORE-030-DS6
    A contiguous ground-station contact interval.

    max_elevation_deg: peak elevation during the pass [deg]
    doppler_shift_hz_at_aos: Doppler frequency offset at Acquisition of Signal
    doppler_shift_hz_at_los: Doppler frequency offset at Loss of Signal
    """
    station_id: str
    aos: datetime                   # Acquisition of Signal
    los: datetime                   # Loss of Signal
    max_elevation_deg: float
    aos_range_km: float
    los_range_km: float
    doppler_shift_hz_at_aos: float
    doppler_shift_hz_at_los: float

    @property
    def duration_seconds(self) -> float:
        return (self.los - self.aos).total_seconds()


# ---------------------------------------------------------------------------
# Julian date helpers
# ---------------------------------------------------------------------------

def _datetime_to_jd(dt: datetime) -> float:
    """
    ID: CORE-030-F1
    Purpose: Convert datetime to Julian Date.
    Reference: Meeus Ch. 7.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    y, m = dt.year, dt.month
    d = (dt.day + dt.hour / 24.0 + dt.minute / 1440.0
         + dt.second / 86400.0 + dt.microsecond / 86400e6)
    if m <= 2:
        y -= 1
        m += 12
    A = int(y / 100)
    B = 2 - A + int(A / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5


def _jd_to_j2000_centuries(jd: float) -> float:
    """Julian centuries from J2000.0 (JD 2451545.0)."""
    return (jd - 2451545.0) / 36525.0


# ---------------------------------------------------------------------------
# Low-precision solar ephemeris
# ---------------------------------------------------------------------------

def sun_eci_unit(dt: datetime) -> np.ndarray:
    """
    ID: CORE-030-F2
    Purpose: Compute unit vector from Earth center to Sun in ECI frame.
    Rationale: Eclipse and power-budget calculations need a Sun direction;
               full DE440 ephemeris is overkill - USNO simplified formulae
               (error < 0.01 deg) are sufficient for shadow geometry.
    Inputs: dt - UTC datetime.
    Outputs: shape-(3,) unit vector (no units; ECI frame, J2000 axes).
    References: Meeus "Astronomical Algorithms" Ch. 27;
                USNO Naval Observatory Circular 163.
    """
    T = _jd_to_j2000_centuries(_datetime_to_jd(dt))
    # Geometric mean longitude of Sun [deg]
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    # Mean anomaly of Sun [deg]
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
    M_rad = math.radians(M % 360.0)
    # Equation of center [deg]
    C = (1.914666471 - 0.004817 * T - 0.000014 * T * T) * math.sin(M_rad)
    C += (0.019994643 - 0.000101 * T) * math.sin(2.0 * M_rad)
    C += 0.000290 * math.sin(3.0 * M_rad)
    lam = math.radians((L0 + C) % 360.0)   # apparent ecliptic longitude
    # Mean obliquity of ecliptic [deg]
    eps = math.radians(23.439291111 - 0.013004167 * T - 0.000000164 * T * T
                       + 0.000000504 * T * T * T)
    # ECI unit vector
    s_hat = np.array([
        math.cos(lam),
        math.cos(eps) * math.sin(lam),
        math.sin(eps) * math.sin(lam),
    ])
    return s_hat / np.linalg.norm(s_hat)


# ---------------------------------------------------------------------------
# J2-perturbed Keplerian propagator
# ---------------------------------------------------------------------------

def _kepler_solve(M: float, e: float, tol: float = 1e-12) -> float:
    """
    ID: CORE-030-F3
    Purpose: Solve Kepler's equation M = E - e*sin(E) for eccentric anomaly E
             using Newton-Raphson iteration.
    Inputs: M [rad], eccentricity e, convergence tolerance.
    Outputs: E [rad].
    Failure Modes: Falls back after 50 iterations with last estimate.
    """
    E = M + e * math.sin(M) * (1.0 + e * math.cos(M))  # starter
    for _ in range(50):
        dE = (M - E + e * math.sin(E)) / (1.0 - e * math.cos(E))
        E += dE
        if abs(dE) < tol:
            break
    return E


def _elements_to_eci(
    a: float, e: float,
    i_rad: float, raan_rad: float, aop_rad: float,
    M_rad: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    ID: CORE-030-F4
    Purpose: Convert Keplerian elements to ECI position [km] and velocity [km/s].
    Inputs: a [km], e, angles [rad].
    Outputs: (r_eci [km], v_eci [km/s]).
    """
    if e < 1e-9:
        # Circular orbit - true anomaly == mean anomaly
        nu = M_rad
        E = M_rad
        r_scalar = a
    else:
        E = _kepler_solve(M_rad, e)
        # True anomaly
        nu = 2.0 * math.atan2(
            math.sqrt(1.0 + e) * math.sin(E / 2.0),
            math.sqrt(1.0 - e) * math.cos(E / 2.0),
        )
        r_scalar = a * (1.0 - e * math.cos(E))

    # Position and velocity in perifocal (PQW) frame
    p = a * (1.0 - e * e)          # semi-latus rectum
    sqrt_mu_p = math.sqrt(MU_EARTH / p)
    cos_nu, sin_nu = math.cos(nu), math.sin(nu)

    r_pqw = np.array([r_scalar * cos_nu, r_scalar * sin_nu, 0.0])
    v_pqw = np.array([-sqrt_mu_p * sin_nu, sqrt_mu_p * (e + cos_nu), 0.0])

    # Rotation matrix: PQW -> ECI  (Rz(-raan) * Rx(-i) * Rz(-aop))
    co, so = math.cos(raan_rad), math.sin(raan_rad)
    ci, si = math.cos(i_rad), math.sin(i_rad)
    cw, sw = math.cos(aop_rad), math.sin(aop_rad)

    # Combined rotation matrix Q (perifocal to ECI)
    Q = np.array([
        [co * cw - so * sw * ci,  -co * sw - so * cw * ci,  so * si],
        [so * cw + co * sw * ci,  -so * sw + co * cw * ci, -co * si],
        [sw * si,                   cw * si,                 ci     ],
    ])

    r_eci = Q @ r_pqw
    v_eci = Q @ v_pqw
    return r_eci, v_eci


def compute_j2_secular_rates(
    a: float, e: float, i_rad: float
) -> Tuple[float, float, float]:
    """
    ID: CORE-030-F5
    Purpose: Compute J2-secular drift rates for RAAN, argument-of-perigee,
             and corrected mean motion.
    Rationale: LEO RAAN drifts ~7 deg/day; omitting it causes > 1000 km
               position error per day.
    Inputs: a [km], eccentricity e, inclination i [rad].
    Outputs: (d_raan_rad_per_s, d_aop_rad_per_s, n_eff_rad_per_s)
    References: Vallado 4th ed. eq. 9-41 to 9-43.
    """
    p = a * (1.0 - e * e)          # semi-latus rectum [km]
    n = math.sqrt(MU_EARTH / a ** 3)  # mean motion [rad/s]
    k = 1.5 * J2 * (R_EARTH / p) ** 2
    ci = math.cos(i_rad)
    si = math.sin(i_rad)
    # RAAN secular rate [rad/s]
    d_raan = -k * n * ci
    # AoP secular rate [rad/s]
    d_aop = k * n * (2.5 * ci * ci - 0.5)
    # Mean motion correction for oblateness
    sqrt_1me2 = math.sqrt(1.0 - e * e)
    n_eff = n * (1.0 + k * sqrt_1me2 * (1.0 - 1.5 * si * si))
    return d_raan, d_aop, n_eff


def propagate_j2(elements: OrbitalElementsJ2, target: datetime) -> EciState:
    """
    ID: CORE-030-F6
    Purpose: Propagate OrbitalElementsJ2 from epoch to target datetime using
             J2-secular perturbations and Newton-Raphson Kepler solver.
    Inputs: elements - initial Keplerian elements with epoch;
            target   - desired propagation epoch (UTC datetime).
    Outputs: EciState at target epoch.
    Preconditions: target >= epoch is NOT required; backward propagation is valid.
    Postconditions: |position| > R_EARTH (satellite above surface).
    Failure Modes: Very large dt (> ~14 days) will accumulate secular error;
                   for operational use, re-ingest TLE every 2-3 days.
    """
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    epoch = elements.epoch
    if epoch.tzinfo is None:
        epoch = epoch.replace(tzinfo=timezone.utc)

    dt_s = (target - epoch).total_seconds()
    a = elements.semi_major_axis
    e = elements.eccentricity
    i_rad = math.radians(elements.inclination_deg)
    raan0 = math.radians(elements.raan_deg)
    aop0 = math.radians(elements.arg_perigee_deg)
    M0 = math.radians(elements.mean_anomaly_deg)

    d_raan, d_aop, n_eff = compute_j2_secular_rates(a, e, i_rad)

    raan = (raan0 + d_raan * dt_s) % (2.0 * math.pi)
    aop = (aop0 + d_aop * dt_s) % (2.0 * math.pi)
    M = (M0 + n_eff * dt_s) % (2.0 * math.pi)

    r_eci, v_eci = _elements_to_eci(a, e, i_rad, raan, aop, M)
    return EciState(position=r_eci, velocity=v_eci, epoch=target)


# ---------------------------------------------------------------------------
# Eclipse detection (conical shadow model)
# ---------------------------------------------------------------------------

def compute_eclipse_state(eci_state: EciState) -> EclipseState:
    """
    ID: CORE-030-F7
    Purpose: Determine whether the satellite is in full sunlight, penumbra,
             or umbra at the given ECI state.
    Rationale: Eclipse fraction directly controls available solar power;
               deep umbra forces battery-only operation.
    Inputs: eci_state - satellite ECI position/velocity/epoch.
    Outputs: EclipseState with type, illumination fraction, and Sun elevation.

    Algorithm (Vallado "Fundamentals" Algorithm 35 - conical shadow):
      1. Compute Sun unit vector s_hat.
      2. Compute apparent angular radius of Sun from satellite:
             alpha_sun  = arcsin( R_sun / |r_sun_abs| )
             where |r_sun_abs| ~ AU_KM.
      3. Compute apparent angular radius of Earth from satellite:
             alpha_earth = arcsin( R_earth / |r_sat| ).
      4. Compute theta = angle between (-r_sat direction) and (r_sun direction)
             as seen from satellite - equivalently the angle at the satellite
             between nadir and the Sun.
      5. Apply classification:
             theta > alpha_sun + alpha_earth  -> SUNLIT
             |alpha_sun - alpha_earth| < theta <= alpha_sun + alpha_earth
                                                 -> PENUMBRA
             theta < alpha_earth - alpha_sun  -> UMBRA (most common for LEO)

    Failure Modes: If |r_sat| -> 0 (impossible physically) arcsin would
                   overflow; guarded by normalization.
    """
    r_sat = eci_state.position
    r_sat_norm = float(np.linalg.norm(r_sat))
    if r_sat_norm < R_EARTH:
        # Satellite below surface - degenerate; treat as umbra
        return EclipseState(
            eclipse_type=EclipseType.UMBRA,
            solar_illumination_fraction=0.0,
            sun_elevation_deg=-90.0,
            epoch=eci_state.epoch,
        )

    s_hat = sun_eci_unit(eci_state.epoch)  # unit vector Earth-to-Sun

    # Apparent angular radii [rad]
    alpha_sun = math.asin(min(1.0, R_SUN / AU_KM))
    alpha_earth = math.asin(min(1.0, R_EARTH / r_sat_norm))

    # Direction from satellite to Sun is approximately s_hat (since |r_sat| << AU)
    # Direction from satellite to Earth center is -r_sat_hat
    r_sat_hat = r_sat / r_sat_norm
    # cos of angle between (sat->Sun) and (sat->Earth center = -r_sat_hat)
    cos_theta = float(np.dot(s_hat, -r_sat_hat))
    cos_theta = max(-1.0, min(1.0, cos_theta))
    theta = math.acos(cos_theta)  # [rad]

    # Sun elevation above satellite's local horizon (positive = above horizon)
    # The satellite's "local horizontal" is perpendicular to r_sat.
    # Sun elevation = arcsin(dot(s_hat, r_sat_hat)) - 90 deg is wrong;
    # elevation relative to local horizontal = arcsin(dot(s_hat, r_sat_hat)).
    # Note: elevation positive means Sun is "above" the orbit horizon as seen
    # from the satellite looking outward.
    sun_elev_rad = math.asin(max(-1.0, min(1.0, float(np.dot(s_hat, r_sat_hat)))))
    sun_elev_deg = math.degrees(sun_elev_rad)

    # Shadow classification
    if theta >= alpha_sun + alpha_earth:
        illum = 1.0
        etype = EclipseType.SUNLIT
    elif theta >= abs(alpha_earth - alpha_sun):
        # Penumbra: linear interpolation of occultation fraction
        # When theta == alpha_sun + alpha_earth -> illum = 1.0 (entry to penumbra)
        # When theta == |alpha_earth - alpha_sun| -> illum = 0.0 (entry to umbra, approximately)
        span = (alpha_sun + alpha_earth) - abs(alpha_earth - alpha_sun)
        if span < 1e-12:
            illum = 0.5
        else:
            illum = (theta - abs(alpha_earth - alpha_sun)) / span
        etype = EclipseType.PENUMBRA
    else:
        illum = 0.0
        etype = EclipseType.UMBRA

    return EclipseState(
        eclipse_type=etype,
        solar_illumination_fraction=float(illum),
        sun_elevation_deg=sun_elev_deg,
        epoch=eci_state.epoch,
    )


# ---------------------------------------------------------------------------
# Solar incidence angle and panel power
# ---------------------------------------------------------------------------

def solar_panel_power_fraction(
    eci_state: EciState,
    eclipse_state: EclipseState,
    panel_normal_eci: Optional[np.ndarray] = None,
) -> float:
    """
    ID: CORE-030-F8
    Purpose: Compute the fraction of nominal solar panel power output
             accounting for eclipse and sun incidence angle.
    Inputs: eci_state        - satellite state.
            eclipse_state    - pre-computed illumination state.
            panel_normal_eci - unit vector of solar panel normal in ECI
                               (None assumes sun-tracking panels that always
                                face the sun perfectly).
    Outputs: power_fraction in [0.0, 1.0] where 1.0 = full nominal output.
    Rationale: A sun-tracking panel has cos(angle)=1.0 by definition.
               Fixed panels degrade as |cos(theta_sun)| where theta_sun
               is the angle between panel normal and Sun vector.
    """
    if eclipse_state.eclipse_type == EclipseType.UMBRA:
        return 0.0
    illum = eclipse_state.solar_illumination_fraction
    if panel_normal_eci is None:
        # Sun-tracking panels
        cos_angle = 1.0
    else:
        s_hat = sun_eci_unit(eci_state.epoch)
        n_hat = np.asarray(panel_normal_eci, dtype=float)
        n_norm = np.linalg.norm(n_hat)
        if n_norm < 1e-9:
            cos_angle = 1.0
        else:
            cos_angle = float(np.dot(n_hat / n_norm, s_hat))
            cos_angle = max(0.0, cos_angle)  # back-illumination -> 0
    return illum * cos_angle


# ---------------------------------------------------------------------------
# ECEF <-> ECI coordinate transforms
# ---------------------------------------------------------------------------

def _gast(dt: datetime) -> float:
    """
    ID: CORE-030-F9
    Purpose: Greenwich Apparent Sidereal Time in radians.
    Inputs: dt - UTC datetime.
    Outputs: GAST [rad] in [0, 2*pi).
    Reference: Vallado eq. 3-47.
    """
    jd = _datetime_to_jd(dt)
    T = _jd_to_j2000_centuries(jd)
    # GMST at 0h UT1 [seconds]
    theta_gmst_deg = (
        100.4606184
        + 36000.77004 * T
        + 0.000387933 * T * T
        - T * T * T / 38710000.0
    )
    # Add Earth rotation for fractional day
    jd0 = math.floor(jd) + 0.5
    ut1_frac = jd - jd0  # fraction of UT1 day
    theta_gmst_deg += 360.98564724 * ut1_frac
    return math.radians(theta_gmst_deg % 360.0)


def ecef_to_eci(r_ecef: np.ndarray, dt: datetime) -> np.ndarray:
    """Rotate ECEF position to ECI using GAST (simplified, no polar motion)."""
    gast = _gast(dt)
    c, s = math.cos(gast), math.sin(gast)
    R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    return R @ r_ecef


def geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> np.ndarray:
    """
    ID: CORE-030-F10
    Purpose: Convert geodetic (WGS-84) coordinates to ECEF Cartesian [km].
    Inputs: lat_deg [-90,90], lon_deg [-180,180], alt_m [m above ellipsoid].
    Outputs: ECEF position [km].
    """
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    alt_km = alt_m / 1000.0
    N = R_EARTH / math.sqrt(1.0 - E2_EARTH * math.sin(lat) ** 2)
    x = (N + alt_km) * math.cos(lat) * math.cos(lon)
    y = (N + alt_km) * math.cos(lat) * math.sin(lon)
    z = (N * (1.0 - E2_EARTH) + alt_km) * math.sin(lat)
    return np.array([x, y, z])


def station_velocity_ecef(lat_deg: float, lon_deg: float, alt_m: float) -> np.ndarray:
    """
    ID: CORE-030-F11
    Purpose: ECEF velocity of a surface station due to Earth rotation [km/s].
    """
    r_ecef = geodetic_to_ecef(lat_deg, lon_deg, alt_m)
    # omega_earth cross r  (omega in z direction)
    vx = -EARTH_ROTATION_RATE * r_ecef[1]
    vy =  EARTH_ROTATION_RATE * r_ecef[0]
    vz = 0.0
    return np.array([vx, vy, vz])


# ---------------------------------------------------------------------------
# Ground station geometry
# ---------------------------------------------------------------------------

def _elevation_and_range(
    r_sat_eci: np.ndarray,
    v_sat_eci: np.ndarray,
    station: GroundStation,
    dt: datetime,
) -> Tuple[float, float, float]:
    """
    ID: CORE-030-F12
    Purpose: Compute elevation angle, slant range, and Doppler shift for a
             satellite pass over a ground station.
    Inputs: r_sat_eci [km], v_sat_eci [km/s], station, UTC datetime.
    Outputs: (elevation_deg, range_km, doppler_hz).
    Algorithm:
      1. Convert station geodetic to ECEF, then rotate to ECI at dt.
      2. Compute range vector rho = r_sat - r_station_eci.
      3. Station zenith = r_station_eci / |r_station_eci|.
      4. elevation = arcsin(dot(rho_hat, zenith)).
      5. Doppler: range_rate = dot(v_rel, rho_hat); f_D = f0 * range_rate / c.
    """
    r_sta_ecef = geodetic_to_ecef(station.latitude_deg, station.longitude_deg, station.altitude_m)
    r_sta_eci = ecef_to_eci(r_sta_ecef, dt)
    v_sta_eci = station_velocity_ecef(station.latitude_deg, station.longitude_deg, station.altitude_m)
    # ECEF velocity rotated to ECI (approximate - ignoring Coriolis contribution)
    gast = _gast(dt)
    c, s = math.cos(gast), math.sin(gast)
    R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    v_sta_eci_full = R @ v_sta_eci

    rho = r_sat_eci - r_sta_eci
    rho_norm = float(np.linalg.norm(rho))
    if rho_norm < 1e-6:
        return 90.0, 0.0, 0.0

    rho_hat = rho / rho_norm
    zenith = r_sta_eci / np.linalg.norm(r_sta_eci)
    cos_elev = float(np.dot(rho_hat, zenith))
    cos_elev = max(-1.0, min(1.0, cos_elev))
    elev_deg = math.degrees(math.asin(cos_elev))

    v_rel = v_sat_eci - v_sta_eci_full
    range_rate = float(np.dot(v_rel, rho_hat))   # km/s; positive = receding
    doppler_hz = -station.downlink_freq_hz * range_rate / C_LIGHT

    return elev_deg, rho_norm, doppler_hz


# ---------------------------------------------------------------------------
# Contact window search
# ---------------------------------------------------------------------------

def find_contact_windows(
    elements: OrbitalElementsJ2,
    station: GroundStation,
    search_start: datetime,
    search_duration_seconds: float = 86400.0,
    time_step_seconds: float = 10.0,
) -> List[ContactWindow]:
    """
    ID: CORE-030-F13
    Purpose: Find all ground-station contact windows within a search interval
             using a fixed time-step scanner with contact refinement.
    Inputs:
        elements             - initial orbital elements.
        station              - ground station parameters.
        search_start         - UTC start of search window.
        search_duration_s    - seconds to search (default 1 day).
        time_step_seconds    - time resolution for coarse scan (default 10 s).
    Outputs: list of ContactWindow (ascending by AOS).
    Algorithm:
        1. Scan the interval at time_step_seconds resolution.
        2. Detect rising edge (elevation crosses mask) -> record candidate AOS.
        3. Detect falling edge -> record LOS; refine both with bisection to
           within ~1 s accuracy.
        4. Compute peak elevation, AOS/LOS range, and Doppler.
    Failure Modes: Windows < time_step_seconds wide may be missed; reduce
                   time_step for accuracy vs. performance trade-off.
    """
    if search_start.tzinfo is None:
        search_start = search_start.replace(tzinfo=timezone.utc)

    mask = station.elevation_mask_deg
    windows: List[ContactWindow] = []

    n_steps = int(search_duration_seconds / time_step_seconds) + 1

    prev_elev: Optional[float] = None
    in_pass = False
    pass_start: Optional[datetime] = None
    pass_start_range: float = 0.0
    pass_start_doppler: float = 0.0
    pass_peak_elev: float = -90.0
    elevs_during_pass: List[float] = []

    for k in range(n_steps):
        t = search_start.__class__(
            *search_start.timetuple()[:6],
            microsecond=search_start.microsecond,
            tzinfo=timezone.utc,
        )
        # Use timedelta arithmetic directly on search_start
        from datetime import timedelta
        t = search_start + timedelta(seconds=k * time_step_seconds)

        state = propagate_j2(elements, t)
        elev, rng, dop = _elevation_and_range(
            state.position, state.velocity, station, t
        )

        if not in_pass:
            if prev_elev is not None and prev_elev < mask <= elev:
                # Rising edge - refine AOS with bisection
                aos_t, aos_rng, aos_dop = _bisect_contact(
                    elements, station,
                    search_start + timedelta(seconds=(k - 1) * time_step_seconds),
                    t, mask, rising=True,
                )
                in_pass = True
                pass_start = aos_t
                pass_start_range = aos_rng
                pass_start_doppler = aos_dop
                pass_peak_elev = elev
                elevs_during_pass = [elev]
        else:
            elevs_during_pass.append(elev)
            if elev > pass_peak_elev:
                pass_peak_elev = elev
            if prev_elev is not None and prev_elev >= mask > elev:
                # Falling edge - refine LOS with bisection
                los_t, los_rng, los_dop = _bisect_contact(
                    elements, station,
                    search_start + timedelta(seconds=(k - 1) * time_step_seconds),
                    t, mask, rising=False,
                )
                in_pass = False
                windows.append(ContactWindow(
                    station_id=station.station_id,
                    aos=pass_start,  # type: ignore[arg-type]
                    los=los_t,
                    max_elevation_deg=max(elevs_during_pass),
                    aos_range_km=pass_start_range,
                    los_range_km=los_rng,
                    doppler_shift_hz_at_aos=pass_start_doppler,
                    doppler_shift_hz_at_los=los_dop,
                ))
                elevs_during_pass = []
                pass_peak_elev = -90.0

        prev_elev = elev

    # Handle pass that was still open at end of search window
    if in_pass and pass_start is not None:
        end_t = search_start + timedelta(seconds=search_duration_seconds)
        state_end = propagate_j2(elements, end_t)
        _, end_rng, end_dop = _elevation_and_range(state_end.position, state_end.velocity, station, end_t)
        windows.append(ContactWindow(
            station_id=station.station_id,
            aos=pass_start,
            los=end_t,
            max_elevation_deg=max(elevs_during_pass) if elevs_during_pass else pass_peak_elev,
            aos_range_km=pass_start_range,
            los_range_km=end_rng,
            doppler_shift_hz_at_aos=pass_start_doppler,
            doppler_shift_hz_at_los=end_dop,
        ))

    return windows


def _bisect_contact(
    elements: OrbitalElementsJ2,
    station: GroundStation,
    t_lo: datetime,
    t_hi: datetime,
    mask: float,
    rising: bool,
    iterations: int = 18,
) -> Tuple[datetime, float, float]:
    """
    ID: CORE-030-F14
    Purpose: Binary search to refine AOS or LOS crossing time.
    Inputs: bracket times t_lo, t_hi; mask elevation; rising flag.
    Outputs: (refined_crossing_time, range_km, doppler_hz).
    """
    from datetime import timedelta

    for _ in range(iterations):
        dt_span = (t_hi - t_lo).total_seconds()
        t_mid = t_lo + timedelta(seconds=dt_span / 2.0)
        state = propagate_j2(elements, t_mid)
        elev, _, _ = _elevation_and_range(state.position, state.velocity, station, t_mid)
        if rising:
            if elev < mask:
                t_lo = t_mid
            else:
                t_hi = t_mid
        else:
            if elev >= mask:
                t_lo = t_mid
            else:
                t_hi = t_mid

    t_cross = t_lo + timedelta(seconds=(t_hi - t_lo).total_seconds() / 2.0)
    state_cross = propagate_j2(elements, t_cross)
    _, rng, dop = _elevation_and_range(state_cross.position, state_cross.velocity, station, t_cross)
    return t_cross, rng, dop


# ---------------------------------------------------------------------------
# Eclipse fraction over a full orbit (for power budget planning)
# ---------------------------------------------------------------------------

def orbit_eclipse_fraction(
    elements: OrbitalElementsJ2,
    dt: datetime,
    n_samples: int = 360,
) -> float:
    """
    ID: CORE-030-F15
    Purpose: Estimate the fraction of the orbit spent in eclipse (umbra only)
             by sampling the orbit uniformly in mean anomaly.
    Inputs: elements - orbital elements; dt - epoch for Sun position;
            n_samples - number of mean-anomaly samples (default 360).
    Outputs: eclipse_fraction in [0, 1].
    Rationale: Average available solar power = P_solar * (1 - eclipse_fraction).
               This scalar feeds directly into the power budget model.
    """
    umbra_count = 0
    from datetime import timedelta
    # Orbital period
    a = elements.semi_major_axis
    period_s = 2.0 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    step_s = period_s / n_samples

    for k in range(n_samples):
        t_k = dt + timedelta(seconds=k * step_s)
        state = propagate_j2(elements, t_k)
        eclipse = compute_eclipse_state(state)
        if eclipse.eclipse_type == EclipseType.UMBRA:
            umbra_count += 1

    return umbra_count / n_samples


# ---------------------------------------------------------------------------
# Power budget adapter - allocator interface
# ---------------------------------------------------------------------------

def compute_power_budget_fraction(
    elements: OrbitalElementsJ2,
    dt: datetime,
    battery_state_of_charge: float = 1.0,
    panel_degradation: float = 0.0,
    panel_normal_eci: Optional[np.ndarray] = None,
) -> float:
    """
    ID: CORE-030-F16
    Purpose: Compute the scalar power_budget_fraction that MissionResourceAllocator
             should use as the multiplier on its distributable budget.
    Inputs:
        elements               - current orbital elements.
        dt                     - current UTC datetime.
        battery_state_of_charge - 0..1 fraction of battery capacity available.
        panel_degradation      - 0..1 fractional loss of panel efficiency from
                                 cumulative radiation damage (0 = new panels).
        panel_normal_eci       - panel orientation (None = sun-tracking).
    Outputs: power_budget_fraction in [0, 1].
    Rationale:
        power = solar_power_fraction * (1 - panel_degradation)
                + battery_contribution
        During umbra the satellite runs on batteries only.
        The allocator uses this to scale available budgets:
            distributable_power = nominal_power * power_budget_fraction.
    Notes:
        Battery contribution: batteries supply up to ~60% of nominal power
        when fully charged (typical LEO spacecraft design margin).
        Exact values are spacecraft-specific; defaults approximate a 100W
        CubeSat with 40W battery bus.
    """
    state = propagate_j2(elements, dt)
    eclipse = compute_eclipse_state(state)
    panel_efficiency = max(0.0, 1.0 - float(panel_degradation))
    solar_fraction = solar_panel_power_fraction(state, eclipse, panel_normal_eci) * panel_efficiency

    # Battery contribution - max 0.60 of nominal, scaled by SOC
    batt_soc = max(0.0, min(1.0, float(battery_state_of_charge)))
    battery_contribution = 0.60 * batt_soc

    # Combined power fraction (clamped to [0, 1])
    raw = solar_fraction + battery_contribution * (1.0 - solar_fraction)
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Radiation dose accumulation
# ---------------------------------------------------------------------------

# Simplified trapped-radiation environment parameters.
# AE8-MAX model approximation for LEO electron flux.
# Reference: Vette, J.I. "The AE-8 Trapped Electron Model Environment" NSSDC 91-24.
_RAD_ALTITUDE_REF_KM: float = 400.0      # reference altitude for dose rate normalization
_RAD_DOSE_RATE_REF_MRAD_PER_S: float = 2.8e-5  # ~1 mrad/s at 400 km ISS orbit
_RAD_SCALE_HEIGHT_KM: float = 400.0      # exponential altitude scale height for trapped flux

# South Atlantic Anomaly (SAA) geographic center and spread.
_SAA_LAT_DEG: float = -28.0              # degrees latitude
_SAA_LON_DEG: float = -45.0             # degrees longitude
_SAA_SIGMA_LAT_DEG: float = 16.0
_SAA_SIGMA_LON_DEG: float = 32.0
_SAA_FLUX_ENHANCEMENT: float = 15.0     # peak dose rate multiplier inside SAA

# Solar cell degradation constant: fractional efficiency loss per Mrad TID.
# Typical space-grade GaAs triple-junction: ~1.5% per 100 krad = 15% per Mrad.
_CELL_DEGRADATION_PER_MRAD: float = 1.5e-4   # fraction per mrad


def _ecef_lat_lon(r_ecef: np.ndarray) -> Tuple[float, float]:
    """
    ID: CORE-031-H1
    Purpose: Convert ECEF position to geographic latitude/longitude [deg].
    Inputs: r_ecef - ECEF position [km].
    Outputs: (latitude_deg, longitude_deg).
    """
    x, y, z = float(r_ecef[0]), float(r_ecef[1]), float(r_ecef[2])
    lon_rad = math.atan2(y, x)
    p = math.sqrt(x * x + y * y)
    # Iterative geodetic latitude (Bowring's method, 3 iterations)
    lat_rad = math.atan2(z, p * (1.0 - E2_EARTH))
    for _ in range(3):
        N = R_EARTH / math.sqrt(1.0 - E2_EARTH * math.sin(lat_rad) ** 2)
        lat_rad = math.atan2(z + E2_EARTH * N * math.sin(lat_rad), p)
    return math.degrees(lat_rad), math.degrees(lon_rad)


def _saa_dose_enhancement(lat_deg: float, lon_deg: float) -> float:
    """
    ID: CORE-031-H2
    Purpose: Gaussian SAA dose enhancement factor at geographic (lat, lon).
    Outputs: dimensionless multiplier >= 1.0.
    """
    dlat = lat_deg - _SAA_LAT_DEG
    dlon = lon_deg - _SAA_LON_DEG
    # Wrap longitude difference to [-180, 180]
    while dlon > 180.0:
        dlon -= 360.0
    while dlon < -180.0:
        dlon += 360.0
    exponent = (dlat / _SAA_SIGMA_LAT_DEG) ** 2 + (dlon / _SAA_SIGMA_LON_DEG) ** 2
    enhancement = 1.0 + (_SAA_FLUX_ENHANCEMENT - 1.0) * math.exp(-0.5 * exponent)
    return enhancement


@dataclass
class RadiationDoseState:
    """
    ID: CORE-031-DS1
    Purpose: Accumulated radiation dose and derived degradation for one orbit.

    Fields:
        total_dose_mrad        - total ionizing dose over the integration interval [mrad]
        saa_dose_mrad          - SAA-attributable component [mrad]
        background_dose_mrad   - non-SAA background component [mrad]
        panel_degradation_delta - fractional solar cell efficiency loss this interval
        cumulative_panel_degradation - running cumulative fraction (0..1, caller must track)
        n_saa_crossings        - number of SAA passes during interval
    """
    total_dose_mrad: float
    saa_dose_mrad: float
    background_dose_mrad: float
    panel_degradation_delta: float
    n_saa_crossings: int
    integration_seconds: float


def compute_radiation_dose(
    elements: OrbitalElementsJ2,
    start: datetime,
    duration_seconds: float,
    n_samples: int = 360,
) -> RadiationDoseState:
    """
    ID: CORE-031-F1
    Purpose: Integrate trapped-particle radiation dose over a given time
             interval, accounting for altitude, SAA, and eclipse shielding.
    Rationale: TID accumulates non-uniformly - SAA contributes ~60-80% of
               total LEO dose despite covering <5% of orbit arc time.
               Accurate dose drives panel_degradation fed to PM engine.
    Inputs:
        elements         - orbital elements at start epoch.
        start            - UTC start of integration window.
        duration_seconds - integration interval (typically one orbit period).
        n_samples        - quadrature points.
    Outputs: RadiationDoseState.
    Algorithm:
        Trapezoidal integration of dose_rate(t) * dt.
        dose_rate = base_rate(h) * saa_factor(lat, lon) * eclipse_shielding
        eclipse_shielding: electrons in eclipse still irradiate; 0.9 multiplier
        applied in eclipse (Earth provides partial shielding of lower belt).
    References: Stassinopoulos & Raymond, Proc. IEEE, 1988.
                Barth et al., IEEE Trans. Nucl. Sci., 2003.
    """
    from datetime import timedelta

    dt_step = duration_seconds / n_samples
    total_dose = 0.0
    saa_dose = 0.0
    background_dose = 0.0
    n_saa = 0
    in_saa = False
    SAA_THRESHOLD = 3.0   # enhancement factor above which we count as SAA crossing

    for k in range(n_samples):
        t = start + timedelta(seconds=k * dt_step)
        state = propagate_j2(elements, t)
        r_norm = float(np.linalg.norm(state.position))
        alt_km = r_norm - R_EARTH

        # Background dose rate: exponential with altitude
        base_rate = _RAD_DOSE_RATE_REF_MRAD_PER_S * math.exp(
            (alt_km - _RAD_ALTITUDE_REF_KM) / _RAD_SCALE_HEIGHT_KM
        )

        # Geographic position for SAA lookup
        gast = _gast(t)
        c_g, s_g = math.cos(gast), math.sin(gast)
        # Rotate ECI to ECEF
        r_ecef = np.array([
            c_g * state.position[0] + s_g * state.position[1],
            -s_g * state.position[0] + c_g * state.position[1],
            state.position[2],
        ])
        lat_deg, lon_deg = _ecef_lat_lon(r_ecef)
        saa_factor = _saa_dose_enhancement(lat_deg, lon_deg)

        # Eclipse partial shielding: Earth's body blocks part of inner belt flux
        eclipse_state = compute_eclipse_state(state)
        eclipse_shield = 0.90 if eclipse_state.is_eclipse else 1.0

        rate = base_rate * saa_factor * eclipse_shield
        dose_step = rate * dt_step
        total_dose += dose_step
        saa_contrib = base_rate * (saa_factor - 1.0) * eclipse_shield * dt_step
        saa_dose += saa_contrib
        background_dose += base_rate * eclipse_shield * dt_step

        # Count SAA crossings (leading edge only)
        currently_in_saa = saa_factor >= SAA_THRESHOLD
        if currently_in_saa and not in_saa:
            n_saa += 1
        in_saa = currently_in_saa

    panel_delta = total_dose * _CELL_DEGRADATION_PER_MRAD
    return RadiationDoseState(
        total_dose_mrad=total_dose,
        saa_dose_mrad=saa_dose,
        background_dose_mrad=background_dose,
        panel_degradation_delta=panel_delta,
        n_saa_crossings=n_saa,
        integration_seconds=duration_seconds,
    )


def panel_degradation_from_dose(cumulative_dose_mrad: float) -> float:
    """
    ID: CORE-031-F2
    Purpose: Convert cumulative TID dose to fractional solar panel efficiency loss.
    Inputs: cumulative_dose_mrad - total accumulated dose since beginning of mission.
    Outputs: degradation fraction in [0, 1] (0 = new panels).
    Rationale: GaAs triple-junction cells follow a power-law degradation model
               with dose; for moderate doses (<10 Mrad) a linear approximation
               is within 5% of Messenger/RBSP measured data.
    """
    return min(1.0, max(0.0, cumulative_dose_mrad * _CELL_DEGRADATION_PER_MRAD))


# ---------------------------------------------------------------------------
# Delta-V station-keeping budget
# ---------------------------------------------------------------------------

# Atmospheric drag model: US Standard Atmosphere 1976 approximate density.
# rho(h) = rho0 * exp(-h / H) for altitude h above reference.
_DRAG_RHO0_KG_M3: float = 1.225           # kg/m^3 at sea level
_DRAG_SCALE_HEIGHT_KM: float = 8.5        # atmospheric scale height [km]
_DRAG_SCALE_HEIGHT_UPPER: float = 60.0    # scale height above 86 km [km]


def atmospheric_density_kg_m3(altitude_km: float) -> float:
    """
    ID: CORE-032-H1
    Purpose: Exponential atmosphere density model for drag calculations.
    Inputs: altitude_km - geodetic altitude above Earth surface [km].
    Outputs: density [kg/m^3].
    References: US Standard Atmosphere 1976.
    """
    if altitude_km < 86.0:
        return _DRAG_RHO0_KG_M3 * math.exp(-altitude_km / _DRAG_SCALE_HEIGHT_KM)
    else:
        rho_86 = _DRAG_RHO0_KG_M3 * math.exp(-86.0 / _DRAG_SCALE_HEIGHT_KM)
        return rho_86 * math.exp(-(altitude_km - 86.0) / _DRAG_SCALE_HEIGHT_UPPER)


@dataclass
class StationKeepingBudget:
    """
    ID: CORE-032-DS1
    Purpose: Delta-V budget breakdown for orbital station-keeping over a
             maintenance interval.

    Fields:
        drag_deltaV_m_per_s      - velocity impulse needed to counter atmospheric drag [m/s]
        raan_correction_m_per_s  - out-of-plane delta-V to correct accumulated RAAN error [m/s]
        total_deltaV_m_per_s     - total station-keeping delta-V [m/s]
        propulsion_demand_fraction - normalized urgency of propulsion subsystem in [0, 1]
        maintenance_interval_days  - period over which this budget applies
    """
    drag_deltaV_m_per_s: float
    raan_correction_m_per_s: float
    total_deltaV_m_per_s: float
    propulsion_demand_fraction: float
    maintenance_interval_days: float


def compute_station_keeping_budget(
    elements: OrbitalElementsJ2,
    spacecraft_mass_kg: float = 12.0,
    drag_area_m2: float = 0.06,
    Cd: float = 2.2,
    raan_tolerance_deg: float = 1.0,
    maintenance_interval_days: float = 30.0,
    max_budget_m_per_s: float = 50.0,
) -> StationKeepingBudget:
    """
    ID: CORE-032-F1
    Purpose: Compute the orbital station-keeping delta-V budget required to
             maintain orbital altitude against drag and correct RAAN drift
             within tolerance over a maintenance interval.
    Rationale: Station-keeping drives propulsion allocation; the allocator
               must reserve propulsion budget proportional to upcoming demand.
    Inputs:
        elements                 - current orbital elements.
        spacecraft_mass_kg       - dry + propellant mass [kg].
        drag_area_m2             - effective cross-sectional area for drag [m^2].
        Cd                       - drag coefficient (2.2 typical for box sat).
        raan_tolerance_deg       - allowed RAAN drift before correction maneuver [deg].
        maintenance_interval_days - period for which budget is computed.
        max_budget_m_per_s       - normalization ceiling for demand fraction.
    Outputs: StationKeepingBudget.
    Algorithm:
        Drag delta-V:
            a_drag = 0.5 * Cd * (A/m) * rho(h) * v^2   [m/s^2]
            dV_drag = a_drag * interval_seconds

        RAAN correction delta-V:
            accumulated_RAAN = |d_raan/dt| * interval_seconds
            If accumulated_RAAN > tolerance:
                dV_raan ~ v_sat * sin(delta_raan/2)  (two-impulse plane change)
                For small angles: dV_raan ~ v_sat * delta_raan / 2  [rad]
            Else: 0 (within deadband; no correction needed yet)
    References: Wertz, J.R. "Space Mission Engineering" 2011, Ch. 19.
    """
    a = elements.semi_major_axis
    e = elements.eccentricity
    i_rad = math.radians(elements.inclination_deg)
    interval_s = maintenance_interval_days * 86400.0

    # Orbital velocity at mean altitude (circular approximation)
    v_circ_km_s = math.sqrt(MU_EARTH / a)
    v_circ_m_s = v_circ_km_s * 1000.0
    alt_km = a - R_EARTH

    # Atmospheric drag deceleration at mean altitude [m/s^2]
    rho = atmospheric_density_kg_m3(alt_km)
    B = Cd * drag_area_m2 / spacecraft_mass_kg   # ballistic coefficient inverse [m^2/kg]
    a_drag_m_s2 = 0.5 * B * rho * (v_circ_m_s ** 2)

    dV_drag = a_drag_m_s2 * interval_s   # [m/s]

    # RAAN correction (only if drift exceeds tolerance deadband)
    d_raan_rad_s, _, _ = compute_j2_secular_rates(a, e, i_rad)
    accumulated_raan_rad = abs(d_raan_rad_s) * interval_s
    accumulated_raan_deg = math.degrees(accumulated_raan_rad)

    if accumulated_raan_deg > raan_tolerance_deg:
        # Out-of-plane correction: dV = 2 * v * sin(delta_i / 2)
        # For RAAN correction via combined inclination change, cost is:
        # (exact for circular orbit plane change)
        excess_raan_rad = math.radians(accumulated_raan_deg - raan_tolerance_deg)
        dV_raan = 2.0 * v_circ_m_s * math.sin(excess_raan_rad / 2.0)
    else:
        dV_raan = 0.0

    total_dV = dV_drag + dV_raan
    demand = min(1.0, total_dV / max(1e-3, max_budget_m_per_s))

    return StationKeepingBudget(
        drag_deltaV_m_per_s=dV_drag,
        raan_correction_m_per_s=dV_raan,
        total_deltaV_m_per_s=total_dV,
        propulsion_demand_fraction=demand,
        maintenance_interval_days=maintenance_interval_days,
    )


# ---------------------------------------------------------------------------
# Inter-satellite link (ISL) visibility
# ---------------------------------------------------------------------------

def check_isl_visibility(
    r1_eci: np.ndarray,
    r2_eci: np.ndarray,
    atmosphere_margin_km: float = 100.0,
) -> Tuple[bool, float]:
    """
    ID: CORE-033-F1
    Purpose: Test whether two satellites have line-of-sight (no Earth occultation)
             and return the range between them.
    Rationale: ISL scheduling requires knowing which satellite pairs can communicate
               at each time step; Earth blocks links at low viewing angles.
    Inputs:
        r1_eci, r2_eci      - ECI positions of the two satellites [km].
        atmosphere_margin_km - minimum clearance above surface [km]
                               (100 km includes ionosphere + nav margin).
    Outputs: (visible: bool, range_km: float).
    Algorithm:
        Parametric ray: P(t) = r1 + t*(r2 - r1),  t in [0, 1].
        Closest Earth-center approach at t* = -dot(r1, d) / dot(d, d)
        where d = r2 - r1.
        Minimum Earth clearance = |P(t*)| if t* in [0,1] else min(|r1|, |r2|).
        Visible when clearance > R_EARTH + atmosphere_margin_km.
    """
    d = r2_eci - r1_eci
    d_sq = float(np.dot(d, d))
    range_km = float(math.sqrt(d_sq))

    if d_sq < 1e-12:
        return True, 0.0   # same position edge case

    t_star = float(-np.dot(r1_eci, d)) / d_sq
    t_clamp = max(0.0, min(1.0, t_star))
    closest_pt = r1_eci + t_clamp * d
    min_dist = float(np.linalg.norm(closest_pt))

    clearance_km = R_EARTH + atmosphere_margin_km
    visible = min_dist >= clearance_km
    return visible, range_km


def compute_isl_link_budget(
    r1_eci: np.ndarray,
    r2_eci: np.ndarray,
    transmit_power_w: float = 2.0,
    transmit_gain_dbi: float = 6.0,
    receive_gain_dbi: float = 6.0,
    carrier_freq_hz: float = 2.4e9,
    required_snr_db: float = 10.0,
    noise_temp_k: float = 290.0,
    bandwidth_hz: float = 1.0e6,
) -> Dict[str, float]:
    """
    ID: CORE-033-F2
    Purpose: Compute ISL RF link budget (received power, path loss, SNR margin).
    Inputs: transmit power [W], antenna gains [dBi], freq [Hz], geometry.
    Outputs: dict with keys: range_km, path_loss_db, received_power_dbw,
             noise_power_dbw, snr_db, link_margin_db.
    References: Proakis "Digital Communications" link budget formulas.
    """
    visible, range_km = check_isl_visibility(r1_eci, r2_eci)
    range_m = range_km * 1000.0

    # Free-space path loss (Friis formula)
    lam = C_LIGHT * 1000.0 / carrier_freq_hz   # wavelength [m]  (C_LIGHT in km/s -> *1000)
    if range_m < 1.0:
        range_m = 1.0
    fspl_db = 20.0 * math.log10(4.0 * math.pi * range_m / lam)

    Pt_dbw = 10.0 * math.log10(transmit_power_w)
    Pr_dbw = Pt_dbw + transmit_gain_dbi + receive_gain_dbi - fspl_db

    kB = 1.380649e-23   # Boltzmann constant
    noise_power_dbw = 10.0 * math.log10(kB * noise_temp_k * bandwidth_hz)

    snr_db = Pr_dbw - noise_power_dbw
    link_margin_db = snr_db - required_snr_db

    return {
        "visible": float(visible),
        "range_km": range_km,
        "path_loss_db": fspl_db,
        "received_power_dbw": Pr_dbw,
        "noise_power_dbw": noise_power_dbw,
        "snr_db": snr_db,
        "link_margin_db": link_margin_db,
    }
