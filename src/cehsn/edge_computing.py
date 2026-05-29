"""
Edge Computing Module for IoST
Based on research: arXiv:2306.00275 - Orbital Edge Computing

Features:
- On-board ML inference using TensorFlow Lite
- Intelligent data reduction
- Local analytics and processing
- Bandwidth optimization
- Federated learning support
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import struct

logger = logging.getLogger(__name__)


@dataclass
class MLModel:
    """ML model metadata for edge deployment"""
    model_id: str
    model_type: str  # "anomaly_detection", "compression", "classification"
    size_bytes: int
    inference_time_ms: float
    accuracy: float
    deployment_date: datetime
    framework: str = "tflite"  # TensorFlow Lite


@dataclass
class DataReductionStrategy:
    """Strategy for intelligent data reduction"""
    strategy_id: str
    compression_ratio: float  # Target compression
    loss_acceptable: float  # Acceptable data loss (0-1)
    methods: List[str]  # e.g., ["decimation", "feature_extraction", "lossless"]
    priority_metrics: List[str]  # Metrics to prioritize


class EdgeInferenceEngine:
    """
    On-board ML inference engine for satellite
    
    Uses TensorFlow Lite for minimal resource footprint
    """
    
    def __init__(self, satellite_id: str, max_model_size_mb: int = 50):
        self.satellite_id = satellite_id
        self.max_model_size_bytes = max_model_size_mb * 1024 * 1024
        
        self.loaded_models: Dict[str, MLModel] = {}
        self.inference_cache: Dict[str, Tuple[Any, datetime]] = {}
        self.inference_stats: Dict[str, Dict[str, float]] = {}
        
        self.available_memory_mb = 512  # Typical satellite available
        self.available_cpu_percent = 80  # Reserve 20% for critical systems
        
        logger.info(f"Edge Inference Engine initialized for {satellite_id}")
    
    def deploy_model(self, model: MLModel) -> bool:
        """
        Deploy ML model on satellite
        
        Returns: Success status
        """
        
        # Check constraints
        if model.size_bytes > self.max_model_size_bytes:
            logger.error(f"Model {model.model_id} exceeds size limit")
            return False
        
        if model.size_bytes > self.available_memory_mb * 1024 * 1024:
            logger.error(f"Insufficient memory for model {model.model_id}")
            return False
        
        # Deploy (simulate)
        self.loaded_models[model.model_id] = model
        self.available_memory_mb -= (model.size_bytes / (1024 * 1024))
        
        logger.info(f"Deployed model {model.model_id} on {self.satellite_id}")
        return True
    
    def infer_anomaly(
        self,
        model_id: str,
        sensor_data: Dict[str, float]
    ) -> Tuple[float, float]:
        """
        Run anomaly detection inference on satellite
        
        Returns: (anomaly_score 0-1, confidence 0-1)
        """
        
        if model_id not in self.loaded_models:
            return 0.0, 0.0
        
        model = self.loaded_models[model_id]
        
        # Simulate TensorFlow Lite inference
        # Real implementation would use:
        # interpreter = tflite.Interpreter(model_path=model.path)
        # interpreter.allocate_tensors()
        # output = interpreter.invoke()
        
        # Simple heuristic for demo
        values = list(sensor_data.values())
        mean = sum(values) / len(values) if values else 0
        variance = sum((v - mean) ** 2 for v in values) / len(values) if values else 0
        
        anomaly_score = min(1.0, variance / 100.0)
        confidence = 0.85
        
        # Update stats
        if model_id not in self.inference_stats:
            self.inference_stats[model_id] = {'count': 0, 'avg_time': 0}
        
        stats = self.inference_stats[model_id]
        stats['count'] += 1
        stats['avg_time'] = (stats['avg_time'] * (stats['count'] - 1) + 
                            model.inference_time_ms) / stats['count']
        
        return anomaly_score, confidence
    
    def infer_classification(
        self,
        model_id: str,
        features: List[float]
    ) -> Tuple[str, float]:
        """
        Run classification inference (e.g., operating mode)
        
        Returns: (predicted_class, confidence)
        """
        
        if model_id not in self.loaded_models:
            return "unknown", 0.0
        
        # Simulate classification
        if features and features[0] > 50:
            return "high_activity", 0.9
        else:
            return "low_activity", 0.85


class DataCompressionEngine:
    """
    Intelligent data compression for bandwidth optimization
    
    Reduces downlink bandwidth while preserving critical data
    """
    
    def __init__(self):
        self.compression_algorithms = {
            'lossless': self._lossless_compress,
            'decimation': self._decimation_compress,
            'feature_extraction': self._feature_extract_compress,
            'quantization': self._quantization_compress
        }
        
        self.strategy_history: List[Dict[str, Any]] = []
        
        logger.info("Data Compression Engine initialized")
    
    def compress_telemetry(
        self,
        raw_data: Dict[str, List[float]],
        strategy: DataReductionStrategy
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Compress telemetry data according to strategy
        
        Returns: (compressed_bytes, compression_metadata)
        """
        
        compressed_data = {}
        metadata = {
            'original_size': self._estimate_size(raw_data),
            'compressed_size': 0,
            'compression_ratio': 0.0,
            'methods_used': [],
            'timestamp': datetime.now(),
            'priority_preserved': {}
        }
        
        for metric_name, values in raw_data.items():
            is_priority = metric_name in strategy.priority_metrics
            target_ratio = 0.5 if is_priority else strategy.compression_ratio
            
            # Select best compression method
            for method in strategy.methods:
                if method in self.compression_algorithms:
                    compressed = self.compression_algorithms[method](
                        values, target_ratio
                    )
                    if len(compressed) < len(values) * target_ratio:
                        compressed_data[metric_name] = compressed
                        metadata['methods_used'].append(method)
                        metadata['priority_preserved'][metric_name] = is_priority
                        break
        
        # Serialize compressed data
        serialized = self._serialize_compressed(compressed_data)
        metadata['compressed_size'] = len(serialized)
        metadata['compression_ratio'] = (
            metadata['compressed_size'] / metadata['original_size']
            if metadata['original_size'] > 0 else 0
        )
        
        logger.debug(f"Compression ratio: {metadata['compression_ratio']:.2%}")
        
        return serialized, metadata
    
    def _lossless_compress(
        self,
        data: List[float],
        target_ratio: float
    ) -> List[float]:
        """Lossless compression using run-length encoding"""
        if not data:
            return []
        
        compressed = []
        i = 0
        while i < len(data):
            count = 1
            while i + count < len(data) and data[i + count] == data[i]:
                count += 1
            
            compressed.extend([count, data[i]])
            i += count
        
        return compressed
    
    def _decimation_compress(
        self,
        data: List[float],
        target_ratio: float
    ) -> List[float]:
        """Decimation (sampling) compression"""
        if not data:
            return []
        
        step = max(1, int(1.0 / target_ratio))
        return data[::step]
    
    def _feature_extract_compress(
        self,
        data: List[float],
        target_ratio: float
    ) -> List[float]:
        """Feature extraction (statistical reduction)"""
        if not data:
            return []
        
        chunk_size = max(1, int(len(data) * target_ratio))
        features = []
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            features.extend([
                sum(chunk) / len(chunk),  # Mean
                max(chunk) - min(chunk),   # Range
                sum((x - sum(chunk)/len(chunk))**2 for x in chunk) / len(chunk)  # Variance
            ])
        
        return features
    
    def _quantization_compress(
        self,
        data: List[float],
        target_ratio: float
    ) -> List[int]:
        """Quantization to reduce precision"""
        if not data:
            return []
        
        min_val = min(data)
        max_val = max(data)
        range_val = max_val - min_val if max_val > min_val else 1.0
        
        # Quantize to 8-bit integers
        quantized = []
        for val in data:
            normalized = (val - min_val) / range_val
            quantized_val = int(normalized * 255)
            quantized.append(quantized_val)
        
        return quantized
    
    def _estimate_size(self, data: Dict[str, List[float]]) -> int:
        """Estimate size of data in bytes (assuming 8 bytes per float)"""
        total_values = sum(len(v) for v in data.values())
        return total_values * 8
    
    def _serialize_compressed(self, data: Dict[str, Any]) -> bytes:
        """Serialize compressed data to bytes"""
        # Simple serialization (real implementation would be more efficient)
        serialized = b''
        for key, values in data.items():
            serialized += key.encode() + b'\x00'
            if isinstance(values[0], float):
                serialized += b'F'
                for v in values:
                    serialized += struct.pack('f', v)
            else:
                serialized += b'I'
                for v in values:
                    serialized += struct.pack('B', v)
        return serialized


