"""
RPA Communication Bridge for CubeSat-Enabled Hybrid Survival Network (CEHSN)
RPA workflow for autonomous mission tasking (drone coordination)
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RPAStatus(Enum):
    """Status of RPA (drone) operations"""
    IDLE = "idle"
    ACTIVE = "active"
    MISSION = "mission"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"
    OFFLINE = "offline"


class MissionType(Enum):
    """Types of autonomous missions"""
    SEARCH_RESCUE = "search_rescue"
    FIRE_SUPPRESSION = "fire_suppression"
    SURVEILLANCE = "surveillance"
    CARGO_DELIVERY = "cargo_delivery"
    ENVIRONMENTAL_MONITORING = "environmental_monitoring"
    COMMUNICATION_RELAY = "communication_relay"
    DAMAGE_ASSESSMENT = "damage_assessment"
    MEDICAL_EVACUATION = "medical_evacuation"


class MissionPriority(Enum):
    """Mission priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class RPACapabilities:
    """RPA capabilities and specifications"""
    rpa_id: str
    model: str
    max_flight_time_minutes: int
    max_range_km: float
    max_payload_kg: float
    sensors: List[str]
    communication_systems: List[str]
    special_equipment: List[str] = field(default_factory=list)
    weather_limitations: Dict[str, float] = field(default_factory=dict)


@dataclass
class Waypoint:
    """Navigation waypoint"""
    latitude: float
    longitude: float
    altitude_meters: float
    action: str = "flyto"  # "flyto", "hover", "land", "takeoff", "scan"
    duration_seconds: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionPlan:
    """Autonomous mission plan"""
    mission_id: str
    mission_type: MissionType
    priority: MissionPriority
    assigned_rpa: str
    waypoints: List[Waypoint]
    estimated_duration_minutes: int
    required_equipment: List[str] = field(default_factory=list)
    safety_constraints: Dict[str, Any] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)
    contingency_plans: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_start: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.mission_id:
            self.mission_id = f"mission_{uuid.uuid4().hex[:8]}"


@dataclass
class MissionStatus:
    """Real-time mission status"""
    mission_id: str
    rpa_id: str
    status: str  # "planning", "executing", "completed", "failed", "aborted"
    current_waypoint: int
    progress_percent: float
    estimated_completion: datetime
    telemetry: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.utcnow)


