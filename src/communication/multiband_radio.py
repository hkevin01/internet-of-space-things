"""
Multiband Communication System for Internet of Space Things
Supports microwave, millimeter-wave, terahertz, and optical frequencies
Implements adaptive frequency selection and cognitive radio capabilities
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class FrequencyBand(Enum):
    """Supported communication frequency bands"""
    MICROWAVE = {
        "name": "Microwave",
        "freq_range": (300e6, 30e9),  # 300 MHz - 30 GHz
        "characteristics": {
            "propagation": "line_of_sight",
            "atmospheric_absorption": "low",
            "rain_fade": "moderate",
            "bandwidth": "high"
        }
    }
    MILLIMETER_WAVE = {
        "name": "Millimeter Wave",
        "freq_range": (30e9, 300e9),  # 30 - 300 GHz
        "characteristics": {
            "propagation": "line_of_sight",
            "atmospheric_absorption": "high",
            "rain_fade": "severe",
            "bandwidth": "very_high"
        }
    }
    TERAHERTZ = {
        "name": "Terahertz",
        "freq_range": (300e9, 3e12),  # 300 GHz - 3 THz
        "characteristics": {
            "propagation": "highly_directional",
            "atmospheric_absorption": "extreme",
            "rain_fade": "critical",
            "bandwidth": "ultra_high"
        }
    }
    OPTICAL = {
        "name": "Optical",
        "freq_range": (1e14, 1e15),  # ~300-30 THz (infrared)
        "characteristics": {
            "propagation": "free_space_optics",
            "atmospheric_absorption": "weather_dependent",
            "rain_fade": "complete_blockage",
            "bandwidth": "extreme"
        }
    }


class ModulationType(Enum):
    BPSK = "binary_phase_shift_keying"
    QPSK = "quadrature_phase_shift_keying"
    QAM16 = "16_quadrature_amplitude_modulation"
    QAM64 = "64_quadrature_amplitude_modulation"
    OFDM = "orthogonal_frequency_division_multiplexing"
    ADAPTIVE = "adaptive_modulation"


@dataclass
class ChannelConditions:
    """Real-time channel condition assessment"""
    signal_to_noise_ratio: float  # dB
    bit_error_rate: float
    atmospheric_loss: float  # dB
    multipath_fading: float
    doppler_shift: float  # Hz
    interference_level: float
    weather_impact: str  # "clear", "cloudy", "rain", "storm"
    link_quality_score: float  # 0.0 - 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CommunicationLink:
    """Represents a communication link between two nodes"""
    link_id: str
    source_node: str
    destination_node: str
    frequency_band: FrequencyBand
    modulation: ModulationType
    data_rate: float  # bps
    power_level: float  # dBm
    antenna_gain: float  # dBi
    is_active: bool = True
    channel_conditions: Optional[ChannelConditions] = None
    quality_history: List[float] = field(default_factory=list)
    established_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TransmissionRequest:
    """Request for data transmission"""
    request_id: str
    source: str
    destination: str
    data_size: int  # bytes
    qos_requirements: Dict[str, Any]
    priority: int  # 1-10 (10 = highest)
    deadline: Optional[datetime] = None
    preferred_bands: List[FrequencyBand] = field(default_factory=list)


class MultibandRadio:
    """
    Advanced multiband radio system with cognitive capabilities
    Supports adaptive frequency selection and interference mitigation
    """
    
    def __init__(self, radio_id: str, supported_bands: List[FrequencyBand]):
        self.radio_id = radio_id
        self.supported_bands = supported_bands
        self.active_links: Dict[str, CommunicationLink] = {}
        self.spectrum_sensing_data: Dict[str, List[float]] = {}
        self.cognitive_engine_enabled = True
        self.ai_models: Dict[str, Any] = {}
        
        # Performance metrics
        self.throughput_history: List[float] = []
        self.error_rate_history: List[float] = []
        self.power_consumption: float = 0.0
        
        # Adaptive parameters
        self.min_snr_threshold = 10.0  # dB
        self.max_acceptable_ber = 1e-6
        self.link_quality_threshold = 0.7
        
        logger.info(f"Multiband radio {radio_id} initialized with {len(supported_bands)} bands")
    
    async def sense_spectrum(self, duration: float = 1.0) -> Dict[FrequencyBand, Dict[str, float]]:
        """Perform spectrum sensing across all supported bands"""
        spectrum_data = {}
        
        for band in self.supported_bands:
            freq_range = band.value["freq_range"]
            
            # Simulate spectrum sensing
            spectrum_info = await self._measure_spectrum_occupancy(band, duration)
            spectrum_data[band] = spectrum_info
            
            # Store historical data
            if band.name not in self.spectrum_sensing_data:
                self.spectrum_sensing_data[band.name] = []
            
            self.spectrum_sensing_data[band.name].append(spectrum_info["occupancy"])
            
            # Keep only recent history
            if len(self.spectrum_sensing_data[band.name]) > 100:
                self.spectrum_sensing_data[band.name].pop(0)
        
        logger.debug(f"Spectrum sensing completed for {len(spectrum_data)} bands")
        return spectrum_data
    
    async def select_optimal_band(self, 
                                transmission_req: TransmissionRequest,
                                channel_conditions: Dict[str, ChannelConditions]) -> Optional[FrequencyBand]:
        """AI-driven optimal frequency band selection"""
        
        # Get current spectrum conditions
        spectrum_data = await self.sense_spectrum()
        
        # Score each available band
        band_scores = {}
        
        for band in self.supported_bands:
            if band in transmission_req.preferred_bands or not transmission_req.preferred_bands:
                score = await self._calculate_band_score(
                    band, transmission_req, spectrum_data.get(band, {}),
                    channel_conditions.get(transmission_req.destination)
                )
                band_scores[band] = score
        
        if not band_scores:
            return None
        
        # Select band with highest score
        optimal_band = max(band_scores.items(), key=lambda x: x[1])[0]
        
        logger.info(f"Selected {optimal_band.value['name']} band (score: {band_scores[optimal_band]:.2f})")
        return optimal_band
    
    async def establish_link(self, 
                           source: str, 
                           destination: str,
                           band: FrequencyBand,
                           qos_requirements: Dict[str, Any]) -> Optional[CommunicationLink]:
        """Establish communication link with specified parameters"""
        
        link_id = f"{source}-{destination}-{band.name}"
        
        # Check if link already exists
        if link_id in self.active_links:
            return self.active_links[link_id]
        
        try:
            # Determine optimal modulation
            modulation = await self._select_modulation(band, qos_requirements)
            
            # Calculate link parameters
            power_level, data_rate = await self._calculate_link_budget(
                band, modulation, qos_requirements
            )
            
            # Create communication link
            link = CommunicationLink(
                link_id=link_id,
                source_node=source,
                destination_node=destination,
                frequency_band=band,
                modulation=modulation,
                data_rate=data_rate,
                power_level=power_level,
                antenna_gain=self._get_antenna_gain(band)
            )
            
            # Perform initial channel assessment
            link.channel_conditions = await self._assess_channel_conditions(link)
            
            if link.channel_conditions.link_quality_score > self.link_quality_threshold:
                self.active_links[link_id] = link
                logger.info(f"Established {band.value['name']} link: {source} -> {destination}")
                return link
            else:
                logger.warning(f"Link quality too low for {link_id}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to establish link {link_id}: {e}")
            return None
    
    async def adaptive_transmission(self, 
                                  link: CommunicationLink,
                                  data: bytes) -> Dict[str, Any]:
        """Perform adaptive transmission with real-time optimization"""
        
        transmission_result = {
            "success": False,
            "bytes_transmitted": 0,
            "transmission_time": 0.0,
            "effective_data_rate": 0.0,
            "retransmissions": 0,
            "final_ber": 0.0
        }
        
        start_time = datetime.utcnow()
        data_size = len(data)
        bytes_transmitted = 0
        retransmissions = 0
        
        try:
            while bytes_transmitted < data_size:
                # Monitor channel conditions
                current_conditions = await self._assess_channel_conditions(link)
                link.channel_conditions = current_conditions
                
                # Adapt transmission parameters if needed
                if current_conditions.link_quality_score < self.link_quality_threshold:
                    await self._adapt_transmission_parameters(link, current_conditions)
                
                # Calculate chunk size based on conditions
                chunk_size = min(
                    data_size - bytes_transmitted,
                    self._calculate_optimal_chunk_size(current_conditions)
                )
                
                # Transmit data chunk
                chunk_result = await self._transmit_chunk(
                    link, data[bytes_transmitted:bytes_transmitted + chunk_size]
                )
                
                if chunk_result["success"]:
                    bytes_transmitted += chunk_size
                    self.throughput_history.append(chunk_result["data_rate"])
                else:
                    retransmissions += 1
                    if retransmissions > 5:  # Max retransmissions
                        break
            
            # Calculate final statistics
            end_time = datetime.utcnow()
            transmission_time = (end_time - start_time).total_seconds()
            
            transmission_result.update({
                "success": bytes_transmitted == data_size,
                "bytes_transmitted": bytes_transmitted,
                "transmission_time": transmission_time,
                "effective_data_rate": bytes_transmitted * 8 / transmission_time if transmission_time > 0 else 0,
                "retransmissions": retransmissions,
                "final_ber": link.channel_conditions.bit_error_rate if link.channel_conditions else 0.0
            })
            
        except Exception as e:
            logger.error(f"Transmission failed: {e}")
        
        return transmission_result
    
    async def cognitive_interference_mitigation(self, 
                                              interfered_links: List[str]) -> Dict[str, bool]:
        """Use cognitive radio to mitigate interference"""
        mitigation_results = {}
        
        for link_id in interfered_links:
            if link_id not in self.active_links:
                mitigation_results[link_id] = False
                continue
            
            link = self.active_links[link_id]
            
            try:
                # Identify interference sources
                interference_sources = await self._identify_interference(link)
                
                # Apply mitigation strategies
                mitigation_success = False
                
                # Strategy 1: Frequency hopping
                if "frequency_hopping" in interference_sources:
                    success = await self._apply_frequency_hopping(link)
                    mitigation_success = mitigation_success or success
                
                # Strategy 2: Power control
                if "co_channel_interference" in interference_sources:
                    success = await self._apply_power_control(link)
                    mitigation_success = mitigation_success or success
                
                # Strategy 3: Beamforming
                if "spatial_interference" in interference_sources:
                    success = await self._apply_beamforming(link)
                    mitigation_success = mitigation_success or success
                
                # Strategy 4: Band switching
                if not mitigation_success:
                    success = await self._switch_frequency_band(link)
                    mitigation_success = success
                
                mitigation_results[link_id] = mitigation_success
                
                if mitigation_success:
                    logger.info(f"Successfully mitigated interference on {link_id}")
                else:
                    logger.warning(f"Failed to mitigate interference on {link_id}")
                    
            except Exception as e:
                logger.error(f"Interference mitigation failed for {link_id}: {e}")
                mitigation_results[link_id] = False
        
        return mitigation_results
    
    def get_radio_status(self) -> Dict[str, Any]:
        """Get comprehensive radio system status"""
        
        # Calculate average metrics
        avg_throughput = np.mean(self.throughput_history) if self.throughput_history else 0.0
        avg_error_rate = np.mean(self.error_rate_history) if self.error_rate_history else 0.0
        
        # Count active links per band
        links_per_band = {}
        for link in self.active_links.values():
            band_name = link.frequency_band.value["name"]
            links_per_band[band_name] = links_per_band.get(band_name, 0) + 1
        
        return {
            "radio_id": self.radio_id,
            "supported_bands": [band.value["name"] for band in self.supported_bands],
            "active_links": len(self.active_links),
            "links_per_band": links_per_band,
            "cognitive_engine": self.cognitive_engine_enabled,
            "average_throughput_mbps": avg_throughput / 1e6,
            "average_error_rate": avg_error_rate,
            "power_consumption_watts": self.power_consumption,
            "spectrum_occupancy": {
                band: np.mean(history) if history else 0.0
                for band, history in self.spectrum_sensing_data.items()
            }
        }
    
    # Private helper methods
    
    async def _measure_spectrum_occupancy(self, band: FrequencyBand, 
                                        duration: float) -> Dict[str, float]:
        """Measure spectrum occupancy for given band"""
        # Simulate spectrum measurement
        import random
        
        base_occupancy = random.uniform(0.1, 0.8)
        interference_level = random.uniform(0.0, 0.3)
        signal_quality = random.uniform(0.6, 1.0)
        
        return {
            "occupancy": base_occupancy,
            "interference": interference_level,
            "signal_quality": signal_quality,
            "available_bandwidth": (1.0 - base_occupancy) * 100  # MHz
        }
    
    async def _calculate_band_score(self, 
                                  band: FrequencyBand,
                                  transmission_req: TransmissionRequest,
                                  spectrum_info: Dict[str, float],
                                  channel_conditions: Optional[ChannelConditions]) -> float:
        """Calculate suitability score for frequency band"""
        
        score = 1.0
        
        # Spectrum availability
        occupancy = spectrum_info.get("occupancy", 0.5)
        score *= (1.0 - occupancy)
        
        # Interference level
        interference = spectrum_info.get("interference", 0.0)
        score *= (1.0 - interference)
        
        # Channel conditions
        if channel_conditions:
            score *= channel_conditions.link_quality_score
            
            # Weather impact for high-frequency bands
            if channel_conditions.weather_impact in ["rain", "storm"]:
                if band in [FrequencyBand.MILLIMETER_WAVE, FrequencyBand.TERAHERTZ]:
                    score *= 0.3  # Severe rain fade
                elif band == FrequencyBand.OPTICAL:
                    score *= 0.1  # Complete blockage
        
        # QoS requirements
        qos = transmission_req.qos_requirements
        
        # Bandwidth requirements
        required_bandwidth = qos.get("bandwidth_mbps", 10)
        available_bandwidth = spectrum_info.get("available_bandwidth", 50)
        
        if available_bandwidth >= required_bandwidth:
            score *= 1.2  # Bonus for sufficient bandwidth
        else:
            score *= 0.5  # Penalty for insufficient bandwidth
        
        # Latency requirements
        required_latency = qos.get("latency_ms", 100)
        if band == FrequencyBand.OPTICAL and required_latency < 10:
            score *= 1.5  # Optical is best for ultra-low latency
        
        return max(0.0, min(1.0, score))
    
    async def _select_modulation(self, band: FrequencyBand, 
                               qos_requirements: Dict[str, Any]) -> ModulationType:
        """Select optimal modulation scheme"""
        
        required_ber = qos_requirements.get("max_ber", 1e-6)
        required_throughput = qos_requirements.get("bandwidth_mbps", 10) * 1e6
        
        # High-frequency bands can support more complex modulation
        if band in [FrequencyBand.MILLIMETER_WAVE, FrequencyBand.TERAHERTZ, FrequencyBand.OPTICAL]:
            if required_ber < 1e-9:
                return ModulationType.QPSK  # Conservative for very low BER
            elif required_throughput > 100e6:
                return ModulationType.QAM64  # High throughput
            else:
                return ModulationType.QAM16  # Balanced
        else:
            # Lower frequency bands - more conservative
            if required_ber < 1e-9:
                return ModulationType.BPSK
            else:
                return ModulationType.QPSK
    
    async def _calculate_link_budget(self, band: FrequencyBand, 
                                   modulation: ModulationType,
                                   qos_requirements: Dict[str, Any]) -> Tuple[float, float]:
        """Calculate power level and data rate for link"""
        
        # Base parameters
        frequency = (band.value["freq_range"][0] + band.value["freq_range"][1]) / 2
        distance_km = qos_requirements.get("distance_km", 1000)
        
        # Free space path loss
        path_loss_db = 20 * np.log10(distance_km * 1000) + 20 * np.log10(frequency) - 147.55
        
        # Required SNR based on modulation
        snr_requirements = {
            ModulationType.BPSK: 10.0,
            ModulationType.QPSK: 13.0,
            ModulationType.QAM16: 18.0,
            ModulationType.QAM64: 24.0,
            ModulationType.OFDM: 15.0
        }
        
        required_snr = snr_requirements.get(modulation, 15.0)
        
        # Calculate required power
        power_level = required_snr + path_loss_db - self._get_antenna_gain(band)
        
        # Calculate achievable data rate
        bandwidth = self._get_band_bandwidth(band)
        spectral_efficiency = self._get_spectral_efficiency(modulation)
        data_rate = bandwidth * spectral_efficiency
        
        return power_level, data_rate
    
    def _get_antenna_gain(self, band: FrequencyBand) -> float:
        """Get antenna gain for frequency band"""
        gains = {
            FrequencyBand.MICROWAVE: 20.0,  # dBi
            FrequencyBand.MILLIMETER_WAVE: 30.0,
            FrequencyBand.TERAHERTZ: 40.0,
            FrequencyBand.OPTICAL: 50.0
        }
        return gains.get(band, 20.0)
    
    def _get_band_bandwidth(self, band: FrequencyBand) -> float:
        """Get available bandwidth for frequency band"""
        bandwidths = {
            FrequencyBand.MICROWAVE: 100e6,  # 100 MHz
            FrequencyBand.MILLIMETER_WAVE: 1e9,  # 1 GHz
            FrequencyBand.TERAHERTZ: 10e9,  # 10 GHz
            FrequencyBand.OPTICAL: 100e9  # 100 GHz
        }
        return bandwidths.get(band, 100e6)
    
    def _get_spectral_efficiency(self, modulation: ModulationType) -> float:
        """Get spectral efficiency for modulation scheme"""
        efficiencies = {
            ModulationType.BPSK: 1.0,  # bits/Hz
            ModulationType.QPSK: 2.0,
            ModulationType.QAM16: 4.0,
            ModulationType.QAM64: 6.0,
            ModulationType.OFDM: 3.0
        }
        return efficiencies.get(modulation, 2.0)
    
    async def _assess_channel_conditions(self, link: CommunicationLink) -> ChannelConditions:
        """Assess current channel conditions for link"""
        
        # Simulate channel assessment
        import random

        # Base conditions
        snr = random.uniform(10, 30)  # dB
        ber = random.uniform(1e-9, 1e-3)
        atmospheric_loss = random.uniform(0.1, 5.0)  # dB
        
        # Weather impact
        weather_conditions = ["clear", "cloudy", "rain", "storm"]
        weather = random.choice(weather_conditions)
        
        # Adjust based on frequency band
        if link.frequency_band in [FrequencyBand.MILLIMETER_WAVE, FrequencyBand.TERAHERTZ]:
            if weather in ["rain", "storm"]:
                atmospheric_loss *= 3  # High rain fade
                snr *= 0.5
        elif link.frequency_band == FrequencyBand.OPTICAL:
            if weather in ["cloudy", "rain", "storm"]:
                atmospheric_loss *= 10  # Severe weather blocking
                snr *= 0.1
        
        # Calculate overall link quality
        quality_factors = [
            min(1.0, snr / 20.0),  # SNR factor
            min(1.0, 1e-6 / ber),  # BER factor (lower is better)
            min(1.0, 10.0 / atmospheric_loss),  # Loss factor
        ]
        
        link_quality = np.mean(quality_factors)
        
        return ChannelConditions(
            signal_to_noise_ratio=snr,
            bit_error_rate=ber,
            atmospheric_loss=atmospheric_loss,
            multipath_fading=random.uniform(0, 3),
            doppler_shift=random.uniform(-1000, 1000),
            interference_level=random.uniform(0, 0.3),
            weather_impact=weather,
            link_quality_score=link_quality
        )
    
    async def _adapt_transmission_parameters(self, link: CommunicationLink,
                                           conditions: ChannelConditions):
        """Adapt transmission parameters based on channel conditions"""
        
        # Reduce data rate if BER is too high
        if conditions.bit_error_rate > self.max_acceptable_ber:
            link.data_rate *= 0.8
            logger.debug(f"Reduced data rate to {link.data_rate/1e6:.1f} Mbps due to high BER")
        
        # Increase power if SNR is too low
        if conditions.signal_to_noise_ratio < self.min_snr_threshold:
            link.power_level += 3.0  # Increase by 3 dB
            logger.debug(f"Increased power to {link.power_level:.1f} dBm due to low SNR")
        
        # Switch modulation if conditions are poor
        if conditions.link_quality_score < 0.5:
            if link.modulation == ModulationType.QAM64:
                link.modulation = ModulationType.QAM16
            elif link.modulation == ModulationType.QAM16:
                link.modulation = ModulationType.QPSK
            elif link.modulation == ModulationType.QPSK:
                link.modulation = ModulationType.BPSK
    
    def _calculate_optimal_chunk_size(self, conditions: ChannelConditions) -> int:
        """Calculate optimal data chunk size based on conditions"""
        
        base_chunk_size = 1024  # bytes
        
        # Reduce chunk size for poor conditions
        quality_factor = conditions.link_quality_score
        optimal_size = int(base_chunk_size * quality_factor)
        
        return max(64, optimal_size)  # Minimum 64 bytes
    
    async def _transmit_chunk(self, link: CommunicationLink, 
                            data_chunk: bytes) -> Dict[str, Any]:
        """Transmit data chunk and return results"""
        
        chunk_size = len(data_chunk)
        
        # Simulate transmission time
        transmission_time = chunk_size * 8 / link.data_rate  # seconds
        await asyncio.sleep(min(0.001, transmission_time))  # Simulate delay
        
        # Simulate transmission success based on channel conditions
        success_probability = (
            link.channel_conditions.link_quality_score 
            if link.channel_conditions else 0.8
        )
        
        import random
        success = random.random() < success_probability
        
        return {
            "success": success,
            "chunk_size": chunk_size,
            "transmission_time": transmission_time,
            "data_rate": chunk_size * 8 / transmission_time if transmission_time > 0 else 0
        }
    
    async def _identify_interference(self, link: CommunicationLink) -> List[str]:
        """Identify types of interference affecting the link"""
        
        interference_types = []
        
        if link.channel_conditions:
            # Analyze interference patterns
            if link.channel_conditions.interference_level > 0.2:
                interference_types.append("co_channel_interference")
            
            if link.channel_conditions.multipath_fading > 2.0:
                interference_types.append("multipath_interference")
            
            if abs(link.channel_conditions.doppler_shift) > 500:
                interference_types.append("frequency_hopping")
            
            # Spatial interference for directional links
            if link.frequency_band in [FrequencyBand.TERAHERTZ, FrequencyBand.OPTICAL]:
                interference_types.append("spatial_interference")
        
        return interference_types
    
    async def _apply_frequency_hopping(self, link: CommunicationLink) -> bool:
        """Apply frequency hopping to mitigate interference"""
        # Simulate frequency hopping
        await asyncio.sleep(0.1)
        logger.debug(f"Applied frequency hopping to {link.link_id}")
        return True
    
    async def _apply_power_control(self, link: CommunicationLink) -> bool:
        """Apply power control to mitigate interference"""
        # Increase power to overcome interference
        link.power_level += 2.0  # Increase by 2 dB
        logger.debug(f"Applied power control to {link.link_id}")
        return True
    
    async def _apply_beamforming(self, link: CommunicationLink) -> bool:
        """Apply beamforming to mitigate spatial interference"""
        # Simulate beamforming for directional antennas
        if link.frequency_band in [FrequencyBand.TERAHERTZ, FrequencyBand.OPTICAL]:
            await asyncio.sleep(0.05)
            logger.debug(f"Applied beamforming to {link.link_id}")
            return True
        return False
    
    async def _switch_frequency_band(self, link: CommunicationLink) -> bool:
        """Switch to different frequency band"""
        # Find alternative band
        for band in self.supported_bands:
            if band != link.frequency_band:
                # Simulate band switching
                old_band = link.frequency_band.value["name"]
                link.frequency_band = band
                logger.info(f"Switched {link.link_id} from {old_band} to {band.value['name']}")
                return True
        
        return False
