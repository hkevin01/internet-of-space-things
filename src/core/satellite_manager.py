"""
Satellite Manager - Manages individual satellites and spacecraft in the constellation
Handles orbital mechanics, attitude control, and system health monitoring
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class SatelliteStatus(Enum):
    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"
    OFFLINE = "offline"


class OrbitType(Enum):
    LEO = "low_earth_orbit"      # < 2000 km
    MEO = "medium_earth_orbit"   # 2000-35786 km  
    GEO = "geostationary_orbit"  # 35786 km
    DEEP_SPACE = "deep_space"    # Beyond Earth orbit


@dataclass
class SatelliteConfiguration:
    """Configuration parameters for a satellite"""
    satellite_id: str
    name: str
    satellite_type: str  # "communications", "earth_observation", "navigation", "scientific"
    orbit_type: OrbitType
    mass: float  # kg
    power_capacity: float  # Watts
    fuel_capacity: float  # kg
    communication_frequency: float  # Hz
    sensor_types: List[str] = field(default_factory=list)
    max_data_rate: float = 100.0  # Mbps


@dataclass
class OrbitalElements:
    """Keplerian orbital elements"""
    semi_major_axis: float  # km
    eccentricity: float
    inclination: float  # degrees
    longitude_of_ascending_node: float  # degrees
    argument_of_periapsis: float  # degrees
    true_anomaly: float  # degrees
    epoch: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SatelliteState:
    """Current state of a satellite"""
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))  # km
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))  # km/s
    attitude: np.ndarray = field(default_factory=lambda: np.zeros(3))  # euler angles (deg)
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))  # deg/s
    power_level: float = 100.0  # percentage
    fuel_remaining: float = 100.0  # percentage
    temperature: float = 20.0  # Celsius
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SatelliteHealthMetrics:
    """Health and performance metrics"""
    cpu_usage: float = 0.0  # percentage
    memory_usage: float = 0.0  # percentage
    disk_usage: float = 0.0  # percentage
    communication_status: str = "nominal"
    sensor_status: Dict[str, str] = field(default_factory=dict)
    last_health_check: datetime = field(default_factory=datetime.utcnow)
    anomaly_score: float = 0.0  # 0-1, higher indicates problems


class Satellite:
    """Individual satellite/spacecraft management"""
    
    def __init__(self, config: SatelliteConfiguration, 
                 orbital_elements: OrbitalElements):
        self.config = config
        self.orbital_elements = orbital_elements
        self.state = SatelliteState()
        self.health = SatelliteHealthMetrics()
        self.status = SatelliteStatus.OPERATIONAL
        
        # Mission parameters
        self.mission_start_time = datetime.utcnow()
        self.total_operation_time = timedelta()
        self.data_collected = 0.0  # GB
        self.commands_executed = 0
        
        # Autonomous systems
        self.autonomous_mode = True
        self.emergency_protocols_active = False
        
        logger.info(f"Satellite {config.name} ({config.satellite_id}) initialized")
    
    async def update_orbital_position(self, current_time: Optional[datetime] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Update satellite position and velocity using orbital mechanics"""
        if current_time is None:
            current_time = datetime.utcnow()
        
        # Time since epoch in seconds
        dt = (current_time - self.orbital_elements.epoch).total_seconds()
        
        # Simplified orbital propagation (Kepler's laws)
        # In reality, this would use SGP4/SDP4 or other precise models
        
        # Earth gravitational parameter (km³/s²)
        mu = 398600.4418
        
        # Calculate mean motion
        a = self.orbital_elements.semi_major_axis
        n = np.sqrt(mu / (a ** 3))  # rad/s
        
        # Mean anomaly
        M0 = np.radians(self.orbital_elements.true_anomaly)  # Initial mean anomaly
        M = M0 + n * dt
        
        # Solve Kepler's equation for eccentric anomaly (simplified)
        e = self.orbital_elements.eccentricity
        E = M + e * np.sin(M)  # First-order approximation
        
        # True anomaly
        nu = 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E/2), np.sqrt(1 - e) * np.cos(E/2))
        
        # Distance from Earth center
        r = a * (1 - e * np.cos(E))
        
        # Position in orbital plane
        x_orbital = r * np.cos(nu)
        y_orbital = r * np.sin(nu)
        
        # Velocity in orbital plane
        h = np.sqrt(mu * a * (1 - e**2))  # Specific angular momentum
        vx_orbital = -mu / h * np.sin(nu)
        vy_orbital = mu / h * (e + np.cos(nu))
        
        # Transform to Earth-centered inertial coordinates
        # Apply inclination, longitude of ascending node, and argument of periapsis
        i = np.radians(self.orbital_elements.inclination)
        omega = np.radians(self.orbital_elements.longitude_of_ascending_node)
        w = np.radians(self.orbital_elements.argument_of_periapsis)
        
        # Rotation matrices
        cos_omega, sin_omega = np.cos(omega), np.sin(omega)
        cos_i, sin_i = np.cos(i), np.sin(i)
        cos_w, sin_w = np.cos(w), np.sin(w)
        
        # Position transformation
        position = np.array([
            (cos_omega * cos_w - sin_omega * sin_w * cos_i) * x_orbital + 
            (-cos_omega * sin_w - sin_omega * cos_w * cos_i) * y_orbital,
            
            (sin_omega * cos_w + cos_omega * sin_w * cos_i) * x_orbital + 
            (-sin_omega * sin_w + cos_omega * cos_w * cos_i) * y_orbital,
            
            sin_w * sin_i * x_orbital + cos_w * sin_i * y_orbital
        ])
        
        # Velocity transformation
        velocity = np.array([
            (cos_omega * cos_w - sin_omega * sin_w * cos_i) * vx_orbital + 
            (-cos_omega * sin_w - sin_omega * cos_w * cos_i) * vy_orbital,
            
            (sin_omega * cos_w + cos_omega * sin_w * cos_i) * vx_orbital + 
            (-sin_omega * sin_w + cos_omega * cos_w * cos_i) * vy_orbital,
            
            sin_w * sin_i * vx_orbital + cos_w * sin_i * vy_orbital
        ])
        
        # Update state
        self.state.position = position
        self.state.velocity = velocity
        self.state.last_updated = current_time
        
        return position, velocity
    
    async def execute_maneuver(self, delta_v: np.ndarray, burn_duration: float) -> bool:
        """Execute orbital maneuver with given delta-V"""
        try:
            # Check fuel availability
            fuel_required = np.linalg.norm(delta_v) * self.config.mass * 0.001  # Simplified
            fuel_percentage = (fuel_required / self.config.fuel_capacity) * 100
            
            if fuel_percentage > self.state.fuel_remaining:
                logger.error(f"Insufficient fuel for maneuver: {fuel_percentage:.1f}% required")
                return False
            
            # Apply velocity change
            self.state.velocity += delta_v
            self.state.fuel_remaining -= fuel_percentage
            
            # Update orbital elements based on new velocity
            await self._update_orbital_elements_from_state()
            
            self.commands_executed += 1
            logger.info(f"Executed maneuver: ΔV={np.linalg.norm(delta_v):.3f} km/s")
            return True
            
        except Exception as e:
            logger.error(f"Maneuver execution failed: {e}")
            return False
    
    async def collect_sensor_data(self, sensor_type: str, duration: float) -> Dict[str, Any]:
        """Simulate sensor data collection"""
        if sensor_type not in self.config.sensor_types:
            logger.warning(f"Sensor type {sensor_type} not available on satellite")
            return {}
        
        # Simulate data collection based on sensor type
        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "satellite_id": self.config.satellite_id,
            "sensor_type": sensor_type,
            "duration": duration,
            "position": self.state.position.tolist(),
            "orbit_type": self.config.orbit_type.value
        }
        
        # Add sensor-specific data
        if sensor_type == "earth_observation":
            data.update({
                "image_count": int(duration * 2),  # 2 images per second
                "resolution": "10m",
                "spectral_bands": ["red", "green", "blue", "nir"],
                "cloud_coverage": np.random.uniform(0, 100)
            })
        elif sensor_type == "atmospheric":
            data.update({
                "temperature": np.random.normal(250, 50),  # Kelvin
                "pressure": np.random.lognormal(0, 1),
                "humidity": np.random.uniform(0, 100),
                "co2_concentration": np.random.normal(410, 10)  # ppm
            })
        elif sensor_type == "radiation":
            data.update({
                "dose_rate": np.random.exponential(0.1),  # mSv/hour
                "particle_count": np.random.poisson(1000),
                "energy_spectrum": np.random.exponential(1, 50).tolist()
            })
        
        # Update statistics
        data_size = len(json.dumps(data).encode()) / (1024 * 1024 * 1024)  # GB
        self.data_collected += data_size
        
        logger.info(f"Collected {sensor_type} data for {duration}s")
        return data
    
    async def monitor_health(self) -> SatelliteHealthMetrics:
        """Monitor satellite health and update metrics"""
        # Simulate health monitoring
        self.health.cpu_usage = np.random.normal(30, 10)
        self.health.memory_usage = np.random.normal(40, 15)
        self.health.disk_usage = min(self.health.disk_usage + np.random.uniform(0, 0.1), 95)
        
        # Check communication status
        if self.state.power_level < 20:
            self.health.communication_status = "degraded"
        elif self.state.power_level < 10:
            self.health.communication_status = "critical"
        else:
            self.health.communication_status = "nominal"
        
        # Update sensor status
        for sensor in self.config.sensor_types:
            # Simulate sensor health with small failure probability
            if np.random.random() < 0.01:  # 1% chance of sensor issue
                self.health.sensor_status[sensor] = "degraded"
            else:
                self.health.sensor_status[sensor] = "nominal"
        
        # Calculate anomaly score based on various factors
        factors = [
            max(0, (self.health.cpu_usage - 80) / 20),  # High CPU usage
            max(0, (self.health.memory_usage - 90) / 10),  # High memory usage
            max(0, (100 - self.state.power_level) / 100),  # Low power
            max(0, (100 - self.state.fuel_remaining) / 100),  # Low fuel
        ]
        self.health.anomaly_score = min(1.0, np.mean(factors))
        
        # Update status based on health
        if self.health.anomaly_score > 0.8:
            self.status = SatelliteStatus.EMERGENCY
        elif self.health.anomaly_score > 0.6:
            self.status = SatelliteStatus.DEGRADED
        elif self.health.anomaly_score > 0.3:
            self.status = SatelliteStatus.MAINTENANCE
        else:
            self.status = SatelliteStatus.OPERATIONAL
        
        self.health.last_health_check = datetime.utcnow()
        return self.health
    
    async def enter_safe_mode(self, reason: str):
        """Enter safe mode to preserve satellite"""
        logger.warning(f"Satellite {self.config.name} entering safe mode: {reason}")
        
        self.autonomous_mode = False
        self.emergency_protocols_active = True
        self.status = SatelliteStatus.EMERGENCY
        
        # Minimize power consumption
        self.state.power_level = max(20, self.state.power_level * 0.5)
        
        # Orient solar panels toward sun (simplified)
        self.state.attitude = np.array([0, 0, 0])  # Sun-pointing attitude
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get current telemetry data"""
        return {
            "satellite_id": self.config.satellite_id,
            "name": self.config.name,
            "timestamp": datetime.utcnow().isoformat(),
            "status": self.status.value,
            "position": self.state.position.tolist(),
            "velocity": self.state.velocity.tolist(),
            "attitude": self.state.attitude.tolist(),
            "power_level": self.state.power_level,
            "fuel_remaining": self.state.fuel_remaining,
            "temperature": self.state.temperature,
            "health_metrics": {
                "cpu_usage": self.health.cpu_usage,
                "memory_usage": self.health.memory_usage,
                "communication_status": self.health.communication_status,
                "anomaly_score": self.health.anomaly_score
            },
            "mission_metrics": {
                "operation_time_hours": self.total_operation_time.total_seconds() / 3600,
                "data_collected_gb": self.data_collected,
                "commands_executed": self.commands_executed
            }
        }
    
    async def _update_orbital_elements_from_state(self):
        """Update orbital elements from current position and velocity"""
        # This is a complex calculation that would normally use specialized libraries
        # For now, we'll keep the existing orbital elements
        # In a real implementation, this would involve converting Cartesian state vectors
        # back to Keplerian elements
        pass


class SatelliteManager:
    """
    Manages constellation of satellites and spacecraft
    Handles orbital mechanics, coordination, and resource allocation
    """
    
    def __init__(self, constellation_name: str = "IoST-Constellation"):
        self.constellation_name = constellation_name
        self.satellites: Dict[str, Satellite] = {}
        self.constellation_status = "operational"
        self.ground_contact_windows: Dict[str, List[Tuple[datetime, datetime]]] = {}
        
        # Configuration
        self.update_interval = 60  # seconds
        self.health_check_interval = 300  # seconds
        
        logger.info(f"Satellite Manager '{constellation_name}' initialized")
    
    async def add_satellite(self, config: SatelliteConfiguration, 
                          orbital_elements: OrbitalElements) -> bool:
        """Add new satellite to constellation"""
        try:
            if config.satellite_id in self.satellites:
                logger.warning(f"Satellite {config.satellite_id} already in constellation")
                return False
            
            satellite = Satellite(config, orbital_elements)
            self.satellites[config.satellite_id] = satellite
            
            # Initialize orbital position
            await satellite.update_orbital_position()
            
            logger.info(f"Added satellite {config.name} to constellation")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add satellite {config.satellite_id}: {e}")
            return False
    
    async def update_constellation(self, current_time: Optional[datetime] = None):
        """Update all satellites in constellation"""
        if current_time is None:
            current_time = datetime.utcnow()
        
        update_tasks = []
        for satellite in self.satellites.values():
            update_tasks.append(satellite.update_orbital_position(current_time))
        
        # Update all satellites concurrently
        await asyncio.gather(*update_tasks, return_exceptions=True)
    
    async def coordinate_maneuvers(self, maneuver_plan: Dict[str, Dict]) -> Dict[str, bool]:
        """Coordinate multiple satellite maneuvers"""
        results = {}
        
        for satellite_id, maneuver_data in maneuver_plan.items():
            if satellite_id in self.satellites:
                satellite = self.satellites[satellite_id]
                delta_v = np.array(maneuver_data.get("delta_v", [0, 0, 0]))
                burn_duration = maneuver_data.get("burn_duration", 0)
                
                result = await satellite.execute_maneuver(delta_v, burn_duration)
                results[satellite_id] = result
            else:
                results[satellite_id] = False
        
        return results
    
    async def monitor_constellation_health(self) -> Dict[str, Any]:
        """Monitor health of entire constellation"""
        health_tasks = []
        for satellite in self.satellites.values():
            health_tasks.append(satellite.monitor_health())
        
        health_reports = await asyncio.gather(*health_tasks, return_exceptions=True)
        
        # Aggregate health metrics
        operational_count = sum(1 for s in self.satellites.values() 
                              if s.status == SatelliteStatus.OPERATIONAL)
        total_satellites = len(self.satellites)
        
        avg_anomaly_score = np.mean([s.health.anomaly_score for s in self.satellites.values()]) if self.satellites else 0
        
        # Update constellation status
        if avg_anomaly_score > 0.7:
            self.constellation_status = "critical"
        elif avg_anomaly_score > 0.4:
            self.constellation_status = "degraded"
        else:
            self.constellation_status = "operational"
        
        return {
            "constellation_name": self.constellation_name,
            "status": self.constellation_status,
            "total_satellites": total_satellites,
            "operational_satellites": operational_count,
            "availability": operational_count / total_satellites if total_satellites > 0 else 0,
            "avg_anomaly_score": avg_anomaly_score,
            "individual_health": {sat_id: sat.health for sat_id, sat in self.satellites.items()}
        }
    
    def get_constellation_telemetry(self) -> Dict[str, Any]:
        """Get telemetry from all satellites"""
        return {
            "constellation_name": self.constellation_name,
            "timestamp": datetime.utcnow().isoformat(),
            "satellites": {sat_id: sat.get_telemetry() for sat_id, sat in self.satellites.items()}
        }
