#!/usr/bin/env python3
"""
Enhanced Data Management System for IoST GUI
Real-time telemetry processing, data storage, and analysis
"""

import json
import queue
import sqlite3
import statistics
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal


@dataclass
class TelemetryPoint:
    """Single telemetry data point"""
    timestamp: datetime
    spacecraft_id: str
    parameter: str
    value: float
    unit: str
    status: str = "normal"  # normal, warning, critical


@dataclass
class SpacecraftState:
    """Complete spacecraft state"""
    spacecraft_id: str
    timestamp: datetime
    position: Dict[str, float]
    velocity: Dict[str, float]
    attitude: Dict[str, float]
    power_level: float
    thermal_status: Dict[str, float]
    communication_status: Dict[str, Any]
    subsystem_health: Dict[str, str]


class TelemetryDatabase:
    """SQLite database for telemetry storage"""
    
    def __init__(self, db_path: str = "telemetry.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Telemetry points table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    spacecraft_id TEXT NOT NULL,
                    parameter TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    status TEXT DEFAULT 'normal',
                    UNIQUE(timestamp, spacecraft_id, parameter)
                )
            """)
            
            # Spacecraft states table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spacecraft_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    spacecraft_id TEXT NOT NULL,
                    position_x REAL,
                    position_y REAL,
                    position_z REAL,
                    velocity_x REAL,
                    velocity_y REAL,
                    velocity_z REAL,
                    attitude_roll REAL,
                    attitude_pitch REAL,
                    attitude_yaw REAL,
                    power_level REAL,
                    UNIQUE(timestamp, spacecraft_id)
                )
            """)
            
            # Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    spacecraft_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    acknowledged INTEGER DEFAULT 0,
                    resolved INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_spacecraft_time 
                ON telemetry_points(spacecraft_id, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_states_spacecraft_time 
                ON spacecraft_states(spacecraft_id, timestamp)
            """)
            
            conn.commit()
    
    def store_telemetry_point(self, point: TelemetryPoint):
        """Store a single telemetry point"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO telemetry_points 
                (timestamp, spacecraft_id, parameter, value, unit, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                point.timestamp.isoformat(),
                point.spacecraft_id,
                point.parameter,
                point.value,
                point.unit,
                point.status
            ))
            conn.commit()
    
    def store_spacecraft_state(self, state: SpacecraftState):
        """Store complete spacecraft state"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO spacecraft_states 
                (timestamp, spacecraft_id, position_x, position_y, position_z,
                 velocity_x, velocity_y, velocity_z, attitude_roll, 
                 attitude_pitch, attitude_yaw, power_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                state.timestamp.isoformat(),
                state.spacecraft_id,
                state.position.get('x', 0),
                state.position.get('y', 0),
                state.position.get('z', 0),
                state.velocity.get('x', 0),
                state.velocity.get('y', 0),
                state.velocity.get('z', 0),
                state.attitude.get('roll', 0),
                state.attitude.get('pitch', 0),
                state.attitude.get('yaw', 0),
                state.power_level
            ))
            conn.commit()
    
    def get_telemetry_history(self, spacecraft_id: str, parameter: str, 
                            hours_back: int = 24) -> List[TelemetryPoint]:
        """Get telemetry history for parameter"""
        start_time = datetime.now() - timedelta(hours=hours_back)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, spacecraft_id, parameter, value, unit, status
                FROM telemetry_points
                WHERE spacecraft_id = ? AND parameter = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """, (spacecraft_id, parameter, start_time.isoformat()))
            
            results = []
            for row in cursor.fetchall():
                results.append(TelemetryPoint(
                    timestamp=datetime.fromisoformat(row[0]),
                    spacecraft_id=row[1],
                    parameter=row[2],
                    value=row[3],
                    unit=row[4],
                    status=row[5]
                ))
            
            return results
    
    def get_spacecraft_trajectory(self, spacecraft_id: str, 
                                hours_back: int = 24) -> List[SpacecraftState]:
        """Get spacecraft trajectory history"""
        start_time = datetime.now() - timedelta(hours=hours_back)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, spacecraft_id, position_x, position_y, 
                       position_z, velocity_x, velocity_y, velocity_z,
                       attitude_roll, attitude_pitch, attitude_yaw, power_level
                FROM spacecraft_states
                WHERE spacecraft_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """, (spacecraft_id, start_time.isoformat()))
            
            results = []
            for row in cursor.fetchall():
                results.append(SpacecraftState(
                    timestamp=datetime.fromisoformat(row[0]),
                    spacecraft_id=row[1],
                    position={'x': row[2], 'y': row[3], 'z': row[4]},
                    velocity={'x': row[5], 'y': row[6], 'z': row[7]},
                    attitude={'roll': row[8], 'pitch': row[9], 'yaw': row[10]},
                    power_level=row[11],
                    thermal_status={},
                    communication_status={},
                    subsystem_health={}
                ))
            
            return results


class TelemetryProcessor(QObject):
    """Real-time telemetry processor"""
    
    # Signals for GUI updates
    telemetry_updated = pyqtSignal(str, str, float)  # spacecraft, parameter, value
    alert_generated = pyqtSignal(str, str, str)  # spacecraft, severity, message
    
    def __init__(self):
        super().__init__()
        self.database = TelemetryDatabase()
        self.processing_queue = queue.Queue()
        self.thresholds = self.load_alert_thresholds()
        self.running = False
        
        # Statistical buffers for analysis
        self.telemetry_buffers = {}  # spacecraft_id -> parameter -> values
        self.buffer_size = 100
        
        # Processing thread
        self.processing_thread = None
    
    def start_processing(self):
        """Start telemetry processing"""
        self.running = True
        self.processing_thread = threading.Thread(
            target=self.process_telemetry_loop,
            daemon=True
        )
        self.processing_thread.start()
    
    def stop_processing(self):
        """Stop telemetry processing"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=1.0)
    
    def process_telemetry_loop(self):
        """Main telemetry processing loop"""
        while self.running:
            try:
                # Process queued telemetry points
                while not self.processing_queue.empty():
                    telemetry_point = self.processing_queue.get_nowait()
                    self.process_single_point(telemetry_point)
                
                time.sleep(0.1)  # Small delay to prevent excessive CPU usage
                
            except Exception as e:
                print(f"Telemetry processing error: {e}")
                time.sleep(1.0)
    
    def process_single_point(self, point: TelemetryPoint):
        """Process a single telemetry point"""
        # Store in database
        self.database.store_telemetry_point(point)
        
        # Update statistical buffers
        self.update_telemetry_buffer(point)
        
        # Check for alerts
        self.check_telemetry_alerts(point)
        
        # Emit update signal
        self.telemetry_updated.emit(
            point.spacecraft_id, 
            point.parameter, 
            point.value
        )
    
    def update_telemetry_buffer(self, point: TelemetryPoint):
        """Update statistical buffer for telemetry analysis"""
        spacecraft_id = point.spacecraft_id
        parameter = point.parameter
        
        if spacecraft_id not in self.telemetry_buffers:
            self.telemetry_buffers[spacecraft_id] = {}
        
        if parameter not in self.telemetry_buffers[spacecraft_id]:
            self.telemetry_buffers[spacecraft_id][parameter] = []
        
        buffer = self.telemetry_buffers[spacecraft_id][parameter]
        buffer.append(point.value)
        
        # Keep buffer size limited
        if len(buffer) > self.buffer_size:
            buffer.pop(0)
    
    def check_telemetry_alerts(self, point: TelemetryPoint):
        """Check telemetry point against alert thresholds"""
        spacecraft_id = point.spacecraft_id
        parameter = point.parameter
        value = point.value
        
        # Get thresholds for this parameter
        thresholds = self.thresholds.get(parameter, {})
        
        # Check critical thresholds
        if 'critical_min' in thresholds and value < thresholds['critical_min']:
            self.generate_alert(
                spacecraft_id, 
                'critical',
                f"{parameter} critically low: {value:.2f}"
            )
        elif 'critical_max' in thresholds and value > thresholds['critical_max']:
            self.generate_alert(
                spacecraft_id,
                'critical', 
                f"{parameter} critically high: {value:.2f}"
            )
        # Check warning thresholds
        elif 'warning_min' in thresholds and value < thresholds['warning_min']:
            self.generate_alert(
                spacecraft_id,
                'warning',
                f"{parameter} low: {value:.2f}"
            )
        elif 'warning_max' in thresholds and value > thresholds['warning_max']:
            self.generate_alert(
                spacecraft_id,
                'warning',
                f"{parameter} high: {value:.2f}"
            )
        
        # Check for rapid changes
        self.check_rate_of_change(point)
    
    def check_rate_of_change(self, point: TelemetryPoint):
        """Check for rapid rate of change in telemetry"""
        spacecraft_id = point.spacecraft_id
        parameter = point.parameter
        
        if (spacecraft_id in self.telemetry_buffers and 
            parameter in self.telemetry_buffers[spacecraft_id]):
            
            buffer = self.telemetry_buffers[spacecraft_id][parameter]
            
            if len(buffer) >= 5:  # Need at least 5 points
                recent_values = buffer[-5:]
                
                # Calculate rate of change
                if len(set(recent_values)) > 1:  # Values are changing
                    slope = np.polyfit(range(len(recent_values)), 
                                     recent_values, 1)[0]
                    
                    # Check if rate of change is excessive
                    rate_thresholds = self.thresholds.get(parameter, {})
                    max_rate = rate_thresholds.get('max_rate_of_change', None)
                    
                    if max_rate and abs(slope) > max_rate:
                        self.generate_alert(
                            spacecraft_id,
                            'warning',
                            f"{parameter} changing rapidly: {slope:.2f}/sample"
                        )
    
    def generate_alert(self, spacecraft_id: str, severity: str, message: str):
        """Generate and emit an alert"""
        # Store alert in database
        with sqlite3.connect(self.database.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts 
                (timestamp, spacecraft_id, alert_type, severity, message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                spacecraft_id,
                'telemetry',
                severity,
                message
            ))
            conn.commit()
        
        # Emit signal
        self.alert_generated.emit(spacecraft_id, severity, message)
    
    def queue_telemetry_point(self, point: TelemetryPoint):
        """Queue a telemetry point for processing"""
        self.processing_queue.put(point)
    
    def get_telemetry_statistics(self, spacecraft_id: str, 
                               parameter: str) -> Dict[str, float]:
        """Get statistical analysis of telemetry parameter"""
        if (spacecraft_id in self.telemetry_buffers and 
            parameter in self.telemetry_buffers[spacecraft_id]):
            
            values = self.telemetry_buffers[spacecraft_id][parameter]
            
            if values:
                return {
                    'mean': statistics.mean(values),
                    'median': statistics.median(values),
                    'stdev': statistics.stdev(values) if len(values) > 1 else 0,
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }
        
        return {}
    
    def load_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Load alert thresholds configuration"""
        # Default thresholds - would normally load from config file
        return {
            'battery_voltage': {
                'warning_min': 11.5,
                'critical_min': 10.5,
                'warning_max': 14.0,
                'critical_max': 15.0,
                'max_rate_of_change': 0.5
            },
            'cpu_temp': {
                'warning_max': 70.0,
                'critical_max': 85.0,
                'max_rate_of_change': 5.0
            },
            'battery_temp': {
                'warning_min': -20.0,
                'critical_min': -30.0,
                'warning_max': 50.0,
                'critical_max': 60.0
            },
            'power_consumption': {
                'warning_max': 90.0,
                'critical_max': 100.0
            },
            'signal_strength': {
                'warning_min': -80.0,
                'critical_min': -90.0
            }
        }


class DataAnalyzer:
    """Advanced data analysis capabilities"""
    
    def __init__(self, database: TelemetryDatabase):
        self.database = database
    
    def calculate_mission_statistics(self, spacecraft_id: str, 
                                   days_back: int = 7) -> Dict[str, Any]:
        """Calculate comprehensive mission statistics"""
        start_time = datetime.now() - timedelta(days=days_back)
        
        with sqlite3.connect(self.database.db_path) as conn:
            cursor = conn.cursor()
            
            # Get telemetry statistics
            cursor.execute("""
                SELECT parameter, AVG(value), MIN(value), MAX(value), COUNT(*)
                FROM telemetry_points
                WHERE spacecraft_id = ? AND timestamp >= ?
                GROUP BY parameter
            """, (spacecraft_id, start_time.isoformat()))
            
            telemetry_stats = {}
            for row in cursor.fetchall():
                telemetry_stats[row[0]] = {
                    'average': row[1],
                    'minimum': row[2],
                    'maximum': row[3],
                    'count': row[4]
                }
            
            # Get alert statistics
            cursor.execute("""
                SELECT severity, COUNT(*)
                FROM alerts
                WHERE spacecraft_id = ? AND timestamp >= ?
                GROUP BY severity
            """, (spacecraft_id, start_time.isoformat()))
            
            alert_stats = {}
            for row in cursor.fetchall():
                alert_stats[row[0]] = row[1]
            
            # Get uptime percentage
            cursor.execute("""
                SELECT COUNT(DISTINCT DATE(timestamp)) as active_days
                FROM telemetry_points
                WHERE spacecraft_id = ? AND timestamp >= ?
            """, (spacecraft_id, start_time.isoformat()))
            
            active_days = cursor.fetchone()[0]
            uptime_percentage = (active_days / days_back) * 100
            
            return {
                'telemetry_statistics': telemetry_stats,
                'alert_statistics': alert_stats,
                'uptime_percentage': uptime_percentage,
                'analysis_period_days': days_back
            }
    
    def detect_anomalies(self, spacecraft_id: str, parameter: str,
                        hours_back: int = 24) -> List[Dict[str, Any]]:
        """Detect anomalies in telemetry data using statistical methods"""
        history = self.database.get_telemetry_history(
            spacecraft_id, parameter, hours_back
        )
        
        if len(history) < 10:  # Need sufficient data
            return []
        
        values = [point.value for point in history]
        timestamps = [point.timestamp for point in history]
        
        # Calculate statistical thresholds
        mean_value = statistics.mean(values)
        std_dev = statistics.stdev(values)
        
        # Define anomaly thresholds (2 standard deviations)
        upper_threshold = mean_value + (2 * std_dev)
        lower_threshold = mean_value - (2 * std_dev)
        
        anomalies = []
        for i, value in enumerate(values):
            if value > upper_threshold or value < lower_threshold:
                anomalies.append({
                    'timestamp': timestamps[i],
                    'value': value,
                    'expected_range': (lower_threshold, upper_threshold),
                    'deviation_sigma': abs(value - mean_value) / std_dev
                })
        
        return anomalies
    
    def predict_next_values(self, spacecraft_id: str, parameter: str,
                          prediction_steps: int = 10) -> List[float]:
        """Simple linear prediction of next telemetry values"""
        history = self.database.get_telemetry_history(
            spacecraft_id, parameter, hours_back=6
        )
        
        if len(history) < 5:
            return []
        
        values = [point.value for point in history[-20:]]  # Use last 20 points
        
        # Simple linear regression for prediction
        x = np.arange(len(values))
        coefficients = np.polyfit(x, values, 1)
        
        # Predict next values
        predictions = []
        for i in range(1, prediction_steps + 1):
            next_x = len(values) + i
            predicted_value = coefficients[0] * next_x + coefficients[1]
            predictions.append(predicted_value)
        
        return predictions


class EnhancedDataProvider:
    """Enhanced data provider with real-time processing"""
    
    def __init__(self):
        self.telemetry_processor = TelemetryProcessor()
        self.data_analyzer = DataAnalyzer(self.telemetry_processor.database)
        
        # Start background processing
        self.telemetry_processor.start_processing()
        
        # Simulation timer for demo data
        self.simulation_timer = QTimer()
        self.simulation_timer.timeout.connect(self.generate_demo_telemetry)
        self.simulation_timer.start(2000)  # Generate every 2 seconds
    
    def generate_demo_telemetry(self):
        """Generate demo telemetry data"""
        spacecraft_list = ["ISS", "Hubble", "JWST", "Dragon", "Starlink-1"]
        
        for spacecraft_id in spacecraft_list:
            timestamp = datetime.now()
            
            # Generate realistic telemetry values
            import random

            # Power system
            self.add_telemetry_point(TelemetryPoint(
                timestamp=timestamp,
                spacecraft_id=spacecraft_id,
                parameter="battery_voltage",
                value=12.0 + random.uniform(-0.5, 0.5),
                unit="V"
            ))
            
            # Thermal
            self.add_telemetry_point(TelemetryPoint(
                timestamp=timestamp,
                spacecraft_id=spacecraft_id,
                parameter="cpu_temp",
                value=35.0 + random.uniform(-5, 15),
                unit="°C"
            ))
            
            # Attitude
            self.add_telemetry_point(TelemetryPoint(
                timestamp=timestamp,
                spacecraft_id=spacecraft_id,
                parameter="roll",
                value=random.uniform(-180, 180),
                unit="°"
            ))
    
    def add_telemetry_point(self, point: TelemetryPoint):
        """Add a telemetry point for processing"""
        self.telemetry_processor.queue_telemetry_point(point)
    
    def get_telemetry_history(self, spacecraft_id: str, parameter: str,
                            hours_back: int = 24) -> List[TelemetryPoint]:
        """Get telemetry history"""
        return self.telemetry_processor.database.get_telemetry_history(
            spacecraft_id, parameter, hours_back
        )
    
    def get_mission_analytics(self, spacecraft_id: str) -> Dict[str, Any]:
        """Get comprehensive mission analytics"""
        return self.data_analyzer.calculate_mission_statistics(spacecraft_id)
    
    def detect_telemetry_anomalies(self, spacecraft_id: str, 
                                 parameter: str) -> List[Dict[str, Any]]:
        """Detect anomalies in telemetry"""
        return self.data_analyzer.detect_anomalies(spacecraft_id, parameter)
    
    def get_telemetry_predictions(self, spacecraft_id: str, 
                                parameter: str) -> List[float]:
        """Get telemetry predictions"""
        return self.data_analyzer.predict_next_values(spacecraft_id, parameter)
    
    def shutdown(self):
        """Shutdown data provider"""
        self.simulation_timer.stop()
        self.telemetry_processor.stop_processing()


# Create global enhanced data provider instance
enhanced_data_provider = EnhancedDataProvider()
