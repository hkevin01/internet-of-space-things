"""
Orbital Inference Engine for CubeSat-Enabled Hybrid Survival Network (CEHSN)
Onboard CubeSat ML for anomaly detection (radiation spikes, wildfires, etc.)
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies the system can detect"""
    RADIATION_SPIKE = "radiation_spike"
    WILDFIRE = "wildfire"
    FLOOD = "flood"
    EARTHQUAKE = "earthquake"
    VOLCANIC_ACTIVITY = "volcanic_activity"
    ATMOSPHERIC_DISTURBANCE = "atmospheric_disturbance"
    SPACE_WEATHER = "space_weather"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Confidence levels for inference results"""
    LOW = "low"        # 0.0 - 0.4
    MEDIUM = "medium"  # 0.4 - 0.7
    HIGH = "high"      # 0.7 - 0.9
    CRITICAL = "critical"  # 0.9 - 1.0


@dataclass
class GeospatialCoordinate:
    """Geospatial coordinate with uncertainty"""
    latitude: float  # degrees
    longitude: float  # degrees
    altitude: Optional[float] = None  # meters
    uncertainty_radius: float = 1000.0  # meters
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SensorReading:
    """Raw sensor reading from CubeSat"""
    sensor_id: str
    sensor_type: str  # "optical", "infrared", "radiation", "magnetometer"
    reading_value: float
    units: str
    coordinate: GeospatialCoordinate
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InferenceResult:
    """Result of anomaly detection inference"""
    anomaly_type: AnomalyType
    confidence_score: float  # 0.0 - 1.0
    confidence_level: ConfidenceLevel
    location: GeospatialCoordinate
    severity: float  # 0.0 - 1.0 (1.0 = most severe)
    description: str
    affected_area_km2: Optional[float] = None
    predicted_duration_hours: Optional[float] = None
    risk_factors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set confidence level based on score"""
        if self.confidence_score >= 0.9:
            self.confidence_level = ConfidenceLevel.CRITICAL
        elif self.confidence_score >= 0.7:
            self.confidence_level = ConfidenceLevel.HIGH
        elif self.confidence_score >= 0.4:
            self.confidence_level = ConfidenceLevel.MEDIUM
        else:
            self.confidence_level = ConfidenceLevel.LOW


