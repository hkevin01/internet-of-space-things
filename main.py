#!/usr/bin/env python3
"""
Internet of Space Things (IoST) - Enhanced Main Application
Advanced space-based IoT platform with CubeSat constellation, SDN, and multiband communication
Implements Georgia Tech's IoST architecture with programmable antennas and reconfigurable transceivers
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from communication.multiband_radio import FrequencyBand, MultibandRadio
from communication.protocols.deep_space_protocol import DeepSpaceProtocol
from core.mission_control import MissionControl
from core.satellite_manager import Satellite, SatelliteManager
from core.space_network import SpaceNetwork

# New IoST components
from cubesat.cubesat_network import CommunicationBand, CubeSat, CubeSatSize
from cubesat.sdn_controller import NetworkSliceType, SDNController
from sensors.environmental.radiation_detector import RadiationDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('iosct.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class EnhancedIoSPlatform:
    """Enhanced Internet of Space Things platform with IoST capabilities"""
    
    def __init__(self):
        """Initialize the enhanced IoST platform"""
        # Legacy components
        self.space_network = SpaceNetwork("MAIN_NETWORK")
        self.satellite_manager = SatelliteManager()
        self.mission_control = MissionControl("MISSION_CONTROL_001")
        self.protocol = DeepSpaceProtocol()
        
        # New IoST components
        self.sdn_controller = SDNController("SDN_CONTROLLER_001")
        self.cubesat_constellation: Dict[str, CubeSat] = {}
        self.multiband_radios: Dict[str, MultibandRadio] = {}
        
        # Environmental sensors
        self.radiation_detector = RadiationDetector("RAD_001")
        
        self.running = False
        
        logger.info("Enhanced IoST Platform initialized with SDN and multiband communication")
    
    async def initialize_cubesat_constellation(self):
        """Initialize the CubeSat constellation with IoST capabilities"""
        logger.info("Initializing IoST CubeSat constellation...")
        
        # Define CubeSat configurations
        cubesat_configs = [
            {
                "id": "CUBESAT-COMMAND-001",
                "name": "IoST Command Node",
                "size": CubeSatSize.SIX_U,
                "altitude": 550,  # km
                "role": "gateway",
                "antennas": [
                    {
                        "id": "ant_cmd_1",
                        "type": "programmable",
                        "bands": ["S_BAND", "X_BAND", "KA_BAND"],
                        "frequency": 8.4e9,
                        "gain": 25.0,
                        "steerable": True
                    }
                ],
                "transceivers": [
                    {
                        "id": "sdr_cmd_1",
                        "bands": ["MICROWAVE", "MILLIMETER_WAVE"],
                        "ai_processing": True,
                        "cognitive_radio": True
                    }
                ],
                "payload": {
                    "id": "cmd_payload_1",
                    "type": "communication",
                    "sensors": ["iot_relay"],
                    "ai_models": ["routing_optimization", "interference_mitigation"]
                }
            },
            {
                "id": "CUBESAT-EARTH-OBS-001",
                "name": "IoST Earth Observation",
                "size": CubeSatSize.TWELVE_U,
                "altitude": 700,
                "role": "node",
                "antennas": [
                    {
                        "id": "ant_eo_1",
                        "type": "phased_array",
                        "bands": ["X_BAND", "KU_BAND"],
                        "frequency": 12e9,
                        "gain": 30.0,
                        "steerable": True
                    }
                ],
                "transceivers": [
                    {
                        "id": "sdr_eo_1",
                        "bands": ["MICROWAVE", "OPTICAL"],
                        "ai_processing": True,
                        "cognitive_radio": True
                    }
                ],
                "payload": {
                    "id": "eo_payload_1",
                    "type": "remote_sensing",
                    "sensors": ["earth_observation", "atmospheric"],
                    "ai_models": ["image_processing", "anomaly_detection"]
                }
            },
            {
                "id": "CUBESAT-IOT-GATEWAY-001", 
                "name": "IoST IoT Gateway",
                "size": CubeSatSize.THREE_U,
                "altitude": 450,
                "role": "relay",
                "antennas": [
                    {
                        "id": "ant_iot_1",
                        "type": "programmable",
                        "bands": ["UHF", "S_BAND", "C_BAND"],
                        "frequency": 2.4e9,
                        "gain": 15.0,
                        "steerable": False
                    }
                ],
                "transceivers": [
                    {
                        "id": "sdr_iot_1",
                        "bands": ["MICROWAVE"],
                        "ai_processing": True,
                        "cognitive_radio": True
                    }
                ],
                "payload": {
                    "id": "iot_payload_1",
                    "type": "iot_gateway",
                    "sensors": ["iot_relay", "atmospheric"],
                    "ai_models": ["traffic_prediction", "load_balancing"]
                }
            },
            {
                "id": "CUBESAT-RESEARCH-001",
                "name": "IoST Research Platform",
                "size": CubeSatSize.SIX_U,
                "altitude": 850,
                "role": "sink",
                "antennas": [
                    {
                        "id": "ant_res_1",
                        "type": "helical",
                        "bands": ["KA_BAND", "MILLIMETER_WAVE"],
                        "frequency": 35e9,
                        "gain": 35.0,
                        "steerable": True
                    }
                ],
                "transceivers": [
                    {
                        "id": "sdr_res_1",
                        "bands": ["MILLIMETER_WAVE", "TERAHERTZ"],
                        "ai_processing": True,
                        "cognitive_radio": True
                    }
                ],
                "payload": {
                    "id": "res_payload_1",
                    "type": "scientific",
                    "sensors": ["atmospheric", "iot_relay"],
                    "ai_models": ["data_fusion", "scientific_analysis"]
                }
            }
        ]
        
        # Create CubeSats
        for config in cubesat_configs:
            cubesat = CubeSat(
                cubesat_id=config["id"],
                name=config["name"],
                size=config["size"],
                orbit_altitude=config["altitude"]
            )
            
            cubesat.network_role = config["role"]
            
            # Add programmable antennas
            for antenna_config in config["antennas"]:
                await cubesat.add_programmable_antenna(antenna_config)
            
            # Add reconfigurable transceivers
            for transceiver_config in config["transceivers"]:
                await cubesat.add_reconfigurable_transceiver(transceiver_config)
            
            # Set payload
            await cubesat.set_payload(config["payload"])
            
            # Register with SDN controller
            capabilities = {
                "antennas": len(config["antennas"]),
                "transceivers": len(config["transceivers"]),
                "payload_type": config["payload"]["type"],
                "ai_processing": True,
                "mesh_networking": True
            }
            await self.sdn_controller.register_cubesat(config["id"], capabilities)
            
            # Create multiband radio for each CubeSat
            supported_bands = []
            for transceiver in config["transceivers"]:
                for band_name in transceiver["bands"]:
                    supported_bands.append(FrequencyBand[band_name])
            
            radio = MultibandRadio(f"radio_{config['id']}", supported_bands)
            self.multiband_radios[config["id"]] = radio
            
            self.cubesat_constellation[config["id"]] = cubesat
            
            logger.info(f"Created CubeSat: {cubesat.name} ({cubesat.size.value})")
        
        # Discover network topology
        await self.sdn_controller.discover_network_topology()
        
        # Enable mesh networking
        for cubesat_id, cubesat in self.cubesat_constellation.items():
            neighbors = list(self.cubesat_constellation.keys())
            neighbors.remove(cubesat_id)
            await cubesat.enable_mesh_networking(neighbors[:3])  # Connect to 3 neighbors
        
        logger.info(
            f"CubeSat constellation initialized with {len(self.cubesat_constellation)} nodes"
        )
    
    async def create_network_slices(self):
        """Create network slices for different IoST services"""
        logger.info("Creating network slices for IoST services...")
        
        # Earth Observation slice - high bandwidth, moderate latency
        eo_slice = {
            "slice_id": "earth_observation_slice",
            "type": NetworkSliceType.EARTH_OBSERVATION.value,
            "bandwidth_mbps": 100,
            "latency_ms": 50,
            "reliability": 0.99,
            "coverage": ["CUBESAT-EARTH-OBS-001", "CUBESAT-COMMAND-001"],
            "sla": {
                "uptime": 0.999,
                "data_integrity": 0.9999
            }
        }
        await self.sdn_controller.create_network_slice(eo_slice)
        
        # Emergency Services slice - ultra-reliable, low latency
        emergency_slice = {
            "slice_id": "emergency_services_slice", 
            "type": NetworkSliceType.URLLC.value,
            "bandwidth_mbps": 50,
            "latency_ms": 10,
            "reliability": 0.9999,
            "coverage": list(self.cubesat_constellation.keys()),
            "sla": {
                "uptime": 0.99999,
                "response_time": 5  # seconds
            }
        }
        await self.sdn_controller.create_network_slice(emergency_slice)
        
        # IoT Gateway slice - massive connectivity
        iot_slice = {
            "slice_id": "iot_connectivity_slice",
            "type": NetworkSliceType.MMTC.value,
            "bandwidth_mbps": 200,
            "latency_ms": 100,
            "reliability": 0.95,
            "coverage": ["CUBESAT-IOT-GATEWAY-001", "CUBESAT-COMMAND-001"],
            "sla": {
                "device_capacity": 10000,
                "message_throughput": 1000  # messages/second
            }
        }
        await self.sdn_controller.create_network_slice(iot_slice)
        
        logger.info("Network slices created successfully")
    
    async def deploy_virtual_network_functions(self):
        """Deploy VNFs for advanced network services"""
        logger.info("Deploying Virtual Network Functions...")
        
        # Traffic Load Balancer VNF
        load_balancer_vnf = {
            "vnf_id": "load_balancer_001",
            "type": "load_balancer",
            "resources": {"cpu": 20, "memory": 128, "bandwidth": 100e6},
            "inputs": ["satellite_traffic"],
            "outputs": ["balanced_traffic"],
            "rules": [
                {"algorithm": "round_robin"},
                {"health_check": True}
            ]
        }
        await self.sdn_controller.deploy_vnf(
            load_balancer_vnf,
            ["CUBESAT-COMMAND-001", "CUBESAT-IOT-GATEWAY-001"]
        )
        
        # Deep Packet Inspection VNF
        dpi_vnf = {
            "vnf_id": "packet_inspector_001",
            "type": "packet_inspector",
            "resources": {"cpu": 30, "memory": 256, "bandwidth": 50e6},
            "inputs": ["network_traffic"],
            "outputs": ["classified_traffic"],
            "rules": [
                {"classify_protocols": True},
                {"detect_anomalies": True}
            ]
        }
        await self.sdn_controller.deploy_vnf(
            dpi_vnf,
            ["CUBESAT-EARTH-OBS-001"]
        )
        
        # Create service chain
        service_chain = {
            "chain_id": "security_chain_001",
            "vnf_sequence": ["packet_inspector_001", "load_balancer_001"]
        }
        await self.sdn_controller.create_service_chain(service_chain)
        
        logger.info("VNFs deployed and service chains created")
    
    async def demonstrate_adaptive_communication(self):
        """Demonstrate adaptive multiband communication"""
        logger.info("Demonstrating adaptive multiband communication...")
        
        for cubesat_id, radio in self.multiband_radios.items():
            # Simulate varying environmental conditions
            environment_conditions = {
                "weather": "clear",
                "atmospheric_loss": 0.5,
                "interference": 0.1,
                "distance": 1000
            }
            
            cubesat = self.cubesat_constellation[cubesat_id]
            
            # Demonstrate adaptive communication
            target_id = next(iter(self.cubesat_constellation.keys()))
            if target_id != cubesat_id:
                success = await cubesat.adaptive_communication(
                    target_id, environment_conditions
                )
                if success:
                    logger.info(f"{cubesat_id} adapted communication to {target_id}")
        
        # Demonstrate spectrum sensing and optimal band selection
        for radio_id, radio in self.multiband_radios.items():
            spectrum_data = await radio.sense_spectrum(1.0)
            logger.info(f"Radio {radio_id} sensed {len(spectrum_data)} frequency bands")
    
    async def simulate_iot_data_relay(self):
        """Simulate IoT data relay through CubeSat constellation"""
        logger.info("Simulating IoT data relay...")
        
        # Find IoT gateway CubeSat
        iot_gateway = None
        for cubesat_id, cubesat in self.cubesat_constellation.items():
            if cubesat.network_role == "relay":
                iot_gateway = cubesat
                break
        
        if iot_gateway:
            # Simulate IoT device data
            iot_devices = [
                {"id": "weather_station_001", "location": "remote_area_1"},
                {"id": "seismic_sensor_002", "location": "earthquake_zone"},
                {"id": "flood_monitor_003", "location": "river_delta"},
                {"id": "wildfire_detector_004", "location": "forest_region"}
            ]
            
            for device in iot_devices:
                data = {
                    "device_id": device["id"],
                    "location": device["location"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "sensor_data": {
                        "temperature": 25.5,
                        "humidity": 60.0,
                        "pressure": 1013.25
                    }
                }
                
                # Relay through CubeSat
                success = await iot_gateway.relay_iot_data(
                    device["id"], "ground_station", data
                )
                
                if success:
                    logger.info(f"Relayed data from {device['id']} through {iot_gateway.name}")
    
    async def demonstrate_ai_processing(self):
        """Demonstrate onboard AI processing capabilities"""
        logger.info("Demonstrating onboard AI processing...")
        
        for cubesat_id, cubesat in self.cubesat_constellation.items():
            if cubesat.payload and cubesat.onboard_ai_enabled:
                # Simulate data collection
                sensor_data = cubesat.payload.collect_sensor_data(60.0)  # 1 minute
                
                # Process with onboard AI
                processed_data = await cubesat.process_data_with_ai(sensor_data)
                
                logger.info(f"{cubesat.name} processed data with AI: "
                           f"{len(str(processed_data))} bytes")
    
    async def start_enhanced_operations(self):
        """Start enhanced IoST operations"""
        logger.info("Starting enhanced IoST operations...")
        
        self.running = True
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._cubesat_monitoring_loop()),
            asyncio.create_task(self._sdn_optimization_loop()),
            asyncio.create_task(self._multiband_communication_loop()),
            asyncio.create_task(self._ai_processing_loop()),
            asyncio.create_task(self._network_slice_monitoring_loop())
        ]
        
        logger.info("Enhanced IoST operations started successfully")
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Enhanced operations cancelled")
        finally:
            self.running = False
            logger.info("Enhanced operations stopped")
    
    async def _cubesat_monitoring_loop(self):
        """Monitor CubeSat constellation health and status"""
        while self.running:
            try:
                for cubesat_id, cubesat in self.cubesat_constellation.items():
                    status = cubesat.get_cubesat_status()
                    
                    if status["health_score"] < 0.8:
                        logger.warning(f"CubeSat {cubesat_id} health degraded: "
                                     f"{status['health_score']:.2f}")
                    
                    # Update last contact time
                    cubesat.last_contact = datetime.utcnow()
                
                await asyncio.sleep(30)  # Every 30 seconds
            except Exception as e:
                logger.error(f"Error in CubeSat monitoring: {e}")
                await asyncio.sleep(10)
    
    async def _sdn_optimization_loop(self):
        """Optimize network routes using SDN controller"""
        while self.running:
            try:
                # Optimize network routes
                optimized_routes = await self.sdn_controller.optimize_network_routes()
                
                logger.debug(f"Optimized routes for {len(optimized_routes)} nodes")
                
                await asyncio.sleep(300)  # Every 5 minutes
            except Exception as e:
                logger.error(f"Error in SDN optimization: {e}")
                await asyncio.sleep(60)
    
    async def _multiband_communication_loop(self):
        """Monitor and optimize multiband communications"""
        while self.running:
            try:
                for radio_id, radio in self.multiband_radios.items():
                    # Perform spectrum sensing
                    spectrum_data = await radio.sense_spectrum(0.5)
                    
                    # Check for interference and mitigate if needed
                    interfered_links = [
                        link_id for link_id, link in radio.active_links.items()
                        if link.channel_conditions and 
                        link.channel_conditions.interference_level > 0.3
                    ]
                    
                    if interfered_links:
                        mitigation_results = await radio.cognitive_interference_mitigation(
                            interfered_links
                        )
                        logger.info(f"Mitigated interference on {len(interfered_links)} links")
                
                await asyncio.sleep(60)  # Every minute
            except Exception as e:
                logger.error(f"Error in multiband communication loop: {e}")
                await asyncio.sleep(30)
    
    async def _ai_processing_loop(self):
        """Process data using onboard AI"""
        while self.running:
            try:
                for cubesat_id, cubesat in self.cubesat_constellation.items():
                    if cubesat.payload and cubesat.onboard_ai_enabled:
                        # Collect and process sensor data
                        sensor_data = cubesat.payload.collect_sensor_data(5.0)
                        processed_data = await cubesat.process_data_with_ai(sensor_data)
                        
                        # Log significant findings
                        if ("ai_analysis" in processed_data and 
                            processed_data["ai_analysis"].get("anomaly_detection", False)):
                            logger.info(f"Anomaly detected by {cubesat.name}")
                
                await asyncio.sleep(120)  # Every 2 minutes
            except Exception as e:
                logger.error(f"Error in AI processing loop: {e}")
                await asyncio.sleep(60)
    
    async def _network_slice_monitoring_loop(self):
        """Monitor network slice performance"""
        while self.running:
            try:
                stats = self.sdn_controller.get_network_statistics()
                
                if stats["active_slices"] > 0:
                    logger.debug(f"Network slices active: {stats['active_slices']}, "
                               f"Average utilization: {stats['average_link_utilization']:.2f}")
                
                await asyncio.sleep(60)  # Every minute
            except Exception as e:
                logger.error(f"Error in slice monitoring: {e}")
                await asyncio.sleep(30)
    
    async def shutdown(self):
        """Gracefully shutdown the enhanced platform"""
        logger.info("Shutting down Enhanced IoST Platform...")
        
        self.running = False
        
        # Stop environmental monitoring
        await self.radiation_detector.stop_monitoring()
        
        # Stop mission control
        await self.mission_control.stop_operations()
        
        logger.info("Enhanced IoST Platform shutdown complete")
    
    def get_enhanced_system_status(self):
        """Get comprehensive enhanced system status"""
        sdn_stats = self.sdn_controller.get_network_statistics()
        
        # CubeSat status
        cubesat_status = {}
        for cubesat_id, cubesat in self.cubesat_constellation.items():
            cubesat_status[cubesat_id] = cubesat.get_cubesat_status()
        
        # Radio status
        radio_status = {}
        for radio_id, radio in self.multiband_radios.items():
            radio_status[radio_id] = radio.get_radio_status()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform_status": "operational" if self.running else "stopped",
            "cubesat_constellation": cubesat_status,
            "sdn_controller": sdn_stats,
            "multiband_radios": radio_status,
            "total_cubeSats": len(self.cubesat_constellation),
            "active_network_slices": sdn_stats["active_slices"],
            "deployed_vnfs": sdn_stats["deployed_vnfs"]
        }


async def main():
    """Main application entry point for enhanced IoST platform"""
    logger.info("Starting Enhanced Internet of Space Things Platform")
    
    # Create enhanced platform instance
    platform = EnhancedIoSPlatform()
    
    # Set up signal handlers for graceful shutdown
    def shutdown_handler():
        asyncio.create_task(platform.shutdown())
    
    signal.signal(signal.SIGINT, lambda s, f: shutdown_handler())
    signal.signal(signal.SIGTERM, lambda s, f: shutdown_handler())
    
    try:
        # Initialize CubeSat constellation
        await platform.initialize_cubesat_constellation()
        
        # Create network slices
        await platform.create_network_slices()
        
        # Deploy VNFs
        await platform.deploy_virtual_network_functions()
        
        # Print enhanced system status
        status = platform.get_enhanced_system_status()
        logger.info(f"Enhanced System Status: {status['total_cubeSats']} CubeSats, "
                   f"{status['active_network_slices']} network slices, "
                   f"{status['deployed_vnfs']} VNFs")
        
        # Demonstrate IoST capabilities
        await platform.demonstrate_adaptive_communication()
        await platform.simulate_iot_data_relay()
        await platform.demonstrate_ai_processing()
        
        # Start enhanced operations - run for 30 seconds for demo
        logger.info("Running IoST platform for 30 seconds to demonstrate capabilities...")
        
        # Create a task for enhanced operations
        operations_task = asyncio.create_task(platform.start_enhanced_operations())
        
        # Wait for 30 seconds or until interrupted
        try:
            await asyncio.wait_for(operations_task, timeout=30.0)
        except asyncio.TimeoutError:
            logger.info("Demo completed after 30 seconds")
            operations_task.cancel()
            
            # Wait a bit for graceful cancellation
            try:
                await operations_task
            except asyncio.CancelledError:
                pass
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await platform.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
