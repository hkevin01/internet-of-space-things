#!/usr/bin/env python3
"""
Demo Data Provider for IoST GUI
Provides realistic simulation data for demonstration purposes
"""

import math
import random
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List


class IoSTDataProvider:
    """Central data provider for IoST GUI demonstration"""
    
    def __init__(self):
        self.spacecraft_data = {}
        self.telemetry_data = {}
        self.alert_data = []
        self.cehsn_data = {}
        self.init_demo_data()
    
    def init_demo_data(self):
        """Initialize demonstration data"""
        self.init_spacecraft_data()
        self.init_telemetry_data()
        self.init_cehsn_data()
        self.generate_sample_alerts()
    
    def init_spacecraft_data(self):
        """Initialize spacecraft demonstration data"""
        self.spacecraft_data = {
            "ISS": {
                "id": "ISS-001",
                "name": "International Space Station",
                "type": "Space Station",
                "status": "operational",
                "position": {"lat": 51.6461, "lon": -0.8061, "alt": 408.2},
                "velocity": 7.66,
                "orbital_period": 92.8,
                "crew_count": 7,
                "power_level": 95.5,
                "thermal_temp": 22.3,
                "attitude_status": "stable",
                "communication_strength": 98.7,
                "last_contact": datetime.now() - timedelta(minutes=2)
            },
            "Luna Gateway": {
                "id": "LG-001", 
                "name": "Lunar Gateway",
                "type": "Lunar Station",
                "status": "operational",
                "position": {"lat": 0.0, "lon": 0.0, "alt": 384400},
                "velocity": 1.02,
                "orbital_period": 2520,  # 42 hours
                "crew_count": 4,
                "power_level": 87.3,
                "thermal_temp": -15.7,
                "attitude_status": "stable",
                "communication_strength": 76.2,
                "last_contact": datetime.now() - timedelta(minutes=5)
            },
            "Crew Dragon": {
                "id": "CD-002",
                "name": "Crew Dragon Endeavour", 
                "type": "Crew Vehicle",
                "status": "in_transit",
                "position": {"lat": 28.3922, "lon": -80.6077, "alt": 425.1},
                "velocity": 7.73,
                "orbital_period": 93.2,
                "crew_count": 4,
                "power_level": 92.1,
                "thermal_temp": 19.8,
                "attitude_status": "stable",
                "communication_strength": 94.5,
                "last_contact": datetime.now() - timedelta(minutes=1)
            },
            "Starship": {
                "id": "SS-015",
                "name": "Starship SN-15",
                "type": "Heavy Lift Vehicle", 
                "status": "operational",
                "position": {"lat": 25.9964, "lon": -97.1557, "alt": 550.0},
                "velocity": 7.61,
                "orbital_period": 95.4,
                "crew_count": 8,
                "power_level": 88.7,
                "thermal_temp": 18.2,
                "attitude_status": "nominal",
                "communication_strength": 91.3,
                "last_contact": datetime.now() - timedelta(minutes=3)
            },
            "CubeSat-Alpha": {
                "id": "CS-A01",
                "name": "CubeSat Alpha-1",
                "type": "3U CubeSat",
                "status": "operational",
                "position": {"lat": 37.7749, "lon": -122.4194, "alt": 520.8},
                "velocity": 7.58,
                "orbital_period": 94.8,
                "crew_count": 0,
                "power_level": 78.9,
                "thermal_temp": 12.5,
                "attitude_status": "stable",
                "communication_strength": 67.8,
                "last_contact": datetime.now() - timedelta(minutes=8)
            },
            "CubeSat-Beta": {
                "id": "CS-B01", 
                "name": "CubeSat Beta-1",
                "type": "6U CubeSat",
                "status": "warning",
                "position": {"lat": 40.7128, "lon": -74.0060, "alt": 485.3},
                "velocity": 7.65,
                "orbital_period": 93.7,
                "crew_count": 0,
                "power_level": 65.4,
                "thermal_temp": 8.1,
                "attitude_status": "drift",
                "communication_strength": 42.1,
                "last_contact": datetime.now() - timedelta(minutes=15)
            }
        }
    
    def init_telemetry_data(self):
        """Initialize telemetry demonstration data"""
        spacecraft_list = list(self.spacecraft_data.keys())
        
        for spacecraft in spacecraft_list:
            self.telemetry_data[spacecraft] = {
                "power": {
                    "battery_voltage": self.generate_time_series(28.5, 0.5, 100),
                    "solar_current": self.generate_time_series(12.3, 1.2, 100),
                    "power_consumption": self.generate_time_series(450, 50, 100),
                    "charging_rate": self.generate_time_series(8.7, 2.1, 100)
                },
                "thermal": {
                    "cpu_temp": self.generate_time_series(45.2, 3.5, 100),
                    "battery_temp": self.generate_time_series(25.8, 2.1, 100),
                    "external_temp": self.generate_time_series(-180.5, 25.0, 100),
                    "radiator_temp": self.generate_time_series(15.3, 4.2, 100)
                },
                "attitude": {
                    "roll": self.generate_time_series(0.0, 0.5, 100),
                    "pitch": self.generate_time_series(0.0, 0.3, 100), 
                    "yaw": self.generate_time_series(0.0, 0.7, 100),
                    "angular_velocity": self.generate_time_series(0.01, 0.005, 100)
                },
                "communication": {
                    "signal_strength": self.generate_time_series(-65.0, 5.0, 100),
                    "data_rate": self.generate_time_series(2.4, 0.8, 100),
                    "packet_loss": self.generate_time_series(0.1, 0.05, 100),
                    "bandwidth_usage": self.generate_time_series(45.6, 15.2, 100)
                }
            }
    
    def init_cehsn_data(self):
        """Initialize CEHSN system demonstration data"""
        self.cehsn_data = {
            "orbital_inference": {
                "predictions": [
                    {
                        "event": "Solar Particle Event",
                        "confidence": 94.7,
                        "time_to_event": "8h 23m",
                        "severity": "moderate",
                        "affected_systems": ["ISS", "Luna Gateway"],
                        "recommended_actions": [
                            "Activate radiation shielding",
                            "Reduce EVA activities",
                            "Monitor crew exposure"
                        ]
                    },
                    {
                        "event": "Equipment Failure - OGS",
                        "confidence": 96.8,
                        "time_to_event": "72h",
                        "severity": "high",
                        "affected_systems": ["ISS"],
                        "recommended_actions": [
                            "Schedule maintenance window",
                            "Prepare backup oxygen",
                            "Alert crew"
                        ]
                    },
                    {
                        "event": "Debris Collision Risk",
                        "confidence": 12.3,
                        "time_to_event": "4d 12h",
                        "severity": "low",
                        "affected_systems": ["CubeSat-Alpha"],
                        "recommended_actions": [
                            "Monitor trajectory",
                            "Prepare avoidance maneuver"
                        ]
                    }
                ],
                "model_accuracy": 97.3,
                "last_update": datetime.now() - timedelta(minutes=3)
            },
            "rpa_bridge": {
                "active_missions": [
                    {
                        "id": "MISSION-001",
                        "type": "Search and Rescue",
                        "area": "Emergency Zone Alpha",
                        "drones_deployed": 3,
                        "status": "active",
                        "progress": 67,
                        "estimated_completion": "2h 15m"
                    },
                    {
                        "id": "MISSION-002", 
                        "type": "Supply Delivery",
                        "area": "Base Camp Delta",
                        "drones_deployed": 1,
                        "status": "en_route",
                        "progress": 23,
                        "estimated_completion": "45m"
                    }
                ],
                "available_drones": 47,
                "total_drones": 50,
                "network_coverage": 94.2
            },
            "ethics_engine": {
                "recent_assessments": [
                    {
                        "scenario": "Resource allocation during emergency",
                        "frameworks_used": ["utilitarian", "deontological"],
                        "recommendation": "Prioritize life support systems",
                        "confidence": 89.4,
                        "timestamp": datetime.now() - timedelta(hours=2)
                    }
                ],
                "total_assessments": 1247,
                "average_processing_time": 0.34
            },
            "survival_maps": {
                "active_maps": 3,
                "total_hazards_tracked": 15,
                "safe_zones_identified": 8,
                "last_map_generation": datetime.now() - timedelta(minutes=12),
                "map_accuracy": 96.7
            },
            "resilience_monitor": {
                "network_health": 94.2,
                "active_nodes": 47,
                "total_nodes": 50,
                "self_healing_events": [
                    {
                        "timestamp": datetime.now() - timedelta(minutes=35),
                        "event": "Node failure detected: SAT-042",
                        "action": "Automatic rerouting initiated",
                        "resolution_time": "2m 15s",
                        "status": "resolved"
                    }
                ],
                "uptime": 99.97
            }
        }
    
    def generate_time_series(self, base_value: float, variance: float, 
                           points: int) -> List[float]:
        """Generate realistic time series data"""
        data = []
        current_value = base_value
        
        for i in range(points):
            # Add some trending and random noise
            trend = math.sin(i * 0.1) * variance * 0.3
            noise = random.uniform(-variance, variance) * 0.5
            current_value = base_value + trend + noise
            data.append(current_value)
        
        return data
    
    def generate_sample_alerts(self):
        """Generate sample system alerts"""
        self.alert_data = [
            {
                "level": "warning",
                "message": "Minor thermal variance detected - ISS Solar Panel 3",
                "timestamp": datetime.now() - timedelta(minutes=5),
                "acknowledged": False,
                "source": "ISS"
            },
            {
                "level": "info", 
                "message": "Scheduled maintenance window - Dragon Capsule",
                "timestamp": datetime.now() - timedelta(minutes=15),
                "acknowledged": False,
                "source": "Crew Dragon"
            },
            {
                "level": "info",
                "message": "Communication window opening - Mars Perseverance", 
                "timestamp": datetime.now() - timedelta(minutes=25),
                "acknowledged": False,
                "source": "Deep Space Network"
            },
            {
                "level": "warning",
                "message": "CubeSat attitude drift detected - Beta-1",
                "timestamp": datetime.now() - timedelta(minutes=18),
                "acknowledged": False,
                "source": "CubeSat-Beta"
            }
        ]
    
    def get_spacecraft_list(self) -> List[str]:
        """Get list of available spacecraft"""
        return list(self.spacecraft_data.keys())
    
    def get_spacecraft_data(self, spacecraft_id: str) -> Dict[str, Any]:
        """Get data for specific spacecraft"""
        return self.spacecraft_data.get(spacecraft_id, {})
    
    def get_telemetry_data(self, spacecraft_id: str, 
                          category: str = None) -> Dict[str, Any]:
        """Get telemetry data for spacecraft"""
        if spacecraft_id not in self.telemetry_data:
            return {}
        
        if category:
            return self.telemetry_data[spacecraft_id].get(category, {})
        return self.telemetry_data[spacecraft_id]
    
    def get_latest_telemetry_value(self, spacecraft_id: str, 
                                  category: str, parameter: str) -> float:
        """Get latest telemetry value"""
        try:
            data = self.telemetry_data[spacecraft_id][category][parameter]
            return data[-1] if data else 0.0
        except KeyError:
            return 0.0
    
    def get_cehsn_data(self, component: str = None) -> Dict[str, Any]:
        """Get CEHSN system data"""
        if component:
            return self.cehsn_data.get(component, {})
        return self.cehsn_data
    
    def get_alerts(self, acknowledged: bool = None) -> List[Dict[str, Any]]:
        """Get system alerts"""
        if acknowledged is None:
            return self.alert_data
        return [alert for alert in self.alert_data 
                if alert["acknowledged"] == acknowledged]
    
    def acknowledge_alert(self, alert_index: int):
        """Acknowledge an alert"""
        if 0 <= alert_index < len(self.alert_data):
            self.alert_data[alert_index]["acknowledged"] = True
    
    def add_new_alert(self, level: str, message: str, source: str = "System"):
        """Add a new alert"""
        new_alert = {
            "level": level,
            "message": message, 
            "timestamp": datetime.now(),
            "acknowledged": False,
            "source": source
        }
        self.alert_data.insert(0, new_alert)  # Add to beginning
        
        # Limit number of alerts
        if len(self.alert_data) > 50:
            self.alert_data = self.alert_data[:50]
    
    def update_spacecraft_position(self, spacecraft_id: str):
        """Update spacecraft orbital position (simplified simulation)"""
        if spacecraft_id not in self.spacecraft_data:
            return
        
        spacecraft = self.spacecraft_data[spacecraft_id]
        
        # Simple orbital motion simulation
        current_time = time.time()
        orbital_period_seconds = spacecraft["orbital_period"] * 60
        
        # Calculate orbital phase
        phase = (current_time % orbital_period_seconds) / orbital_period_seconds
        angle = phase * 2 * math.pi
        
        # Update position (simplified circular orbit)
        if spacecraft_id == "ISS":
            spacecraft["position"]["lat"] = 51.6 * math.cos(angle)
            spacecraft["position"]["lon"] = 180 * (angle / math.pi - 1)
        elif spacecraft_id == "Luna Gateway":
            # Lunar orbit is much larger
            spacecraft["position"]["lat"] = 10.0 * math.sin(angle)
            spacecraft["position"]["lon"] = 360 * (angle / (2 * math.pi))
    
    def simulate_telemetry_update(self, spacecraft_id: str):
        """Simulate real-time telemetry updates"""
        if spacecraft_id not in self.telemetry_data:
            return
        
        telemetry = self.telemetry_data[spacecraft_id]
        
        for category in telemetry:
            for parameter in telemetry[category]:
                data_series = telemetry[category][parameter]
                
                # Remove oldest value and add new one
                if len(data_series) >= 100:
                    data_series.pop(0)
                
                # Generate new value based on last value with some drift
                last_value = data_series[-1] if data_series else 0
                drift = random.uniform(-0.5, 0.5)
                noise = random.uniform(-0.1, 0.1)
                new_value = last_value + drift + noise
                
                data_series.append(new_value)
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get overall system statistics"""
        operational_count = sum(1 for s in self.spacecraft_data.values() 
                              if s["status"] == "operational")
        warning_count = sum(1 for s in self.spacecraft_data.values()
                          if s["status"] == "warning")
        
        return {
            "total_spacecraft": len(self.spacecraft_data),
            "operational_spacecraft": operational_count,
            "warning_spacecraft": warning_count,
            "total_alerts": len(self.alert_data),
            "unacknowledged_alerts": len(self.get_alerts(acknowledged=False)),
            "cehsn_health": self.cehsn_data["resilience_monitor"]["network_health"],
            "average_communication_strength": sum(
                s["communication_strength"] for s in self.spacecraft_data.values()
            ) / len(self.spacecraft_data)
        }


# Global data provider instance
data_provider = IoSTDataProvider()
