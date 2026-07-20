"""
thermal_model.py - Attitude-dependent spacecraft thermal model with allocator coupling.

ID: CORE-035
Requirement: Given a satellite ECI state and attitude, compute steady-state
             face temperatures, identify thermal constraint violations, and
             produce a thermal subsystem demand fraction for the allocator.
Purpose: Replace the fixed thermal demand constant with a physically grounded
         demand signal that rises when faces are near operational limits and
         falls when thermal environment is benign.
Rationale: Thermal environment varies by roughly 200 K between eclipse and
           peak solar exposure; ignoring this produces suboptimal heater/
           radiator allocations and risks component damage.
Inputs: EciState, SpacecraftGeometry, datetime, optional attitude quaternion.
Outputs: SpacecraftThermalState, thermal_demand_fraction.
Preconditions: orbit_dynamics module available.
Postconditions: demand_fraction in [0, 1].
Assumptions: Steady-state thermal equilibrium per face (no thermal mass).
             Gray body (alpha = epsilon) approximation for non-solar surfaces.
             Earth IR modelled as uniform flux from nadir hemisphere.
Failure Modes: Division by zero guarded when emissivity -> 0.
Verification: tests/test_orbital_extensions.py.
References: Gilmore, D.G. "Spacecraft Thermal Control Handbook" 2nd ed.
            Wertz "Space Mission Engineering" Ch. 11.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np

from .orbit_dynamics import (
    EciState,
    EclipseType,
    R_EARTH,
    compute_eclipse_state,
    sun_eci_unit,
)

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

SIGMA_SB: float = 5.670374419e-8   # Stefan-Boltzmann [W/m^2/K^4]
SOLAR_CONSTANT_W_M2: float = 1361.0  # solar irradiance at 1 AU [W/m^2]
EARTH_IR_FLUX_W_M2: float = 237.0    # Earth outgoing longwave radiation [W/m^2]
EARTH_ALBEDO: float = 0.30           # Earth Bond albedo


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SpacecraftGeometry:
    """
    ID: CORE-035-DS1
    Purpose: Geometric and thermal properties of each spacecraft face.

    face_normals_body: dict mapping face_id to unit normal in body frame.
    face_areas_m2: dict mapping face_id to face area [m^2].
    solar_absorptance: dict mapping face_id to alpha_s [0, 1].
    ir_absorptance: dict mapping face_id to alpha_IR [0, 1]
                    (often ~= emissivity for gray-body assumption).
    emissivity: dict mapping face_id to thermal emissivity [0, 1].
    internal_dissipation_w: dict mapping face_id to internal heat load [W]
                             (electronics behind this face).
    op_temp_min_k: minimum operational temperature [K].
    op_temp_max_k: maximum operational temperature [K].
    """
    face_normals_body: Dict[str, np.ndarray]
    face_areas_m2: Dict[str, float]
    solar_absorptance: Dict[str, float]
    ir_absorptance: Dict[str, float]
    emissivity: Dict[str, float]
    internal_dissipation_w: Dict[str, float]
    op_temp_min_k: float = 253.0    # -20 deg C
    op_temp_max_k: float = 348.0    # +75 deg C


@dataclass
class FaceThermalState:
    """
    ID: CORE-035-DS2
    Purpose: Steady-state thermal result for one spacecraft face.

    Fields:
        face_id              - face identifier.
        equilibrium_temp_k   - steady-state temperature [K].
        solar_flux_absorbed_w - absorbed solar power [W].
        earth_ir_absorbed_w  - absorbed Earth IR [W].
        earth_albedo_absorbed_w - absorbed Earth-reflected solar [W].
        internal_dissipation_w - internal heat source [W].
        radiated_power_w     - total radiated power [W] (= sum of inputs at SS).
        in_operational_range - True if T in [op_temp_min_k, op_temp_max_k].
        heater_demand_w      - required heater power to reach min temp if too cold [W].
        radiator_demand_w    - required extra radiator capacity if too hot [W].
    """
    face_id: str
    equilibrium_temp_k: float
    solar_flux_absorbed_w: float
    earth_ir_absorbed_w: float
    earth_albedo_absorbed_w: float
    internal_dissipation_w: float
    radiated_power_w: float
    in_operational_range: bool
    heater_demand_w: float
    radiator_demand_w: float


@dataclass
class SpacecraftThermalState:
    """
    ID: CORE-035-DS3
    Purpose: Aggregate spacecraft thermal result from compute_thermal_state.

    Fields:
        face_states           - per-face thermal results.
        total_heater_demand_w - sum of heater demand across all faces [W].
        total_radiator_demand_w - sum of radiator demand [W].
        worst_cold_face_id    - face with lowest temperature.
        worst_hot_face_id     - face with highest temperature.
        min_temp_k            - minimum face temperature [K].
        max_temp_k            - maximum face temperature [K].
        thermal_demand_fraction - [0, 1] normalized for allocator.
        eclipse_type_str      - "sunlit"/"penumbra"/"umbra" at this epoch.
    """
    face_states: Dict[str, FaceThermalState]
    total_heater_demand_w: float
    total_radiator_demand_w: float
    worst_cold_face_id: str
    worst_hot_face_id: str
    min_temp_k: float
    max_temp_k: float
    thermal_demand_fraction: float
    eclipse_type_str: str


# ---------------------------------------------------------------------------
# Default 6U CubeSat geometry (convenience constructor)
# ---------------------------------------------------------------------------

def default_cubesat_geometry(
    body_solar_absorptance: float = 0.85,
    body_emissivity: float = 0.85,
    panel_solar_absorptance: float = 0.92,   # solar panel face
    panel_emissivity: float = 0.85,
    internal_power_w: float = 20.0,           # total internal dissipation [W]
) -> SpacecraftGeometry:
    """
    ID: CORE-035-F0
    Purpose: Build a default 6U CubeSat (100 mm x 200 mm x 340 mm) geometry.
    Face naming: +X, -X, +Y, -Y, +Z (nadir/zenith), -Z (nadir/zenith).
    The +Z face is assumed to be the solar-panel face.
    Internal dissipation distributed 70% to +Z panel face, 30% to body.
    """
    # 6U CubeSat: 100 x 200 x 340 mm
    A_z = 0.10 * 0.20   # 0.02 m^2 (panel face)
    A_x = 0.20 * 0.34   # 0.068 m^2 (long sides)
    A_y = 0.10 * 0.34   # 0.034 m^2 (short sides)

    face_ids = ["+X", "-X", "+Y", "-Y", "+Z", "-Z"]
    normals = {
        "+X": np.array([1.0, 0.0, 0.0]),
        "-X": np.array([-1.0, 0.0, 0.0]),
        "+Y": np.array([0.0, 1.0, 0.0]),
        "-Y": np.array([0.0, -1.0, 0.0]),
        "+Z": np.array([0.0, 0.0, 1.0]),
        "-Z": np.array([0.0, 0.0, -1.0]),
    }
    areas = {"+X": A_x, "-X": A_x, "+Y": A_y, "-Y": A_y, "+Z": A_z, "-Z": A_z}
    alpha_s = {f: body_solar_absorptance for f in face_ids}
    alpha_s["+Z"] = panel_solar_absorptance
    alpha_ir = {f: body_emissivity for f in face_ids}
    eps = {f: body_emissivity for f in face_ids}
    eps["+Z"] = panel_emissivity
    q_int = {f: 0.3 * internal_power_w / 4.0 for f in ("+X", "-X", "+Y", "-Y")}
    q_int["+Z"] = 0.7 * internal_power_w
    q_int["-Z"] = 0.0

    return SpacecraftGeometry(
        face_normals_body=normals,
        face_areas_m2=areas,
        solar_absorptance=alpha_s,
        ir_absorptance=alpha_ir,
        emissivity=eps,
        internal_dissipation_w=q_int,
    )


# ---------------------------------------------------------------------------
# Attitude helpers
# ---------------------------------------------------------------------------

def _nadir_pointing_body_to_eci(r_eci: np.ndarray, v_eci: np.ndarray) -> np.ndarray:
    """
    ID: CORE-035-H1
    Purpose: Compute body-to-ECI rotation matrix for nadir-pointing attitude.
    Convention: +Z body axis points toward nadir (Earth center).
                +X body axis is in the direction of velocity (along-track).
                +Y completes the right-hand frame (orbit-normal direction, toward South).
    Inputs: r_eci [km], v_eci [km/s].
    Outputs: 3x3 rotation matrix R where r_eci_vec = R @ r_body_vec.
    """
    nadir = -r_eci / np.linalg.norm(r_eci)       # +Z body points toward Earth
    along_track = v_eci / np.linalg.norm(v_eci)   # +X body in velocity direction
    orbit_normal = np.cross(along_track, nadir)
    orbit_normal /= np.linalg.norm(orbit_normal)  # +Y
    # Correct along_track to be orthogonal
    along_track = np.cross(nadir, orbit_normal)
    # Columns: x_body_in_eci, y_body_in_eci, z_body_in_eci
    R = np.column_stack([along_track, orbit_normal, nadir])
    return R


def _sun_body_vector(
    eci_state: EciState,
    body_to_eci: np.ndarray,
) -> np.ndarray:
    """
    ID: CORE-035-H2
    Purpose: Compute unit vector from spacecraft body center to Sun, in body frame.
    """
    s_eci = sun_eci_unit(eci_state.epoch)
    R_eci_to_body = body_to_eci.T   # rotation matrix is orthogonal
    return R_eci_to_body @ s_eci


def _nadir_body_vector(
    eci_state: EciState,
    body_to_eci: np.ndarray,
) -> np.ndarray:
    """
    ID: CORE-035-H3
    Purpose: Compute unit vector from spacecraft body center toward Earth nadir,
             in body frame.
    """
    nadir_eci = -eci_state.position / np.linalg.norm(eci_state.position)
    R_eci_to_body = body_to_eci.T
    return R_eci_to_body @ nadir_eci


# ---------------------------------------------------------------------------
# Per-face heat flux calculation
# ---------------------------------------------------------------------------

def _solar_heat_absorbed(
    face_normal_body: np.ndarray,
    sun_body: np.ndarray,
    face_area_m2: float,
    alpha_s: float,
    solar_flux_w_m2: float,
) -> float:
    """
    ID: CORE-035-H4
    Purpose: Absorbed solar power for one face [W].
    Q_solar = alpha_s * A * q_solar * max(0, cos(theta_sun))
    where theta_sun is angle between face normal and Sun direction.
    """
    cos_theta = float(np.dot(face_normal_body, sun_body))
    return alpha_s * face_area_m2 * solar_flux_w_m2 * max(0.0, cos_theta)


def _earth_ir_absorbed(
    face_normal_body: np.ndarray,
    nadir_body: np.ndarray,
    face_area_m2: float,
    alpha_ir: float,
    earth_ir_w_m2: float,
    view_factor: float,
) -> float:
    """
    ID: CORE-035-H5
    Purpose: Absorbed Earth IR power for one face [W].
    Only faces with a positive view of the nadir hemisphere receive Earth flux.
    Q_earth = alpha_IR * A * q_earth * view_factor * max(0, cos(theta_nadir))
    """
    cos_nadir = float(np.dot(face_normal_body, nadir_body))
    return alpha_ir * face_area_m2 * earth_ir_w_m2 * view_factor * max(0.0, cos_nadir)


def _equilibrium_temperature_k(
    q_total_absorbed_w: float,
    face_area_m2: float,
    emissivity: float,
) -> float:
    """
    ID: CORE-035-H6
    Purpose: Compute steady-state face temperature from absorbed heat [K].
    Derivation: Q_out = epsilon * sigma * A * T^4 = Q_in
                T = (Q_in / (epsilon * sigma * A))^(1/4)
    Failure Modes: q_total_absorbed_w <= 0 returns 2.7 K (cosmic background).
                   emissivity near zero returns artificially high temperature;
                   guarded with minimum 0.01.
    """
    eps = max(0.01, emissivity)
    area = max(1e-6, face_area_m2)
    if q_total_absorbed_w <= 0.0:
        return 2.7   # cosmic microwave background
    q = q_total_absorbed_w / (eps * SIGMA_SB * area)
    return q ** 0.25


# ---------------------------------------------------------------------------
# Main thermal computation
# ---------------------------------------------------------------------------

def compute_thermal_state(
    eci_state: EciState,
    geometry: SpacecraftGeometry,
    body_to_eci: Optional[np.ndarray] = None,
    nominal_power_w: float = 100.0,
) -> SpacecraftThermalState:
    """
    ID: CORE-035-F1
    Purpose: Compute steady-state per-face temperatures and aggregate
             thermal demand fraction for the resource allocator.
    Inputs:
        eci_state     - satellite ECI position/velocity/epoch.
        geometry      - spacecraft face geometry and optical properties.
        body_to_eci   - optional 3x3 body-to-ECI rotation matrix.
                        None triggers automatic nadir-pointing attitude.
        nominal_power_w - spacecraft nominal power bus [W]; used to normalize
                          heater/radiator demands into fractions.
    Outputs: SpacecraftThermalState.
    Algorithm:
        1. Determine eclipse state -> set solar_flux_w_m2.
        2. Compute view factor F_earth = (R_earth / |r_sat|)^2.
        3. For each face:
           a. Q_solar = alpha_s * A * q_s * cos(theta_sun)  (0 if eclipse or back-facing)
           b. Q_earth_IR = alpha_IR * A * q_earth * F * cos(theta_nadir) (0 if back-facing)
           c. Q_earth_albedo = alpha_s * A * q_s * albedo * F * cos(theta_nadir) (0 in eclipse)
           d. Q_internal = from geometry spec
           e. Q_total = Q_solar + Q_earth_IR + Q_earth_albedo + Q_internal
           f. T_eq = (Q_total / (eps * sigma * A))^(1/4)
        4. Compute heater/radiator demand from temperature vs. operational range.
        5. Normalize total demand to [0, 1].
    """
    eclipse = compute_eclipse_state(eci_state)
    illum = eclipse.solar_illumination_fraction
    solar_flux = SOLAR_CONSTANT_W_M2 * illum

    r_norm = float(np.linalg.norm(eci_state.position))
    earth_view_factor = (R_EARTH / r_norm) ** 2

    # Attitude: default to nadir-pointing
    if body_to_eci is None:
        body_to_eci = _nadir_pointing_body_to_eci(eci_state.position, eci_state.velocity)

    sun_body = _sun_body_vector(eci_state, body_to_eci)
    nadir_body = _nadir_body_vector(eci_state, body_to_eci)

    face_states: Dict[str, FaceThermalState] = {}
    op_min = geometry.op_temp_min_k
    op_max = geometry.op_temp_max_k

    for fid, n_hat in geometry.face_normals_body.items():
        area = geometry.face_areas_m2.get(fid, 0.0)
        a_s = geometry.solar_absorptance.get(fid, 0.85)
        a_ir = geometry.ir_absorptance.get(fid, 0.85)
        eps = geometry.emissivity.get(fid, 0.85)
        q_int = geometry.internal_dissipation_w.get(fid, 0.0)

        q_solar = _solar_heat_absorbed(n_hat, sun_body, area, a_s, solar_flux)
        q_earth_ir = _earth_ir_absorbed(n_hat, nadir_body, area, a_ir, EARTH_IR_FLUX_W_M2, earth_view_factor)
        # Earth-reflected solar (albedo): only in sunlit half
        if illum > 0.0:
            q_albedo = _solar_heat_absorbed(n_hat, nadir_body, area, a_s,
                                             SOLAR_CONSTANT_W_M2 * EARTH_ALBEDO * earth_view_factor * illum)
        else:
            q_albedo = 0.0

        q_total = q_solar + q_earth_ir + q_albedo + q_int
        T_eq = _equilibrium_temperature_k(q_total, area, eps)
        q_rad = eps * SIGMA_SB * area * (T_eq ** 4)

        in_range = op_min <= T_eq <= op_max
        # Heater demand: power needed to bring face to op_temp_min
        if T_eq < op_min:
            q_deficit = eps * SIGMA_SB * area * (op_min ** 4 - T_eq ** 4)
            heater_w = max(0.0, q_deficit - q_int)
            radiator_w = 0.0
        elif T_eq > op_max:
            q_excess = q_total - eps * SIGMA_SB * area * (op_max ** 4)
            heater_w = 0.0
            radiator_w = max(0.0, q_excess)
        else:
            heater_w = 0.0
            radiator_w = 0.0

        face_states[fid] = FaceThermalState(
            face_id=fid,
            equilibrium_temp_k=T_eq,
            solar_flux_absorbed_w=q_solar,
            earth_ir_absorbed_w=q_earth_ir,
            earth_albedo_absorbed_w=q_albedo,
            internal_dissipation_w=q_int,
            radiated_power_w=q_rad,
            in_operational_range=in_range,
            heater_demand_w=heater_w,
            radiator_demand_w=radiator_w,
        )

    # Aggregate
    total_heater = sum(fs.heater_demand_w for fs in face_states.values())
    total_radiator = sum(fs.radiator_demand_w for fs in face_states.values())
    temps = {fid: fs.equilibrium_temp_k for fid, fs in face_states.items()}
    cold_id = min(temps, key=temps.__getitem__)
    hot_id = max(temps, key=temps.__getitem__)

    # Thermal demand fraction: proportional to combined heater + radiator active demand
    # normalized by nominal power bus; clamped to [0.05, 1.0] (always some base thermal load)
    thermal_demand_raw = (total_heater + total_radiator) / max(1.0, nominal_power_w)
    thermal_demand = max(0.05, min(1.0, thermal_demand_raw))

    return SpacecraftThermalState(
        face_states=face_states,
        total_heater_demand_w=total_heater,
        total_radiator_demand_w=total_radiator,
        worst_cold_face_id=cold_id,
        worst_hot_face_id=hot_id,
        min_temp_k=temps[cold_id],
        max_temp_k=temps[hot_id],
        thermal_demand_fraction=thermal_demand,
        eclipse_type_str=eclipse.eclipse_type.value,
    )


def compute_thermal_demand_fraction(
    eci_state: EciState,
    geometry: SpacecraftGeometry,
    body_to_eci: Optional[np.ndarray] = None,
    nominal_power_w: float = 100.0,
) -> float:
    """
    ID: CORE-035-F2
    Purpose: Convenience wrapper returning only the thermal_demand_fraction scalar.
    Suitable for direct injection into SubsystemState.demand_fraction for the
    'thermal' subsystem.
    """
    state = compute_thermal_state(eci_state, geometry, body_to_eci, nominal_power_w)
    return state.thermal_demand_fraction
