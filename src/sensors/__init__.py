"""
src/sensors/__init__.py - Sensor subsystem package exports
ID: SEN-000
Purpose: Expose all sensor fusion, navigation, and life support classes
         from the sensors package for convenient importing.
"""

from src.sensors.environmental.sensor_fusion import (
    EnvironmentalSensorFusion,
    FusedEnvironmentalState,
    FusedChannelEstimate,
    RawSensorReading,
    EnvironmentalChannel,
    SensorStatus,
)
from src.sensors.navigation.nav_sensor_integration import (
    NavigationSensorIntegration,
    NavigationState,
    StarTrackerReading,
    IMUReading,
    GPSReading,
)
from src.sensors.life_support.life_support_monitor import (
    LifeSupportMonitor,
    LifeSupportState,
    LifeSupportAlert,
    LifeSupportAlertLevel,
    SafetyLimits,
    ECLSSCommand,
)

__all__ = [
    # Environmental
    "EnvironmentalSensorFusion",
    "FusedEnvironmentalState",
    "FusedChannelEstimate",
    "RawSensorReading",
    "EnvironmentalChannel",
    "SensorStatus",
    # Navigation
    "NavigationSensorIntegration",
    "NavigationState",
    "StarTrackerReading",
    "IMUReading",
    "GPSReading",
    # Life support
    "LifeSupportMonitor",
    "LifeSupportState",
    "LifeSupportAlert",
    "LifeSupportAlertLevel",
    "SafetyLimits",
    "ECLSSCommand",
]