class RPACommunicationBridge:
    """
    RPA Communication Bridge for autonomous drone coordination
    Handles mission planning, task assignment, and real-time control
    """
    
    def __init__(self, bridge_id: str):
        self.bridge_id = bridge_id
        self.is_active = False
        
        # RPA fleet management
        self.available_rpas: Dict[str, RPACapabilities] = {}
        self.rpa_status: Dict[str, RPAStatus] = {}
        self.active_missions: Dict[str, MissionPlan] = {}
        self.mission_status: Dict[str, MissionStatus] = {}
        
        # Mission queue
        self.mission_queue: List[MissionPlan] = []
        
        # Communication parameters
        self.max_communication_range_km = 50.0
        self.backup_communication_methods = ["satellite", "mesh_network"]
        
        # Performance metrics
        self.metrics = {
            "missions_completed": 0,
            "missions_failed": 0,
            "total_flight_time": 0.0,
            "average_success_rate": 0.0
        }
        
        logger.info(f"RPA Communication Bridge {bridge_id} initialized")
    
    async def start_bridge(self) -> bool:
        """Start the RPA communication bridge"""
        try:
            self.is_active = True
            
            # Start background tasks
            await self._start_mission_scheduler()
            await self._start_health_monitor()
            
            logger.info(f"RPA Communication Bridge {self.bridge_id} started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start RPA bridge: {e}")
            return False
    
    async def stop_bridge(self) -> bool:
        """Stop the RPA communication bridge"""
        self.is_active = False
        
        # Safely abort active missions
        for mission_id in list(self.active_missions.keys()):
            await self.abort_mission(mission_id, "Bridge shutdown")
        
        logger.info(f"RPA Communication Bridge {self.bridge_id} stopped")
        return True
    
    async def register_rpa(self, capabilities: RPACapabilities) -> bool:
        """Register a new RPA with the bridge"""
        try:
            self.available_rpas[capabilities.rpa_id] = capabilities
            self.rpa_status[capabilities.rpa_id] = RPAStatus.IDLE
            
            logger.info(f"RPA {capabilities.rpa_id} registered successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register RPA {capabilities.rpa_id}: {e}")
            return False
    
    async def unregister_rpa(self, rpa_id: str) -> bool:
        """Unregister an RPA from the bridge"""
        try:
            # Check if RPA is on an active mission
            active_mission = None
            for mission_id, plan in self.active_missions.items():
                if plan.assigned_rpa == rpa_id:
                    active_mission = mission_id
                    break
            
            if active_mission:
                await self.abort_mission(active_mission, "RPA unregistered")
            
            # Remove from registry
            self.available_rpas.pop(rpa_id, None)
            self.rpa_status.pop(rpa_id, None)
            
            logger.info(f"RPA {rpa_id} unregistered")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unregister RPA {rpa_id}: {e}")
            return False
    
    async def create_mission(self, mission_type: MissionType, waypoints: List[Waypoint], 
                           priority: MissionPriority = MissionPriority.MEDIUM,
                           required_equipment: List[str] = None,
                           safety_constraints: Dict[str, Any] = None) -> Optional[str]:
        """Create a new autonomous mission"""
        try:
            # Select best RPA for mission
            suitable_rpa = await self._select_optimal_rpa(
                mission_type, required_equipment or [], waypoints
            )
            
            if not suitable_rpa:
                logger.warning(f"No suitable RPA available for {mission_type.value}")
                return None
            
            # Calculate mission parameters
            estimated_duration = self._calculate_mission_duration(waypoints, suitable_rpa)
            
            # Create mission plan
            mission_plan = MissionPlan(
                mission_id="",  # Will be generated in __post_init__
                mission_type=mission_type,
                priority=priority,
                assigned_rpa=suitable_rpa,
                waypoints=waypoints,
                estimated_duration_minutes=estimated_duration,
                required_equipment=required_equipment or [],
                safety_constraints=safety_constraints or {},
                success_criteria=self._generate_success_criteria(mission_type),
                contingency_plans=self._generate_contingency_plans(mission_type)
            )
            
            # Add to mission queue
            self.mission_queue.append(mission_plan)
            self._sort_mission_queue()
            
            logger.info(f"Mission {mission_plan.mission_id} created for RPA {suitable_rpa}")
            return mission_plan.mission_id
            
        except Exception as e:
            logger.error(f"Failed to create mission: {e}")
            return None
    
    async def execute_mission(self, mission_id: str) -> bool:
        """Execute a planned mission"""
        try:
            # Find mission in queue
            mission_plan = None
            for i, plan in enumerate(self.mission_queue):
                if plan.mission_id == mission_id:
                    mission_plan = self.mission_queue.pop(i)
                    break
            
            if not mission_plan:
                logger.error(f"Mission {mission_id} not found in queue")
                return False
            
            # Check RPA availability
            rpa_id = mission_plan.assigned_rpa
            if self.rpa_status.get(rpa_id) != RPAStatus.IDLE:
                logger.warning(f"RPA {rpa_id} not available for mission {mission_id}")
                # Try to reassign
                new_rpa = await self._select_optimal_rpa(
                    mission_plan.mission_type, 
                    mission_plan.required_equipment,
                    mission_plan.waypoints
                )
                if not new_rpa:
                    # Put mission back in queue
                    self.mission_queue.append(mission_plan)
                    self._sort_mission_queue()
                    return False
                
                mission_plan.assigned_rpa = new_rpa
                rpa_id = new_rpa
            
            # Start mission execution
            self.active_missions[mission_id] = mission_plan
            self.rpa_status[rpa_id] = RPAStatus.MISSION
            
            # Create mission status
            self.mission_status[mission_id] = MissionStatus(
                mission_id=mission_id,
                rpa_id=rpa_id,
                status="executing",
                current_waypoint=0,
                progress_percent=0.0,
                estimated_completion=datetime.utcnow() + timedelta(
                    minutes=mission_plan.estimated_duration_minutes
                )
            )
            
            # Send mission to RPA (simulated)
            success = await self._send_mission_to_rpa(rpa_id, mission_plan)
            
            if success:
                logger.info(f"Mission {mission_id} started on RPA {rpa_id}")
                return True
            else:
                # Clean up failed mission
                await self._cleanup_failed_mission(mission_id)
                return False
                
        except Exception as e:
            logger.error(f"Failed to execute mission {mission_id}: {e}")
            return False
    
    async def abort_mission(self, mission_id: str, reason: str = "User requested") -> bool:
        """Abort an active mission"""
        try:
            if mission_id not in self.active_missions:
                logger.warning(f"Mission {mission_id} not active")
                return False
            
            mission_plan = self.active_missions[mission_id]
            rpa_id = mission_plan.assigned_rpa
            
            # Send abort command to RPA
            await self._send_abort_command(rpa_id, mission_id, reason)
            
            # Update mission status
            if mission_id in self.mission_status:
                self.mission_status[mission_id].status = "aborted"
                self.mission_status[mission_id].issues.append(f"Aborted: {reason}")
            
            # Clean up
            await self._cleanup_mission(mission_id, "aborted")
            
            logger.info(f"Mission {mission_id} aborted: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to abort mission {mission_id}: {e}")
            return False
    
    async def get_mission_status(self, mission_id: str) -> Optional[MissionStatus]:
        """Get current status of a mission"""
        return self.mission_status.get(mission_id)
    
    async def get_rpa_status(self, rpa_id: str) -> Optional[RPAStatus]:
        """Get current status of an RPA"""
        return self.rpa_status.get(rpa_id)
    
    async def get_fleet_overview(self) -> Dict[str, Any]:
        """Get overview of entire RPA fleet"""
        total_rpas = len(self.available_rpas)
        status_counts = {}
        
        for status in self.rpa_status.values():
            status_key = status.value
            status_counts[status_key] = status_counts.get(status_key, 0) + 1
        
        return {
            "bridge_id": self.bridge_id,
            "total_rpas": total_rpas,
            "rpa_status_distribution": status_counts,
            "active_missions": len(self.active_missions),
            "queued_missions": len(self.mission_queue),
            "performance_metrics": self.metrics,
            "is_active": self.is_active
        }
    
    async def update_telemetry(self, rpa_id: str, telemetry_data: Dict[str, Any]) -> bool:
        """Update RPA telemetry data"""
        try:
            # Find active mission for this RPA
            active_mission_id = None
            for mission_id, plan in self.active_missions.items():
                if plan.assigned_rpa == rpa_id:
                    active_mission_id = mission_id
                    break
            
            if active_mission_id and active_mission_id in self.mission_status:
                # Update mission status with telemetry
                mission_status = self.mission_status[active_mission_id]
                mission_status.telemetry.update(telemetry_data)
                mission_status.last_update = datetime.utcnow()
                
                # Update progress if position data available
                if "latitude" in telemetry_data and "longitude" in telemetry_data:
                    await self._update_mission_progress(active_mission_id, telemetry_data)
            
            logger.debug(f"Telemetry updated for RPA {rpa_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update telemetry for RPA {rpa_id}: {e}")
            return False
    
    # Private helper methods
    
    async def _select_optimal_rpa(self, mission_type: MissionType, 
                                 required_equipment: List[str],
                                 waypoints: List[Waypoint]) -> Optional[str]:
        """Select the best RPA for a given mission"""
        available_rpas = [
            rpa_id for rpa_id, status in self.rpa_status.items() 
            if status == RPAStatus.IDLE
        ]
        
        if not available_rpas:
            return None
        
        # Calculate mission requirements
        total_distance = self._calculate_total_distance(waypoints)
        
        best_rpa = None
        best_score = -1
        
        for rpa_id in available_rpas:
            capabilities = self.available_rpas[rpa_id]
            score = 0
            
            # Check range requirement
            if capabilities.max_range_km >= total_distance:
                score += 10
            else:
                continue  # Cannot complete mission
            
            # Check equipment requirements
            has_all_equipment = all(
                eq in capabilities.sensors + capabilities.special_equipment
                for eq in required_equipment
            )
            if has_all_equipment:
                score += 5
            
            # Mission type suitability
            mission_suitability = self._get_mission_suitability(mission_type, capabilities)
            score += mission_suitability
            
            # Prefer RPAs with longer flight time
            score += min(5, capabilities.max_flight_time_minutes / 60)
            
            if score > best_score:
                best_score = score
                best_rpa = rpa_id
        
        return best_rpa
    
    def _calculate_total_distance(self, waypoints: List[Waypoint]) -> float:
        """Calculate total distance of waypoint path"""
        if len(waypoints) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(1, len(waypoints)):
            prev_wp = waypoints[i-1]
            curr_wp = waypoints[i]
            
            # Haversine formula for distance
            distance = self._haversine_distance(
                prev_wp.latitude, prev_wp.longitude,
                curr_wp.latitude, curr_wp.longitude
            )
            total_distance += distance
        
        return total_distance
    
    def _haversine_distance(self, lat1: float, lon1: float, 
                           lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        import math
        
        R = 6371.0  # Earth radius in km
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _calculate_mission_duration(self, waypoints: List[Waypoint], rpa_id: str) -> int:
        """Calculate estimated mission duration in minutes"""
        capabilities = self.available_rpas[rpa_id]
        total_distance = self._calculate_total_distance(waypoints)
        
        # Assume average speed of 50 km/h
        flight_time = (total_distance / 50.0) * 60  # minutes
        
        # Add time for waypoint actions
        action_time = sum(wp.duration_seconds for wp in waypoints) / 60  # minutes
        
        # Add 20% buffer
        estimated_time = int((flight_time + action_time) * 1.2)
        
        return min(estimated_time, capabilities.max_flight_time_minutes)
    
    def _get_mission_suitability(self, mission_type: MissionType, 
                               capabilities: RPACapabilities) -> int:
        """Get suitability score for mission type and RPA capabilities"""
        suitability_map = {
            MissionType.SEARCH_RESCUE: {"thermal_camera": 3, "high_resolution_camera": 2},
            MissionType.FIRE_SUPPRESSION: {"fire_suppression_system": 5, "thermal_camera": 2},
            MissionType.SURVEILLANCE: {"high_resolution_camera": 3, "night_vision": 2},
            MissionType.CARGO_DELIVERY: {"cargo_bay": 5, "precision_landing": 2},
            MissionType.ENVIRONMENTAL_MONITORING: {"air_quality_sensor": 3, "weather_station": 2},
            MissionType.COMMUNICATION_RELAY: {"communication_repeater": 5, "high_gain_antenna": 2},
            MissionType.DAMAGE_ASSESSMENT: {"high_resolution_camera": 3, "lidar": 3},
            MissionType.MEDICAL_EVACUATION: {"medical_kit": 5, "stabilization_platform": 3}
        }
        
        required_equipment = suitability_map.get(mission_type, {})
        score = 0
        
        all_equipment = capabilities.sensors + capabilities.special_equipment
        for equipment, points in required_equipment.items():
            if equipment in all_equipment:
                score += points
        
        return score
    
    def _generate_success_criteria(self, mission_type: MissionType) -> List[str]:
        """Generate success criteria based on mission type"""
        criteria_map = {
            MissionType.SEARCH_RESCUE: [
                "All waypoints visited successfully",
                "Search pattern completed",
                "Any detected persons reported to command"
            ],
            MissionType.FIRE_SUPPRESSION: [
                "Fire suppression payload deployed",
                "Target area covered",
                "Fire status assessed and reported"
            ],
            MissionType.SURVEILLANCE: [
                "All surveillance points monitored",
                "Images/video captured and transmitted",
                "No detection by hostile forces"
            ],
            MissionType.CARGO_DELIVERY: [
                "Cargo delivered to specified location",
                "Delivery confirmed by recipient",
                "RPA returned safely to base"
            ]
        }
        
        return criteria_map.get(mission_type, ["Mission completed successfully"])
    
    def _generate_contingency_plans(self, mission_type: MissionType) -> List[str]:
        """Generate contingency plans based on mission type"""
        base_plans = [
            "Return to home if communication lost for >5 minutes",
            "Emergency landing if battery <20%",
            "Abort mission if weather conditions deteriorate"
        ]
        
        mission_specific = {
            MissionType.SEARCH_RESCUE: [
                "Alert rescue teams if person detected",
                "Drop emergency supplies if safe landing available"
            ],
            MissionType.FIRE_SUPPRESSION: [
                "Retreat if fire intensity exceeds safe limits",
                "Coordinate with ground fire teams"
            ]
        }
        
        return base_plans + mission_specific.get(mission_type, [])
    
    def _sort_mission_queue(self):
        """Sort mission queue by priority and creation time"""
        self.mission_queue.sort(
            key=lambda m: (-m.priority.value, m.created_at)
        )
    
    async def _send_mission_to_rpa(self, rpa_id: str, mission_plan: MissionPlan) -> bool:
        """Send mission commands to RPA (simulated)"""
        # In a real implementation, this would use actual communication protocols
        logger.info(f"Sending mission {mission_plan.mission_id} to RPA {rpa_id}")
        
        # Simulate mission transmission delay
        await asyncio.sleep(0.1)
        
        # Simulate 95% success rate
        import random
        return random.random() > 0.05
    
    async def _send_abort_command(self, rpa_id: str, mission_id: str, reason: str):
        """Send abort command to RPA"""
        logger.info(f"Sending abort command to RPA {rpa_id} for mission {mission_id}")
        # In a real implementation, this would send actual abort commands
        await asyncio.sleep(0.1)
    
    async def _cleanup_mission(self, mission_id: str, final_status: str):
        """Clean up completed or aborted mission"""
        if mission_id in self.active_missions:
            mission_plan = self.active_missions.pop(mission_id)
            rpa_id = mission_plan.assigned_rpa
            
            # Update RPA status
            self.rpa_status[rpa_id] = RPAStatus.IDLE
            
            # Update metrics
            if final_status == "completed":
                self.metrics["missions_completed"] += 1
                self.metrics["total_flight_time"] += mission_plan.estimated_duration_minutes
            elif final_status in ["failed", "aborted"]:
                self.metrics["missions_failed"] += 1
            
            # Update success rate
            total_missions = self.metrics["missions_completed"] + self.metrics["missions_failed"]
            if total_missions > 0:
                self.metrics["average_success_rate"] = self.metrics["missions_completed"] / total_missions
    
    async def _cleanup_failed_mission(self, mission_id: str):
        """Clean up a mission that failed to start"""
        await self._cleanup_mission(mission_id, "failed")
        
        if mission_id in self.mission_status:
            self.mission_status[mission_id].status = "failed"
    
    async def _update_mission_progress(self, mission_id: str, telemetry: Dict[str, Any]):
        """Update mission progress based on telemetry"""
        if mission_id not in self.mission_status:
            return
        
        mission_status = self.mission_status[mission_id]
        mission_plan = self.active_missions[mission_id]
        
        current_lat = telemetry.get("latitude")
        current_lon = telemetry.get("longitude")
        
        if current_lat is None or current_lon is None:
            return
        
        # Find closest waypoint
        min_distance = float('inf')
        closest_waypoint_idx = mission_status.current_waypoint
        
        for i, waypoint in enumerate(mission_plan.waypoints):
            distance = self._haversine_distance(
                current_lat, current_lon,
                waypoint.latitude, waypoint.longitude
            )
            
            if distance < min_distance:
                min_distance = distance
                closest_waypoint_idx = i
        
        # Update progress
        mission_status.current_waypoint = closest_waypoint_idx
        total_waypoints = len(mission_plan.waypoints)
        if total_waypoints > 0:
            mission_status.progress_percent = (closest_waypoint_idx / total_waypoints) * 100
        
        # Check if mission completed
        if (closest_waypoint_idx >= total_waypoints - 1 and 
            min_distance < 0.1):  # Within 100m of final waypoint
            mission_status.status = "completed"
            await self._cleanup_mission(mission_id, "completed")
    
    async def _start_mission_scheduler(self):
        """Start background mission scheduler"""
        # In a real implementation, this would be a continuous background task
        logger.info("Mission scheduler started")
    
    async def _start_health_monitor(self):
        """Start RPA health monitoring"""
        # In a real implementation, this would monitor RPA health
        logger.info("RPA health monitor started")