class FederatedLearningManager:
    """
    Manages federated learning across satellite constellation
    
    Enables collaborative ML without centralizing sensitive data
    """
    
    def __init__(self, satellite_id: str):
        self.satellite_id = satellite_id
        self.local_model_version = 1
        self.global_model_version = 0
        
        self.local_gradients: List[Dict[str, float]] = []
        self.aggregated_updates: List[Dict[str, Any]] = []
        
        logger.info(f"Federated Learning Manager initialized for {satellite_id}")
    
    def compute_local_gradients(
        self,
        training_data: List[Dict[str, float]],
        model_type: str
    ) -> Dict[str, float]:
        """
        Compute local gradients on satellite
        
        Returns: Gradient updates (no raw data shared)
        """
        
        # Simulate gradient computation
        gradients = {}
        
        if training_data:
            # Simple gradient estimation
            for i, data_point in enumerate(training_data):
                for key, value in data_point.items():
                    if key not in gradients:
                        gradients[key] = 0.0
                    gradients[key] += value / len(training_data)
        
        logger.info(f"Computed gradients on {self.satellite_id}")
        return gradients
    
    def update_global_model(
        self,
        aggregated_gradients: Dict[str, float],
        learning_rate: float = 0.01
    ) -> bool:
        """
        Apply aggregated gradient updates to local model
        """
        
        # Update local model
        self.aggregated_updates.append({
            'version': self.global_model_version,
            'timestamp': datetime.now(),
            'gradients': aggregated_gradients,
            'learning_rate': learning_rate
        })
        
        self.local_model_version += 1
        logger.info(f"Updated model on {self.satellite_id} to version {self.local_model_version}")
        
        return True


logger.info("Edge Computing module loaded with TensorFlow Lite and data compression")
