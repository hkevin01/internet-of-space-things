"""
Internet of Space Things (IoST) - Main Application Entry Point
Demonstrates the core functionality of the space communication platform
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.mission_control import (
    CommandPriority,
    MissionCommand,
    MissionControl,
    MissionObjective,
)
from core.satellite_manager import (
    OrbitalElements,
    OrbitType,
    SatelliteConfiguration,
    SatelliteManager,
)
from core.space_network import (
    CommunicationMode,
    NetworkNode,
    NetworkStatus,
    SpaceNetwork,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def create_sample_constellation():
    """Create a sample satellite constellation for demonstration"""
    logger.info("Creating sample satellite constellation...")
    
    # Initialize managers
    network = SpaceNetwork("IoST-Demo-Network")
    satellite_manager = SatelliteManager("IoST-Demo-Constellation")
    mission_control = MissionControl("IoST-Demo-Mission", network, satellite_manager)
    
    # Create sample satellites
    satellites_config = [
        {
            "id": "ISS-MAIN",
            "name": "International Space Station",
            "type": "space_station",
            "orbit": OrbitType.LEO,
            "mass": 420000,  # kg
            "power": 75000,  # watts
            "fuel": 1000,    # kg
            "frequency": 2.4e9,  # Hz
            "sensors": ["atmospheric", "radiation", "earth_observation", "life_support"]
        },
        {
            "id": "LUNAR-SAT-1", 
            "name": "Lunar Gateway Comm Satellite",
            "type": "communications",
            "orbit": OrbitType.DEEP_SPACE,
            "mass": 5000,
            "power": 15000,
            "fuel": 500,
            "frequency": 8.4e9,
            "sensors": ["navigation", "radiation", "atmospheric"]
        },
        {
            "id": "MARS-RELAY",
            "name": "Mars Communication Relay",
            "type": "communications", 
            "orbit": OrbitType.DEEP_SPACE,
            "mass": 3000,
            "power": 10000,
            "fuel": 300,
            "frequency": 32e9,
            "sensors": ["navigation", "radiation"]
        }
    ]
    
    # Add satellites to constellation
    for sat_config in satellites_config:
        config = SatelliteConfiguration(
            satellite_id=sat_config["id"],
            name=sat_config["name"],
            satellite_type=sat_config["type"],
            orbit_type=sat_config["orbit"],
            mass=sat_config["mass"],
            power_capacity=sat_config["power"],
            fuel_capacity=sat_config["fuel"],
            communication_frequency=sat_config["frequency"],
            sensor_types=sat_config["sensors"]
        )
        
        # Create orbital elements (simplified for demo)
        if sat_config["orbit"] == OrbitType.LEO:
            orbital_elements = OrbitalElements(
                semi_major_axis=6800,  # km
                eccentricity=0.01,
                inclination=51.6,      # degrees
                longitude_of_ascending_node=0.0,
                argument_of_periapsis=0.0,
                true_anomaly=0.0
            )
        else:  # Deep space
            orbital_elements = OrbitalElements(
                semi_major_axis=50000,  # km
                eccentricity=0.1,
                inclination=0.0,
                longitude_of_ascending_node=0.0,
                argument_of_periapsis=0.0,
                true_anomaly=0.0
            )
        
        await satellite_manager.add_satellite(config, orbital_elements)
        
        # Add to network
        node = NetworkNode(
            node_id=sat_config["id"],
            name=sat_config["name"],
            node_type="spacecraft",
            status=NetworkStatus.ACTIVE,
            communication_modes=[CommunicationMode.INTER_SATELLITE, CommunicationMode.DEEP_SPACE],
            signal_strength=0.8,
            bandwidth_capacity=100.0,  # Mbps
            priority_level=3 if "ISS" in sat_config["id"] else 2
        )
        await network.add_node(node)
    
    # Establish communication links
    await network.establish_link("ISS-MAIN", "LUNAR-SAT-1", CommunicationMode.INTER_SATELLITE)
    await network.establish_link("LUNAR-SAT-1", "MARS-RELAY", CommunicationMode.DEEP_SPACE)
    await network.establish_link("ISS-MAIN", "MARS-RELAY", CommunicationMode.DEEP_SPACE)
    
    return mission_control


async def demonstrate_mission_operations(mission_control):
    """Demonstrate mission operations"""
    logger.info("Starting mission operations demonstration...")
    
    # Start the mission
    mission_duration = timedelta(hours=24)  # 24-hour demo mission
    await mission_control.start_mission(mission_duration)
    
    # Add mission objectives
    objectives = [
        MissionObjective(
            objective_id="life-support-monitoring",
            title="Continuous Life Support Monitoring",
            description="Monitor oxygen, CO2, and atmospheric conditions on ISS",
            target_completion=datetime.utcnow() + timedelta(hours=1),
            success_criteria={"oxygen_level": ">95%", "co2_level": "<0.5%"},
            assigned_assets=["ISS-MAIN"]
        ),
        MissionObjective(
            objective_id="deep-space-comm-test", 
            title="Deep Space Communication Test",
            description="Test communication reliability to Mars relay",
            target_completion=datetime.utcnow() + timedelta(hours=2),
            success_criteria={"packet_loss": "<5%", "latency": "<300ms"},
            assigned_assets=["LUNAR-SAT-1", "MARS-RELAY"]
        ),
        MissionObjective(
            objective_id="orbital-maintenance",
            title="Orbital Position Maintenance",
            description="Maintain optimal orbital positions for constellation",
            target_completion=datetime.utcnow() + timedelta(hours=6),
            success_criteria={"position_accuracy": "<1km", "fuel_usage": "<5%"},
            assigned_assets=["ISS-MAIN", "LUNAR-SAT-1", "MARS-RELAY"]
        )
    ]
    
    for objective in objectives:
        await mission_control.add_mission_objective(objective)
    
    # Queue some commands
    commands = [
        MissionCommand(
            command_id="health-check-iss",
            target_id="ISS-MAIN",
            command_type="health_check",
            parameters={},
            priority=CommandPriority.NORMAL
        ),
        MissionCommand(
            command_id="collect-atmospheric-data",
            target_id="ISS-MAIN", 
            command_type="collect_data",
            parameters={"sensor_type": "atmospheric", "duration": 300},
            priority=CommandPriority.HIGH
        ),
        MissionCommand(
            command_id="establish-mars-link",
            target_id="network",
            command_type="establish_link",
            parameters={
                "source_id": "LUNAR-SAT-1",
                "target_id": "MARS-RELAY", 
                "link_type": "deep_space"
            },
            priority=CommandPriority.HIGH
        ),
        MissionCommand(
            command_id="transmit-telemetry",
            target_id="network",
            command_type="transmit_data",
            parameters={
                "source_id": "ISS-MAIN",
                "target_id": "MARS-RELAY",
                "data": {"telemetry": "life_support_status", "timestamp": datetime.utcnow().isoformat()},
                "priority": 3
            },
            priority=CommandPriority.NORMAL
        )
    ]
    
    for command in commands:
        await mission_control.queue_command(command)
    
    # Run mission for demonstration period
    demo_duration = 60  # seconds
    start_time = datetime.utcnow()
    
    while (datetime.utcnow() - start_time).total_seconds() < demo_duration:
        # Update constellation
        await mission_control.satellite_manager.update_constellation()
        
        # Get mission status
        status = await mission_control.get_mission_status()
        
        # Log status every 10 seconds
        if int((datetime.utcnow() - start_time).total_seconds()) % 10 == 0:
            logger.info(f"Mission Status: {status['status']}")
            logger.info(f"Active Commands: {status['commands']['active']}")
            logger.info(f"Network Health: {status['network_health']['node_availability']:.2%}")
            logger.info(f"Constellation Health: {status['constellation_health']['availability']:.2%}")
        
        await asyncio.sleep(1)
    
    # Get final mission status
    final_status = await mission_control.get_mission_status()
    
    logger.info("Mission Demonstration Complete!")
    logger.info(f"Final Status: {json.dumps(final_status, indent=2, default=str)}")


async def demonstrate_emergency_scenario(mission_control):
    """Demonstrate emergency response capabilities"""
    logger.info("Demonstrating emergency response scenario...")
    
    # Simulate emergency on ISS
    await mission_control.handle_emergency(
        "life_support_failure",
        ["ISS-MAIN"]
    )
    
    # Wait for emergency response
    await asyncio.sleep(5)
    
    # Check status after emergency
    status = await mission_control.get_mission_status()
    logger.info(f"Emergency Status: {status['status']}")
    logger.info(f"Active Alerts: {status['alerts']['active']}")


async def main():
    """Main application entry point"""
    logger.info("🚀 Starting Internet of Space Things (IoST) Demonstration")
    logger.info("=" * 60)
    
    try:
        # Create sample constellation
        mission_control = await create_sample_constellation()
        
        # Demonstrate normal operations
        await demonstrate_mission_operations(mission_control)
        
        # Demonstrate emergency response
        await demonstrate_emergency_scenario(mission_control)
        
        # Final network health check
        network_health = await mission_control.network.monitor_network_health()
        constellation_health = await mission_control.satellite_manager.monitor_constellation_health()
        
        logger.info("=" * 60)
        logger.info("🎯 Demo Summary:")
        logger.info(f"Network Nodes: {network_health['total_nodes']}")
        logger.info(f"Network Availability: {network_health['node_availability']:.2%}")
        logger.info(f"Data Transmitted: {network_health['data_transmitted_gb']:.2f} GB")
        logger.info(f"Satellites: {constellation_health['total_satellites']}")
        logger.info(f"Constellation Availability: {constellation_health['availability']:.2%}")
        logger.info("=" * 60)
        logger.info("✅ Internet of Space Things demonstration completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
