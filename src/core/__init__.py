"""
Internet of Space Things (IoST) Core Module
Advanced Space Communication & Monitoring Platform
"""

__version__ = "1.0.0"
__author__ = "Internet of Space Things Team"
__license__ = "MIT"

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
    compute_eclipse_state,
    compute_j2_secular_rates,
    compute_power_budget_fraction,
    find_contact_windows,
    orbit_eclipse_fraction,
    propagate_j2,
    solar_panel_power_fraction,
)
from .satellite_manager import SatelliteManager
from .space_network import SpaceNetwork

__all__ = [
    "SpaceNetwork",
    "SatelliteManager",
    "MissionControl",
    "MissionResourceAllocator",
    "SubsystemState",
    "AllocationPlan",
    "PhaseTraceSample",
    # orbit dynamics
    "OrbitalElementsJ2",
    "EciState",
    "EclipseState",
    "EclipseType",
    "GroundStation",
    "ContactWindow",
    "propagate_j2",
    "compute_eclipse_state",
    "compute_j2_secular_rates",
    "solar_panel_power_fraction",
    "orbit_eclipse_fraction",
    "find_contact_windows",
    "compute_power_budget_fraction",
]
