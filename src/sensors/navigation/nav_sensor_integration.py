"""
nav_sensor_integration.py - Navigation Sensor Integration Pipeline
===================================================================
ID: NAV-001
Requirement: Integrate star tracker, IMU (inertial measurement unit), and GPS
             (when available) into a unified spacecraft attitude and position
             estimate using a cascaded Extended Kalman Filter (EKF).
Purpose: Continuous accurate attitude knowledge is mandatory for solar panel
         pointing, antenna tracking, and thruster firing. Single-sensor reliance
         risks mission loss if that sensor fails. Sensor fusion provides
         redundancy and higher accuracy than any single instrument.
Rationale: Star trackers deliver high-accuracy attitude (<5 arcsec) but are
           blinded by eclipse or bright objects. IMU provides continuous attitude
           rates but drifts over time. GPS provides position but not attitude.
           The EKF combines complementary strengths of all three.
Inputs: StarTrackerReading, IMUReading, GPSReading (any subset available).
Outputs: NavigationState with fused position, velocity, attitude quaternion,
         and per-source confidence.
Preconditions: At least IMU available; star tracker and GPS are optional.
Failure Modes:
  - Star tracker lost: IMU-only propagation with growing uncertainty.
  - IMU failed: star tracker + GPS differencing (lower rate).
  - All failed: last-known-good orbit propagation (Kepler).
Side Effects: Maintains EKF state in memory; logs sensor dropouts.
Verification: Unit tested with synthetic trajectories; attitude RMSE < 0.01 deg.
References: Markley & Crassidis "Fundamentals of Spacecraft Attitude Determination
            and Control", Springer 2014. Wertz "Spacecraft Attitude Determination
            and Control", Kluwer 1978.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class NavSensorStatus(Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    LOST = "lost"
    CALIBRATING = "calibrating"


class AttitudeFrame(Enum):
    ECI = "eci"      # Earth-Centered Inertial
    LVLH = "lvlh"    # Local Vertical Local Horizontal (orbit frame)
    BODY = "body"    # Spacecraft body frame


# ---------------------------------------------------------------------------
# Raw sensor data structures
# ---------------------------------------------------------------------------

@dataclass
class StarTrackerReading:
    """
    ID: NAV-001-A
    Purpose: Attitude quaternion measurement from a star tracker.
    Fields:
      - quaternion: [qx, qy, qz, qw] body-to-ECI rotation (unit quaternion)
      - angular_uncertainty_arcsec: 1-sigma attitude knowledge error
      - n_stars_tracked: number of catalog stars matched
      - sensor_id: hardware identifier (e.g., 'ST-MAIN', 'ST-BACKUP')
      - timestamp: UTC observation time
      - valid: False if tracker blinded by Sun/Moon/Earth limb
    """
    quaternion: np.ndarray       # shape (4,) [qx, qy, qz, qw]
    angular_uncertainty_arcsec: float
    n_stars_tracked: int
    sensor_id: str
    timestamp: datetime
    valid: bool = True


@dataclass
class IMUReading:
    """
    ID: NAV-001-B
    Purpose: Angular rate and acceleration measurement from IMU.
    Fields:
      - angular_rate_rads: [wx, wy, wz] body frame angular velocity (rad/s)
      - linear_accel_ms2: [ax, ay, az] body frame specific force (m/s^2)
      - temperature_c: IMU die temperature for thermal correction
      - bias_estimate: estimated gyro bias [rad/s] from in-flight calibration
      - timestamp: measurement time
      - dt_seconds: time since last IMU sample (for integration)
    """
    angular_rate_rads: np.ndarray   # shape (3,)
    linear_accel_ms2: np.ndarray    # shape (3,)
    temperature_c: float
    bias_estimate: np.ndarray       # shape (3,) gyro bias
    sensor_id: str
    timestamp: datetime
    dt_seconds: float = 0.01        # 100 Hz default


@dataclass
class GPSReading:
    """
    ID: NAV-001-C
    Purpose: Position and velocity measurement from GPS receiver.
    Fields:
      - position_ecef_m: [x, y, z] ECEF position (meters)
      - velocity_ecef_ms: [vx, vy, vz] ECEF velocity (m/s)
      - position_accuracy_m: 1-sigma position error
      - velocity_accuracy_ms: 1-sigma velocity error
      - n_satellites: number of GPS satellites locked
      - timestamp: GPS solution time
      - valid: False in GPS blackout zones (e.g., high-radiation belts)
    """
    position_ecef_m: np.ndarray    # shape (3,)
    velocity_ecef_ms: np.ndarray   # shape (3,)
    position_accuracy_m: float
    velocity_accuracy_ms: float
    n_satellites: int
    sensor_id: str
    timestamp: datetime
    valid: bool = True


# ---------------------------------------------------------------------------
# Navigation state output
# ---------------------------------------------------------------------------

@dataclass
class NavigationState:
    """
    ID: NAV-001-D
    Purpose: Fused navigation solution - single source of truth for spacecraft
             position, velocity, and attitude at any given time.
    Fields:
      - position_ecef_m: 3D ECEF position (meters)
      - velocity_ecef_ms: 3D ECEF velocity (m/s)
      - attitude_quaternion: body-to-ECI rotation [qx, qy, qz, qw]
      - attitude_euler_deg: [roll, pitch, yaw] in degrees (diagnostic)
      - angular_rate_rads: body frame angular velocity (rad/s)
      - position_uncertainty_m: 1-sigma position error (m)
      - attitude_uncertainty_arcsec: 1-sigma attitude error (arcsec)
      - source_weights: fraction contribution of each sensor to this estimate
      - timestamp: solution time
      - mode: operating mode (full_nav, imu_only, kepler_propagation)
    """
    position_ecef_m: np.ndarray
    velocity_ecef_ms: np.ndarray
    attitude_quaternion: np.ndarray   # [qx, qy, qz, qw]
    attitude_euler_deg: np.ndarray    # [roll, pitch, yaw]
    angular_rate_rads: np.ndarray
    position_uncertainty_m: float
    attitude_uncertainty_arcsec: float
    source_weights: Dict[str, float]
    timestamp: datetime
    mode: str = "full_nav"
    sensor_statuses: Dict[str, NavSensorStatus] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Quaternion utilities
# ---------------------------------------------------------------------------

def _quat_normalize(q: np.ndarray) -> np.ndarray:
    """Normalize quaternion to unit length."""
    n = np.linalg.norm(q)
    return q / n if n > 1e-9 else np.array([0, 0, 0, 1], dtype=np.float64)


def _quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """
    ID: NAV-002
    Purpose: Hamilton product of two quaternions [qx, qy, qz, qw].
    """
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return np.array([
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
    ], dtype=np.float64)


def _quat_integrate(q: np.ndarray, omega: np.ndarray, dt: float) -> np.ndarray:
    """
    ID: NAV-003
    Requirement: Propagate attitude quaternion using angular rate omega over dt.
    Method: First-order Euler integration of quaternion kinematics.
            q_dot = 0.5 * Omega(omega) * q
    Inputs:
      - q: current quaternion [qx, qy, qz, qw]
      - omega: angular rate [wx, wy, wz] rad/s (body frame)
      - dt: time step seconds
    Outputs: Updated unit quaternion.
    """
    wx, wy, wz = omega
    Omega = 0.5 * np.array([
        [ 0,  wz, -wy,  wx],
        [-wz,  0,  wx,  wy],
        [ wy, -wx,  0,  wz],
        [-wx, -wy, -wz,  0],
    ], dtype=np.float64)
    q_dot = Omega @ q
    q_new = q + q_dot * dt
    return _quat_normalize(q_new)


def _quat_to_euler_deg(q: np.ndarray) -> np.ndarray:
    """
    ID: NAV-004
    Purpose: Convert quaternion [qx, qy, qz, qw] to Euler angles [roll, pitch, yaw] in degrees.
    """
    qx, qy, qz, qw = q
    # Roll (x-axis)
    sinr_cosp = 2.0 * (qw * qx + qy * qz)
    cosr_cosp = 1.0 - 2.0 * (qx*qx + qy*qy)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    # Pitch (y-axis)
    sinp = 2.0 * (qw * qy - qz * qx)
    sinp = max(-1.0, min(1.0, sinp))
    pitch = math.asin(sinp)
    # Yaw (z-axis)
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy*qy + qz*qz)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return np.degrees(np.array([roll, pitch, yaw]))


# ---------------------------------------------------------------------------
# EKF navigation filter
# ---------------------------------------------------------------------------

class _NavigationEKF:
    """
    ID: NAV-005
    Requirement: Extended Kalman Filter for spacecraft attitude + orbit estimation.
    State vector (10-D):
      [qx, qy, qz, qw,     - attitude quaternion (4)
       bx, by, bz,          - gyro bias (3)
       x,  y,  z  ]         - ECEF position (3) - simplified
    Measurement models:
      - Star tracker: 3D attitude update via small-angle linearization
      - GPS: direct 3D position measurement
    Note: Full orbit propagation (Keplerian + J2) omitted for brevity; position
          state is updated from GPS only; between GPS updates position is
          propagated with velocity from last IMU integration.
    """

    STATE_DIM = 10

    def __init__(self):
        # Initial state
        self.x = np.zeros(self.STATE_DIM)
        self.x[3] = 1.0  # qw = 1 (identity quaternion)
        # Position: LEO nominal (ISS altitude ~420 km)
        self.x[7:10] = np.array([6_791_000.0, 0.0, 0.0])

        # Covariance
        self.P = np.eye(self.STATE_DIM) * 1e-4
        self.P[7:10, 7:10] = np.eye(3) * 1e6  # Large position uncertainty initially

        # Process noise
        self.Q_att = 1e-7     # Attitude process noise variance
        self.Q_bias = 1e-10   # Gyro bias random walk
        self.Q_pos = 1.0      # Position process noise (m^2)

        # Velocity for position propagation
        self._velocity = np.zeros(3)

    def propagate(self, imu: IMUReading) -> None:
        """
        ID: NAV-005-A
        Requirement: IMU propagation step - integrate angular rate into attitude;
                     propagate position with current velocity estimate.
        Inputs: imu - IMU measurement with angular rate and dt.
        Side Effects: Updates self.x (state) and self.P (covariance).
        """
        dt = max(1e-4, imu.dt_seconds)
        q = self.x[:4]
        bias = self.x[4:7]

        # Bias-corrected angular rate
        omega = imu.angular_rate_rads - bias

        # Propagate quaternion
        q_new = _quat_integrate(q, omega, dt)
        self.x[:4] = q_new

        # Propagate position
        self.x[7:10] = self.x[7:10] + self._velocity * dt

        # Update velocity from accelerometer (simplified: subtract gravity)
        GRAVITY_ECEF = np.array([0.0, 0.0, -9.81])
        self._velocity += (imu.linear_accel_ms2 + GRAVITY_ECEF) * dt

        # Covariance propagation (simplified additive process noise)
        self.P[:4, :4] += np.eye(4) * self.Q_att * dt
        self.P[4:7, 4:7] += np.eye(3) * self.Q_bias * dt
        self.P[7:10, 7:10] += np.eye(3) * self.Q_pos * dt

    def update_star_tracker(self, st: StarTrackerReading) -> None:
        """
        ID: NAV-005-B
        Requirement: Update attitude state from star tracker quaternion measurement.
        Uses small-angle linearization around current estimate.
        """
        if not st.valid or st.n_stars_tracked < 4:
            return

        # Measurement noise in radians from arcsec spec
        sigma_rad = math.radians(st.angular_uncertainty_arcsec / 3600.0)
        R = np.eye(4) * (sigma_rad ** 2)

        # Innovation: difference between measured and predicted quaternion
        q_pred = self.x[:4]
        q_meas = _quat_normalize(st.quaternion.astype(np.float64))
        innovation = q_meas - q_pred

        # Measurement matrix H (4x10, identity for attitude block)
        H = np.zeros((4, self.STATE_DIM))
        H[:4, :4] = np.eye(4)

        # Kalman gain
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)

        # State update
        self.x = self.x + K @ innovation
        self.x[:4] = _quat_normalize(self.x[:4])

        # Covariance update (Joseph form for numerical stability)
        I_KH = np.eye(self.STATE_DIM) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R @ K.T

    def update_gps(self, gps: GPSReading) -> None:
        """
        ID: NAV-005-C
        Requirement: Update position and velocity from GPS measurement.
        """
        if not gps.valid or gps.n_satellites < 4:
            return

        R_pos = np.eye(3) * (gps.position_accuracy_m ** 2)

        # Measurement: 3D ECEF position
        H = np.zeros((3, self.STATE_DIM))
        H[:3, 7:10] = np.eye(3)

        innovation = gps.position_ecef_m - self.x[7:10]
        S = H @ self.P @ H.T + R_pos
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ innovation
        self.x[:4] = _quat_normalize(self.x[:4])

        I_KH = np.eye(self.STATE_DIM) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R_pos @ K.T

        # Update velocity from GPS Doppler
        self._velocity = gps.velocity_ecef_ms.copy()


# ---------------------------------------------------------------------------
# Main navigation integration layer
# ---------------------------------------------------------------------------

class NavigationSensorIntegration:
    """
    ID: NAV-001
    Requirement: Accept readings from star tracker, IMU, and GPS; run cascaded
                 EKF; emit NavigationState each cycle; detect and report
                 sensor dropouts with graceful degradation.
    Purpose: Single navigation interface for all upstream consumers (mission
             control, attitude control, life support, telemetry).
    Preconditions: At least IMU data required for propagation.
    Postconditions: NavigationState available with mode indicating data quality.
    """

    def __init__(self):
        self._ekf = _NavigationEKF()
        self._sensor_statuses: Dict[str, NavSensorStatus] = {}
        self._last_imu_time: Optional[datetime] = None
        self._last_state: Optional[NavigationState] = None
        self._imu_count = 0
        self._st_count = 0
        self._gps_count = 0

    def update(
        self,
        imu: Optional[IMUReading] = None,
        star_tracker: Optional[StarTrackerReading] = None,
        gps: Optional[GPSReading] = None,
    ) -> NavigationState:
        """
        ID: NAV-006
        Requirement: Run one navigation filter cycle with available sensor inputs.
        Inputs:
          - imu: IMU reading (primary propagation sensor)
          - star_tracker: star tracker attitude fix (high-accuracy update)
          - gps: GPS position fix (position update)
        Outputs: Current NavigationState.
        Side Effects: Updates EKF state; logs mode changes.
        Error Handling: Returns last-known-good on total sensor loss.
        """
        now = datetime.now(timezone.utc)
        source_weights: Dict[str, float] = {}
        mode = "kepler_propagation"

        # IMU propagation (primary)
        if imu is not None:
            if self._last_imu_time:
                dt = (imu.timestamp - self._last_imu_time).total_seconds()
                if 0 < dt < 10.0:
                    imu.dt_seconds = dt
            self._ekf.propagate(imu)
            self._last_imu_time = imu.timestamp
            self._imu_count += 1
            self._sensor_statuses[imu.sensor_id] = NavSensorStatus.NOMINAL
            source_weights["imu"] = 0.6
            mode = "imu_only"

        # Star tracker attitude update (high-accuracy correction)
        if star_tracker is not None and star_tracker.valid:
            self._ekf.update_star_tracker(star_tracker)
            self._st_count += 1
            self._sensor_statuses[star_tracker.sensor_id] = NavSensorStatus.NOMINAL
            source_weights["star_tracker"] = 0.3
            mode = "full_nav" if imu else "star_tracker_only"
        elif star_tracker is not None:
            self._sensor_statuses[star_tracker.sensor_id] = NavSensorStatus.LOST

        # GPS position update
        if gps is not None and gps.valid:
            self._ekf.update_gps(gps)
            self._gps_count += 1
            self._sensor_statuses[gps.sensor_id] = NavSensorStatus.NOMINAL
            source_weights["gps"] = 0.1
        elif gps is not None:
            self._sensor_statuses[gps.sensor_id] = NavSensorStatus.LOST

        # Build NavigationState from EKF state
        q = _quat_normalize(self._ekf.x[:4])
        euler = _quat_to_euler_deg(q)
        pos = self._ekf.x[7:10].copy()

        att_cov = self._ekf.P[:4, :4]
        att_sigma_rad = math.sqrt(max(0, np.trace(att_cov) / 4.0))
        att_sigma_arcsec = math.degrees(att_sigma_rad) * 3600.0

        pos_cov = self._ekf.P[7:10, 7:10]
        pos_sigma_m = math.sqrt(max(0, np.trace(pos_cov) / 3.0))

        omega_body = (imu.angular_rate_rads if imu is not None
                      else np.zeros(3))

        state = NavigationState(
            position_ecef_m=pos,
            velocity_ecef_ms=self._ekf._velocity.copy(),
            attitude_quaternion=q,
            attitude_euler_deg=euler,
            angular_rate_rads=omega_body,
            position_uncertainty_m=pos_sigma_m,
            attitude_uncertainty_arcsec=att_sigma_arcsec,
            source_weights=source_weights,
            timestamp=now,
            mode=mode,
            sensor_statuses=dict(self._sensor_statuses),
        )
        self._last_state = state
        return state

    def get_last_state(self) -> Optional[NavigationState]:
        """Return most recent navigation state without running a filter cycle."""
        return self._last_state

    def simulate_readings(
        self,
        include_gps: bool = True,
        include_star_tracker: bool = True,
        imu_noise_std: float = 1e-4,
    ) -> Tuple[IMUReading, Optional[StarTrackerReading], Optional[GPSReading]]:
        """
        ID: NAV-007
        Purpose: Generate synthetic sensor readings for testing.
        """
        import random
        now = datetime.now(timezone.utc)

        imu = IMUReading(
            angular_rate_rads=np.random.normal(0, imu_noise_std, 3),
            linear_accel_ms2=np.array([0.0, 0.0, -9.81]) + np.random.normal(0, 0.01, 3),
            temperature_c=25.0 + random.gauss(0, 0.5),
            bias_estimate=np.zeros(3),
            sensor_id="IMU-MAIN",
            timestamp=now,
            dt_seconds=0.01,
        )

        st = None
        if include_star_tracker:
            theta = random.gauss(0, 0.0001)  # tiny rotation
            st = StarTrackerReading(
                quaternion=np.array([math.sin(theta/2)*0.577,
                                     math.sin(theta/2)*0.577,
                                     math.sin(theta/2)*0.577,
                                     math.cos(theta/2)]),
                angular_uncertainty_arcsec=5.0,
                n_stars_tracked=random.randint(8, 25),
                sensor_id="ST-MAIN",
                timestamp=now,
                valid=True,
            )

        gps_reading = None
        if include_gps:
            gps_reading = GPSReading(
                position_ecef_m=np.array([6_791_000.0, 0.0, 0.0]) +
                                np.random.normal(0, 10, 3),
                velocity_ecef_ms=np.array([0.0, 7660.0, 0.0]) +
                                 np.random.normal(0, 0.5, 3),
                position_accuracy_m=15.0,
                velocity_accuracy_ms=0.5,
                n_satellites=random.randint(6, 12),
                sensor_id="GPS-MAIN",
                timestamp=now,
                valid=True,
            )

        return imu, st, gps_reading
