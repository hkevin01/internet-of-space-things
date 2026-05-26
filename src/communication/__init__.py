"""
Communication Module for Internet of Space Things
Handles all space communication protocols and encryption
"""

from .encryption.quantum_encryption import QuantumEncryption
from .encryption.space_grade_crypto import SpaceGradeCrypto
from .protocols.deep_space_protocol import DeepSpaceProtocol

__all__ = [
    "DeepSpaceProtocol",
    "QuantumEncryption",
    "SpaceGradeCrypto",
]
