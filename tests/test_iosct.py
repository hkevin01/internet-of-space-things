#!/usr/bin/env python3
"""
Test script for Internet of Space Things (IoST) system
Verifies core functionality including CubeSats, SDN, and multiband communication
"""

import asyncio
import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from communication.multiband_radio import FrequencyBand, MultibandRadio
from cubesat.cubesat_network import CubeSat, CubeSatSize
from cubesat.sdn_controller import SDNController


async def test_cubesat_creation():
    """Test CubeSat creation and configuration"""
    print("Testing CubeSat creation...")
    
    # Create a basic CubeSat
    cubesat = CubeSat(
        cubesat_id="TEST-001",
        name="Test CubeSat",
        size=CubeSatSize.THREE_U,
        orbit_altitude=550
    )
    
    # Add antenna
    antenna_config = {
        "id": "test_antenna",
        "type": "programmable",
        "bands": ["S_BAND", "X_BAND"],
        "frequency": 8.4e9,
        "gain": 20.0,
        "steerable": True
    }
    
    success = await cubesat.add_programmable_antenna(antenna_config)
    assert success, "Failed to add antenna"
    
    # Add transceiver
    transceiver_config = {
        "id": "test_transceiver",
        "bands": ["MICROWAVE"],
        "ai_processing": True,
        "cognitive_radio": True
    }
    
    success = await cubesat.add_reconfigurable_transceiver(transceiver_config)
    assert success, "Failed to add transceiver"
    
    # Set payload
    payload_config = {
        "id": "test_payload",
        "type": "communication",
        "sensors": ["iot_relay"]
    }
    
    success = await cubesat.set_payload(payload_config)
    assert success, "Failed to set payload"
    
    # Get status
    status = cubesat.get_cubesat_status()
    assert status["cubesat_id"] == "TEST-001"
    assert status["size"] == "3U"
    
    print("✓ CubeSat creation test passed")


async def test_sdn_controller():
    """Test SDN controller functionality"""
    print("Testing SDN controller...")
    
    # Create SDN controller
    controller = SDNController("TEST_SDN")
    
    # Register a test CubeSat
    capabilities = {
        "antennas": 1,
        "transceivers": 1,
        "payload_type": "communication",
        "ai_processing": True
    }
    
    success = await controller.register_cubesat("TEST-001", capabilities)
    assert success, "Failed to register CubeSat"
    
    # Test network slice creation
    slice_config = {
        "slice_id": "test_slice",
        "type": "enhanced_mobile_broadband",
        "bandwidth_mbps": 50,
        "latency_ms": 20,
        "reliability": 0.99,
        "coverage": ["TEST-001"]
    }
    
    success = await controller.create_network_slice(slice_config)
    assert success, "Failed to create network slice"
    
    # Get statistics
    stats = controller.get_network_statistics()
    assert stats["total_nodes"] == 1
    assert stats["active_slices"] == 1
    
    print("✓ SDN controller test passed")


async def test_multiband_radio():
    """Test multiband radio functionality"""
    print("Testing multiband radio...")
    
    # Create radio with multiple bands
    supported_bands = [FrequencyBand.MICROWAVE, FrequencyBand.MILLIMETER_WAVE]
    radio = MultibandRadio("TEST_RADIO", supported_bands)
    
    # Test spectrum sensing
    spectrum_data = await radio.sense_spectrum(duration=0.1)
    assert len(spectrum_data) == 2, "Should sense 2 frequency bands"
    
    # Get radio status
    status = radio.get_radio_status()
    assert status["radio_id"] == "TEST_RADIO"
    assert len(status["supported_bands"]) == 2
    
    print("✓ Multiband radio test passed")


async def test_integration():
    """Test integration between components"""
    print("Testing component integration...")
    
    # Create CubeSat
    cubesat = CubeSat("INTEGRATION-001", "Integration Test", CubeSatSize.SIX_U)
    
    # Create SDN controller
    controller = SDNController("INTEGRATION_SDN")
    
    # Register CubeSat with controller
    capabilities = {"ai_processing": True, "mesh_networking": True}
    success = await controller.register_cubesat("INTEGRATION-001", capabilities)
    assert success, "Integration test failed - CubeSat registration"
    
    # Create multiband radio
    radio = MultibandRadio("INTEGRATION_RADIO", [FrequencyBand.MICROWAVE])
    
    # Test basic operations
    await radio.sense_spectrum(0.1)
    
    # Verify everything is working
    cubesat_status = cubesat.get_cubesat_status()
    sdn_stats = controller.get_network_statistics()
    radio_status = radio.get_radio_status()
    
    assert cubesat_status["is_operational"]
    assert sdn_stats["total_nodes"] == 1
    assert radio_status["cognitive_engine"]
    
    print("✓ Integration test passed")


async def main():
    """Run all tests"""
    print("Starting IoST System Tests...")
    print("=" * 50)
    
    try:
        await test_cubesat_creation()
        await test_sdn_controller()
        await test_multiband_radio()
        await test_integration()
        
        print("=" * 50)
        print("✓ All tests passed! IoST system is working correctly.")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
