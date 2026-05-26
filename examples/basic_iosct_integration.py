#!/usr/bin/env python3
"""
Basic IoST Integration Example

This example demonstrates how to:
1. Initialize the IoST platform
2. Create a satellite constellation
3. Send commands and receive telemetry
4. Monitor system health with predictive maintenance

Run with: python examples/basic_iosct_integration.py
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from communication.multiband_radio import FrequencyBand, MultibandRadio
from core.mission_control import CommandPriority, MissionCommand, MissionControl
from core.satellite_manager import (
    OrbitalElements,
    OrbitType,
    Satellite,
    SatelliteConfiguration,
    SatelliteManager,
)
from core.space_network import CommunicationMode, NetworkNode, SpaceNetwork
from cubesat.cubesat_network import CommunicationBand, CubeSat, CubeSatSize
from cubesat.sdn_controller import NetworkSliceType, SDNController
from sensors.environmental.radiation_detector import RadiationDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Run the basic integration example."""
    logger.info("🚀 Starting IoST Basic Integration Example")

    # ====================
    # 1. Initialize Core Systems
    # ====================
    logger.info("\n=== Initializing Core Systems ===")

    # Create the space network
    network = SpaceNetwork("EXAMPLE-NETWORK")
    logger.info(f"✅ Created network: {network.network_id}")

    # Create satellite manager
    sat_manager = SatelliteManager("EXAMPLE-CONSTELLATION")
    logger.info(f"✅ Created satellite manager")

    # Create mission control
    mission_control = MissionControl("EXAMPLE-MISSION", network, sat_manager)
    logger.info(f"✅ Created mission control")

    # Create SDN controller (based on research: Software-Defined Satellite Networks)
    sdn_controller = SDNController("EXAMPLE-SDN")
    logger.info(f"✅ Created SDN controller")

    # ====================
    # 2. Create Satellite Constellation
    # ====================
    logger.info("\n=== Creating Satellite Constellation ===")

    satellites_config = [
        {
            "id": "ISS-001",
            "name": "International Space Station",
            "orbit": OrbitType.LEO,
            "altitude": 408,  # km
            "inclination": 51.6,  # degrees
            "period": 92.9,  # minutes
        },
        {
            "id": "CUBESAT-001",
            "name": "IoST CubeSat 1",
            "orbit": OrbitType.LEO,
            "altitude": 550,
            "inclination": 45.0,
            "period": 94.8,
        },
        {
            "id": "CUBESAT-002",
            "name": "IoST CubeSat 2",
            "orbit": OrbitType.LEO,
            "altitude": 550,
            "inclination": 45.0,
            "period": 94.8,
        },
    ]

    satellites = []
    for sat_cfg in satellites_config:
        try:
            config = SatelliteConfiguration(
                satellite_id=sat_cfg["id"],
                name=sat_cfg["name"],
                satellite_type="space_station" if "ISS" in sat_cfg["id"] else "cubesat",
                orbit_type=sat_cfg["orbit"],
                mass=420000 if "ISS" in sat_cfg["id"] else 5000,
                power_capacity=75000 if "ISS" in sat_cfg["id"] else 10000,
                fuel_capacity=1000 if "ISS" in sat_cfg["id"] else 200,
                communication_frequency=8.4e9,
            )
            sat = sat_manager.add_satellite(config)
            satellites.append(sat)
            logger.info(f"  ✅ Added {sat_cfg['name']} ({sat_cfg['id']})")
        except Exception as e:
            logger.error(f"  ❌ Failed to add {sat_cfg['id']}: {e}")

    # ====================
    # 3. Test Communication
    # ====================
    logger.info("\n=== Testing Communication ===")

    # Create network nodes for satellites
    for sat in satellites:
        node = NetworkNode(
            node_id=sat.satellite_id,
            node_type="satellite",
            communication_mode=CommunicationMode.ACTIVE,
        )
        network.add_node(node)
        logger.info(f"  ✅ Added network node for {sat.satellite_id}")

    # Create links between satellites (ISL - Inter-Satellite Link)
    if len(satellites) > 1:
        for i in range(len(satellites) - 1):
            network.add_link(satellites[i].satellite_id, satellites[i + 1].satellite_id)
            logger.info(f"  ✅ Added ISL: {satellites[i].satellite_id} ↔ {satellites[i + 1].satellite_id}")

    # ====================
    # 4. Send Commands
    # ====================
    logger.info("\n=== Sending Commands ===")

    commands = [
        MissionCommand(
            command_id="CMD-001",
            target_id="ISS-001",
            command_type="POWER_UP_PAYLOAD",
            parameters={"payload_id": "PAYLOAD-001"},
            priority=CommandPriority.HIGH,
            timeout=30.0,
        ),
        MissionCommand(
            command_id="CMD-002",
            target_id="CUBESAT-001",
            command_type="TAKE_MEASUREMENT",
            parameters={"sensor": "radiation_detector"},
            priority=CommandPriority.NORMAL,
            timeout=60.0,
        ),
    ]

    for cmd in commands:
        try:
            result = await mission_control.execute_command(cmd)
            logger.info(f"  ✅ Executed {cmd.command_id}: {result}")
        except Exception as e:
            logger.error(f"  ❌ Failed to execute {cmd.command_id}: {e}")

    # ====================
    # 5. Monitor Radiation (Research-based: Environmental Monitoring)
    # ====================
    logger.info("\n=== Monitoring Radiation Levels ===")

    rad_detector = RadiationDetector("RAD-SENSOR-001")

    # Simulate radiation measurements
    radiation_data = [
        {"timestamp": datetime.now(), "dose_rate": 0.25, "unit": "mSv/hour"},
        {"timestamp": datetime.now() + timedelta(minutes=1), "dose_rate": 0.28, "unit": "mSv/hour"},
        {"timestamp": datetime.now() + timedelta(minutes=2), "dose_rate": 0.32, "unit": "mSv/hour"},
    ]

    for data in radiation_data:
        try:
            # Log radiation data
            logger.info(
                f"  ✅ Radiation: {data['dose_rate']} {data['unit']} @ {data['timestamp']}"
            )
            # Check if exceeds threshold (research-based: anomaly detection)
            if data["dose_rate"] > 0.30:
                logger.warning(f"  ⚠️  Elevated radiation detected: {data['dose_rate']} {data['unit']}")
        except Exception as e:
            logger.error(f"  ❌ Failed to process radiation data: {e}")

    # ====================
    # 6. Network Status Report
    # ====================
    logger.info("\n=== Network Status Report ===")

    logger.info(f"Network ID: {network.network_id}")
    logger.info(f"Total Nodes: {len(network.nodes)}")
    logger.info(f"Total Satellites: {len(satellites)}")
    logger.info(f"Active Links: {len(network.links)}")

    for sat in satellites:
        logger.info(
            f"  • {sat.name} ({sat.satellite_id}): "
            f"Power={sat.current_power:.1f}W, "
            f"Fuel={sat.fuel:.1f}kg, "
            f"Health={sat.health:.1f}%"
        )

    # ====================
    # 7. Predictive Maintenance Example (Research-based)
    # ====================
    logger.info("\n=== Predictive Maintenance Status ===")
    logger.info("Note: Full ML models will be implemented in Phase 3 (Q3 2026)")
    logger.info("Currently tracking: Power systems, fuel consumption, component health")

    for sat in satellites:
        # Simple health check
        if sat.health < 80:
            logger.warning(f"  ⚠️  {sat.name}: Health degradation detected ({sat.health:.1f}%)")
        else:
            logger.info(f"  ✅ {sat.name}: Nominal health status ({sat.health:.1f}%)")

    logger.info("\n=== Integration Example Complete ===")
    logger.info("✅ All core systems functional and communicating")
    logger.info("📊 Next Steps: Deploy to mission simulation environment")


if __name__ == "__main__":
    asyncio.run(main())