class OrbitalInferenceEngine:
    """
    AI-powered orbital inference engine for anomaly detection
    Runs onboard CubeSats for real-time disaster and environmental monitoring
    """
    
    def __init__(self, cubesat_id: str, model_config: Optional[Dict[str, Any]] = None):
        self.cubesat_id = cubesat_id
        self.model_config = model_config or {}
        self.is_active = False
        self.inference_history: List[InferenceResult] = []
        self.sensor_calibration: Dict[str, Dict[str, float]] = {}
        
        # Model parameters (simplified ML models)
        self.radiation_threshold = 1000.0  # counts per minute
        self.temperature_anomaly_std = 3.0  # standard deviations
        self.optical_fire_threshold = 0.8  # normalized brightness
        self.seismic_threshold = 4.0  # Richter scale equivalent
        
        # Historical data for baseline comparison
        self.baseline_data: Dict[str, List[float]] = {
            "radiation": [],
            "temperature": [],
            "optical_brightness": [],
            "seismic_activity": []
        }
        
        # Bayesian update parameters
        self.prior_probabilities: Dict[AnomalyType, float] = {
            AnomalyType.RADIATION_SPIKE: 0.05,
            AnomalyType.WILDFIRE: 0.10,
            AnomalyType.FLOOD: 0.08,
            AnomalyType.EARTHQUAKE: 0.03,
            AnomalyType.VOLCANIC_ACTIVITY: 0.01,
            AnomalyType.ATMOSPHERIC_DISTURBANCE: 0.15,
            AnomalyType.SPACE_WEATHER: 0.12,
            AnomalyType.UNKNOWN: 0.46
        }
        
        logger.info(f"Orbital Inference Engine initialized for CubeSat {cubesat_id}")
    
    async def start_inference_engine(self) -> bool:
        """Start the inference engine"""
        try:
            self.is_active = True
            await self._load_baseline_data()
            await self._calibrate_sensors()
            
            logger.info(f"Inference engine started for {self.cubesat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start inference engine: {e}")
            return False
    
    async def stop_inference_engine(self) -> bool:
        """Stop the inference engine"""
        self.is_active = False
        logger.info(f"Inference engine stopped for {self.cubesat_id}")
        return True
    
    async def process_sensor_reading(self, reading: SensorReading) -> Optional[InferenceResult]:
        """Process a single sensor reading and detect anomalies"""
        if not self.is_active:
            logger.warning("Inference engine not active")
            return None
        
        try:
            # Update baseline data
            await self._update_baseline(reading)
            
            # Perform anomaly detection based on sensor type
            result = None
            
            if reading.sensor_type == "radiation":
                result = await self._detect_radiation_anomaly(reading)
            elif reading.sensor_type == "optical":
                result = await self._detect_optical_anomaly(reading)
            elif reading.sensor_type == "infrared":
                result = await self._detect_thermal_anomaly(reading)
            elif reading.sensor_type == "seismic":
                result = await self._detect_seismic_anomaly(reading)
            elif reading.sensor_type == "magnetometer":
                result = await self._detect_magnetic_anomaly(reading)
            else:
                logger.warning(f"Unknown sensor type: {reading.sensor_type}")
                return None
            
            if result and result.confidence_score > 0.3:  # Minimum threshold
                self.inference_history.append(result)
                
                # Keep only recent history (last 1000 results)
                if len(self.inference_history) > 1000:
                    self.inference_history = self.inference_history[-1000:]
                
                logger.info(f"Anomaly detected: {result.anomaly_type.value} "
                           f"(confidence: {result.confidence_score:.2f})")
                
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing sensor reading: {e}")
            return None
    
    async def process_multiple_readings(self, readings: List[SensorReading]) -> List[InferenceResult]:
        """Process multiple sensor readings and perform fusion analysis"""
        results = []
        
        # Process individual readings
        individual_results = []
        for reading in readings:
            result = await self.process_sensor_reading(reading)
            if result:
                individual_results.append(result)
        
        # Perform sensor fusion if multiple results
        if len(individual_results) > 1:
            fused_result = await self._fuse_multiple_detections(individual_results)
            if fused_result:
                results.append(fused_result)
        else:
            results.extend(individual_results)
        
        return results
    
    async def get_inference_summary(self, hours_back: float = 24.0) -> Dict[str, Any]:
        """Get summary of inference results over specified time period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        recent_results = [
            result for result in self.inference_history
            if result.timestamp >= cutoff_time
        ]
        
        if not recent_results:
            return {
                "period_hours": hours_back,
                "total_detections": 0,
                "anomaly_types": {},
                "confidence_distribution": {},
                "severity_stats": {}
            }
        
        # Analyze anomaly types
        anomaly_counts = {}
        for result in recent_results:
            anomaly_type = result.anomaly_type.value
            anomaly_counts[anomaly_type] = anomaly_counts.get(anomaly_type, 0) + 1
        
        # Analyze confidence distribution
        confidence_dist = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for result in recent_results:
            confidence_dist[result.confidence_level.value] += 1
        
        # Calculate severity statistics
        severities = [result.severity for result in recent_results]
        severity_stats = {
            "mean": float(np.mean(severities)),
            "max": float(np.max(severities)),
            "min": float(np.min(severities)),
            "std": float(np.std(severities))
        }
        
        return {
            "period_hours": hours_back,
            "total_detections": len(recent_results),
            "anomaly_types": anomaly_counts,
            "confidence_distribution": confidence_dist,
            "severity_stats": severity_stats,
            "most_recent": recent_results[-1].__dict__ if recent_results else None
        }
    
    async def calibrate_sensor(self, sensor_id: str, calibration_data: Dict[str, float]) -> bool:
        """Calibrate a specific sensor"""
        try:
            self.sensor_calibration[sensor_id] = calibration_data
            logger.info(f"Calibrated sensor {sensor_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to calibrate sensor {sensor_id}: {e}")
            return False
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get current status of the inference engine"""
        return {
            "cubesat_id": self.cubesat_id,
            "is_active": self.is_active,
            "total_inferences": len(self.inference_history),
            "calibrated_sensors": len(self.sensor_calibration),
            "baseline_data_points": {
                sensor: len(data) for sensor, data in self.baseline_data.items()
            },
            "last_inference": (
                self.inference_history[-1].timestamp.isoformat()
                if self.inference_history else None
            )
        }
    
    # Private methods for anomaly detection
    
    async def _detect_radiation_anomaly(self, reading: SensorReading) -> Optional[InferenceResult]:
        """Detect radiation spike anomalies"""
        radiation_level = reading.reading_value
        
        # Simple threshold-based detection
        if radiation_level > self.radiation_threshold:
            confidence = min(1.0, radiation_level / (self.radiation_threshold * 2))
            severity = min(1.0, radiation_level / (self.radiation_threshold * 3))
            
            return InferenceResult(
                anomaly_type=AnomalyType.RADIATION_SPIKE,
                confidence_score=confidence,
                confidence_level=ConfidenceLevel.LOW,  # Will be set in __post_init__
                location=reading.coordinate,
                severity=severity,
                description=f"Radiation spike detected: {radiation_level:.1f} {reading.units}",
                affected_area_km2=100.0,  # Estimated
                predicted_duration_hours=2.0,
                risk_factors=["radiation_exposure", "space_weather"],
                raw_data={"radiation_level": radiation_level, "threshold": self.radiation_threshold}
            )
        
        return None
    
    async def _detect_optical_anomaly(self, reading: SensorReading) -> Optional[InferenceResult]:
        """Detect optical anomalies (fires, explosions)"""
        brightness = reading.reading_value
        
        # Normalize brightness and detect fires
        if brightness > self.optical_fire_threshold:
            confidence = min(1.0, brightness)
            severity = min(1.0, brightness * 0.8)
            
            return InferenceResult(
                anomaly_type=AnomalyType.WILDFIRE,
                confidence_score=confidence,
                confidence_level=ConfidenceLevel.LOW,
                location=reading.coordinate,
                severity=severity,
                description=f"Optical anomaly detected: normalized brightness {brightness:.2f}",
                affected_area_km2=25.0,
                predicted_duration_hours=12.0,
                risk_factors=["fire_spread", "smoke_inhalation", "ecosystem_damage"],
                raw_data={"brightness": brightness, "threshold": self.optical_fire_threshold}
            )
        
        return None
    
    async def _detect_thermal_anomaly(self, reading: SensorReading) -> Optional[InferenceResult]:
        """Detect thermal anomalies using infrared data"""
        temperature = reading.reading_value
        
        # Use baseline temperature data for anomaly detection
        baseline_temps = self.baseline_data.get("temperature", [])
        if len(baseline_temps) < 10:  # Need sufficient baseline
            return None
        
        mean_temp = np.mean(baseline_temps)
        std_temp = np.std(baseline_temps)
        
        if abs(temperature - mean_temp) > (self.temperature_anomaly_std * std_temp):
            z_score = abs(temperature - mean_temp) / std_temp
            confidence = min(1.0, z_score / (self.temperature_anomaly_std * 2))
            severity = min(1.0, z_score / (self.temperature_anomaly_std * 3))
            
            # Determine anomaly type based on temperature deviation
            if temperature > mean_temp:
                anomaly_type = AnomalyType.WILDFIRE
                description = f"High temperature anomaly: {temperature:.1f}°C (baseline: {mean_temp:.1f}°C)"
            else:
                anomaly_type = AnomalyType.ATMOSPHERIC_DISTURBANCE
                description = f"Low temperature anomaly: {temperature:.1f}°C (baseline: {mean_temp:.1f}°C)"
            
            return InferenceResult(
                anomaly_type=anomaly_type,
                confidence_score=confidence,
                confidence_level=ConfidenceLevel.LOW,
                location=reading.coordinate,
                severity=severity,
                description=description,
                affected_area_km2=50.0,
                predicted_duration_hours=6.0,
                risk_factors=["temperature_extreme"],
                raw_data={
                    "temperature": temperature,
                    "baseline_mean": mean_temp,
                    "baseline_std": std_temp,
                    "z_score": z_score
                }
            )
        
        return None
    
    async def _detect_seismic_anomaly(self, reading: SensorReading) -> Optional[InferenceResult]:
        """Detect seismic activity"""
        seismic_magnitude = reading.reading_value
        
        if seismic_magnitude > self.seismic_threshold:
            confidence = min(1.0, seismic_magnitude / 8.0)  # Normalize to Richter scale
            severity = min(1.0, seismic_magnitude / 9.0)
            
            # Calculate affected area based on magnitude
            affected_area = math.pow(10, seismic_magnitude - 3)  # Rough estimation
            
            return InferenceResult(
                anomaly_type=AnomalyType.EARTHQUAKE,
                confidence_score=confidence,
                confidence_level=ConfidenceLevel.LOW,
                location=reading.coordinate,
                severity=severity,
                description=f"Seismic activity detected: magnitude {seismic_magnitude:.1f}",
                affected_area_km2=affected_area,
                predicted_duration_hours=0.5,  # Main event duration
                risk_factors=["structural_damage", "tsunamis", "aftershocks"],
                raw_data={"magnitude": seismic_magnitude, "threshold": self.seismic_threshold}
            )
        
        return None
    
    async def _detect_magnetic_anomaly(self, reading: SensorReading) -> Optional[InferenceResult]:
        """Detect magnetic field anomalies (space weather)"""
        magnetic_field = reading.reading_value
        
        # Use baseline magnetic field data
        baseline_mag = self.baseline_data.get("magnetometer", [])
        if len(baseline_mag) < 10:
            return None
        
        mean_mag = np.mean(baseline_mag)
        std_mag = np.std(baseline_mag)
        
        deviation = abs(magnetic_field - mean_mag)
        if deviation > (2.0 * std_mag):  # 2-sigma threshold
            confidence = min(1.0, deviation / (4.0 * std_mag))
            severity = min(1.0, deviation / (5.0 * std_mag))
            
            return InferenceResult(
                anomaly_type=AnomalyType.SPACE_WEATHER,
                confidence_score=confidence,
                confidence_level=ConfidenceLevel.LOW,
                location=reading.coordinate,
                severity=severity,
                description=f"Magnetic field anomaly: {magnetic_field:.2f} nT (baseline: {mean_mag:.2f} nT)",
                affected_area_km2=10000.0,  # Large area for space weather
                predicted_duration_hours=24.0,
                risk_factors=["satellite_interference", "communication_disruption", "navigation_errors"],
                raw_data={
                    "magnetic_field": magnetic_field,
                    "baseline_mean": mean_mag,
                    "baseline_std": std_mag,
                    "deviation": deviation
                }
            )
        
        return None
    
    async def _fuse_multiple_detections(self, results: List[InferenceResult]) -> Optional[InferenceResult]:
        """Fuse multiple detection results using Bayesian inference"""
        if not results:
            return None
        
        # Group results by anomaly type
        type_groups = {}
        for result in results:
            anomaly_type = result.anomaly_type
            if anomaly_type not in type_groups:
                type_groups[anomaly_type] = []
            type_groups[anomaly_type].append(result)
        
        # Find the most likely anomaly type
        best_type = None
        max_combined_confidence = 0.0
        
        for anomaly_type, type_results in type_groups.items():
            # Combine confidences using Bayesian update
            combined_confidence = self._bayesian_confidence_fusion(type_results)
            
            if combined_confidence > max_combined_confidence:
                max_combined_confidence = combined_confidence
                best_type = anomaly_type
        
        if best_type and max_combined_confidence > 0.4:
            # Create fused result
            type_results = type_groups[best_type]
            
            # Average location
            avg_lat = np.mean([r.location.latitude for r in type_results])
            avg_lon = np.mean([r.location.longitude for r in type_results])
            
            fused_location = GeospatialCoordinate(
                latitude=avg_lat,
                longitude=avg_lon,
                uncertainty_radius=max(r.location.uncertainty_radius for r in type_results)
            )
            
            # Combine other attributes
            max_severity = max(r.severity for r in type_results)
            all_risk_factors = list(set(sum([r.risk_factors for r in type_results], [])))
            
            return InferenceResult(
                anomaly_type=best_type,
                confidence_score=max_combined_confidence,
                confidence_level=ConfidenceLevel.LOW,  # Will be set in __post_init__
                location=fused_location,
                severity=max_severity,
                description=f"Fused detection: {best_type.value} from {len(type_results)} sensors",
                affected_area_km2=max(r.affected_area_km2 or 0 for r in type_results),
                predicted_duration_hours=max(r.predicted_duration_hours or 0 for r in type_results),
                risk_factors=all_risk_factors,
                raw_data={"fused_from": len(type_results), "original_results": [r.__dict__ for r in type_results]}
            )
        
        return None
    
    def _bayesian_confidence_fusion(self, results: List[InferenceResult]) -> float:
        """Combine multiple confidence scores using Bayesian inference"""
        if not results:
            return 0.0
        
        # Start with prior probability
        anomaly_type = results[0].anomaly_type
        prior = self.prior_probabilities.get(anomaly_type, 0.1)
        
        # Update with each result using Bayes' theorem
        posterior = prior
        for result in results:
            likelihood = result.confidence_score
            # Simplified Bayesian update: P(A|B) ∝ P(B|A) * P(A)
            posterior = (likelihood * posterior) / ((likelihood * posterior) + ((1 - likelihood) * (1 - posterior)))
        
        return min(1.0, posterior)
    
    async def _update_baseline(self, reading: SensorReading):
        """Update baseline data with new reading"""
        sensor_type = reading.sensor_type
        
        if sensor_type not in self.baseline_data:
            self.baseline_data[sensor_type] = []
        
        self.baseline_data[sensor_type].append(reading.reading_value)
        
        # Keep only recent baseline data (last 1000 readings)
        if len(self.baseline_data[sensor_type]) > 1000:
            self.baseline_data[sensor_type] = self.baseline_data[sensor_type][-1000:]
    
    async def _load_baseline_data(self):
        """Load historical baseline data (placeholder)"""
        # In a real implementation, this would load from persistent storage
        logger.info("Loading baseline data...")
        
        # Generate some dummy baseline data for demonstration
        for sensor_type in ["radiation", "temperature", "optical_brightness", "seismic_activity"]:
            if sensor_type == "radiation":
                self.baseline_data[sensor_type] = list(np.random.normal(500, 50, 100))
            elif sensor_type == "temperature":
                self.baseline_data[sensor_type] = list(np.random.normal(20, 5, 100))
            elif sensor_type == "optical_brightness":
                self.baseline_data[sensor_type] = list(np.random.uniform(0.1, 0.5, 100))
            elif sensor_type == "seismic_activity":
                self.baseline_data[sensor_type] = list(np.random.exponential(1.0, 100))
    
    async def _calibrate_sensors(self):
        """Calibrate sensors (placeholder)"""
        logger.info("Calibrating sensors...")
        # In a real implementation, this would perform sensor calibration
        pass
