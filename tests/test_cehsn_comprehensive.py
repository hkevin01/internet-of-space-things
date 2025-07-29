"""
Comprehensive Test Suite for CubeSat-Enabled Hybrid Survival Network (CEHSN)
Tests all documented features and functionality
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cehsn.ethics_engine import (
    DecisionSeverity,
    EthicalContext,
    EthicalPrinciple,
    EthicalRule,
    EthicalViolationType,
    EthicsEngine,
)

# Import CEHSN modules
from cehsn.orbital_infer import (
    AnomalyType,
    ConfidenceLevel,
    GeospatialCoordinate,
    InferenceResult,
    OrbitalInferenceEngine,
    SensorReading,
)
from cehsn.resilience_monitor import (
    AlertLevel,
    HealthMetric,
    HealthStatus,
    NetworkAlert,
    NetworkNode,
    NodeType,
    ResilienceMonitor,
)
from cehsn.rpa_comm_bridge import (
    MissionPlan,
    MissionPriority,
    MissionType,
    RPACapabilities,
    RPACommunicationBridge,
    RPAStatus,
    Waypoint,
)
from cehsn.survival_mapgen import (
    GeographicBounds,
    HazardType,
    MapType,
    ResourceType,
    SafetyLevel,
    SurvivalMap,
    SurvivalMapGenerator,
)


class TestOrbitalInferenceEngine:
    """Test orbital inference engine for anomaly detection"""
    
    @pytest.fixture
    async def inference_engine(self):
        """Create test inference engine"""
        engine = OrbitalInferenceEngine("test-cubesat-01")
        await engine.start_inference_engine()
        return engine
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        """Test that orbital inference engine initializes correctly"""
        engine = OrbitalInferenceEngine("cubesat-001")
        
        # Verify initialization
        assert engine.cubesat_id == "cubesat-001"
        assert engine.is_active is False
        assert len(engine.inference_history) == 0
        assert engine.radiation_threshold == 1000.0
        
        # Test engine startup
        result = await engine.start_inference_engine()
        assert result is True
        assert engine.is_active is True
    
    @pytest.mark.asyncio
    async def test_radiation_anomaly_detection(self, inference_engine):
        """Test detection of radiation spike anomalies"""
        # Create test sensor reading with high radiation
        coordinate = GeospatialCoordinate(latitude=45.0, longitude=-122.0)
        reading = SensorReading(
            sensor_id="rad-001",
            sensor_type="radiation",
            reading_value=1500.0,  # Above threshold
            units="cpm",
            coordinate=coordinate
        )
        
        # Process reading
        result = await inference_engine.process_sensor_reading(reading)
        
        # Verify anomaly detected
        assert result is not None
        assert result.anomaly_type == AnomalyType.RADIATION_SPIKE
        assert result.confidence_score > 0.5
        assert "radiation spike" in result.description.lower()
        assert result.location.latitude == 45.0
        assert result.location.longitude == -122.0
    
    @pytest.mark.asyncio
    async def test_no_anomaly_detected_for_normal_reading(self, inference_engine):
        """Test that normal readings don't trigger anomalies"""
        coordinate = GeospatialCoordinate(latitude=40.0, longitude=-74.0)
        reading = SensorReading(
            sensor_id="rad-002",
            sensor_type="radiation",
            reading_value=500.0,  # Below threshold
            units="cpm",
            coordinate=coordinate
        )
        
        result = await inference_engine.process_sensor_reading(reading)
        
        # Should not detect anomaly
        assert result is None
    
    @pytest.mark.asyncio
    async def test_multiple_sensor_fusion(self, inference_engine):
        """Test fusion of multiple sensor readings"""
        coordinate = GeospatialCoordinate(latitude=37.7749, longitude=-122.4194)
        
        # Create multiple readings indicating fire
        readings = [
            SensorReading("optical-001", "optical", 0.9, "normalized", coordinate),
            SensorReading("thermal-001", "infrared", 45.0, "celsius", coordinate),
            SensorReading("smoke-001", "optical", 0.8, "normalized", coordinate)
        ]
        
        results = await inference_engine.process_multiple_readings(readings)
        
        # Should get fused result
        assert len(results) > 0
        fused_result = results[0]
        assert fused_result.anomaly_type in [AnomalyType.WILDFIRE, AnomalyType.ATMOSPHERIC_DISTURBANCE]
        assert "fused" in fused_result.description.lower()
    
    @pytest.mark.asyncio
    async def test_inference_summary_generation(self, inference_engine):
        """Test generation of inference summaries"""
        # Add some test inference results
        coordinate = GeospatialCoordinate(latitude=35.0, longitude=-118.0)
        reading = SensorReading("test-sensor", "radiation", 1200.0, "cpm", coordinate)
        
        await inference_engine.process_sensor_reading(reading)
        
        # Get summary
        summary = await inference_engine.get_inference_summary(hours_back=1.0)
        
        assert summary["total_detections"] > 0
        assert "anomaly_types" in summary
        assert "confidence_distribution" in summary
        assert "severity_stats" in summary
    
    @pytest.mark.asyncio
    async def test_sensor_calibration(self, inference_engine):
        """Test sensor calibration functionality"""
        calibration_data = {
            "offset": 10.0,
            "scale_factor": 1.05,
            "last_calibrated": datetime.utcnow().isoformat()
        }
        
        result = await inference_engine.calibrate_sensor("sensor-001", calibration_data)
        
        assert result is True
        assert "sensor-001" in inference_engine.sensor_calibration
        assert inference_engine.sensor_calibration["sensor-001"]["offset"] == 10.0
    
    @pytest.mark.asyncio
    async def test_confidence_levels_correctly_assigned(self, inference_engine):
        """Test that confidence levels are correctly assigned based on scores"""
        coordinate = GeospatialCoordinate(latitude=0.0, longitude=0.0)
        
        # Test different confidence levels
        test_cases = [
            (0.95, ConfidenceLevel.CRITICAL),
            (0.8, ConfidenceLevel.HIGH),
            (0.6, ConfidenceLevel.MEDIUM),
            (0.3, ConfidenceLevel.LOW)
        ]
        
        for confidence_score, expected_level in test_cases:
            result = InferenceResult(
                anomaly_type=AnomalyType.RADIATION_SPIKE,
                confidence_score=confidence_score,
                confidence_level=ConfidenceLevel.LOW,  # Will be overridden
                location=coordinate,
                severity=0.5,
                description="Test"
            )
            
            assert result.confidence_level == expected_level


