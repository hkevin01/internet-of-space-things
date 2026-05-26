"""
CubeSat-Enabled Hybrid Survival Network (CEHSN) Package
Provides orbital inference, RPA communication bridge, ethics engine,
survival map generation, resilience monitoring, ML training pipelines,
reinforcement learning resource optimization, and federated learning.
"""

from .ethics_engine import EthicalDecision, EthicsEngine
from .orbital_infer import AnomalyType, InferenceResult, OrbitalInferenceEngine
from .resilience_monitor import AlertLevel, ResilienceMonitor
from .rpa_comm_bridge import RPACommunicationBridge
from .survival_mapgen import SurvivalMap, SurvivalMapGenerator

# ML pipelines
from .lstm_training_pipeline import (
    FailureDataGenerator,
    FailureSample,
    LSTMTrainingPipeline,
    TrainingConfig,
    TrainingResult,
)
from .xgboost_pipeline import (
    XGBConfig,
    XGBTrainingResult,
    XGBoostRULPredictor,
)
from .rl_resource_optimizer import (
    MissionState,
    ResourceAllocation,
    RLResourceOptimizer,
    SpaceMissionEnv,
)
from .federated_aggregation_server import (
    AggregationResult,
    ClientUpdate,
    FederatedAggregationServer,
    GlobalModelState,
    SimulatedSatelliteClient,
)

__all__ = [
    # Legacy
    'OrbitalInferenceEngine', 'AnomalyType', 'InferenceResult',
    'RPACommunicationBridge',
    'EthicsEngine', 'EthicalDecision',
    'SurvivalMapGenerator', 'SurvivalMap',
    'ResilienceMonitor', 'AlertLevel',
    # LSTM pipeline
    'FailureDataGenerator', 'FailureSample', 'LSTMTrainingPipeline',
    'TrainingConfig', 'TrainingResult',
    # XGBoost pipeline
    'XGBConfig', 'XGBTrainingResult', 'XGBoostRULPredictor',
    # RL optimizer
    'MissionState', 'ResourceAllocation', 'RLResourceOptimizer', 'SpaceMissionEnv',
    # Federated learning
    'AggregationResult', 'ClientUpdate', 'FederatedAggregationServer',
    'GlobalModelState', 'SimulatedSatelliteClient',
]

__version__ = "1.0.0"
