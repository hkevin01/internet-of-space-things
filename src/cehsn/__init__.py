"""
CubeSat-Enabled Hybrid Survival Network (CEHSN) Package
Provides orbital inference, RPA communication bridge, ethics engine, 
survival map generation, and resilience monitoring.
"""

from .ethics_engine import DecisionContext, EthicalDecision, EthicsEngine
from .orbital_infer import AnomalyType, InferenceResult, OrbitalInferenceEngine
from .resilience_monitor import AlertLevel, ResilienceMonitor, SensorHealth
from .rpa_comm_bridge import MissionTask, RPACommBridge, TaskPriority
from .survival_mapgen import GeospatialData, RiskAssessment, SurvivalMapGenerator

__all__ = [
    'OrbitalInferenceEngine',
    'AnomalyType', 
    'InferenceResult',
    'RPACommBridge',
    'MissionTask',
    'TaskPriority',
    'EthicsEngine',
    'EthicalDecision',
    'DecisionContext',
    'SurvivalMapGenerator',
    'GeospatialData',
    'RiskAssessment',
    'ResilienceMonitor',
    'SensorHealth',
    'AlertLevel'
]

__version__ = "1.0.0"
