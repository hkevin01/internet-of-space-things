"""
CubeSat Network Nodes for Internet of Space Things
Implements miniaturized satellites as active/passive sensors and network nodes
Based on Georgia Tech's IoST Architecture with programmable antennas and
reconfigurable transceivers
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class CubeSatSize(Enum):
    ONE_U = "1U"  # 10x10x10 cm
    TWO_U = "2U"  # 10x10x20 cm
    THREE_U = "3U"  # 10x10x30 cm
    SIX_U = "6U"  # 20x10x30 cm
    TWELVE_U = "12U"  # 20x20x30 cm


class AntennaType(Enum):
    PATCH = "patch"
    DIPOLE = "dipole"
    HELICAL = "helical"
    PARABOLIC = "parabolic"
    PHASED_ARRAY = "phased_array"
    PROGRAMMABLE = "programmable"


class CommunicationBand(Enum):
    VHF = {"name": "VHF", "freq": (30e6, 300e6), "wave": "1-10m"}
    UHF = {"name": "UHF", "freq": (300e6, 3e9), "wave": "10cm-1m"}
    L_BAND = {"name": "L-Band", "freq": (1e9, 2e9), "wave": "15-30cm"}
    S_BAND = {"name": "S-Band", "freq": (2e9, 4e9), "wave": "7.5-15cm"}
    C_BAND = {"name": "C-Band", "freq": (4e9, 8e9), "wave": "3.75-7.5cm"}
    X_BAND = {"name": "X-Band", "freq": (8e9, 12e9), "wave": "2.5-3.75cm"}
    KU_BAND = {"name": "Ku-Band", "freq": (12e9, 18e9), "wave": "1.67-2.5cm"}
    K_BAND = {"name": "K-Band", "freq": (18e9, 27e9), "wave": "1.11-1.67cm"}
    KA_BAND = {"name": "Ka-Band", "freq": (27e9, 40e9), "wave": "0.75-1.11cm"}
    MILLIMETER_WAVE = {
        "name": "mmWave", "freq": (30e9, 300e9), "wave": "1-10mm"
    }
    TERAHERTZ = {"name": "THz", "freq": (300e9, 3e12), "wave": "0.1-1mm"}
    OPTICAL = {"name": "Optical", "freq": (3e14, 3e15), "wave": "100nm-1μm"}


@dataclass
class ProgrammableAntenna:
    """Programmable antenna system for adaptive communication"""
    antenna_id: str
    antenna_type: AntennaType
    supported_bands: List[CommunicationBand]
    current_frequency: float = 2.4e9  # Hz
    current_polarization: str = "circular"
    beam_width: float = 30.0  # degrees
    gain: float = 10.0  # dBi
    efficiency: float = 0.85
    is_steerable: bool = True
    pointing_accuracy: float = 0.1  # degrees
    reconfiguration_time: float = 0.1  # seconds
    
    def __post_init__(self):
        # Validate frequency is within supported bands
        frequency_valid = False
        for band in self.supported_bands:
            freq_range = band.value["frequency_range"]
            if freq_range[0] <= self.current_frequency <= freq_range[1]:
                frequency_valid = True
                break
        
        if not frequency_valid and self.supported_bands:
            # Set to first supported band's center frequency
            first_band = self.supported_bands[0].value["frequency_range"]
            self.current_frequency = (first_band[0] + first_band[1]) / 2


@dataclass
class ReconfigurableTransceiver:
    """Software-defined radio transceiver for multiband communication"""
    transceiver_id: str
    supported_bands: List[CommunicationBand] = field(default_factory=list)
    current_band: Optional[CommunicationBand] = None
    data_rate: float = 1e6  # bps
    power_consumption: float = 5.0  # watts
    processing_power: float = 10.0  # GFLOPS
    memory_capacity: float = 8.0  # GB
    has_ai_processing: bool = True
    encryption_capability: bool = True
    adaptive_modulation: bool = True
    cognitive_radio: bool = True
    
    def configure_for_band(self, band: CommunicationBand) -> bool:
        """Reconfigure transceiver for specific frequency band"""
        if band not in self.supported_bands:
            logger.error(f"Band {band.name} not supported by transceiver")
            return False
        
        self.current_band = band
        
        # Adjust parameters based on frequency band
        mmwave_bands = [CommunicationBand.MILLIMETER_WAVE,
                        CommunicationBand.TERAHERTZ]
        if band in mmwave_bands:
            self.data_rate = 10e9  # Higher data rates for mmWave/THz
            self.power_consumption = 15.0  # Higher power consumption
        elif band == CommunicationBand.OPTICAL:
            self.data_rate = 100e9  # Extreme data rates for optical
            self.power_consumption = 20.0
        else:
            self.data_rate = 100e6  # Standard rates for lower bands
            self.power_consumption = 5.0
        
        logger.info(f"Transceiver reconfigured for {band.value['name']} band")
        return True


@dataclass
class CubeSatPayload:
    """Scientific and sensor payload for CubeSat"""
    payload_id: str
    # Types: "remote_sensing", "communication", "scientific", "iot_gateway"
    payload_type: str
    sensors: List[str] = field(default_factory=list)
    data_collection_rate: float = 1.0  # Hz
    storage_capacity: float = 1.0  # GB
    processing_capability: str = "edge"  # "edge", "cloud", "hybrid"
    ai_models: List[str] = field(default_factory=list)
    power_requirements: float = 2.0  # watts
    mass: float = 0.5  # kg
    
    def collect_sensor_data(self, duration: float) -> Dict[str, Any]:
        """Simulate sensor data collection"""
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "payload_id": self.payload_id,
            "duration": duration,
            "sensors": {}
        }
        
        for sensor in self.sensors:
            if sensor == "earth_observation":
                collected_data["sensors"][sensor] = {
                    "images_captured": int(
                        duration * self.data_collection_rate
                    ),
                    "resolution": "3m/pixel",
                    "spectral_bands": ["RGB", "NIR", "SWIR"],
                    "coverage_area": duration * 100  # km²
                }
            elif sensor == "atmospheric":
                collected_data["sensors"][sensor] = {
                    "temperature": np.random.normal(250, 30),  # K
                    "pressure": np.random.lognormal(0, 1),
                    "humidity": np.random.uniform(0, 100),
                    "co2_concentration": np.random.normal(410, 10)  # ppm
                }
            elif sensor == "iot_relay":
                collected_data["sensors"][sensor] = {
                    "devices_connected": np.random.randint(10, 1000),
                    "messages_relayed": int(duration * 50),
                    "signal_quality": np.random.uniform(0.7, 1.0)
                }
        
        return collected_data


class CubeSat:
    """
    Advanced CubeSat implementation with IoST capabilities
    Supports programmable antennas, multiband communication, and onboard AI
    """
    
    def __init__(self, cubesat_id: str, name: str, size: CubeSatSize,
                 orbit_altitude: float = 550):  # km
        self.cubesat_id = cubesat_id
        self.name = name
        self.size = size
        self.orbit_altitude = orbit_altitude
        
        # Physical characteristics based on size
        self.mass = self._calculate_mass()
        self.power_generation = self._calculate_power_generation()
        self.volume = self._calculate_volume()
        
        # Communication systems
        self.antennas: List[ProgrammableAntenna] = []
        self.transceivers: List[ReconfigurableTransceiver] = []
        self.current_communication_mode = "autonomous"
        
        # Payload systems
        self.payload: Optional[CubeSatPayload] = None
        
        # Network capabilities
        self.network_role = "node"  # "node", "gateway", "relay", "sink"
        self.routing_table: Dict[str, str] = {}
        self.neighbor_discovery_enabled = True
        self.mesh_networking_enabled = True
        
        # SDN/NFV capabilities
        self.virtual_functions: List[str] = []
        self.service_chains: List[Dict[str, Any]] = []
        self.network_slices: Dict[str, Dict[str, Any]] = {}
        
        # AI/Edge processing
        self.onboard_ai_enabled = True
        self.processing_queue: List[Dict[str, Any]] = []
        self.ml_models: Dict[str, Any] = {}
        
        # Status and health
        self.is_operational = True
        self.health_score = 1.0
        self.last_contact = datetime.utcnow()
        self.total_data_collected = 0.0  # GB
        self.total_messages_relayed = 0
        
        logger.info(f"CubeSat {name} ({size.value}) initialized")
    
    def add_programmable_antenna(self, antenna_config: Dict[str, Any]) -> bool:
        """Add programmable antenna to CubeSat"""
        try:
            antenna = ProgrammableAntenna(
                antenna_id=antenna_config["id"],
                antenna_type=AntennaType(antenna_config["type"]),
                supported_bands=[
                    CommunicationBand(band) for band in antenna_config["bands"]
                ],
                current_frequency=antenna_config.get("frequency", 2.4e9),
                gain=antenna_config.get("gain", 10.0),
                is_steerable=antenna_config.get("steerable", True)
            )
            
            self.antennas.append(antenna)
            ant_type = antenna.antenna_type.value
            logger.info(f"Added {ant_type} antenna to {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add antenna: {e}")
            return False
    
    def add_reconfigurable_transceiver(
            self, transceiver_config: Dict[str, Any]
    ) -> bool:
        """Add software-defined radio transceiver"""
        try:
            transceiver = ReconfigurableTransceiver(
                transceiver_id=transceiver_config["id"],
                supported_bands=[
                    CommunicationBand(band) 
                    for band in transceiver_config["bands"]
                ],
                has_ai_processing=transceiver_config.get(
                    "ai_processing", True
                ),
                cognitive_radio=transceiver_config.get("cognitive_radio", True)
            )
            
            if transceiver.supported_bands:
                transceiver.configure_for_band(transceiver.supported_bands[0])
            
            self.transceivers.append(transceiver)
            logger.info(f"Added SDR transceiver to {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add transceiver: {e}")
            return False
    
    def set_payload(self, payload_config: Dict[str, Any]) -> bool:
        """Configure CubeSat payload"""
        try:
            self.payload = CubeSatPayload(
                payload_id=payload_config["id"],
                payload_type=payload_config["type"],
                sensors=payload_config.get("sensors", []),
                ai_models=payload_config.get("ai_models", []),
                processing_capability=payload_config.get("processing", "edge")
            )
            
            logger.info(f"Configured {self.payload.payload_type} payload for {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure payload: {e}")
            return False
    
    async def adaptive_communication(self, target_cubesat: str, 
                                   environment_conditions: Dict[str, Any]) -> bool:
        """Implement adaptive communication based on environment"""
        if not self.transceivers:
            return False
        
        # Analyze environment conditions
        weather = environment_conditions.get("weather", "clear")
        atmospheric_loss = environment_conditions.get("atmospheric_loss", 0.1)
        interference_level = environment_conditions.get("interference", 0.05)
        distance_km = environment_conditions.get("distance", 1000)
        
        # Select optimal communication band
        optimal_band = None
        best_score = 0
        
        for transceiver in self.transceivers:
            for band in transceiver.supported_bands:
                score = self._calculate_band_suitability(
                    band, weather, atmospheric_loss, interference_level, distance_km
                )
                if score > best_score:
                    best_score = score
                    optimal_band = band
                    best_transceiver = transceiver
        
        if optimal_band:
            # Reconfigure transceiver
            success = best_transceiver.configure_for_band(optimal_band)
            if success:
                # Configure matching antenna
                await self._configure_antenna_for_band(optimal_band)
                logger.info(f"Adapted communication to {optimal_band.value['name']} for {target_cubesat}")
                return True
        
        return False
    
    async def enable_mesh_networking(self, neighbors: List[str]) -> bool:
        """Enable mesh networking with neighbor CubeSats"""
        if not self.mesh_networking_enabled:
            return False
        
        # Update routing table for mesh network
        for neighbor in neighbors:
            self.routing_table[neighbor] = neighbor  # Direct connection
        
        # Enable neighbor discovery
        if self.neighbor_discovery_enabled:
            await self._discover_neighbors()
        
        logger.info(f"Mesh networking enabled with {len(neighbors)} neighbors")
        return True
    
    async def create_network_slice(self, slice_id: str, 
                                 requirements: Dict[str, Any]) -> bool:
        """Create virtual network slice for specific service"""
        try:
            network_slice = {
                "slice_id": slice_id,
                "bandwidth_requirement": requirements.get("bandwidth", 1e6),  # bps
                "latency_requirement": requirements.get("latency", 100),  # ms
                "reliability_requirement": requirements.get("reliability", 0.99),
                "service_type": requirements.get("service_type", "best_effort"),
                "created_at": datetime.utcnow(),
                "active": True
            }
            
            self.network_slices[slice_id] = network_slice
            
            # Configure virtual network function
            await self._deploy_vnf_for_slice(slice_id, requirements)
            
            logger.info(f"Created network slice {slice_id} on {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create network slice: {e}")
            return False
    
    async def process_data_with_ai(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process collected data using onboard AI"""
        if not self.onboard_ai_enabled or not self.payload:
            return data
        
        processed_data = data.copy()
        
        # Simulate AI processing based on payload type
        if self.payload.payload_type == "remote_sensing":
            processed_data["ai_analysis"] = {
                "cloud_coverage": np.random.uniform(0, 100),
                "land_classification": ["urban", "forest", "water", "agriculture"],
                "anomaly_detection": np.random.choice([True, False], p=[0.1, 0.9]),
                "processing_confidence": np.random.uniform(0.8, 1.0)
            }
        elif self.payload.payload_type == "iot_gateway":
            processed_data["ai_analysis"] = {
                "traffic_patterns": "normal",
                "device_health_prediction": np.random.uniform(0.7, 1.0),
                "optimal_routing": self._calculate_optimal_routing(),
                "bandwidth_prediction": np.random.uniform(0.5, 2.0)
            }
        
        # Add processing metadata
        processed_data["processing_info"] = {
            "processed_by": self.cubesat_id,
            "processing_time": datetime.utcnow().isoformat(),
            "ai_models_used": self.payload.ai_models,
            "edge_processing": True
        }
        
        self.total_data_collected += len(json.dumps(processed_data)) / (1024**3)  # GB
        
        return processed_data
    
    async def relay_iot_data(self, source_device: str, destination: str, 
                           data: Dict[str, Any]) -> bool:
        """Relay IoT data from terrestrial devices"""
        try:
            # Add relay metadata
            relay_info = {
                "relayed_by": self.cubesat_id,
                "relay_time": datetime.utcnow().isoformat(),
                "source": source_device,
                "destination": destination,
                "hop_count": data.get("hop_count", 0) + 1
            }
            
            data["relay_info"] = relay_info
            
            # Route through network
            next_hop = self.routing_table.get(destination, destination)
            
            # Simulate transmission
            await asyncio.sleep(0.1)  # Transmission delay
            
            self.total_messages_relayed += 1
            logger.debug(f"Relayed IoT data from {source_device} to {destination}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to relay IoT data: {e}")
            return False
    
    def get_cubesat_status(self) -> Dict[str, Any]:
        """Get comprehensive CubeSat status"""
        return {
            "cubesat_id": self.cubesat_id,
            "name": self.name,
            "size": self.size.value,
            "orbit_altitude": self.orbit_altitude,
            "mass": self.mass,
            "power_generation": self.power_generation,
            "is_operational": self.is_operational,
            "health_score": self.health_score,
            "network_role": self.network_role,
            "antennas": len(self.antennas),
            "transceivers": len(self.transceivers),
            "payload_type": self.payload.payload_type if self.payload else None,
            "mesh_networking": self.mesh_networking_enabled,
            "ai_processing": self.onboard_ai_enabled,
            "network_slices": len(self.network_slices),
            "total_data_collected_gb": self.total_data_collected,
            "messages_relayed": self.total_messages_relayed,
            "last_contact": self.last_contact.isoformat()
        }
    
    def _calculate_mass(self) -> float:
        """Calculate CubeSat mass based on size"""
        base_masses = {
            CubeSatSize.ONE_U: 1.33,    # kg
            CubeSatSize.TWO_U: 2.66,
            CubeSatSize.THREE_U: 4.0,
            CubeSatSize.SIX_U: 8.0,
            CubeSatSize.TWELVE_U: 16.0
        }
        return base_masses.get(self.size, 4.0)
    
    def _calculate_power_generation(self) -> float:
        """Calculate solar panel power generation"""
        base_power = {
            CubeSatSize.ONE_U: 2.0,     # watts
            CubeSatSize.TWO_U: 4.0,
            CubeSatSize.THREE_U: 8.0,
            CubeSatSize.SIX_U: 15.0,
            CubeSatSize.TWELVE_U: 30.0
        }
        return base_power.get(self.size, 8.0)
    
    def _calculate_volume(self) -> float:
        """Calculate CubeSat volume in liters"""
        volumes = {
            CubeSatSize.ONE_U: 1.0,     # liters
            CubeSatSize.TWO_U: 2.0,
            CubeSatSize.THREE_U: 3.0,
            CubeSatSize.SIX_U: 6.0,
            CubeSatSize.TWELVE_U: 12.0
        }
        return volumes.get(self.size, 3.0)
    
    def _calculate_band_suitability(self, band: CommunicationBand, weather: str,
                                  atmospheric_loss: float, interference: float,
                                  distance: float) -> float:
        """Calculate suitability score for communication band"""
        base_score = 1.0
        
        # Weather effects
        if weather == "rain" and band in [CommunicationBand.KA_BAND, CommunicationBand.MILLIMETER_WAVE]:
            base_score *= 0.5  # Rain fade
        elif weather == "storm" and band == CommunicationBand.OPTICAL:
            base_score *= 0.1  # Optical blocked by clouds
        
        # Distance effects
        if distance > 2000 and band in [CommunicationBand.TERAHERTZ, CommunicationBand.OPTICAL]:
            base_score *= 0.3  # High frequency attenuation
        elif distance < 500 and band in [CommunicationBand.VHF, CommunicationBand.UHF]:
            base_score *= 1.2  # Good for short range
        
        # Interference effects
        if band in [CubeSatSize.S_BAND, CommunicationBand.C_BAND]:
            base_score *= (1.0 - interference)
        
        return max(0.1, min(1.0, base_score))
    
    async def _configure_antenna_for_band(self, band: CommunicationBand) -> bool:
        """Configure antenna for specific frequency band"""
        for antenna in self.antennas:
            if band in antenna.supported_bands:
                freq_range = band.value["frequency_range"]
                antenna.current_frequency = (freq_range[0] + freq_range[1]) / 2
                await asyncio.sleep(antenna.reconfiguration_time)
                return True
        return False
    
    async def _discover_neighbors(self) -> List[str]:
        """Discover neighboring CubeSats for mesh networking"""
        # Simulate neighbor discovery
        await asyncio.sleep(1.0)
        
        # In real implementation, this would use radio beacon scanning
        discovered_neighbors = []
        num_neighbors = np.random.randint(2, 8)
        
        for i in range(num_neighbors):
            neighbor_id = f"CUBESAT-{np.random.randint(1000, 9999)}"
            discovered_neighbors.append(neighbor_id)
            self.routing_table[neighbor_id] = neighbor_id
        
        return discovered_neighbors
    
    async def _deploy_vnf_for_slice(self, slice_id: str, requirements: Dict[str, Any]):
        """Deploy Virtual Network Function for network slice"""
        service_type = requirements.get("service_type", "best_effort")
        
        vnf_config = {
            "vnf_id": f"vnf_{slice_id}",
            "function_type": service_type,
            "resources_allocated": {
                "cpu": requirements.get("cpu_cores", 1),
                "memory": requirements.get("memory_mb", 256),
                "bandwidth": requirements.get("bandwidth", 1e6)
            },
            "deployed_at": datetime.utcnow()
        }
        
        self.virtual_functions.append(vnf_config)
    
    def _calculate_optimal_routing(self) -> Dict[str, str]:
        """Calculate optimal routing for current network topology"""
        # Simplified routing calculation
        optimal_routes = {}
        
        for destination in self.routing_table:
            # In real implementation, this would use shortest path algorithms
            optimal_routes[destination] = self.routing_table[destination]
        
        return optimal_routes
