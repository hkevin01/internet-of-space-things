"""
Radiation Detector for Space Environment Monitoring
Monitors cosmic radiation, solar particle events, and radiation dose rates
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class RadiationType(Enum):
    COSMIC_RAY = "cosmic_ray"
    SOLAR_PARTICLE = "solar_particle"
    TRAPPED_RADIATION = "trapped_radiation"
    NEUTRON = "neutron"
    GAMMA = "gamma"


class AlertLevel(Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class RadiationReading:
    """Individual radiation measurement"""
    timestamp: datetime
    radiation_type: RadiationType
    dose_rate: float  # mSv/hr
    particle_count: int
    energy_spectrum: List[float]  # keV
    location: Optional[List[float]] = None  # [x, y, z] coordinates
    confidence: float = 1.0  # 0-1 confidence in reading


@dataclass
class RadiationAlert:
    """Radiation alert condition"""
    alert_id: str
    level: AlertLevel
    message: str
    readings: List[RadiationReading]
    triggered_at: datetime
    resolved_at: Optional[datetime] = None


class RadiationDetector:
    """
    Space-Grade Radiation Detection System
    Monitors various types of radiation in space environment
    """
    
    def __init__(self, detector_id: str, sensitivity: float = 1.0):
        self.detector_id = detector_id
        self.sensitivity = sensitivity
        self.is_active = False
        self.is_calibrated = True
        
        # Measurement parameters
        self.measurement_interval = 1.0  # seconds
        self.integration_time = 10.0     # seconds for averaging
        self.alert_thresholds = {
            AlertLevel.ELEVATED: 0.5,    # mSv/hr
            AlertLevel.HIGH: 2.0,
            AlertLevel.SEVERE: 10.0,
            AlertLevel.EXTREME: 50.0
        }
        
        # Detector characteristics
        self.detector_area = 10.0  # cm²
        self.energy_range = (1.0, 10000.0)  # keV
        self.efficiency = 0.85  # Detection efficiency
        
        # Data storage
        self.readings_history: List[RadiationReading] = []
        self.active_alerts: Dict[str, RadiationAlert] = {}
        self.calibration_factors = {
            RadiationType.COSMIC_RAY: 1.0,
            RadiationType.SOLAR_PARTICLE: 1.1,
            RadiationType.TRAPPED_RADIATION: 0.9,
            RadiationType.NEUTRON: 1.2,
            RadiationType.GAMMA: 1.0
        }
        
        # Statistics
        self.total_dose = 0.0  # Total accumulated dose (mSv)
        self.peak_dose_rate = 0.0  # Highest dose rate recorded
        self.detector_uptime = datetime.utcnow()
        
        logger.info(f"Radiation detector {detector_id} initialized")
    
    async def start_monitoring(self) -> bool:
        """Start continuous radiation monitoring"""
        if self.is_active:
            logger.warning("Radiation monitoring already active")
            return False
        
        if not self.is_calibrated:
            logger.error("Detector not calibrated, cannot start monitoring")
            return False
        
        self.is_active = True
        self.detector_uptime = datetime.utcnow()
        
        # Start monitoring task
        asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"Started radiation monitoring on detector {self.detector_id}")
        return True
    
    async def stop_monitoring(self) -> bool:
        """Stop radiation monitoring"""
        self.is_active = False
        logger.info(f"Stopped radiation monitoring on detector {self.detector_id}")
        return True
    
    async def calibrate_detector(self, calibration_source: str = "Cs-137") -> bool:
        """Calibrate the radiation detector"""
        try:
            logger.info(f"Calibrating detector with {calibration_source} source...")
            
            # Simulate calibration process
            await asyncio.sleep(2.0)  # Calibration time
            
            # Generate calibration readings
            calibration_readings = []
            for _ in range(10):
                reading = await self._simulate_calibration_reading(calibration_source)
                calibration_readings.append(reading)
                await asyncio.sleep(0.1)
            
            # Calculate calibration factors
            expected_dose_rate = 1.0  # Expected mSv/hr for Cs-137
            measured_rates = [r.dose_rate for r in calibration_readings]
            avg_measured = np.mean(measured_rates)
            
            if avg_measured > 0:
                calibration_factor = expected_dose_rate / avg_measured
                
                # Update calibration factors
                for rad_type in RadiationType:
                    self.calibration_factors[rad_type] *= calibration_factor
                
                self.is_calibrated = True
                logger.info(f"Detector calibrated successfully. Factor: {calibration_factor:.3f}")
                return True
            else:
                logger.error("Calibration failed: no signal detected")
                return False
                
        except Exception as e:
            logger.error(f"Detector calibration failed: {e}")
            self.is_calibrated = False
            return False
    
    async def take_reading(self, integration_time: Optional[float] = None) -> RadiationReading:
        """Take a single radiation reading"""
        if integration_time is None:
            integration_time = self.integration_time
        
        # Simulate measurement process
        await asyncio.sleep(integration_time)
        
        # Generate realistic radiation reading based on space environment
        radiation_type = self._determine_radiation_type()
        reading = await self._simulate_reading(radiation_type, integration_time)
        
        # Apply calibration
        reading.dose_rate *= self.calibration_factors[radiation_type]
        
        # Store reading
        self.readings_history.append(reading)
        
        # Update statistics
        self.total_dose += reading.dose_rate * (integration_time / 3600)  # Convert to hours
        self.peak_dose_rate = max(self.peak_dose_rate, reading.dose_rate)
        
        # Check for alerts
        await self._check_radiation_alerts(reading)
        
        return reading
    
    async def get_dose_rate_trend(self, duration: timedelta) -> Dict[str, Any]:
        """Get radiation dose rate trend over specified duration"""
        cutoff_time = datetime.utcnow() - duration
        recent_readings = [r for r in self.readings_history if r.timestamp > cutoff_time]
        
        if not recent_readings:
            return {"trend": "no_data", "readings": 0}
        
        dose_rates = [r.dose_rate for r in recent_readings]
        timestamps = [r.timestamp for r in recent_readings]
        
        # Calculate trend using linear regression
        if len(dose_rates) > 1:
            time_deltas = [(t - timestamps[0]).total_seconds() for t in timestamps]
            slope = np.polyfit(time_deltas, dose_rates, 1)[0]
            
            if slope > 0.01:
                trend = "increasing"
            elif slope < -0.01:
                trend = "decreasing"  
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "trend": trend,
            "readings": len(recent_readings),
            "current_rate": dose_rates[-1] if dose_rates else 0,
            "average_rate": np.mean(dose_rates),
            "peak_rate": max(dose_rates),
            "slope": slope if len(dose_rates) > 1 else 0
        }
    
    async def predict_solar_event(self) -> Dict[str, Any]:
        """Predict potential solar particle events based on radiation patterns"""
        # Look for characteristic patterns in recent readings
        recent_readings = self.readings_history[-100:]  # Last 100 readings
        
        solar_readings = [r for r in recent_readings 
                         if r.radiation_type == RadiationType.SOLAR_PARTICLE]
        
        if len(solar_readings) < 10:
            return {"prediction": "insufficient_data", "confidence": 0.0}
        
        # Analyze trends in solar particle flux
        recent_rates = [r.dose_rate for r in solar_readings[-10:]]
        rate_increase = np.mean(recent_rates[-5:]) - np.mean(recent_rates[:5])
        
        particle_counts = [r.particle_count for r in solar_readings[-10:]]
        count_trend = np.polyfit(range(len(particle_counts)), particle_counts, 1)[0]
        
        # Prediction logic
        if rate_increase > 1.0 and count_trend > 100:
            prediction = "major_event_likely"
            confidence = min(0.9, (rate_increase + count_trend/1000))
        elif rate_increase > 0.5 or count_trend > 50:
            prediction = "minor_event_possible"
            confidence = min(0.7, (rate_increase + count_trend/2000))
        else:
            prediction = "no_event_expected"
            confidence = 0.8
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "rate_increase": rate_increase,
            "particle_trend": count_trend,
            "estimated_arrival": datetime.utcnow() + timedelta(hours=2) if prediction != "no_event_expected" else None
        }
    
    def get_detector_status(self) -> Dict[str, Any]:
        """Get comprehensive detector status"""
        uptime = (datetime.utcnow() - self.detector_uptime).total_seconds()
        
        return {
            "detector_id": self.detector_id,
            "is_active": self.is_active,
            "is_calibrated": self.is_calibrated,
            "sensitivity": self.sensitivity,
            "uptime_hours": uptime / 3600,
            "total_readings": len(self.readings_history),
            "active_alerts": len(self.active_alerts),
            "total_dose_msv": self.total_dose,
            "peak_dose_rate": self.peak_dose_rate,
            "current_status": "operational" if self.is_active and self.is_calibrated else "offline"
        }
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_active:
            try:
                await self.take_reading()
                await asyncio.sleep(self.measurement_interval)
                
            except Exception as e:
                logger.error(f"Error in radiation monitoring loop: {e}")
                await asyncio.sleep(5.0)  # Wait before retrying
    
    async def _simulate_reading(self, radiation_type: RadiationType, 
                               integration_time: float) -> RadiationReading:
        """Simulate a radiation reading"""
        # Base dose rates for different radiation types in space (mSv/hr)
        base_rates = {
            RadiationType.COSMIC_RAY: 0.1,
            RadiationType.SOLAR_PARTICLE: 0.05,
            RadiationType.TRAPPED_RADIATION: 0.2,
            RadiationType.NEUTRON: 0.02,
            RadiationType.GAMMA: 0.03
        }
        
        # Add random variation
        base_rate = base_rates[radiation_type]
        dose_rate = np.random.gamma(2, base_rate / 2)  # Gamma distribution for realism
        
        # Simulate particle counting
        expected_counts = dose_rate * integration_time * 1000  # Rough conversion
        particle_count = np.random.poisson(expected_counts)
        
        # Generate energy spectrum (simplified)
        spectrum_points = 50
        if radiation_type == RadiationType.COSMIC_RAY:
            # High energy spectrum
            energies = np.random.lognormal(8, 2, spectrum_points)
        elif radiation_type == RadiationType.SOLAR_PARTICLE:
            # Lower energy spectrum
            energies = np.random.lognormal(6, 1.5, spectrum_points)
        else:
            # Mixed spectrum
            energies = np.random.lognormal(7, 1.8, spectrum_points)
        
        # Ensure energies are within detector range
        energies = np.clip(energies, self.energy_range[0], self.energy_range[1])
        
        return RadiationReading(
            timestamp=datetime.utcnow(),
            radiation_type=radiation_type,
            dose_rate=dose_rate,
            particle_count=particle_count,
            energy_spectrum=energies.tolist(),
            confidence=self.efficiency
        )
    
    async def _simulate_calibration_reading(self, source: str) -> RadiationReading:
        """Simulate calibration reading"""
        # Known calibration sources
        source_properties = {
            "Cs-137": {"dose_rate": 1.0, "energy": 662},  # keV
            "Co-60": {"dose_rate": 2.0, "energy": 1253},
            "Am-241": {"dose_rate": 0.1, "energy": 60}
        }
        
        props = source_properties.get(source, source_properties["Cs-137"])
        
        # Add measurement uncertainty
        measured_rate = np.random.normal(props["dose_rate"], props["dose_rate"] * 0.05)
        measured_rate = max(0, measured_rate)  # Ensure positive
        
        # Simplified spectrum for calibration source
        spectrum = [props["energy"]] * 10  # Monoenergetic source
        
        return RadiationReading(
            timestamp=datetime.utcnow(),
            radiation_type=RadiationType.GAMMA,
            dose_rate=measured_rate,
            particle_count=int(measured_rate * 1000),
            energy_spectrum=spectrum,
            confidence=0.95
        )
    
    def _determine_radiation_type(self) -> RadiationType:
        """Determine which type of radiation to simulate based on space environment"""
        # Probabilities for different radiation types in space
        probabilities = {
            RadiationType.COSMIC_RAY: 0.4,
            RadiationType.SOLAR_PARTICLE: 0.2,
            RadiationType.TRAPPED_RADIATION: 0.25,
            RadiationType.NEUTRON: 0.1,
            RadiationType.GAMMA: 0.05
        }
        
        return np.random.choice(
            list(probabilities.keys()),
            p=list(probabilities.values())
        )
    
    async def _check_radiation_alerts(self, reading: RadiationReading):
        """Check if reading triggers any radiation alerts"""
        current_level = AlertLevel.NORMAL
        
        # Determine alert level based on dose rate
        for level, threshold in sorted(self.alert_thresholds.items(), 
                                     key=lambda x: x[1], reverse=True):
            if reading.dose_rate >= threshold:
                current_level = level
                break
        
        # Generate alert if above normal
        if current_level != AlertLevel.NORMAL:
            alert_id = f"radiation_{current_level.value}_{reading.timestamp.timestamp()}"
            
            if alert_id not in self.active_alerts:
                alert = RadiationAlert(
                    alert_id=alert_id,
                    level=current_level,
                    message=f"Radiation level {current_level.value}: {reading.dose_rate:.2f} mSv/hr",
                    readings=[reading],
                    triggered_at=reading.timestamp
                )
                
                self.active_alerts[alert_id] = alert
                logger.warning(f"Radiation alert: {alert.message}")
        
        # Check for resolved alerts
        resolved_alerts = []
        for alert_id, alert in self.active_alerts.items():
            if (reading.timestamp - alert.triggered_at).total_seconds() > 300:  # 5 minutes
                if reading.dose_rate < self.alert_thresholds[AlertLevel.ELEVATED]:
                    alert.resolved_at = reading.timestamp
                    resolved_alerts.append(alert_id)
        
        # Remove resolved alerts
        for alert_id in resolved_alerts:
            del self.active_alerts[alert_id]
            logger.info(f"Radiation alert {alert_id} resolved")
