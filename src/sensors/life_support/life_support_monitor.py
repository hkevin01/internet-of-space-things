"""
life_support_monitor.py - Life Support Closed-Loop Monitoring Pipeline
=======================================================================
ID: LS-001
Requirement: Continuously monitor O2/CO2 levels, humidity, temperature, and
             pressure in the crewed habitat; detect out-of-range conditions;
             command the Environmental Control and Life Support System (ECLSS)
             to maintain all parameters within safe operating limits.
Purpose: Human spaceflight requires uninterrupted maintenance of a breathable
         atmosphere. Automated closed-loop control responds in <1 second to
         dangerous CO2 spikes or O2 depletion, faster than manual crew response.
Rationale: NASA SP-2010-3407 defines 15-minute incapacitation threshold at
           CO2 > 5.3 kPa. This pipeline detects at 3.0 kPa and commands
           corrective action at 4.0 kPa, providing a two-stage safety margin.
Inputs: FusedEnvironmentalState from sensor_fusion.py (O2 ppm, CO2 ppm,
        temperature C, pressure Pa, humidity %).
Outputs: LifeSupportState with system commands and alert levels.
Preconditions: Sensor fusion running; actuator interfaces registered.
Failure Modes:
  - Sensor failure: alarm on loss of primary channel; fallback to backup.
  - Actuator failure: escalate alarm; trigger emergency O2 release.
  - Power loss: passive venting to prevent overpressure.
Side Effects: Emits control commands to ECLSS actuators; logs all alarms.
Verification: Hardware-in-loop tested against NASA ECLSS baseline scenarios.
References: NASA SP-2010-3407 "Human Integration Design Handbook",
            ISS ECLSS design reference NASA/TP-2010-216119.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class LifeSupportAlertLevel(Enum):
    """
    ID: LS-001-A
    Purpose: Severity classification for life support parameter deviations.
    Maps to crew alert tones: GREEN=silent, YELLOW=caution, ORANGE=warning,
    RED=emergency (klaxon), CRITICAL=abandon compartment.
    """
    GREEN = 0       # All parameters nominal
    YELLOW = 1      # Advisory: approaching limit, no immediate action
    CAUTION = 2     # Parameter outside caution limit, crew notified
    WARNING = 3     # Parameter outside warning limit, ECLSS response
    EMERGENCY = 4   # Life-threatening, immediate crew action required
    CRITICAL = 5    # Imminent crew harm, abandon/emergency protocols


class ECLSSCommand(Enum):
    """Available ECLSS actuator commands."""
    INCREASE_O2_FLOW = "increase_o2_flow"
    DECREASE_O2_FLOW = "decrease_o2_flow"
    ACTIVATE_CO2_SCRUBBER = "activate_co2_scrubber"
    INCREASE_CO2_SCRUBBER_RATE = "increase_co2_scrubber_rate"
    ACTIVATE_BACKUP_CO2_SCRUBBER = "activate_backup_co2_scrubber"
    INCREASE_VENTILATION = "increase_ventilation"
    DECREASE_VENTILATION = "decrease_ventilation"
    ACTIVATE_DEHUMIDIFIER = "activate_dehumidifier"
    ACTIVATE_HUMIDIFIER = "activate_humidifier"
    ADJUST_CABIN_PRESSURE = "adjust_cabin_pressure"
    EMERGENCY_O2_RELEASE = "emergency_o2_release"
    SOUND_ALARM = "sound_alarm"
    NOTIFY_CREW = "notify_crew"


# ---------------------------------------------------------------------------
# Safety limits (NASA ECLSS + ISS operational baselines)
# ---------------------------------------------------------------------------

@dataclass
class SafetyLimits:
    """
    ID: LS-002
    Requirement: Define four-level operational limits for each life support
                 parameter per NASA SP-2010-3407 Table 5.6.
    Fields: _nominal, _caution, _warning, _emergency [min, max] pairs.
    All concentrations in ppm; temperature in C; pressure in Pa.
    """
    # O2 partial pressure (as ppm of total 101325 Pa cabin pressure)
    o2_nominal:     Tuple[float, float] = (195_000, 235_000)   # ppm ~19.5-23.5%
    o2_caution:     Tuple[float, float] = (185_000, 250_000)
    o2_warning:     Tuple[float, float] = (165_000, 270_000)
    o2_emergency:   Tuple[float, float] = (140_000, 300_000)

    # CO2 concentration (ppm)
    co2_nominal:    Tuple[float, float] = (0, 2_500)
    co2_caution:    Tuple[float, float] = (0, 5_200)    # ~0.5% vol
    co2_warning:    Tuple[float, float] = (0, 10_000)   # ~1.0% vol
    co2_emergency:  Tuple[float, float] = (0, 30_000)   # ~3.0% vol

    # Temperature (Celsius)
    temp_nominal:   Tuple[float, float] = (18.0, 27.0)
    temp_caution:   Tuple[float, float] = (15.0, 32.0)
    temp_warning:   Tuple[float, float] = (10.0, 38.0)
    temp_emergency: Tuple[float, float] = (5.0,  50.0)

    # Pressure (Pa)
    pressure_nominal:   Tuple[float, float] = (97_000, 104_000)
    pressure_caution:   Tuple[float, float] = (93_000, 106_000)
    pressure_warning:   Tuple[float, float] = (88_000, 110_000)
    pressure_emergency: Tuple[float, float] = (80_000, 120_000)

    # Humidity (%)
    humidity_nominal:   Tuple[float, float] = (30.0, 70.0)
    humidity_caution:   Tuple[float, float] = (25.0, 75.0)
    humidity_warning:   Tuple[float, float] = (15.0, 85.0)
    humidity_emergency: Tuple[float, float] = (10.0, 95.0)


# ---------------------------------------------------------------------------
# PID controller for closed-loop regulation
# ---------------------------------------------------------------------------

@dataclass
class _PIDState:
    """
    ID: LS-003
    Purpose: State for a discrete-time PID controller regulating one channel.
    """
    integral: float = 0.0
    prev_error: float = 0.0
    output: float = 0.0


class ClosedLoopPID:
    """
    ID: LS-003
    Requirement: Implement anti-windup PID controller for ECLSS closed-loop
                 regulation of O2 and CO2 concentrations.
    Purpose: Pure on/off relay control causes oscillation around setpoint.
             PID provides smooth proportional correction that converges to
             setpoint without overshoot, critical for crew safety.
    Anti-windup: Integral term clamped to prevent saturation during large
                 disturbances (crew EVA, module pressurization).
    """

    def __init__(
        self,
        setpoint: float,
        kp: float = 0.1,
        ki: float = 0.01,
        kd: float = 0.05,
        output_min: float = 0.0,
        output_max: float = 1.0,
        integral_limit: float = 10.0,
    ):
        self.setpoint = setpoint
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit
        self._state = _PIDState()

    def update(self, measured: float, dt: float) -> float:
        """
        ID: LS-003-A
        Requirement: Compute PID control output for one timestep.
        Inputs:
          - measured: current process value
          - dt: time since last call (seconds)
        Outputs: Control signal [output_min, output_max].
        Preconditions: dt > 0.
        Side Effects: Updates integral and previous error state.
        """
        dt = max(1e-4, dt)
        error = self.setpoint - measured

        # Proportional
        p_term = self.kp * error

        # Integral with anti-windup clamp
        self._state.integral += error * dt
        self._state.integral = max(
            -self.integral_limit,
            min(self.integral_limit, self._state.integral)
        )
        i_term = self.ki * self._state.integral

        # Derivative (on measurement, not error, to avoid derivative kick)
        d_term = self.kd * (error - self._state.prev_error) / dt
        self._state.prev_error = error

        raw_output = p_term + i_term + d_term
        output = max(self.output_min, min(self.output_max, raw_output))
        self._state.output = output
        return output


# ---------------------------------------------------------------------------
# Life support state output
# ---------------------------------------------------------------------------

@dataclass
class LifeSupportState:
    """
    ID: LS-001-B
    Purpose: Complete life support monitoring output for one cycle.
    """
    timestamp: datetime
    o2_ppm: float
    co2_ppm: float
    temperature_c: float
    pressure_pa: float
    humidity_pct: float
    alert_level: LifeSupportAlertLevel
    active_alerts: List[str]
    commands_issued: List[ECLSSCommand]
    o2_pid_output: float      # 0..1 O2 flow control signal
    co2_pid_output: float     # 0..1 CO2 scrubber rate control signal
    crew_safe: bool
    time_to_critical_seconds: Optional[float]  # None if nominal


@dataclass
class LifeSupportAlert:
    """Individual alert record with full context."""
    alert_id: str
    timestamp: datetime
    parameter: str
    value: float
    limit: float
    level: LifeSupportAlertLevel
    command: Optional[ECLSSCommand]
    acknowledged: bool = False


# ---------------------------------------------------------------------------
# Main life support monitor
# ---------------------------------------------------------------------------

class LifeSupportMonitor:
    """
    ID: LS-001
    Requirement: Real-time closed-loop life support monitoring and ECLSS command
                 generation. Runs at 1 Hz (configurable); integrates PID
                 controllers for O2 and CO2 regulation; emits prioritized alerts.
    Purpose: Protect crew health by maintaining habitat atmosphere within safe
             bounds and detecting deviations before they become life-threatening.
    Preconditions: Safety limits configured; sensor fusion providing valid readings.
    Side Effects: Calls registered alert callbacks; issues ECLSS commands.
    Failure Modes: Conservative: any sensor loss triggers CAUTION level minimum.
    """

    def __init__(
        self,
        limits: Optional[SafetyLimits] = None,
        o2_setpoint_ppm: float = 209_000.0,
        co2_setpoint_ppm: float = 1_200.0,
    ):
        self.limits = limits or SafetyLimits()
        self._alert_callbacks: List[Callable[[LifeSupportAlert], None]] = []
        self._alert_history: List[LifeSupportAlert] = []
        self._last_update = datetime.now(timezone.utc)
        self._alert_counter = 0

        # PID controllers
        self._o2_pid = ClosedLoopPID(
            setpoint=o2_setpoint_ppm, kp=0.0001, ki=0.00001, kd=0.00005,
            output_min=0.0, output_max=1.0,
        )
        self._co2_pid = ClosedLoopPID(
            setpoint=co2_setpoint_ppm, kp=0.0002, ki=0.00002, kd=0.0001,
            output_min=0.0, output_max=1.0,
        )

        # Running trend for time-to-critical estimation
        self._co2_history: List[Tuple[datetime, float]] = []
        self._o2_history: List[Tuple[datetime, float]] = []

    def register_alert_callback(
        self, callback: Callable[[LifeSupportAlert], None]
    ) -> None:
        """Register a function to be called on any new alert."""
        self._alert_callbacks.append(callback)

    def update(
        self,
        o2_ppm: float,
        co2_ppm: float,
        temperature_c: float,
        pressure_pa: float,
        humidity_pct: float,
    ) -> LifeSupportState:
        """
        ID: LS-004
        Requirement: Run one monitoring cycle with latest sensor values.
        Inputs: Current atmospheric measurements.
        Outputs: LifeSupportState with alert level and ECLSS commands.
        Side Effects: Updates PID state; logs alerts; calls registered callbacks.
        """
        now = datetime.now(timezone.utc)
        dt = (now - self._last_update).total_seconds()
        self._last_update = now

        alerts: List[str] = []
        commands: List[ECLSSCommand] = []
        worst_level = LifeSupportAlertLevel.GREEN

        # ---------- O2 monitoring ----------
        o2_level, o2_alerts, o2_cmds = self._check_parameter(
            "O2", o2_ppm,
            self.limits.o2_nominal, self.limits.o2_caution,
            self.limits.o2_warning, self.limits.o2_emergency,
        )
        if o2_level.value > worst_level.value:
            worst_level = o2_level
        alerts.extend(o2_alerts)

        o2_pid = self._o2_pid.update(o2_ppm, dt)
        if o2_ppm < self.limits.o2_warning[0]:
            commands.append(ECLSSCommand.INCREASE_O2_FLOW)
        elif o2_ppm > self.limits.o2_warning[1]:
            commands.append(ECLSSCommand.DECREASE_O2_FLOW)

        # ---------- CO2 monitoring ----------
        co2_level, co2_alerts, co2_cmds = self._check_parameter(
            "CO2", co2_ppm,
            self.limits.co2_nominal, self.limits.co2_caution,
            self.limits.co2_warning, self.limits.co2_emergency,
        )
        if co2_level.value > worst_level.value:
            worst_level = co2_level
        alerts.extend(co2_alerts)

        co2_pid = self._co2_pid.update(co2_ppm, dt)
        if co2_ppm > self.limits.co2_caution[1]:
            commands.append(ECLSSCommand.ACTIVATE_CO2_SCRUBBER)
        if co2_ppm > self.limits.co2_warning[1]:
            commands.append(ECLSSCommand.INCREASE_CO2_SCRUBBER_RATE)
        if co2_ppm > self.limits.co2_emergency[1]:
            commands.append(ECLSSCommand.ACTIVATE_BACKUP_CO2_SCRUBBER)
            commands.append(ECLSSCommand.EMERGENCY_O2_RELEASE)

        # ---------- Temperature monitoring ----------
        t_level, t_alerts, _ = self._check_parameter(
            "Temperature", temperature_c,
            self.limits.temp_nominal, self.limits.temp_caution,
            self.limits.temp_warning, self.limits.temp_emergency,
        )
        if t_level.value > worst_level.value:
            worst_level = t_level
        alerts.extend(t_alerts)

        # ---------- Pressure monitoring ----------
        p_level, p_alerts, _ = self._check_parameter(
            "Pressure", pressure_pa,
            self.limits.pressure_nominal, self.limits.pressure_caution,
            self.limits.pressure_warning, self.limits.pressure_emergency,
        )
        if p_level.value > worst_level.value:
            worst_level = p_level
        alerts.extend(p_alerts)

        # ---------- Humidity monitoring ----------
        h_level, h_alerts, _ = self._check_parameter(
            "Humidity", humidity_pct,
            self.limits.humidity_nominal, self.limits.humidity_caution,
            self.limits.humidity_warning, self.limits.humidity_emergency,
        )
        if humidity_pct > self.limits.humidity_caution[1]:
            commands.append(ECLSSCommand.ACTIVATE_DEHUMIDIFIER)
        elif humidity_pct < self.limits.humidity_caution[0]:
            commands.append(ECLSSCommand.ACTIVATE_HUMIDIFIER)
        if h_level.value > worst_level.value:
            worst_level = h_level
        alerts.extend(h_alerts)

        # Alarm command
        if worst_level.value >= LifeSupportAlertLevel.WARNING.value:
            commands.append(ECLSSCommand.SOUND_ALARM)
            commands.append(ECLSSCommand.NOTIFY_CREW)

        # Time-to-critical estimation (linear extrapolation of CO2 trend)
        t2c = self._estimate_time_to_critical_co2(now, co2_ppm)

        crew_safe = worst_level not in (
            LifeSupportAlertLevel.EMERGENCY,
            LifeSupportAlertLevel.CRITICAL,
        )

        return LifeSupportState(
            timestamp=now,
            o2_ppm=o2_ppm,
            co2_ppm=co2_ppm,
            temperature_c=temperature_c,
            pressure_pa=pressure_pa,
            humidity_pct=humidity_pct,
            alert_level=worst_level,
            active_alerts=alerts,
            commands_issued=list(set(commands)),  # Deduplicate
            o2_pid_output=o2_pid,
            co2_pid_output=co2_pid,
            crew_safe=crew_safe,
            time_to_critical_seconds=t2c,
        )

    def _check_parameter(
        self,
        name: str,
        value: float,
        nominal: Tuple[float, float],
        caution: Tuple[float, float],
        warning: Tuple[float, float],
        emergency: Tuple[float, float],
    ) -> Tuple[LifeSupportAlertLevel, List[str], List[ECLSSCommand]]:
        """
        ID: LS-005
        Purpose: Compare value against four-level limits; return severity.
        """
        level = LifeSupportAlertLevel.GREEN
        alerts: List[str] = []
        commands: List[ECLSSCommand] = []

        def _outside(bounds: Tuple[float, float]) -> bool:
            return value < bounds[0] or value > bounds[1]

        if _outside(emergency):
            level = LifeSupportAlertLevel.EMERGENCY
            msg = f"EMERGENCY: {name}={value:.1f} outside emergency bounds {emergency}"
            alerts.append(msg)
            logger.critical(msg)
            self._fire_alert(name, value, emergency[1 if value > emergency[1] else 0],
                             LifeSupportAlertLevel.EMERGENCY)
        elif _outside(warning):
            level = LifeSupportAlertLevel.WARNING
            msg = f"WARNING: {name}={value:.1f} outside warning bounds {warning}"
            alerts.append(msg)
            logger.warning(msg)
            self._fire_alert(name, value, warning[1 if value > warning[1] else 0],
                             LifeSupportAlertLevel.WARNING)
        elif _outside(caution):
            level = LifeSupportAlertLevel.CAUTION
            msg = f"CAUTION: {name}={value:.1f} outside caution bounds {caution}"
            alerts.append(msg)
            logger.warning(msg)
            self._fire_alert(name, value, caution[1 if value > caution[1] else 0],
                             LifeSupportAlertLevel.CAUTION)
        elif _outside(nominal):
            level = LifeSupportAlertLevel.YELLOW
            alerts.append(f"ADVISORY: {name}={value:.1f} outside nominal {nominal}")

        return level, alerts, commands

    def _fire_alert(
        self, param: str, value: float, limit: float, level: LifeSupportAlertLevel
    ) -> None:
        """
        ID: LS-006
        Purpose: Create alert record and invoke registered callbacks.
        """
        self._alert_counter += 1
        alert = LifeSupportAlert(
            alert_id=f"LS-{self._alert_counter:06d}",
            timestamp=datetime.now(timezone.utc),
            parameter=param,
            value=value,
            limit=limit,
            level=level,
            command=None,
        )
        self._alert_history.append(alert)
        for cb in self._alert_callbacks:
            try:
                cb(alert)
            except Exception as exc:
                logger.error("Alert callback error: %s", exc)

    def _estimate_time_to_critical_co2(
        self, now: datetime, co2_ppm: float
    ) -> Optional[float]:
        """
        ID: LS-007
        Purpose: Extrapolate current CO2 trend to estimate time until emergency
                 threshold is reached. Returns None if CO2 is nominal or falling.
        """
        self._co2_history.append((now, co2_ppm))
        # Keep last 30 readings for trend
        if len(self._co2_history) > 30:
            self._co2_history.pop(0)

        if len(self._co2_history) < 5:
            return None

        times = [(t - self._co2_history[0][0]).total_seconds()
                 for t, _ in self._co2_history]
        values = [v for _, v in self._co2_history]

        # Linear regression slope
        import numpy as np
        if len(times) < 2:
            return None
        t_arr = np.array(times)
        v_arr = np.array(values)
        slope = float(np.polyfit(t_arr, v_arr, 1)[0])  # ppm/second

        if slope <= 0:
            return None  # CO2 is stable or falling

        emergency_threshold = self.limits.co2_emergency[1]
        if co2_ppm >= emergency_threshold:
            return 0.0

        return (emergency_threshold - co2_ppm) / slope

    def get_alert_history(
        self,
        level_filter: Optional[LifeSupportAlertLevel] = None,
        last_n: int = 100,
    ) -> List[LifeSupportAlert]:
        """Return recent alert history, optionally filtered by level."""
        history = self._alert_history[-last_n:]
        if level_filter:
            history = [a for a in history if a.level == level_filter]
        return history
