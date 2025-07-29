"""
Test Suite for Internet of Space Things Core Functionality
"""

import asyncio
import os
import sys

import pytest

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

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


class TestSpaceNetwork:
    """Test space network functionality"""
    
    @pytest.fixture
    async def network(self):
        """Create test network"""
        return SpaceNetwork("test-network")
    
    @pytest.mark.asyncio
    async def test_network_initialization(self, network):
        """Test network initialization"""
        assert network.network_name == "test-network"
        assert network.network_status == NetworkStatus.ACTIVE
        assert len(network.nodes) == 0
        assert len(network.links) == 0
    
    @pytest.mark.asyncio
    async def test_add_node(self, network):
        """Test adding nodes to network"""
        node = NetworkNode(
            node_id="test-node-1",
            name="Test Node 1",
            node_type="spacecraft",
            status=NetworkStatus.ACTIVE
        )
        
        result = await network.add_node(node)
        assert result is True
        assert "test-node-1" in network.nodes
        assert network.nodes["test-node-1"].name == "Test Node 1"
    
    @pytest.mark.asyncio
    async def test_establish_link(self, network):
        """Test establishing communication links"""
        # Add two nodes
        node1 = NetworkNode("node1", "Node 1", "spacecraft")
        node2 = NetworkNode("node2", "Node 2", "ground_station")
        
        await network.add_node(node1)
        await network.add_node(node2)
        
        # Establish link
        link = await network.establish_link("node1", "node2", CommunicationMode.INTER_SATELLITE)
        
        assert link is not None
        assert link.source_node == "node1"
        assert link.target_node == "node2"
        assert link.link_type == CommunicationMode.INTER_SATELLITE
    
    @pytest.mark.asyncio
    async def test_data_transmission(self, network):
        """Test data transmission through network"""
        # Set up network with nodes and links
        node1 = NetworkNode("transmitter", "Transmitter", "spacecraft")
        node2 = NetworkNode("receiver", "Receiver", "ground_station")
        
        await network.add_node(node1)
        await network.add_node(node2)
        await network.establish_link("transmitter", "receiver", CommunicationMode.GROUND_STATION)
        
        # Transmit data
        test_data = {"message": "Hello from space!", "timestamp": "2025-07-29T10:00:00Z"}
        result = await network.transmit_data("transmitter", "receiver", test_data)
        
        assert result is True
        assert network.total_data_transmitted > 0


class TestSatelliteManager:
    """Test satellite management functionality"""
    
    @pytest.fixture
    async def satellite_manager(self):
        """Create test satellite manager"""
        return SatelliteManager("test-constellation")
    
    @pytest.fixture
    def sample_config(self):
        """Sample satellite configuration"""
        return SatelliteConfiguration(
            satellite_id="test-sat-1",
            name="Test Satellite 1",
            satellite_type="communications",
            orbit_type=OrbitType.LEO,
            mass=1000.0,
            power_capacity=5000.0,
            fuel_capacity=100.0,
            communication_frequency=2.4e9,
            sensor_types=["atmospheric", "radiation"]
        )
    
    @pytest.fixture
    def sample_orbit(self):
        """Sample orbital elements"""
        return OrbitalElements(
            semi_major_axis=6800,
            eccentricity=0.01,
            inclination=51.6,
            longitude_of_ascending_node=0.0,
            argument_of_periapsis=0.0,
            true_anomaly=0.0
        )
    
    @pytest.mark.asyncio
    async def test_satellite_manager_init(self, satellite_manager):
        """Test satellite manager initialization"""
        assert satellite_manager.constellation_name == "test-constellation"
        assert len(satellite_manager.satellites) == 0
        assert satellite_manager.constellation_status == "operational"
    
    @pytest.mark.asyncio
    async def test_add_satellite(self, satellite_manager, sample_config, sample_orbit):
        """Test adding satellite to constellation"""
        result = await satellite_manager.add_satellite(sample_config, sample_orbit)
        
        assert result is True
        assert "test-sat-1" in satellite_manager.satellites
        
        satellite = satellite_manager.satellites["test-sat-1"]
        assert satellite.config.name == "Test Satellite 1"
        assert satellite.config.orbit_type == OrbitType.LEO
    
    @pytest.mark.asyncio
    async def test_constellation_health_monitoring(self, satellite_manager, sample_config, sample_orbit):
        """Test constellation health monitoring"""
        await satellite_manager.add_satellite(sample_config, sample_orbit)
        
        health = await satellite_manager.monitor_constellation_health()
        
        assert health["constellation_name"] == "test-constellation"
        assert health["total_satellites"] == 1
        assert health["operational_satellites"] >= 0
        assert "avg_anomaly_score" in health


