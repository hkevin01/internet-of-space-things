"""
Internet of Space Things (IoST) Core Module
Advanced Space Communication & Monitoring Platform
"""

__version__ = "1.0.0"
__author__ = "Internet of Space Things Team"
__license__ = "MIT"

from .battery_model import (
    BatteryConfig,
    BatteryOrbitTrace,
    BatteryStepState,
    SolarConfig,
    eclipse_aware_power_budget,
    propagate_battery_soc,
    soc_at_time,
)
from .constellation_scheduler import (
    ConstellationSat,
    ConstellationSchedule,
    ScheduleEntry,
    ScheduleEntryType,
    build_constellation_schedule,
)
from .mission_control import MissionControl
from .mission_resource_allocator import (
    AllocationPlan,
    MissionResourceAllocator,
    PhaseTraceSample,
    SubsystemState,
)
from .orbit_dynamics import (
    ContactWindow,
    EciState,
    EclipseState,
    EclipseType,
    GroundStation,
    OrbitalElementsJ2,
    RAANPhasingPlan,
    RadiationDoseState,
    StationKeepingBudget,
    check_isl_visibility,
    compute_eclipse_state,
    compute_isl_link_budget,
    compute_j2_secular_rates,
    compute_power_budget_fraction,
    compute_radiation_dose,
    compute_raan_phasing_plan,
    compute_station_keeping_budget,
    find_contact_windows,
    orbit_eclipse_fraction,
    panel_degradation_from_dose,
    propagate_j2,
    solar_panel_power_fraction,
)
from .data_volume_model import (
    BufferStep,
    DataVolumeState,
    InstrumentProfile,
    buffer_fill_fractions_from_simulation,
    simulate_constellation_data_volume,
    simulate_data_volume,
)
from .fault_tree import (
    BasicEvent,
    FaultGate,
    FaultTreeDefinition,
    FaultTreeResult,
    FMEAEntry,
    GateType,
    RiskLevel,
    SubsystemHealthInput,
    analyze_fault_tree,
    default_mission_fault_tree,
)
from .satellite_manager import SatelliteManager
from .space_network import SpaceNetwork
from .thermal_model import (
    FaceThermalState,
    SpacecraftGeometry,
    SpacecraftThermalState,
    compute_thermal_demand_fraction,
    compute_thermal_state,
    default_cubesat_geometry,
)

__all__ = [
    "SpaceNetwork",
    "SatelliteManager",
    "MissionControl",
    "MissionResourceAllocator",
    "SubsystemState",
    "AllocationPlan",
    "PhaseTraceSample",
    # battery model
    "SolarConfig",
    "BatteryConfig",
    "BatteryOrbitTrace",
    "BatteryStepState",
    "propagate_battery_soc",
    "soc_at_time",
    "eclipse_aware_power_budget",
    # orbit dynamics
    "OrbitalElementsJ2",
    "EciState",
    "EclipseState",
    "EclipseType",
    "GroundStation",
    "ContactWindow",
    "RadiationDoseState",
    "StationKeepingBudget",
    "RAANPhasingPlan",
    "propagate_j2",
    "compute_eclipse_state",
    "compute_j2_secular_rates",
    "solar_panel_power_fraction",
    "orbit_eclipse_fraction",
    "find_contact_windows",
    "compute_power_budget_fraction",
    "compute_radiation_dose",
    "panel_degradation_from_dose",
    "compute_station_keeping_budget",
    "compute_raan_phasing_plan",
    "check_isl_visibility",
    "compute_isl_link_budget",
    # constellation scheduler
    "ConstellationSat",
    "ConstellationSchedule",
    "ScheduleEntry",
    "ScheduleEntryType",
    "build_constellation_schedule",
    # data volume model
    "InstrumentProfile",
    "DataVolumeState",
    "BufferStep",
    "simulate_data_volume",
    "simulate_constellation_data_volume",
    "buffer_fill_fractions_from_simulation",
    # fault tree
    "SubsystemHealthInput",
    "BasicEvent",
    "FaultGate",
    "FaultTreeDefinition",
    "FaultTreeResult",
    "FMEAEntry",
    "GateType",
    "RiskLevel",
    "analyze_fault_tree",
    "default_mission_fault_tree",
    # thermal model
    "SpacecraftGeometry",
    "FaceThermalState",
    "SpacecraftThermalState",
    "default_cubesat_geometry",
    "compute_thermal_state",
    "compute_thermal_demand_fraction",
]