class TestRPACommunicationBridge:
    """Test RPA communication bridge for drone coordination"""
    
    @pytest.fixture
    async def rpa_bridge(self):
        """Create test RPA communication bridge"""
        bridge = RPACommunicationBridge("test-bridge-01")
        await bridge.start_bridge()
        return bridge
    
    @pytest.fixture
    def sample_rpa_capabilities(self):
        """Sample RPA capabilities"""
        return RPACapabilities(
            rpa_id="drone-001",
            model="Quadcopter-X1",
            max_flight_time_minutes=120,
            max_range_km=50.0,
            max_payload_kg=5.0,
            sensors=["high_resolution_camera", "thermal_camera", "lidar"],
            communication_systems=["radio", "satellite"],
            special_equipment=["fire_suppression_system"]
        )
    
    @pytest.mark.asyncio
    async def test_bridge_initialization(self):
        """Test RPA bridge initialization"""
        bridge = RPACommunicationBridge("bridge-001")
        
        assert bridge.bridge_id == "bridge-001"
        assert bridge.is_active is False
        assert len(bridge.available_rpas) == 0
        assert len(bridge.active_missions) == 0
        
        # Test startup
        result = await bridge.start_bridge()
        assert result is True
        assert bridge.is_active is True
    
    @pytest.mark.asyncio
    async def test_rpa_registration(self, rpa_bridge, sample_rpa_capabilities):
        """Test RPA registration with bridge"""
        result = await rpa_bridge.register_rpa(sample_rpa_capabilities)
        
        assert result is True
        assert "drone-001" in rpa_bridge.available_rpas
        assert rpa_bridge.rpa_status["drone-001"] == RPAStatus.IDLE
        assert rpa_bridge.available_rpas["drone-001"].model == "Quadcopter-X1"
    
    @pytest.mark.asyncio
    async def test_mission_creation_and_execution(self, rpa_bridge, sample_rpa_capabilities):
        """Test creating and executing autonomous missions"""
        # Register RPA first
        await rpa_bridge.register_rpa(sample_rpa_capabilities)
        
        # Create waypoints for search and rescue mission
        waypoints = [
            Waypoint(37.7749, -122.4194, 100.0, "takeoff", 30),
            Waypoint(37.7849, -122.4294, 150.0, "scan", 120),
            Waypoint(37.7749, -122.4194, 100.0, "land", 60)
        ]
        
        # Create mission
        mission_id = await rpa_bridge.create_mission(
            mission_type=MissionType.SEARCH_RESCUE,
            waypoints=waypoints,
            priority=MissionPriority.HIGH,
            required_equipment=["thermal_camera"]
        )
        
        assert mission_id is not None
        assert len(rpa_bridge.mission_queue) == 1
        
        # Execute mission
        execution_result = await rpa_bridge.execute_mission(mission_id)
        assert execution_result is True
        assert mission_id in rpa_bridge.active_missions
    
    @pytest.mark.asyncio
    async def test_mission_abort(self, rpa_bridge, sample_rpa_capabilities):
        """Test mission abort functionality"""
        await rpa_bridge.register_rpa(sample_rpa_capabilities)
        
        waypoints = [Waypoint(0.0, 0.0, 100.0, "hover", 300)]
        mission_id = await rpa_bridge.create_mission(
            MissionType.SURVEILLANCE, waypoints, MissionPriority.MEDIUM
        )
        
        await rpa_bridge.execute_mission(mission_id)
        
        # Abort mission
        abort_result = await rpa_bridge.abort_mission(mission_id, "Test abort")
        
        assert abort_result is True
        assert mission_id not in rpa_bridge.active_missions
    
    @pytest.mark.asyncio
    async def test_fleet_overview(self, rpa_bridge, sample_rpa_capabilities):
        """Test fleet overview functionality"""
        await rpa_bridge.register_rpa(sample_rpa_capabilities)
        
        overview = await rpa_bridge.get_fleet_overview()
        
        assert overview["bridge_id"] == "test-bridge-01"
        assert overview["total_rpas"] == 1
        assert overview["rpa_status_distribution"]["idle"] == 1
        assert overview["active_missions"] == 0
        assert overview["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_telemetry_updates(self, rpa_bridge, sample_rpa_capabilities):
        """Test RPA telemetry updates"""
        await rpa_bridge.register_rpa(sample_rpa_capabilities)
        
        # Create and start a mission
        waypoints = [Waypoint(40.0, -74.0, 200.0, "scan", 60)]
        mission_id = await rpa_bridge.create_mission(
            MissionType.ENVIRONMENTAL_MONITORING, waypoints
        )
        await rpa_bridge.execute_mission(mission_id)
        
        # Update telemetry
        telemetry_data = {
            "latitude": 40.0,
            "longitude": -74.0,
            "altitude": 200.0,
            "battery_level": 75.0,
            "speed": 15.0
        }
        
        result = await rpa_bridge.update_telemetry("drone-001", telemetry_data)
        
        assert result is True
        
        # Check mission status updated
        mission_status = await rpa_bridge.get_mission_status(mission_id)
        assert mission_status is not None
        assert "latitude" in mission_status.telemetry
    
    @pytest.mark.asyncio
    async def test_no_suitable_rpa_for_mission(self, rpa_bridge):
        """Test mission creation when no suitable RPA is available"""
        # Don't register any RPAs
        
        waypoints = [Waypoint(0.0, 0.0, 100.0, "scan", 60)]
        mission_id = await rpa_bridge.create_mission(
            MissionType.FIRE_SUPPRESSION,
            waypoints,
            required_equipment=["fire_suppression_system"]
        )
        
        # Should fail to create mission
        assert mission_id is None


class TestEthicsEngine:
    """Test ethics engine for AI decision making"""
    
    @pytest.fixture
    async def ethics_engine(self):
        """Create test ethics engine"""
        engine = EthicsEngine("test-ethics-01", "utilitarian")
        await engine.start_engine()
        return engine
    
    @pytest.fixture
    def sample_ethical_context(self):
        """Sample ethical decision context"""
        return EthicalContext(
            decision_id="decision-001",
            decision_type="resource_allocation",
            affected_parties=["humans", "environment"],
            potential_consequences=["help disaster victims", "use limited resources"],
            urgency_level=3,
            available_alternatives=["delay action", "seek additional resources"]
        )
    
    @pytest.mark.asyncio
    async def test_ethics_engine_initialization(self):
        """Test ethics engine initialization"""
        engine = EthicsEngine("engine-001", "deontological")
        
        assert engine.engine_id == "engine-001"
        assert engine.ethical_framework == "deontological"
        assert engine.is_active is False
        assert len(engine.ethical_rules) > 0  # Should have default rules
        
        # Test startup
        result = await engine.start_engine()
        assert result is True
        assert engine.is_active is True
    
    @pytest.mark.asyncio
    async def test_ethical_assessment_with_good_decision(self, ethics_engine, sample_ethical_context):
        """Test ethical assessment of a beneficial decision"""
        # Modify context for clearly beneficial decision
        sample_ethical_context.potential_consequences = [
            "save human lives", "protect environment", "help community"
        ]
        sample_ethical_context.affected_parties = ["humans"]
        
        assessment = await ethics_engine.assess_ethical_decision(sample_ethical_context)
        
        assert assessment.decision_id == "decision-001"
        assert assessment.ethical_score >= 0.5  # Should be reasonably ethical
        assert len(assessment.applicable_rules) > 0
        assert assessment.confidence > 0.0
        assert "recommend" in assessment.recommended_action.lower()
    
    @pytest.mark.asyncio
    async def test_ethical_assessment_with_harmful_decision(self, ethics_engine):
        """Test ethical assessment of potentially harmful decision"""
        harmful_context = EthicalContext(
            decision_id="harmful-001",
            decision_type="surveillance",
            affected_parties=["humans"],
            potential_consequences=["harm humans", "violate privacy", "cause distress"],
            urgency_level=1,
            available_alternatives=["seek consent", "use anonymized data"]
        )
        
        assessment = await ethics_engine.assess_ethical_decision(harmful_context)
        
        assert assessment.ethical_score < 0.7  # Should have low ethical score
        assert len(assessment.violations) > 0
        assert any(v == EthicalViolationType.PRIVACY_BREACH for v in assessment.violations)
        assert "reject" in assessment.recommended_action.lower() or "review" in assessment.recommended_action.lower()
    
    @pytest.mark.asyncio
    async def test_ethical_decision_making_process(self, ethics_engine, sample_ethical_context):
        """Test complete ethical decision making process"""
        decision = await ethics_engine.make_ethical_decision(
            sample_ethical_context,
            "Allocate emergency supplies to affected area"
        )
        
        assert decision.decision_id == "decision-001"
        assert decision.original_proposal == "Allocate emergency supplies to affected area"
        assert decision.assessment is not None
        assert decision.final_decision is not None
        assert len(decision.audit_log) > 0
        assert decision.implementation_status in ["approved", "pending_approval"]
    
    @pytest.mark.asyncio
    async def test_human_approval_required_for_critical_decisions(self, ethics_engine):
        """Test that critical decisions require human approval"""
        critical_context = EthicalContext(
            decision_id="critical-001",
            decision_type="autonomous_action",
            affected_parties=["humans"],
            potential_consequences=["potential harm to humans"],
            urgency_level=5,  # High urgency
            available_alternatives=["wait for human input"]
        )
        
        decision = await ethics_engine.make_ethical_decision(
            critical_context,
            "Take autonomous action that might affect human safety"
        )
        
        assert decision.human_approval_required is True
        assert decision.implementation_status == "pending_approval"
    
    @pytest.mark.asyncio
    async def test_adding_custom_ethical_rule(self, ethics_engine):
        """Test adding custom ethical rules"""
        custom_rule = EthicalRule(
            rule_id="custom_rule_001",
            principle=EthicalPrinciple.SUSTAINABILITY,
            description="Minimize environmental impact in all decisions",
            conditions={"affected_parties": ["environment"]},
            weight=0.8,
            is_absolute=False
        )
        
        result = await ethics_engine.add_ethical_rule(custom_rule)
        
        assert result is True
        assert "custom_rule_001" in ethics_engine.ethical_rules
        assert ethics_engine.ethical_rules["custom_rule_001"].weight == 0.8
    
    @pytest.mark.asyncio
    async def test_decision_approval_workflow(self, ethics_engine, sample_ethical_context):
        """Test human approval workflow for pending decisions"""
        decision = await ethics_engine.make_ethical_decision(
            sample_ethical_context,
            "Test decision requiring approval"
        )
        
        if decision.human_approval_required:
            # Test approval
            approval_result = await ethics_engine.approve_decision(
                decision.decision_id,
                "supervisor@example.com",
                "Approved after review"
            )
            
            assert approval_result is True
            assert decision.human_approver == "supervisor@example.com"
            assert decision.implementation_status == "approved"
            assert "Approved by supervisor@example.com" in decision.audit_log[-1]
    
    @pytest.mark.asyncio
    async def test_different_ethical_frameworks(self):
        """Test different ethical frameworks produce different results"""
        context = EthicalContext(
            decision_id="framework-test",
            decision_type="resource_allocation",
            affected_parties=["humans"],
            potential_consequences=["help few people significantly", "help many people minimally"],
            urgency_level=2,
            available_alternatives=["hybrid approach"]
        )
        
        # Test utilitarian framework
        util_engine = EthicsEngine("util", "utilitarian")
        await util_engine.start_engine()
        util_assessment = await util_engine.assess_ethical_decision(context)
        
        # Test deontological framework
        deont_engine = EthicsEngine("deont", "deontological")
        await deont_engine.start_engine()
        deont_assessment = await deont_engine.assess_ethical_decision(context)
        
        # Frameworks should potentially produce different scores
        # (though not necessarily - depends on specific rules and context)
        assert util_assessment.justification != deont_assessment.justification


class TestSurvivalMapGenerator:
    """Test survival map generator for hazard and resource mapping"""
    
    @pytest.fixture
    async def map_generator(self):
        """Create test map generator"""
        generator = SurvivalMapGenerator("test-generator-01")
        await generator.start_generator()
        return generator
    
    @pytest.fixture
    def sample_bounds(self):
        """Sample geographic bounds"""
        return GeographicBounds(
            north_lat=40.0,
            south_lat=39.0,
            east_lon=-121.0,
            west_lon=-122.0
        )
    
    @pytest.mark.asyncio
    async def test_map_generator_initialization(self):
        """Test map generator initialization"""
        generator = SurvivalMapGenerator("gen-001", ["satellite", "sensors"])
        
        assert generator.generator_id == "gen-001"
        assert generator.data_sources == ["satellite", "sensors"]
        assert generator.is_active is False
        assert len(generator.active_maps) == 0
        
        # Test startup
        result = await generator.start_generator()
        assert result is True
        assert generator.is_active is True
    
    @pytest.mark.asyncio
    async def test_survival_map_generation(self, map_generator, sample_bounds):
        """Test generation of survival maps with multiple layers"""
        map_types = [MapType.HAZARD, MapType.RESOURCE, MapType.SAFE_ZONE]
        
        map_id = await map_generator.generate_survival_map(
            bounds=sample_bounds,
            map_types=map_types,
            resolution_meters=200.0,
            name="Test Emergency Map"
        )
        
        assert map_id is not None
        assert map_id in map_generator.active_maps
        
        survival_map = map_generator.active_maps[map_id]
        assert survival_map.name == "Test Emergency Map"
        assert len(survival_map.layers) == len(map_types)
        assert survival_map.bounds == sample_bounds
    
    @pytest.mark.asyncio
    async def test_hazard_layer_generation(self, map_generator, sample_bounds):
        """Test specific hazard layer generation"""
        map_id = await map_generator.generate_survival_map(
            bounds=sample_bounds,
            map_types=[MapType.HAZARD],
            resolution_meters=100.0
        )
        
        survival_map = await map_generator.get_survival_map(map_id)
        hazard_layer = survival_map.get_layer("hazard_layer")
        
        assert hazard_layer is not None
        assert hazard_layer.layer_type == MapType.HAZARD
        assert len(hazard_layer.points) > 0
        
        # Check that hazard points have expected attributes
        sample_point = hazard_layer.points[0]
        assert hasattr(sample_point, 'latitude')
        assert hasattr(sample_point, 'longitude')
        assert hasattr(sample_point, 'value')
        assert sample_point.value >= 0.0
    
    @pytest.mark.asyncio
    async def test_resource_layer_generation(self, map_generator, sample_bounds):
        """Test resource layer generation"""
        map_id = await map_generator.generate_survival_map(
            bounds=sample_bounds,
            map_types=[MapType.RESOURCE],
            resolution_meters=150.0
        )
        
        survival_map = await map_generator.get_survival_map(map_id)
        resource_layer = survival_map.get_layer("resource_layer")
        
        assert resource_layer is not None
        assert resource_layer.layer_type == MapType.RESOURCE
        assert len(resource_layer.points) > 0
        
        # Check resource attributes
        for point in resource_layer.points[:5]:  # Check first 5 points
            assert "resource_types" in point.attributes
            assert isinstance(point.attributes["resource_types"], list)
            assert len(point.attributes["resource_types"]) > 0
    
    @pytest.mark.asyncio
    async def test_safe_zone_identification(self, map_generator, sample_bounds):
        """Test safe zone identification"""
        map_id = await map_generator.generate_survival_map(
            bounds=sample_bounds,
            map_types=[MapType.HAZARD, MapType.SAFE_ZONE],
            resolution_meters=100.0
        )
        
        safe_zones = await map_generator.find_safe_zones(
            map_id=map_id,
            min_safety_radius_meters=500.0,
            safety_threshold=0.7
        )
        
        assert isinstance(safe_zones, list)
        # Should find at least some safe zones in test data
        if len(safe_zones) > 0:
            safe_zone = safe_zones[0]
            assert "latitude" in safe_zone
            assert "longitude" in safe_zone
            assert "safety_score" in safe_zone
            assert safe_zone["safety_score"] >= 0.7
    
    @pytest.mark.asyncio
    async def test_map_data_query_at_point(self, map_generator, sample_bounds):
        """Test querying map data at specific coordinates"""
        map_id = await map_generator.generate_survival_map(
            bounds=sample_bounds,
            map_types=[MapType.HAZARD, MapType.RESOURCE],
            resolution_meters=100.0
        )
        
        # Query point within bounds
        query_lat = (sample_bounds.north_lat + sample_bounds.south_lat) / 2
        query_lon = (sample_bounds.east_lon + sample_bounds.west_lon) / 2
        
        data = await map_generator.get_map_data_at_point(
            map_id=map_id,
            latitude=query_lat,
            longitude=query_lon,
            radius_meters=200.0
        )
        
        assert data["map_id"] == map_id
        assert data["query_point"]["lat"] == query_lat
        assert data["query_point"]["lon"] == query_lon
        assert "hazard_layer" in data
        assert "resource_layer" in data
    
    @pytest.mark.asyncio
    async def test_evacuation_route_generation(self, map_generator, sample_bounds):
        """Test evacuation route generation"""
        map_id = await map_generator.generate_survival_map(
            bounds=sample_bounds,
            map_types=[MapType.HAZARD, MapType.SAFE_ZONE],
            resolution_meters=100.0
        )
        
        start_points = [(sample_bounds.south_lat + 0.1, sample_bounds.west_lon + 0.1)]
        end_points = [(sample_bounds.north_lat - 0.1, sample_bounds.east_lon - 0.1)]
        
        routes = await map_generator.generate_evacuation_routes(
            map_id=map_id,
            start_points=start_points,
            end_points=end_points
        )
        
        assert isinstance(routes, list)
        if len(routes) > 0:
            route = routes[0]
            assert "start" in route
            assert "end" in route
            assert "waypoints" in route
            assert "total_distance_m" in route
            assert "average_safety_score" in route
    
    @pytest.mark.asyncio
    async def test_map_export_functionality(self, map_generator, sample_bounds):
        """Test map export to different formats"""
        map_id = await map_generator.generate_survival_map(
            bounds=sample_bounds,
            map_types=[MapType.HAZARD],
            resolution_meters=200.0
        )
        
        # Test GeoJSON export
        geojson_export = await map_generator.export_map(map_id, "geojson")
        assert geojson_export is not None
        
        # Verify it's valid JSON
        geojson_data = json.loads(geojson_export)
        assert geojson_data["type"] == "FeatureCollection"
        assert "features" in geojson_data
        assert len(geojson_data["features"]) > 0
        
        # Test JSON export
        json_export = await map_generator.export_map(map_id, "json")
        assert json_export is not None
        json_data = json.loads(json_export)
        assert "map_id" in json_data
    
    @pytest.mark.asyncio
    async def test_geographic_bounds_functionality(self):
        """Test geographic bounds utility functions"""
        bounds = GeographicBounds(
            north_lat=45.0,
            south_lat=40.0,
            east_lon=-70.0,
            west_lon=-75.0
        )
        
        # Test point containment
        assert bounds.contains_point(42.5, -72.5) is True  # Inside
        assert bounds.contains_point(50.0, -72.5) is False  # Outside (north)
        assert bounds.contains_point(42.5, -60.0) is False  # Outside (east)
        
        # Test center calculation
        center_lat, center_lon = bounds.get_center()
        assert center_lat == 42.5
        assert center_lon == -72.5


class TestResilienceMonitor:
    """Test resilience monitor for network health monitoring"""
    
    @pytest.fixture
    async def resilience_monitor(self):
        """Create test resilience monitor"""
        monitor = ResilienceMonitor("test-monitor-01", "Test Network")
        await monitor.start_monitoring()
        return monitor
    
    @pytest.fixture
    def sample_network_node(self):
        """Sample network node"""
        return NetworkNode(
            node_id="sensor-001",
            node_type=NodeType.SENSOR,
            location={"lat": 37.7749, "lon": -122.4194},
            hardware_version="v2.1",
            firmware_version="fw-1.5.2",
            capabilities=["temperature", "humidity", "air_quality"],
            connections={"gateway-001", "sensor-002"}
        )
    
    @pytest.mark.asyncio
    async def test_resilience_monitor_initialization(self):
        """Test resilience monitor initialization"""
        monitor = ResilienceMonitor("monitor-001", "Production Network")
        
        assert monitor.monitor_id == "monitor-001"
        assert monitor.network_name == "Production Network"
        assert monitor.is_active is False
        assert len(monitor.topology.nodes) == 0
        
        # Test startup
        result = await monitor.start_monitoring()
        assert result is True
        assert monitor.is_active is True
    
    @pytest.mark.asyncio
    async def test_node_registration(self, resilience_monitor, sample_network_node):
        """Test network node registration"""
        result = await resilience_monitor.register_node(sample_network_node)
        
        assert result is True
        assert "sensor-001" in resilience_monitor.topology.nodes
        assert resilience_monitor.topology.nodes["sensor-001"].node_type == NodeType.SENSOR
        assert resilience_monitor.metrics["nodes_monitored"] == 1
    
    @pytest.mark.asyncio
    async def test_health_metric_reporting(self, resilience_monitor, sample_network_node):
        """Test health metric reporting and threshold checking"""
        await resilience_monitor.register_node(sample_network_node)
        
        # Report normal metric
        normal_metric = HealthMetric(
            node_id="sensor-001",
            metric_name="battery_level",
            value=75.0,
            unit="percent"
        )
        
        result = await resilience_monitor.report_health_metric(normal_metric)
        assert result is True
        
        # Report critical metric that should trigger alert
        critical_metric = HealthMetric(
            node_id="sensor-001",
            metric_name="battery_level",
            value=5.0,  # Below critical threshold
            unit="percent"
        )
        
        await resilience_monitor.report_health_metric(critical_metric)
        
        # Should have generated an alert
        assert len(resilience_monitor.active_alerts) > 0
        
        # Check node health status updated
        node_health = await resilience_monitor.get_node_health("sensor-001")
        assert node_health is not None
        assert node_health["health_status"] in ["critical", "warning", "degraded"]
    
    @pytest.mark.asyncio
    async def test_network_health_overview(self, resilience_monitor, sample_network_node):
        """Test network health overview generation"""
        await resilience_monitor.register_node(sample_network_node)
        
        # Add a healthy metric
        metric = HealthMetric("sensor-001", "cpu_usage", 25.0, "percent")
        await resilience_monitor.report_health_metric(metric)
        
        health_overview = await resilience_monitor.get_network_health()
        
        assert health_overview["total_nodes"] == 1
        assert "overall_health" in health_overview
        assert "health_score" in health_overview
        assert "node_status_counts" in health_overview
        assert health_overview["health_score"] >= 0.0
        assert health_overview["health_score"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_connection_reporting_and_loss_detection(self, resilience_monitor, sample_network_node):
        """Test connection reporting and loss detection"""
        await resilience_monitor.register_node(sample_network_node)
        
        # Report initial connections
        initial_connections = {"gateway-001", "sensor-002", "sensor-003"}
        result = await resilience_monitor.report_node_connection("sensor-001", initial_connections)
        assert result is True
        
        # Report connection loss
        reduced_connections = {"gateway-001"}  # Lost connections to sensors
        await resilience_monitor.report_node_connection("sensor-001", reduced_connections)
        
        # Should detect connection loss and generate alerts
        node_alerts = [
            alert for alert in resilience_monitor.active_alerts.values()
            if alert.node_id == "sensor-001"
        ]
        
        # Should have alerts about lost connections
        connection_alerts = [
            alert for alert in node_alerts
            if "connection" in alert.message.lower()
        ]
        assert len(connection_alerts) > 0
    
    @pytest.mark.asyncio
    async def test_alert_management(self, resilience_monitor, sample_network_node):
        """Test alert acknowledgment and resolution"""
        await resilience_monitor.register_node(sample_network_node)
        
        # Generate an alert by reporting critical metric
        critical_metric = HealthMetric(
            node_id="sensor-001",
            metric_name="temperature",
            value=95.0,  # Above critical threshold
            unit="celsius"
        )
        await resilience_monitor.report_health_metric(critical_metric)
        
        # Should have at least one alert
        assert len(resilience_monitor.active_alerts) > 0
        
        alert_id = list(resilience_monitor.active_alerts.keys())[0]
        alert = resilience_monitor.active_alerts[alert_id]
        
        # Test acknowledgment
        ack_result = await resilience_monitor.acknowledge_alert(alert_id, "operator@example.com")
        assert ack_result is True
        assert alert.acknowledged is True
        
        # Test resolution
        resolve_result = await resilience_monitor.resolve_alert(
            alert_id, "technician@example.com", "Replaced faulty temperature sensor"
        )
        assert resolve_result is True
        assert alert.resolved is True
        assert alert.resolution_time is not None
    
    @pytest.mark.asyncio
    async def test_healing_operation_triggering(self, resilience_monitor, sample_network_node):
        """Test automatic and manual healing operations"""
        await resilience_monitor.register_node(sample_network_node)
        
        # Test manual healing operation
        from cehsn.resilience_monitor import HealingAction
        
        operation_id = await resilience_monitor.trigger_healing_operation(
            node_id="sensor-001",
            action=HealingAction.RESTART_NODE,
            parameters={"force": True}
        )
        
        assert operation_id is not None
        assert operation_id in resilience_monitor.healing_operations
        
        operation = resilience_monitor.healing_operations[operation_id]
        assert operation.node_id == "sensor-001"
        assert operation.action == HealingAction.RESTART_NODE
        assert operation.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_network_topology_updates(self, resilience_monitor):
        """Test network topology tracking and updates"""
        # Create multiple nodes with different types
        nodes = [
            NetworkNode("sensor-001", NodeType.SENSOR, connections={"gateway-001"}),
            NetworkNode("gateway-001", NodeType.GATEWAY, connections={"sensor-001", "base-001"}),
            NetworkNode("base-001", NodeType.BASE_STATION, connections={"gateway-001"})
        ]
        
        for node in nodes:
            await resilience_monitor.register_node(node)
        
        # Check topology was updated
        assert len(resilience_monitor.topology.nodes) == 3
        assert len(resilience_monitor.topology.connections) == 3
        
        # Test connectivity calculation
        network_health = await resilience_monitor.get_network_health()
        connectivity = network_health.get("network_connectivity", 0)
        assert connectivity > 0  # Should have some connectivity
    
    @pytest.mark.asyncio
    async def test_performance_metrics_tracking(self, resilience_monitor, sample_network_node):
        """Test performance metrics tracking and updates"""
        await resilience_monitor.register_node(sample_network_node)
        
        initial_metrics = resilience_monitor.metrics.copy()
        
        # Trigger some operations that should update metrics
        metric = HealthMetric("sensor-001", "signal_strength", -95.0, "dBm")
        await resilience_monitor.report_health_metric(metric)
        
        # Check metrics were updated
        updated_metrics = resilience_monitor.metrics
        assert updated_metrics["nodes_monitored"] >= initial_metrics["nodes_monitored"]
        
        # If alerts were generated, alert count should increase
        if len(resilience_monitor.active_alerts) > 0:
            assert updated_metrics["alerts_generated"] > initial_metrics["alerts_generated"]


class TestCEHSNIntegration:
    """Integration tests for complete CEHSN system"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_emergency_response_scenario(self):
        """Test complete emergency response scenario using all CEHSN components"""
        # Initialize all components
        inference_engine = OrbitalInferenceEngine("emergency-cubesat-01")
        await inference_engine.start_inference_engine()
        
        rpa_bridge = RPACommunicationBridge("emergency-rpa-bridge")
        await rpa_bridge.start_bridge()
        
        ethics_engine = EthicsEngine("emergency-ethics", "utilitarian")
        await ethics_engine.start_engine()
        
        map_generator = SurvivalMapGenerator("emergency-maps")
        await map_generator.start_generator()
        
        resilience_monitor = ResilienceMonitor("emergency-monitor", "Emergency Network")
        await resilience_monitor.start_monitoring()
        
        # Scenario: Wildfire detected by orbital inference
        fire_location = GeospatialCoordinate(latitude=34.0522, longitude=-118.2437)
        fire_reading = SensorReading(
            sensor_id="thermal-sat-01",
            sensor_type="infrared",
            reading_value=65.0,  # High temperature
            units="celsius",
            coordinate=fire_location
        )
        
        # Step 1: Detect anomaly
        fire_detection = await inference_engine.process_sensor_reading(fire_reading)
        assert fire_detection is not None
        assert fire_detection.anomaly_type in [AnomalyType.WILDFIRE, AnomalyType.ATMOSPHERIC_DISTURBANCE]
        
        # Step 2: Make ethical decision about response
        response_context = EthicalContext(
            decision_id="fire-response-001",
            decision_type="emergency_response",
            affected_parties=["humans", "environment", "wildlife"],
            potential_consequences=["save lives", "protect property", "use resources"],
            urgency_level=4,
            available_alternatives=["immediate response", "wait for confirmation"]
        )
        
        ethical_decision = await ethics_engine.make_ethical_decision(
            response_context,
            "Deploy fire suppression drones immediately"
        )
        
        assert ethical_decision.implementation_status in ["approved", "pending_approval"]
        
        # Step 3: Generate survival map for area
        fire_bounds = GeographicBounds(
            north_lat=34.1522,
            south_lat=33.9522,
            east_lon=-118.1437,
            west_lon=-118.3437
        )
        
        emergency_map_id = await map_generator.generate_survival_map(
            bounds=fire_bounds,
            map_types=[MapType.HAZARD, MapType.SAFE_ZONE, MapType.EVACUATION_ROUTE],
            resolution_meters=100.0,
            name="Wildfire Emergency Response Map"
        )
        
        assert emergency_map_id is not None
        
        # Step 4: Deploy RPA if ethical decision approved
        if ethical_decision.implementation_status == "approved":
            # Register fire suppression drone
            fire_drone = RPACapabilities(
                rpa_id="fire-drone-01",
                model="FireSuppressionX1",
                max_flight_time_minutes=90,
                max_range_km=30.0,
                max_payload_kg=10.0,
                sensors=["thermal_camera", "smoke_detector"],
                communication_systems=["satellite"],
                special_equipment=["fire_suppression_system"]
            )
            
            await rpa_bridge.register_rpa(fire_drone)
            
            # Create suppression mission
            suppression_waypoints = [
                Waypoint(34.0522, -118.2437, 200.0, "scan", 60),
                Waypoint(34.0522, -118.2437, 100.0, "suppress", 300),
                Waypoint(34.0500, -118.2400, 200.0, "monitor", 120)
            ]
            
            mission_id = await rpa_bridge.create_mission(
                mission_type=MissionType.FIRE_SUPPRESSION,
                waypoints=suppression_waypoints,
                priority=MissionPriority.EMERGENCY,
                required_equipment=["fire_suppression_system"]
            )
            
            assert mission_id is not None
            
            # Execute mission
            execution_result = await rpa_bridge.execute_mission(mission_id)
            assert execution_result is True
        
        # Step 5: Monitor network health during emergency
        emergency_sensor = NetworkNode(
            node_id="emergency-sensor-01",
            node_type=NodeType.SENSOR,
            location={"lat": 34.0522, "lon": -118.2437},
            capabilities=["temperature", "smoke_detection", "air_quality"]
        )
        
        await resilience_monitor.register_node(emergency_sensor)
        
        # Simulate high-stress metrics
        stress_metric = HealthMetric(
            node_id="emergency-sensor-01",
            metric_name="temperature",
            value=80.0,  # High temperature due to fire
            unit="celsius"
        )
        
        await resilience_monitor.report_health_metric(stress_metric)
        
        # Check that system is monitoring the emergency
        network_health = await resilience_monitor.get_network_health()
        assert network_health["total_nodes"] >= 1
        
        # Verify integration worked
        assert fire_detection.confidence_score > 0.3
        assert ethical_decision.assessment.ethical_score >= 0.0
        assert emergency_map_id in map_generator.active_maps
        
        # Clean up
        await inference_engine.stop_inference_engine()
        await rpa_bridge.stop_bridge()
        await ethics_engine.stop_engine()
        await map_generator.stop_generator()
        await resilience_monitor.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_multi_component_data_flow(self):
        """Test data flow between multiple CEHSN components"""
        # This test verifies that components can work together
        # and share data appropriately
        
        map_gen = SurvivalMapGenerator("integration-maps")
        await map_gen.start_generator()
        
        resilience_mon = ResilienceMonitor("integration-monitor")
        await resilience_mon.start_monitoring()
        
        # Generate map with hazards
        bounds = GeographicBounds(40.0, 39.0, -73.0, -74.0)
        map_id = await map_gen.generate_survival_map(
            bounds, [MapType.HAZARD], name="Integration Test Map"
        )
        
        # Query map data
        map_data = await map_gen.get_map_data_at_point(map_id, 39.5, -73.5, 500.0)
        
        # Use map data to inform network monitoring
        sensor_node = NetworkNode(
            node_id="integration-sensor",
            node_type=NodeType.SENSOR,
            location={"lat": 39.5, "lon": -73.5}
        )
        
        await resilience_mon.register_node(sensor_node)
        
        # Based on hazard data, simulate appropriate sensor readings
        if "hazard_layer" in map_data:
            hazard_data = map_data["hazard_layer"]
            if hazard_data.get("count", 0) > 0:
                # Simulate elevated readings due to hazards
                hazard_metric = HealthMetric(
                    node_id="integration-sensor",
                    metric_name="environmental_hazard",
                    value=0.8,
                    unit="normalized"
                )
                await resilience_mon.report_health_metric(hazard_metric)
        
        # Verify data flowed correctly
        node_health = await resilience_mon.get_node_health("integration-sensor")
        assert node_health is not None
        assert "latest_metrics" in node_health
        
        await map_gen.stop_generator()
        await resilience_mon.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_system_performance_under_load(self):
        """Test CEHSN system performance under high load"""
        # Initialize components
        inference_engine = OrbitalInferenceEngine("load-test-cubesat")
        await inference_engine.start_inference_engine()
        
        # Generate many sensor readings rapidly
        readings = []
        for i in range(100):
            reading = SensorReading(
                sensor_id=f"sensor-{i:03d}",
                sensor_type="radiation",
                reading_value=500.0 + i * 5,  # Varying values
                units="cpm",
                coordinate=GeospatialCoordinate(
                    latitude=40.0 + (i * 0.01),
                    longitude=-74.0 + (i * 0.01)
                )
            )
            readings.append(reading)
        
        # Process readings and measure performance
        start_time = datetime.utcnow()
        
        results = []
        for reading in readings:
            result = await inference_engine.process_sensor_reading(reading)
            if result:
                results.append(result)
        
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        # Verify performance
        assert processing_time < 30.0  # Should process 100 readings in under 30 seconds
        assert len(results) > 0  # Should detect some anomalies
        
        # Check engine status
        status = inference_engine.get_engine_status()
        assert status["total_inferences"] == len(results)
        
        await inference_engine.stop_inference_engine()


# Error handling and edge case tests
class TestCEHSNErrorHandling:
    """Test error handling and edge cases in CEHSN components"""
    
    @pytest.mark.asyncio
    async def test_orbital_inference_invalid_sensor_data(self):
        """Test orbital inference with invalid sensor data"""
        engine = OrbitalInferenceEngine("error-test")
        await engine.start_inference_engine()
        
        # Test with invalid sensor type
        invalid_reading = SensorReading(
            sensor_id="invalid-001",
            sensor_type="unknown_sensor_type",
            reading_value=100.0,
            units="unknown",
            coordinate=GeospatialCoordinate(0.0, 0.0)
        )
        
        result = await engine.process_sensor_reading(invalid_reading)
        assert result is None  # Should not process unknown sensor types
        
        await engine.stop_inference_engine()
    
    @pytest.mark.asyncio
    async def test_rpa_bridge_mission_with_no_drones(self):
        """Test RPA bridge behavior when no drones are available"""
        bridge = RPACommunicationBridge("no-drones-test")
        await bridge.start_bridge()
        
        # Try to create mission without any registered RPAs
        waypoints = [Waypoint(0.0, 0.0, 100.0, "scan", 60)]
        mission_id = await bridge.create_mission(
            MissionType.SURVEILLANCE, waypoints, MissionPriority.HIGH
        )
        
        assert mission_id is None  # Should fail gracefully
        
        await bridge.stop_bridge()
    
    @pytest.mark.asyncio
    async def test_ethics_engine_with_empty_context(self):
        """Test ethics engine with minimal context"""
        engine = EthicsEngine("empty-context-test")
        await engine.start_engine()
        
        minimal_context = EthicalContext(
            decision_id="minimal-001",
            decision_type="unknown",
            affected_parties=[],
            potential_consequences=[],
            urgency_level=1,
            available_alternatives=[]
        )
        
        # Should still produce some assessment
        assessment = await engine.assess_ethical_decision(minimal_context)
        assert assessment is not None
        assert assessment.ethical_score >= 0.0
        assert assessment.ethical_score <= 1.0
        
        await engine.stop_engine()
    
    @pytest.mark.asyncio
    async def test_map_generator_invalid_bounds(self):
        """Test map generator with invalid geographic bounds"""
        generator = SurvivalMapGenerator("invalid-bounds-test")
        await generator.start_generator()
        
        # Invalid bounds (south > north)
        invalid_bounds = GeographicBounds(
            north_lat=30.0,
            south_lat=40.0,  # Invalid: south > north
            east_lon=-70.0,
            west_lon=-75.0
        )
        
        # Should handle gracefully
        map_id = await generator.generate_survival_map(
            invalid_bounds, [MapType.HAZARD]
        )
        
        # Might return None or handle the error gracefully
        # The exact behavior depends on implementation
        
        await generator.stop_generator()
    
    @pytest.mark.asyncio
    async def test_resilience_monitor_duplicate_node_registration(self):
        """Test resilience monitor handling duplicate node registrations"""
        monitor = ResilienceMonitor("duplicate-test")
        await monitor.start_monitoring()
        
        node = NetworkNode("duplicate-node", NodeType.SENSOR)
        
        # Register node twice
        result1 = await monitor.register_node(node)
        result2 = await monitor.register_node(node)
        
        assert result1 is True
        # Second registration should either succeed (update) or fail gracefully
        assert result2 in [True, False]
        
        # Should still have only one instance
        assert len(monitor.topology.nodes) == 1
        
        await monitor.stop_monitoring()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