class TestMissionControl:
    """Test mission control functionality"""
    
    @pytest.fixture
    async def mission_control(self):
        """Create test mission control"""
        network = SpaceNetwork("test-network")
        satellite_manager = SatelliteManager("test-constellation")
        return MissionControl("test-mission", network, satellite_manager)
    
    @pytest.mark.asyncio
    async def test_mission_control_init(self, mission_control):
        """Test mission control initialization"""
        assert mission_control.mission_name == "test-mission"
        assert len(mission_control.command_queue) == 0
        assert len(mission_control.mission_objectives) == 0
    
    @pytest.mark.asyncio
    async def test_add_mission_objective(self, mission_control):
        """Test adding mission objectives"""
        from datetime import datetime, timedelta
        
        objective = MissionObjective(
            objective_id="test-obj-1",
            title="Test Objective",
            description="A test objective",
            target_completion=datetime.utcnow() + timedelta(hours=1),
            success_criteria={"test": "passed"}
        )
        
        result = await mission_control.add_mission_objective(objective)
        
        assert result is True
        assert "test-obj-1" in mission_control.mission_objectives
        assert mission_control.mission_objectives["test-obj-1"].title == "Test Objective"
    
    @pytest.mark.asyncio
    async def test_queue_command(self, mission_control):
        """Test command queuing"""
        command = MissionCommand(
            command_id="test-cmd-1",
            target_id="test-satellite",
            command_type="health_check",
            parameters={},
            priority=CommandPriority.NORMAL
        )
        
        result = await mission_control.queue_command(command)
        
        assert result is True
        assert len(mission_control.command_queue) == 1
        assert mission_control.command_queue[0].command_id == "test-cmd-1"
    
    @pytest.mark.asyncio
    async def test_mission_status(self, mission_control):
        """Test getting mission status"""
        status = await mission_control.get_mission_status()
        
        assert status["mission_name"] == "test-mission"
        assert "status" in status
        assert "objectives" in status
        assert "commands" in status
        assert "network_health" in status
        assert "constellation_health" in status


class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.mark.asyncio
    async def test_complete_system_workflow(self):
        """Test complete system workflow"""
        # Initialize system components
        network = SpaceNetwork("integration-test-network")
        satellite_manager = SatelliteManager("integration-test-constellation")
        mission_control = MissionControl("integration-test-mission", network, satellite_manager)
        
        # Add a satellite
        config = SatelliteConfiguration(
            satellite_id="integration-sat",
            name="Integration Test Satellite",
            satellite_type="communications",
            orbit_type=OrbitType.LEO,
            mass=2000.0,
            power_capacity=10000.0,
            fuel_capacity=200.0,
            communication_frequency=2.4e9,
            sensor_types=["atmospheric", "radiation", "navigation"]
        )
        
        orbit = OrbitalElements(
            semi_major_axis=6800,
            eccentricity=0.01,
            inclination=51.6,
            longitude_of_ascending_node=0.0,
            argument_of_periapsis=0.0,
            true_anomaly=0.0
        )
        
        # Add satellite to manager
        sat_result = await satellite_manager.add_satellite(config, orbit)
        assert sat_result is True
        
        # Add satellite as network node
        node = NetworkNode(
            node_id="integration-sat",
            name="Integration Test Satellite",
            node_type="spacecraft",
            status=NetworkStatus.ACTIVE
        )
        net_result = await network.add_node(node)
        assert net_result is True
        
        # Start mission
        from datetime import timedelta
        mission_start = await mission_control.start_mission(timedelta(hours=1))
        assert mission_start is True
        
        # Add mission objective
        from datetime import datetime, timedelta
        objective = MissionObjective(
            objective_id="integration-test-obj",
            title="Integration Test Objective", 
            description="Test the complete system integration",
            target_completion=datetime.utcnow() + timedelta(minutes=30),
            success_criteria={"system_operational": True},
            assigned_assets=["integration-sat"]
        )
        obj_result = await mission_control.add_mission_objective(objective)
        assert obj_result is True
        
        # Queue a command
        command = MissionCommand(
            command_id="integration-test-cmd",
            target_id="integration-sat",
            command_type="health_check",
            parameters={},
            priority=CommandPriority.HIGH
        )
        cmd_result = await mission_control.queue_command(command)
        assert cmd_result is True
        
        # Allow some processing time
        await asyncio.sleep(2)
        
        # Check final system status
        mission_status = await mission_control.get_mission_status()
        network_health = await network.monitor_network_health()
        constellation_health = await satellite_manager.monitor_constellation_health()
        
        # Verify system is operational
        assert mission_status["status"] == "active"
        assert network_health["total_nodes"] == 1
        assert constellation_health["total_satellites"] == 1
        
        print("✅ Complete system integration test passed!")


# Test runner
if __name__ == "__main__":
    async def run_tests():
        """Run all tests"""
        print("🚀 Running Internet of Space Things Test Suite")
        print("=" * 50)
        
        # Run individual component tests
        print("Testing Space Network...")
        network_test = TestSpaceNetwork()
        network = await network_test.network()
        await network_test.test_network_initialization(network)
        await network_test.test_add_node(network)
        await network_test.test_establish_link(network)
        await network_test.test_data_transmission(network)
        print("✅ Space Network tests passed")
        
        print("Testing Satellite Manager...")
        sat_test = TestSatelliteManager()
        sat_manager = await sat_test.satellite_manager()
        config = sat_test.sample_config()
        orbit = sat_test.sample_orbit()
        await sat_test.test_satellite_manager_init(sat_manager)
        await sat_test.test_add_satellite(sat_manager, config, orbit)
        await sat_test.test_constellation_health_monitoring(sat_manager, config, orbit)
        print("✅ Satellite Manager tests passed")
        
        print("Testing Mission Control...")
        mc_test = TestMissionControl()
        mission_control = await mc_test.mission_control()
        await mc_test.test_mission_control_init(mission_control)
        await mc_test.test_add_mission_objective(mission_control)
        await mc_test.test_queue_command(mission_control)
        await mc_test.test_mission_status(mission_control)
        print("✅ Mission Control tests passed")
        
        print("Running Integration Tests...")
        integration_test = TestIntegration()
        await integration_test.test_complete_system_workflow()
        print("✅ Integration tests passed")
        
        print("=" * 50)
        print("🎉 All tests completed successfully!")
    
    asyncio.run(run_tests())
