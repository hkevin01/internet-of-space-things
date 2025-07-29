"""
Mission Control - Central command and control system for space operations
Manages missions, coordinates activities, and provides decision-making support
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .satellite_manager import Satellite, SatelliteManager, SatelliteStatus
from .space_network import CommunicationMode, NetworkNode, SpaceNetwork

logger = logging.getLogger(__name__)


class MissionStatus(Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    NOMINAL = "nominal"
    CAUTION = "caution"
    WARNING = "warning"
    EMERGENCY = "emergency"
    COMPLETED = "completed"
    ABORTED = "aborted"


class CommandPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class MissionCommand:
    """Command to be executed by spacecraft or ground systems"""
    command_id: str
    target_id: str  # satellite or system ID
    command_type: str
    parameters: Dict[str, Any]
    priority: CommandPriority
    scheduled_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, executing, completed, failed


@dataclass
class MissionObjective:
    """Mission objective definition"""
    objective_id: str
    title: str
    description: str
    target_completion: datetime
    success_criteria: Dict[str, Any]
    assigned_assets: List[str] = field(default_factory=list)
    progress: float = 0.0  # 0-100%
    status: str = "active"  # active, completed, failed, paused


@dataclass
class AlertCondition:
    """System alert/alarm condition"""
    alert_id: str
    severity: str  # info, warning, caution, critical, emergency
    source: str  # system/satellite that generated the alert
    message: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    resolved: bool = False


class MissionControl:
    """
    Central Mission Control System for IoST
    Coordinates all space operations, manages missions, and provides
    real-time command and control capabilities
    """
    
    def __init__(self, mission_name: str = "IoST-Mission", 
                 network: Optional[SpaceNetwork] = None,
                 satellite_manager: Optional[SatelliteManager] = None):
        self.mission_name = mission_name
        self.network = network or SpaceNetwork()
        self.satellite_manager = satellite_manager or SatelliteManager()
        
        # Mission state
        self.mission_status = MissionStatus.PLANNING
        self.mission_start_time: Optional[datetime] = None
        self.mission_duration: Optional[timedelta] = None
        
        # Command and control
        self.command_queue: List[MissionCommand] = []
        self.command_history: List[MissionCommand] = []
        self.active_commands: Dict[str, MissionCommand] = {}
        
        # Mission planning
        self.mission_objectives: Dict[str, MissionObjective] = {}
        self.flight_plan: List[Dict[str, Any]] = []
        
        # Monitoring and alerts
        self.active_alerts: Dict[str, AlertCondition] = {}
        self.alert_history: List[AlertCondition] = []
        
        # Configuration
        self.max_command_queue_size = 1000
        self.command_timeout = timedelta(minutes=30)
        self.health_check_interval = 60  # seconds
        
        # Callbacks for external systems
        self.alert_callbacks: List[Callable] = []
        self.telemetry_callbacks: List[Callable] = []
        
        logger.info(f"Mission Control '{mission_name}' initialized")
    
    async def start_mission(self, duration: Optional[timedelta] = None) -> bool:
        """Start the mission operations"""
        try:
            if self.mission_status != MissionStatus.PLANNING:
                logger.warning("Mission already started or completed")
                return False
            
            self.mission_start_time = datetime.utcnow()
            self.mission_duration = duration
            self.mission_status = MissionStatus.ACTIVE
            
            # Start background monitoring tasks
            asyncio.create_task(self._command_processor())
            asyncio.create_task(self._health_monitor())
            asyncio.create_task(self._telemetry_processor())
            
            await self._generate_alert("info", "mission_control", 
                                     f"Mission {self.mission_name} started")
            
            logger.info(f"Mission {self.mission_name} started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start mission: {e}")
            return False
    
    async def add_mission_objective(self, objective: MissionObjective) -> bool:
        """Add new mission objective"""
        try:
            self.mission_objectives[objective.objective_id] = objective
            
            await self._generate_alert("info", "mission_control",
                                     f"New objective added: {objective.title}")
            
            logger.info(f"Added mission objective: {objective.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add objective: {e}")
            return False
    
    async def queue_command(self, command: MissionCommand) -> bool:
        """Queue command for execution"""
        try:
            if len(self.command_queue) >= self.max_command_queue_size:
                logger.error("Command queue is full")
                return False
            
            # Insert command based on priority
            inserted = False
            for i, queued_cmd in enumerate(self.command_queue):
                if command.priority.value > queued_cmd.priority.value:
                    self.command_queue.insert(i, command)
                    inserted = True
                    break
            
            if not inserted:
                self.command_queue.append(command)
            
            logger.info(f"Queued command {command.command_id} "
                       f"({command.priority.name} priority)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue command: {e}")
            return False
    
    async def execute_immediate_command(self, command: MissionCommand) -> bool:
        """Execute command immediately (emergency/critical commands)"""
        try:
            if command.priority.value < CommandPriority.CRITICAL.value:
                logger.warning("Immediate execution reserved for critical+ commands")
                return False
            
            return await self._execute_command(command)
            
        except Exception as e:
            logger.error(f"Failed to execute immediate command: {e}")
            return False
    
    async def abort_mission(self, reason: str) -> bool:
        """Abort the current mission"""
        try:
            self.mission_status = MissionStatus.ABORTED
            
            # Clear command queue
            self.command_queue.clear()
            
            # Send abort commands to all satellites
            for satellite_id in self.satellite_manager.satellites:
                abort_cmd = MissionCommand(
                    command_id=f"abort_{satellite_id}_{datetime.utcnow().timestamp()}",
                    target_id=satellite_id,
                    command_type="abort_mission",
                    parameters={"reason": reason},
                    priority=CommandPriority.EMERGENCY
                )
                await self._execute_command(abort_cmd)
            
            await self._generate_alert("critical", "mission_control",
                                     f"Mission aborted: {reason}")
            
            logger.critical(f"Mission {self.mission_name} aborted: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to abort mission: {e}")
            return False
    
    async def get_mission_status(self) -> Dict[str, Any]:
        """Get comprehensive mission status"""
        # Calculate mission elapsed time
        elapsed_time = None
        if self.mission_start_time:
            elapsed_time = (datetime.utcnow() - self.mission_start_time).total_seconds()
        
        # Calculate objective completion
        total_objectives = len(self.mission_objectives)
        completed_objectives = sum(1 for obj in self.mission_objectives.values() 
                                 if obj.status == "completed")
        
        # Get network and satellite health
        network_health = await self.network.monitor_network_health()
        constellation_health = await self.satellite_manager.monitor_constellation_health()
        
        # Count active alerts by severity
        alert_counts = {}
        for alert in self.active_alerts.values():
            alert_counts[alert.severity] = alert_counts.get(alert.severity, 0) + 1
        
        return {
            "mission_name": self.mission_name,
            "status": self.mission_status.value,
            "start_time": self.mission_start_time.isoformat() if self.mission_start_time else None,
            "elapsed_time_seconds": elapsed_time,
            "duration_seconds": self.mission_duration.total_seconds() if self.mission_duration else None,
            "objectives": {
                "total": total_objectives,
                "completed": completed_objectives,
                "completion_rate": completed_objectives / total_objectives if total_objectives > 0 else 0
            },
            "commands": {
                "queued": len(self.command_queue),
                "active": len(self.active_commands),
                "completed": len(self.command_history)
            },
            "alerts": {
                "active": len(self.active_alerts),
                "by_severity": alert_counts
            },
            "network_health": network_health,
            "constellation_health": constellation_health
        }
    
    async def handle_emergency(self, emergency_type: str, 
                             affected_systems: List[str]) -> bool:
        """Handle emergency situation"""
        try:
            self.mission_status = MissionStatus.EMERGENCY
            
            # Generate emergency alert
            await self._generate_alert("emergency", "mission_control",
                                     f"Emergency declared: {emergency_type}",
                                     {"affected_systems": affected_systems})
            
            # Activate emergency protocols in network
            await self.network.activate_emergency_protocol(emergency_type, 
                                                          affected_systems)
            
            # Put affected satellites in safe mode
            for system_id in affected_systems:
                if system_id in self.satellite_manager.satellites:
                    satellite = self.satellite_manager.satellites[system_id]
                    await satellite.enter_safe_mode(f"Emergency: {emergency_type}")
            
            # Execute emergency response plan
            await self._execute_emergency_response(emergency_type, affected_systems)
            
            logger.critical(f"Emergency response activated: {emergency_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle emergency: {e}")
            return False
    
    async def _command_processor(self):
        """Background task to process command queue"""
        while self.mission_status in [MissionStatus.ACTIVE, MissionStatus.NOMINAL]:
            try:
                if self.command_queue:
                    command = self.command_queue.pop(0)
                    
                    # Check if command is scheduled for future execution
                    if command.scheduled_time and datetime.utcnow() < command.scheduled_time:
                        # Re-queue for later
                        self.command_queue.append(command)
                        await asyncio.sleep(1)
                        continue
                    
                    # Execute command
                    await self._execute_command(command)
                
                await asyncio.sleep(1)  # Process commands every second
                
            except Exception as e:
                logger.error(f"Error in command processor: {e}")
                await asyncio.sleep(5)
    
    async def _execute_command(self, command: MissionCommand) -> bool:
        """Execute a single command"""
        try:
            command.status = "executing"
            command.executed_at = datetime.utcnow()
            self.active_commands[command.command_id] = command
            
            # Route command based on target and type
            if command.target_id in self.satellite_manager.satellites:
                result = await self._execute_satellite_command(command)
            elif command.target_id == "mission_control":
                result = await self._execute_control_command(command)
            elif command.target_id == "network":
                result = await self._execute_network_command(command)
            else:
                logger.error(f"Unknown command target: {command.target_id}")
                result = False
            
            # Update command status
            command.status = "completed" if result else "failed"
            command.result = {"success": result, "timestamp": datetime.utcnow().isoformat()}
            
            # Move to history
            self.command_history.append(command)
            if command.command_id in self.active_commands:
                del self.active_commands[command.command_id]
            
            return result
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            command.status = "failed"
            command.result = {"success": False, "error": str(e)}
            return False
    
    async def _execute_satellite_command(self, command: MissionCommand) -> bool:
        """Execute command directed at satellite"""
        satellite = self.satellite_manager.satellites.get(command.target_id)
        if not satellite:
            return False
        
        try:
            if command.command_type == "maneuver":
                delta_v = np.array(command.parameters.get("delta_v", [0, 0, 0]))
                burn_duration = command.parameters.get("burn_duration", 0)
                return await satellite.execute_maneuver(delta_v, burn_duration)
            
            elif command.command_type == "collect_data":
                sensor_type = command.parameters.get("sensor_type", "")
                duration = command.parameters.get("duration", 60)
                data = await satellite.collect_sensor_data(sensor_type, duration)
                return len(data) > 0
            
            elif command.command_type == "safe_mode":
                reason = command.parameters.get("reason", "Command initiated")
                await satellite.enter_safe_mode(reason)
                return True
            
            elif command.command_type == "health_check":
                await satellite.monitor_health()
                return True
            
            else:
                logger.warning(f"Unknown satellite command: {command.command_type}")
                return False
                
        except Exception as e:
            logger.error(f"Satellite command execution failed: {e}")
            return False
    
    async def _execute_control_command(self, command: MissionCommand) -> bool:
        """Execute mission control command"""
        try:
            if command.command_type == "update_objective":
                obj_id = command.parameters.get("objective_id")
                progress = command.parameters.get("progress", 0)
                if obj_id in self.mission_objectives:
                    self.mission_objectives[obj_id].progress = progress
                    return True
            
            elif command.command_type == "change_status":
                new_status = command.parameters.get("status")
                if new_status in [s.value for s in MissionStatus]:
                    self.mission_status = MissionStatus(new_status)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Control command execution failed: {e}")
            return False
    
    async def _execute_network_command(self, command: MissionCommand) -> bool:
        """Execute network command"""
        try:
            if command.command_type == "establish_link":
                source = command.parameters.get("source_id")
                target = command.parameters.get("target_id")
                link_type = CommunicationMode(command.parameters.get("link_type", "inter_satellite"))
                link = await self.network.establish_link(source, target, link_type)
                return link is not None
            
            elif command.command_type == "transmit_data":
                source = command.parameters.get("source_id")
                target = command.parameters.get("target_id")
                data = command.parameters.get("data", {})
                priority = command.parameters.get("priority", 1)
                return await self.network.transmit_data(source, target, data, priority)
            
            return False
            
        except Exception as e:
            logger.error(f"Network command execution failed: {e}")
            return False
    
    async def _health_monitor(self):
        """Background health monitoring task"""
        while self.mission_status in [MissionStatus.ACTIVE, MissionStatus.NOMINAL]:
            try:
                # Monitor network health
                network_health = await self.network.monitor_network_health()
                if network_health["node_availability"] < 0.8:
                    await self._generate_alert("warning", "network",
                                             "Network availability degraded")
                
                # Monitor constellation health
                constellation_health = await self.satellite_manager.monitor_constellation_health()
                if constellation_health["availability"] < 0.9:
                    await self._generate_alert("caution", "constellation",
                                             "Constellation availability degraded")
                
                # Check for satellite anomalies
                for sat_id, satellite in self.satellite_manager.satellites.items():
                    if satellite.health.anomaly_score > 0.7:
                        await self._generate_alert("warning", sat_id,
                                                 f"High anomaly score: {satellite.health.anomaly_score:.2f}")
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(60)
    
    async def _telemetry_processor(self):
        """Background telemetry processing task"""
        while self.mission_status in [MissionStatus.ACTIVE, MissionStatus.NOMINAL]:
            try:
                # Collect telemetry from all satellites
                telemetry = self.satellite_manager.get_constellation_telemetry()
                
                # Process telemetry through callbacks
                for callback in self.telemetry_callbacks:
                    try:
                        await callback(telemetry)
                    except Exception as e:
                        logger.error(f"Telemetry callback error: {e}")
                
                await asyncio.sleep(10)  # Process every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in telemetry processor: {e}")
                await asyncio.sleep(30)
    
    async def _generate_alert(self, severity: str, source: str, message: str,
                            parameters: Dict[str, Any] = None) -> AlertCondition:
        """Generate system alert"""
        alert = AlertCondition(
            alert_id=f"{source}_{datetime.utcnow().timestamp()}",
            severity=severity,
            source=source,
            message=message,
            parameters=parameters or {}
        )
        
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        
        # Execute alert callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        logger.log(
            logging.CRITICAL if severity == "emergency" else
            logging.ERROR if severity == "critical" else
            logging.WARNING if severity in ["warning", "caution"] else
            logging.INFO,
            f"Alert [{severity.upper()}] {source}: {message}"
        )
        
        return alert
    
    async def _execute_emergency_response(self, emergency_type: str, 
                                        affected_systems: List[str]):
        """Execute emergency response procedures"""
        # This would contain specific emergency response logic
        # For now, implement basic safe mode activation
        
        for system_id in affected_systems:
            if system_id in self.satellite_manager.satellites:
                safe_mode_cmd = MissionCommand(
                    command_id=f"emergency_safe_{system_id}_{datetime.utcnow().timestamp()}",
                    target_id=system_id,
                    command_type="safe_mode",
                    parameters={"reason": f"Emergency response: {emergency_type}"},
                    priority=CommandPriority.EMERGENCY
                )
                await self._execute_command(safe_mode_cmd)
    
    def register_alert_callback(self, callback: Callable):
        """Register callback for alert notifications"""
        self.alert_callbacks.append(callback)
    
    def register_telemetry_callback(self, callback: Callable):
        """Register callback for telemetry processing"""
        self.telemetry_callbacks.append(callback)
