"""
sensor_fusion.py - Environmental Sensor Fusion Pipeline
=========================================================
ID: SEN-001
Requirement: Fuse readings from redundant temperature, pressure, and humidity
             sensors into a single high-confidence environmental state estimate
             using a complementary Kalman filter with fault-detection voting.
Purpose: Space environments expose sensors to radiation-induced drift, thermal
         extremes, and transient spike faults. Multi-sensor fusion provides
         noise reduction and fault isolation unavailable from a single sensor.
Rationale: Sensor fusion via weighted least-squares and Kalman smoothing reduces
           RMS noise by sqrt(N) for N redundant sensors, and outlier voting
           rejects single-sensor faults without halting the measurement pipeline.
Inputs: Raw readings from N >= 2 sensors per physical quantity.
Outputs: FusedEnvironmentalState with estimated value, uncertainty, and
         confidence score per channel.
Preconditions: At least one valid sensor per channel must be available.
Postconditions: Fused state published; faulty sensors flagged in SensorStatus.
Failure Modes:
  - Single-sensor faults isolated via majority voting (requires N >= 3).
  - All-sensor failure returns last-known-good value with confidence=0.
Side Effects: Maintains running Kalman filter state in memory.
Verification: Unit tested with injected fault cases; confidence drops on fault.
References: Kalman 1960, IEEE Trans. ASME; Brown & Hwang "Introduction to Random
            Signals and Applied Kalman Filtering" 4th ed.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SensorStatus(Enum):
    """
    ID: SEN-001-A
    Purpose: Health classification for each individual sensor instance.
    """
    NOMINAL = "nominal"           # Reading within expected bounds
    DEGRADED = "degraded"         # Reading borderline; reduced weight
    FAULTY = "faulty"             # Outlier-detected; excluded from fusion
    OFFLINE = "offline"           # No data received within timeout window
    CALIBRATING = "calibrating"   # Warm-up period; reduced weight


class EnvironmentalChannel(Enum):
    """Measurable environmental quantities."""
    TEMPERATURE_C = "temperature_c"
    PRESSURE_PA = "pressure_pa"
    HUMIDITY_PCT = "humidity_pct"
    CO2_PPM = "co2_ppm"
    O2_PPM = "o2_ppm"
    CABIN_DEW_POINT_C = "cabin_dew_point_c"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RawSensorReading:
    """
    ID: SEN-001-B
    Purpose: Single raw measurement from one physical sensor.
    Fields:
      - sensor_id: unique hardware identifier (e.g., 'TEMP-A1')
      - channel: physical quantity being measured
      - value: raw measurement in SI units (C, Pa, %, ppm)
      - uncertainty: 1-sigma measurement noise standard deviation
      - timestamp: UTC measurement time
      - quality_flag: 0=good, 1=suspect, 2=bad (from sensor's own BITE)
    """
    sensor_id: str
    channel: EnvironmentalChannel
    value: float
    uncertainty: float
    timestamp: datetime
    quality_flag: int = 0


@dataclass
class FusedChannelEstimate:
    """
    ID: SEN-001-C
    Purpose: Post-fusion estimate for one environmental channel.
    Fields:
      - value: best estimate of physical quantity
      - uncertainty: posterior 1-sigma from Kalman update
      - confidence: 0..1 overall confidence (1 = all sensors agree, nominal)
      - contributing_sensors: IDs of sensors included in this estimate
      - excluded_sensors: IDs of sensors rejected as outliers
      - kalman_gain: last applied Kalman gain (diagnostic)
    """
    channel: EnvironmentalChannel
    value: float
    uncertainty: float
    confidence: float
    contributing_sensors: List[str]
    excluded_sensors: List[str]
    timestamp: datetime
    kalman_gain: float = 0.0


@dataclass
class FusedEnvironmentalState:
    """
    ID: SEN-001-D
    Purpose: Complete fused environmental state snapshot across all channels.
    """
    channels: Dict[EnvironmentalChannel, FusedChannelEstimate]
    timestamp: datetime
    overall_confidence: float  # min(channel confidences)
    sensor_statuses: Dict[str, SensorStatus]

    def get(self, channel: EnvironmentalChannel) -> Optional[FusedChannelEstimate]:
        """Retrieve estimate for a specific channel."""
        return self.channels.get(channel)


# ---------------------------------------------------------------------------
# Kalman filter state (one per channel)
# ---------------------------------------------------------------------------

@dataclass
class _KalmanState:
    """
    ID: SEN-002
    Purpose: Per-channel 1D Kalman filter state (scalar position model).
    State x = physical quantity; process noise Q models slow drift.
    Measurement noise R updated dynamically from weighted sensor variances.
    """
    x: float           # State estimate
    P: float           # Estimate covariance
    Q: float = 1e-3    # Process noise variance (slow environmental drift)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def predict(self, dt_seconds: float) -> None:
        """
        ID: SEN-002-A
        Purpose: Kalman prediction step - propagate state forward by dt.
        Inputs: dt_seconds - elapsed time since last update.
        Side Effects: Updates self.x and self.P.
        """
        # Constant-value model (F=1, B=0); process noise grows with time
        self.P = self.P + self.Q * dt_seconds

    def update(self, z: float, R: float) -> float:
        """
        ID: SEN-002-B
        Requirement: Apply Kalman measurement update with measurement z, noise R.
        Inputs:
          - z: measurement value
          - R: measurement noise variance
        Outputs: Kalman gain K (diagnostic).
        Side Effects: Updates self.x and self.P.
        """
        H = 1.0
        K = self.P * H / (H * self.P * H + R + 1e-12)
        self.x = self.x + K * (z - H * self.x)
        self.P = (1 - K * H) * self.P
        self.P = max(self.P, 1e-9)  # Covariance floor
        self.last_updated = datetime.now(timezone.utc)
        return float(K)


# ---------------------------------------------------------------------------
# Outlier / fault detection
# ---------------------------------------------------------------------------

class _OutlierDetector:
    """
    ID: SEN-003
    Requirement: Identify sensor readings that deviate significantly from the
                 median of the sensor population for the same channel.
    Approach: Modified Z-score using median absolute deviation (MAD), which is
              robust to outliers unlike standard deviation.
    Threshold: |z_mad| > 3.5 flags reading as outlier (Iglewicz & Hoaglin 1993).
    """

    MAD_THRESHOLD = 3.5

    def detect(
        self, readings: List[RawSensorReading]
    ) -> Tuple[List[RawSensorReading], List[RawSensorReading]]:
        """
        ID: SEN-003-A
        Inputs: readings - list of raw readings for the same channel.
        Outputs: (good_readings, outlier_readings)
        """
        if len(readings) < 2:
            return readings, []

        values = np.array([r.value for r in readings])
        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad < 1e-9:
            return readings, []

        z_scores = 0.6745 * np.abs(values - median) / mad
        good, bad = [], []
        for r, z in zip(readings, z_scores):
            if z > self.MAD_THRESHOLD or r.quality_flag >= 2:
                bad.append(r)
            else:
                good.append(r)

        if bad:
            logger.warning(
                "Outlier sensors on %s: %s",
                readings[0].channel.value,
                [r.sensor_id for r in bad],
            )
        return good, bad


# ---------------------------------------------------------------------------
# Main sensor fusion engine
# ---------------------------------------------------------------------------

class EnvironmentalSensorFusion:
    """
    ID: SEN-001
    Requirement: Accept raw readings from multiple redundant sensors per channel,
                 detect and isolate faulty sensors, apply Kalman filtering to
                 the ensemble, and emit a high-confidence fused state estimate.
    Purpose: Provide reliable environmental telemetry to life support, mission
             control, and health monitoring systems despite sensor degradation.
    Preconditions: At least 1 valid sensor per channel must be registered.
    Side Effects: Maintains Kalman state and sensor status history in memory.
    Failure Modes: Returns last-known-good with confidence=0 on total sensor loss.
    """

    # Physical validity bounds per channel [min, max]
    BOUNDS: Dict[EnvironmentalChannel, Tuple[float, float]] = {
        EnvironmentalChannel.TEMPERATURE_C:    (-270.0, 200.0),
        EnvironmentalChannel.PRESSURE_PA:      (0.0, 200_000.0),
        EnvironmentalChannel.HUMIDITY_PCT:     (0.0, 100.0),
        EnvironmentalChannel.CO2_PPM:          (0.0, 50_000.0),
        EnvironmentalChannel.O2_PPM:           (0.0, 300_000.0),
        EnvironmentalChannel.CABIN_DEW_POINT_C: (-80.0, 60.0),
    }

    def __init__(self):
        self._kalman: Dict[EnvironmentalChannel, _KalmanState] = {}
        self._outlier_detector = _OutlierDetector()
        self._sensor_status: Dict[str, SensorStatus] = {}
        self._last_state: Optional[FusedEnvironmentalState] = None

    def fuse(self, readings: List[RawSensorReading]) -> FusedEnvironmentalState:
        """
        ID: SEN-004
        Requirement: Process a batch of raw sensor readings and return fused state.
        Inputs: readings - all sensor readings to be fused (may span multiple channels).
        Outputs: FusedEnvironmentalState with per-channel estimates.
        Side Effects: Updates internal Kalman state; logs anomalies.
        Error Handling: Channels with no valid readings return last-known-good.
        """
        now = datetime.now(timezone.utc)

        # Group by channel
        by_channel: Dict[EnvironmentalChannel, List[RawSensorReading]] = {}
        for r in readings:
            by_channel.setdefault(r.channel, []).append(r)

        channels_out: Dict[EnvironmentalChannel, FusedChannelEstimate] = {}

        for channel, ch_readings in by_channel.items():
            estimate = self._fuse_channel(channel, ch_readings, now)
            channels_out[channel] = estimate

        # Carry forward last-known-good for missing channels
        if self._last_state:
            for ch, est in self._last_state.channels.items():
                if ch not in channels_out:
                    stale = FusedChannelEstimate(
                        channel=ch, value=est.value,
                        uncertainty=est.uncertainty * 2,  # Growing uncertainty
                        confidence=max(0.0, est.confidence - 0.1),
                        contributing_sensors=[], excluded_sensors=[],
                        timestamp=now,
                    )
                    channels_out[ch] = stale

        overall_conf = (
            min(e.confidence for e in channels_out.values())
            if channels_out else 0.0
        )

        state = FusedEnvironmentalState(
            channels=channels_out,
            timestamp=now,
            overall_confidence=overall_conf,
            sensor_statuses=dict(self._sensor_status),
        )
        self._last_state = state
        return state

    def _fuse_channel(
        self,
        channel: EnvironmentalChannel,
        readings: List[RawSensorReading],
        now: datetime,
    ) -> FusedChannelEstimate:
        """
        ID: SEN-005
        Purpose: Fuse all readings for a single channel into one estimate.
        Steps:
          1. Physical bounds check - reject physically impossible values.
          2. Outlier detection via MAD Z-score.
          3. Weighted least-squares combination of good readings.
          4. Kalman filter update with combined measurement.
          5. Confidence scoring.
        """
        bounds = self.BOUNDS.get(channel, (-1e9, 1e9))

        # 1. Physical bounds
        valid = [r for r in readings
                 if bounds[0] <= r.value <= bounds[1] and r.quality_flag < 2]
        for r in readings:
            if r not in valid:
                self._sensor_status[r.sensor_id] = SensorStatus.FAULTY

        if not valid:
            logger.error("All sensors failed on %s - using last-known-good.", channel.value)
            return self._last_known_good(channel, now)

        # 2. Outlier detection
        good, outliers = self._outlier_detector.detect(valid)
        for r in outliers:
            self._sensor_status[r.sensor_id] = SensorStatus.FAULTY
        for r in good:
            status = (SensorStatus.DEGRADED if r.quality_flag == 1
                      else SensorStatus.NOMINAL)
            self._sensor_status[r.sensor_id] = status

        if not good:
            good = valid  # Fall back to all valid if all are outliers

        # 3. Weighted least-squares: w_i = 1/sigma_i^2
        variances = np.array([max(r.uncertainty ** 2, 1e-9) for r in good])
        values = np.array([r.value for r in good])
        weights = 1.0 / variances
        wls_value = float(np.sum(weights * values) / np.sum(weights))
        wls_variance = float(1.0 / np.sum(weights))

        # 4. Kalman update
        if channel not in self._kalman:
            self._kalman[channel] = _KalmanState(x=wls_value, P=wls_variance)

        kf = self._kalman[channel]
        dt = (now - kf.last_updated).total_seconds()
        if 0 < dt < 3600:
            kf.predict(dt)
        K = kf.update(wls_value, wls_variance)

        # 5. Confidence: penalize for outliers and faulty sensors
        n_total = len(readings)
        n_good = len(good)
        outlier_penalty = (n_total - n_good) / max(1, n_total) * 0.4
        confidence = max(0.0, min(1.0, 1.0 - outlier_penalty))
        if n_good == 1:
            confidence *= 0.7  # Single sensor - reduced confidence

        return FusedChannelEstimate(
            channel=channel,
            value=kf.x,
            uncertainty=math.sqrt(max(kf.P, 1e-9)),
            confidence=confidence,
            contributing_sensors=[r.sensor_id for r in good],
            excluded_sensors=[r.sensor_id for r in outliers],
            timestamp=now,
            kalman_gain=K,
        )

    def _last_known_good(
        self, channel: EnvironmentalChannel, now: datetime
    ) -> FusedChannelEstimate:
        """
        ID: SEN-006
        Purpose: Return last-known-good estimate when all sensors fail.
        Outputs: FusedChannelEstimate with confidence=0 and growing uncertainty.
        """
        default_values = {
            EnvironmentalChannel.TEMPERATURE_C: 22.0,
            EnvironmentalChannel.PRESSURE_PA: 101_325.0,
            EnvironmentalChannel.HUMIDITY_PCT: 50.0,
            EnvironmentalChannel.CO2_PPM: 1000.0,
            EnvironmentalChannel.O2_PPM: 209_000.0,
            EnvironmentalChannel.CABIN_DEW_POINT_C: 10.0,
        }
        if self._last_state and channel in self._last_state.channels:
            last = self._last_state.channels[channel]
            return FusedChannelEstimate(
                channel=channel, value=last.value,
                uncertainty=last.uncertainty * 3.0,
                confidence=0.0,
                contributing_sensors=[], excluded_sensors=[],
                timestamp=now,
            )
        return FusedChannelEstimate(
            channel=channel,
            value=default_values.get(channel, 0.0),
            uncertainty=999.0,
            confidence=0.0,
            contributing_sensors=[], excluded_sensors=[],
            timestamp=now,
        )

    def get_sensor_status(self) -> Dict[str, SensorStatus]:
        """Return current health status for all registered sensors."""
        return dict(self._sensor_status)

    def inject_simulated_readings(
        self,
        n_temp: int = 3,
        n_pressure: int = 3,
        n_humidity: int = 2,
        n_o2: int = 2,
        n_co2: int = 2,
        fault_fraction: float = 0.0,
    ) -> List[RawSensorReading]:
        """
        ID: SEN-007
        Purpose: Generate synthetic sensor readings for testing and simulation.
        Inputs:
          - n_*: number of sensors per channel
          - fault_fraction: fraction of sensors to inject faults into [0..1]
        Outputs: List of RawSensorReading suitable for fuse().
        """
        import random
        readings: List[RawSensorReading] = []
        now = datetime.now(timezone.utc)

        specs = [
            (EnvironmentalChannel.TEMPERATURE_C, n_temp, 22.0, 0.3, "TEMP"),
            (EnvironmentalChannel.PRESSURE_PA, n_pressure, 101_325.0, 50.0, "PRES"),
            (EnvironmentalChannel.HUMIDITY_PCT, n_humidity, 45.0, 1.0, "HUM"),
            (EnvironmentalChannel.O2_PPM, n_o2, 209_000.0, 500.0, "O2"),
            (EnvironmentalChannel.CO2_PPM, n_co2, 800.0, 20.0, "CO2"),
        ]

        for channel, n, nominal, noise, prefix in specs:
            for i in range(n):
                sensor_id = f"{prefix}-{i+1:02d}"
                is_fault = random.random() < fault_fraction
                value = (nominal + random.uniform(-999, 999)
                         if is_fault
                         else nominal + random.gauss(0, noise))
                readings.append(RawSensorReading(
                    sensor_id=sensor_id,
                    channel=channel,
                    value=value,
                    uncertainty=noise,
                    timestamp=now,
                    quality_flag=2 if is_fault else 0,
                ))
        return readings
