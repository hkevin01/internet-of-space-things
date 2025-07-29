"""
Web Dashboard for Internet of Space Things Mission Control
FastAPI-based real-time dashboard for monitoring and controlling space operations
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

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

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Internet of Space Things Dashboard",
    description="Real-time mission control dashboard for space operations",
    version="1.0.0"
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Global system components
mission_control: MissionControl = None
active_connections: List[WebSocket] = []


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove disconnected clients
                if connection in self.active_connections:
                    self.active_connections.remove(connection)


manager = ConnectionManager()


async def initialize_demo_system():
    """Initialize demo space system"""
    global mission_control
    
    logger.info("Initializing IoST Demo System...")
    
    # Create system components
    network = SpaceNetwork("IoST-Dashboard-Network")
    satellite_manager = SatelliteManager("IoST-Dashboard-Constellation")
    mission_control = MissionControl("IoST-Dashboard-Mission", network, satellite_manager)
    
    # Add sample satellites
    satellites_config = [
        {
            "id": "ISS-MAIN",
            "name": "International Space Station",
            "type": "space_station",
            "orbit": OrbitType.LEO,
            "mass": 420000,
            "power": 75000,
            "fuel": 1000,
            "sensors": ["atmospheric", "radiation", "life_support"]
        },
        {
            "id": "LUNAR-GATEWAY",
            "name": "Lunar Gateway Station",
            "type": "communications",
            "orbit": OrbitType.DEEP_SPACE,
            "mass": 15000,
            "power": 20000,
            "fuel": 800,
            "sensors": ["navigation", "radiation"]
        }
    ]
    
    for sat_config in satellites_config:
        config = SatelliteConfiguration(
            satellite_id=sat_config["id"],
            name=sat_config["name"],
            satellite_type=sat_config["type"],
            orbit_type=sat_config["orbit"],
            mass=sat_config["mass"],
            power_capacity=sat_config["power"],
            fuel_capacity=sat_config["fuel"],
            communication_frequency=2.4e9,
            sensor_types=sat_config["sensors"]
        )
        
        orbit = OrbitalElements(
            semi_major_axis=6800 if sat_config["orbit"] == OrbitType.LEO else 50000,
            eccentricity=0.01,
            inclination=51.6 if sat_config["orbit"] == OrbitType.LEO else 0.0,
            longitude_of_ascending_node=0.0,
            argument_of_periapsis=0.0,
            true_anomaly=0.0
        )
        
        await satellite_manager.add_satellite(config, orbit)
        
        # Add to network
        node = NetworkNode(
            node_id=sat_config["id"],
            name=sat_config["name"],
            node_type="spacecraft",
            status=NetworkStatus.ACTIVE,
            communication_modes=[CommunicationMode.INTER_SATELLITE],
            signal_strength=0.85,
            bandwidth_capacity=150.0
        )
        await network.add_node(node)
    
    # Establish links
    await network.establish_link("ISS-MAIN", "LUNAR-GATEWAY", CommunicationMode.INTER_SATELLITE)
    
    # Start mission
    await mission_control.start_mission(timedelta(hours=24))
    
    # Add objectives
    objectives = [
        MissionObjective(
            objective_id="life-support-monitoring",
            title="Life Support Monitoring",
            description="Monitor critical life support systems",
            target_completion=datetime.utcnow() + timedelta(hours=2),
            success_criteria={"oxygen_level": ">95%"},
            assigned_assets=["ISS-MAIN"]
        ),
        MissionObjective(
            objective_id="communication-test",
            title="Deep Space Communication Test",
            description="Test communication with lunar gateway",
            target_completion=datetime.utcnow() + timedelta(hours=4),
            success_criteria={"latency": "<500ms"},
            assigned_assets=["LUNAR-GATEWAY"]
        )
    ]
    
    for objective in objectives:
        await mission_control.add_mission_objective(objective)
    
    logger.info("Demo system initialized successfully")


@app.on_event("startup")
async def startup_event():
    """Initialize system on startup"""
    await initialize_demo_system()
    
    # Start telemetry broadcast task
    asyncio.create_task(broadcast_telemetry())


async def broadcast_telemetry():
    """Broadcast telemetry data to connected clients"""
    while True:
        try:
            if mission_control and manager.active_connections:
                # Get system status
                mission_status = await mission_control.get_mission_status()
                
                # Broadcast to all connected clients
                await manager.broadcast(json.dumps({
                    "type": "telemetry",
                    "data": mission_status,
                    "timestamp": datetime.utcnow().isoformat()
                }, default=str))
            
            await asyncio.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            logger.error(f"Error broadcasting telemetry: {e}")
            await asyncio.sleep(10)


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/status")
async def get_system_status():
    """Get current system status"""
    if not mission_control:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    return await mission_control.get_mission_status()


@app.get("/api/satellites")
async def get_satellites():
    """Get satellite information"""
    if not mission_control:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    return mission_control.satellite_manager.get_constellation_telemetry()


@app.get("/api/network")
async def get_network_status():
    """Get network status"""
    if not mission_control:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    return await mission_control.network.monitor_network_health()


@app.post("/api/commands")
async def execute_command(command_data: Dict[str, Any]):
    """Execute a mission command"""
    if not mission_control:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        command = MissionCommand(
            command_id=f"web_{datetime.utcnow().timestamp()}",
            target_id=command_data.get("target_id", ""),
            command_type=command_data.get("command_type", ""),
            parameters=command_data.get("parameters", {}),
            priority=CommandPriority(command_data.get("priority", CommandPriority.NORMAL.value))
        )
        
        result = await mission_control.queue_command(command)
        return {"success": result, "command_id": command.command_id}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/objectives")
async def get_objectives():
    """Get mission objectives"""
    if not mission_control:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    return {
        obj_id: {
            "title": obj.title,
            "description": obj.description,
            "progress": obj.progress,
            "status": obj.status,
            "target_completion": obj.target_completion.isoformat(),
            "assigned_assets": obj.assigned_assets
        }
        for obj_id, obj in mission_control.mission_objectives.items()
    }


@app.post("/api/emergency")
async def declare_emergency(emergency_data: Dict[str, Any]):
    """Declare emergency situation"""
    if not mission_control:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        emergency_type = emergency_data.get("type", "unknown")
        affected_systems = emergency_data.get("affected_systems", [])
        
        result = await mission_control.handle_emergency(emergency_type, affected_systems)
        return {"success": result, "emergency_type": emergency_type}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Create templates directory and files
import os

os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IoST Mission Control Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #0c1445 0%, #1a237e 50%, #000051 100%);
            color: #ffffff;
            min-height: 100vh;
        }
        .header {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid #64b5f6;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .panel {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(100, 181, 246, 0.3);
        }
        .panel h3 {
            color: #64b5f6;
            margin-top: 0;
            border-bottom: 1px solid rgba(100, 181, 246, 0.3);
            padding-bottom: 10px;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-active { background-color: #4caf50; }
        .status-warning { background-color: #ff9800; }
        .status-error { background-color: #f44336; }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .metric:last-child {
            border-bottom: none;
        }
        .metric-value {
            font-weight: bold;
            color: #64b5f6;
        }
        .control-button {
            background: linear-gradient(45deg, #1976d2, #42a5f5);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            margin: 5px;
            transition: all 0.3s ease;
        }
        .control-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(25, 118, 210, 0.4);
        }
        .emergency-button {
            background: linear-gradient(45deg, #d32f2f, #f44336);
        }
        #connectionStatus {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 12px;
        }
        .connected { background-color: #4caf50; }
        .disconnected { background-color: #f44336; }
        .satellite-list {
            max-height: 300px;
            overflow-y: auto;
        }
        .satellite-item {
            background: rgba(255, 255, 255, 0.05);
            margin: 5px 0;
            padding: 10px;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div id="connectionStatus" class="disconnected">Disconnected</div>
    
    <div class="header">
        <h1>🚀 Internet of Space Things - Mission Control</h1>
        <p>Real-time Space Operations Dashboard</p>
    </div>
    
    <div class="dashboard">
        <!-- Mission Status Panel -->
        <div class="panel">
            <h3>Mission Status</h3>
            <div class="metric">
                <span>Mission:</span>
                <span class="metric-value" id="missionName">Loading...</span>
            </div>
            <div class="metric">
                <span>Status:</span>
                <span class="metric-value" id="missionStatus">
                    <span class="status-indicator status-active"></span>Loading...
                </span>
            </div>
            <div class="metric">
                <span>Elapsed Time:</span>
                <span class="metric-value" id="elapsedTime">--:--:--</span>
            </div>
            <div class="metric">
                <span>Objectives:</span>
                <span class="metric-value" id="objectives">0/0</span>
            </div>
        </div>
        
        <!-- Network Health Panel -->
        <div class="panel">
            <h3>Network Health</h3>
            <div class="metric">
                <span>Active Nodes:</span>
                <span class="metric-value" id="activeNodes">0</span>
            </div>
            <div class="metric">
                <span>Network Availability:</span>
                <span class="metric-value" id="networkAvailability">0%</span>
            </div>
            <div class="metric">
                <span>Data Transmitted:</span>
                <span class="metric-value" id="dataTransmitted">0 GB</span>
            </div>
            <div class="metric">
                <span>Avg Latency:</span>
                <span class="metric-value" id="avgLatency">0 ms</span>
            </div>
        </div>
        
        <!-- Satellites Panel -->
        <div class="panel">
            <h3>Satellites</h3>
            <div class="metric">
                <span>Total Satellites:</span>
                <span class="metric-value" id="totalSatellites">0</span>
            </div>
            <div class="metric">
                <span>Operational:</span>
                <span class="metric-value" id="operationalSatellites">0</span>
            </div>
            <div class="satellite-list" id="satelliteList">
                Loading satellites...
            </div>
        </div>
        
        <!-- Mission Control Panel -->
        <div class="panel">
            <h3>Mission Control</h3>
            <div class="metric">
                <span>Queued Commands:</span>
                <span class="metric-value" id="queuedCommands">0</span>
            </div>
            <div class="metric">
                <span>Active Alerts:</span>
                <span class="metric-value" id="activeAlerts">0</span>
            </div>
            <div style="margin-top: 15px;">
                <button class="control-button" onclick="executeHealthCheck()">Health Check</button>
                <button class="control-button" onclick="collectData()">Collect Data</button>
                <button class="control-button emergency-button" onclick="declareEmergency()">Emergency</button>
            </div>
        </div>
    </div>
    
    <script>
        let ws;
        let connectionStatus = document.getElementById('connectionStatus');
        
        function connectWebSocket() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);
            
            ws.onopen = function(event) {
                connectionStatus.textContent = 'Connected';
                connectionStatus.className = 'connected';
                console.log('WebSocket connected');
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'telemetry') {
                    updateDashboard(data.data);
                }
            };
            
            ws.onclose = function(event) {
                connectionStatus.textContent = 'Disconnected';
                connectionStatus.className = 'disconnected';
                console.log('WebSocket disconnected');
                
                // Reconnect after 5 seconds
                setTimeout(connectWebSocket, 5000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        function updateDashboard(data) {
            // Update mission status
            document.getElementById('missionName').textContent = data.mission_name || 'Unknown';
            document.getElementById('missionStatus').innerHTML = 
                `<span class="status-indicator status-${data.status === 'active' ? 'active' : 'warning'}"></span>${data.status || 'Unknown'}`;
            
            if (data.elapsed_time_seconds) {
                const hours = Math.floor(data.elapsed_time_seconds / 3600);
                const minutes = Math.floor((data.elapsed_time_seconds % 3600) / 60);
                const seconds = Math.floor(data.elapsed_time_seconds % 60);
                document.getElementById('elapsedTime').textContent = 
                    `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            }
            
            if (data.objectives) {
                document.getElementById('objectives').textContent = 
                    `${data.objectives.completed}/${data.objectives.total}`;
            }
            
            // Update network health
            if (data.network_health) {
                document.getElementById('activeNodes').textContent = data.network_health.active_nodes || 0;
                document.getElementById('networkAvailability').textContent = 
                    `${Math.round((data.network_health.node_availability || 0) * 100)}%`;
                document.getElementById('dataTransmitted').textContent = 
                    `${(data.network_health.data_transmitted_gb || 0).toFixed(2)} GB`;
                document.getElementById('avgLatency').textContent = 
                    `${Math.round(data.network_health.avg_latency_ms || 0)} ms`;
            }
            
            // Update satellites
            if (data.constellation_health) {
                document.getElementById('totalSatellites').textContent = data.constellation_health.total_satellites || 0;
                document.getElementById('operationalSatellites').textContent = data.constellation_health.operational_satellites || 0;
            }
            
            // Update commands and alerts
            if (data.commands) {
                document.getElementById('queuedCommands').textContent = data.commands.queued || 0;
            }
            if (data.alerts) {
                document.getElementById('activeAlerts').textContent = data.alerts.active || 0;
            }
        }
        
        async function executeHealthCheck() {
            try {
                const response = await fetch('/api/commands', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target_id: 'ISS-MAIN',
                        command_type: 'health_check',
                        parameters: {},
                        priority: 2
                    })
                });
                const result = await response.json();
                alert(`Health check command queued: ${result.command_id}`);
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }
        
        async function collectData() {
            try {
                const response = await fetch('/api/commands', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target_id: 'ISS-MAIN',
                        command_type: 'collect_data',
                        parameters: { sensor_type: 'atmospheric', duration: 300 },
                        priority: 3
                    })
                });
                const result = await response.json();
                alert(`Data collection command queued: ${result.command_id}`);
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }
        
        async function declareEmergency() {
            if (confirm('Are you sure you want to declare an emergency?')) {
                try {
                    const response = await fetch('/api/emergency', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            type: 'system_failure',
                            affected_systems: ['ISS-MAIN']
                        })
                    });
                    const result = await response.json();
                    alert(`Emergency declared: ${result.emergency_type}`);
                } catch (error) {
                    alert(`Error: ${error.message}`);
                }
            }
        }
        
        // Initialize WebSocket connection
        connectWebSocket();
        
        // Initial data load
        fetch('/api/status')
            .then(response => response.json())
            .then(data => updateDashboard(data))
            .catch(error => console.error('Error loading initial data:', error));
    </script>
</body>
</html>
"""

# Write the dashboard template
with open("templates/dashboard.html", "w") as f:
    f.write(dashboard_html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
