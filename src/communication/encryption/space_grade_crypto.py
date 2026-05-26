"""
space_grade_crypto.py - Space-Grade Cryptographic Primitives for IoST
======================================================================
ID: SEC-001
Requirement: Provide authenticated encryption and command signing for all
             satellite command uplinks and telemetry downlinks.
Purpose: Protect mission-critical communications from interception,
         replay attacks, and unauthorized command injection in the
         hostile space radio-frequency environment.
Rationale: AES-256-GCM provides confidentiality + integrity in one pass,
           critical for bandwidth-constrained space links. ECDSA P-384
           gives strong command authentication with smaller key/signature
           sizes than RSA, saving precious uplink bytes.
References: CCSDS 352.0-B-2 (Security Architecture), NIST SP 800-38D
"""

import os
import time
import hashlib
import hmac
import logging
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
    SECP384R1,
)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """
    ID: SEC-001-A
    Requirement: Map mission context to an appropriate key length and algorithm set.
    """
    STANDARD = "standard"       # AES-128-GCM - low-power CubeSat nodes
    HIGH = "high"               # AES-256-GCM - crewed vehicles, ground uplink
    QUANTUM_RESISTANT = "qr"    # AES-256-GCM + CRYSTALS-Kyber hybrid (placeholder)


@dataclass
class EncryptedPacket:
    """
    ID: SEC-001-B
    Purpose: Wire format for an authenticated-encrypted data packet.
    Inputs:
      - ciphertext: AES-GCM encrypted payload bytes
      - nonce: 96-bit random nonce (must be unique per key)
      - tag: 128-bit GCM authentication tag (appended by AESGCM)
      - satellite_id: originating or destination node identifier
      - sequence_number: monotonically increasing counter for replay detection
      - timestamp: Unix epoch float for staleness check
    """
    ciphertext: bytes          # Encrypted payload (tag appended by AESGCM)
    nonce: bytes               # 12-byte random IV
    satellite_id: str          # Node that created this packet
    sequence_number: int       # Replay-detection counter
    timestamp: float           # Creation time (UTC epoch seconds)
    aad: bytes = b""           # Additional Authenticated Data (headers)


@dataclass
class CommandSignature:
    """
    ID: SEC-001-C
    Purpose: ECDSA P-384 digital signature over a ground command payload.
    Ensures only authenticated ground operators can inject commands.
    """
    signature: bytes           # DER-encoded ECDSA signature
    public_key_fingerprint: str
    command_hash: bytes        # SHA3-384 digest of the command bytes
    signed_at: float           # Signing timestamp (UTC epoch)


class SpaceGradeCrypto:
    """
    ID: SEC-001
    Requirement: Provide AES-256-GCM symmetric encryption and ECDSA P-384
                 asymmetric command authentication for space communication links.
    Purpose: Protect all telemetry downlinks and command uplinks from
             interception, tampering, and replay attacks.
    Preconditions: Python cryptography library >= 41.0 installed.
    Postconditions: Encrypted packets are indistinguishable from random bytes
                    to an observer without the symmetric key.
    Assumptions: Key distribution is handled out-of-band (e.g., pre-loaded
                 at launch or distributed via ECDH key exchange before use).
    Side Effects: Generates cryptographically random nonces using os.urandom().
    Failure Modes: InvalidTag raised on tampered ciphertext; sequence counter
                   prevents replay within the replay_window.
    Verification: Unit tested with known-answer tests for AES-GCM vectors.
    """

    # Inputs: satellite_id - unique node identifier string
    #         security_level - determines AES key length
    #         replay_window - max accepted sequence gap (anti-replay)
    def __init__(
        self,
        satellite_id: str,
        security_level: SecurityLevel = SecurityLevel.HIGH,
        replay_window: int = 1000,
    ) -> None:
        self.satellite_id = satellite_id
        self.security_level = security_level
        self.replay_window = replay_window
        self._sequence_counter: int = 0
        self._seen_sequences: set = set()
        self._symmetric_key: Optional[bytes] = None
        self._private_key: Optional[EllipticCurvePrivateKey] = None
        self._public_key: Optional[EllipticCurvePublicKey] = None
        logger.info(
            "SpaceGradeCrypto initialized for %s (level=%s)",
            satellite_id,
            security_level.value,
        )

    # ---------- Key Management ----------

    def generate_symmetric_key(self) -> bytes:
        """
        ID: SEC-002
        Requirement: Generate a cryptographically random AES key of the
                     appropriate length for the configured security level.
        Outputs: 32-byte (256-bit) random key bytes.
        Side Effects: Stores key internally; logs key generation event.
        Failure Modes: os.urandom() raises if OS entropy is exhausted (rare).
        """
        key_size = 32  # AES-256 for HIGH and QR levels
        if self.security_level == SecurityLevel.STANDARD:
            key_size = 16  # AES-128 for power-constrained nodes
        self._symmetric_key = os.urandom(key_size)
        logger.info("Symmetric key generated (%d bytes) for %s", key_size, self.satellite_id)
        return self._symmetric_key

    def load_symmetric_key(self, key: bytes) -> None:
        """
        ID: SEC-003
        Requirement: Load a pre-shared symmetric key (e.g., mission key
                     injected at launch) for subsequent encrypt/decrypt operations.
        Inputs: key - 16 or 32 bytes
        Error Handling: Raises ValueError if key length is invalid.
        """
        if len(key) not in (16, 32):
            raise ValueError(f"Invalid AES key length {len(key)}; must be 16 or 32 bytes.")
        self._symmetric_key = key

    def generate_signing_keypair(self) -> Tuple[bytes, bytes]:
        """
        ID: SEC-004
        Requirement: Generate an ECDSA P-384 key pair for command signing/verification.
        Outputs: (private_key_pem, public_key_pem) as PEM-encoded bytes.
        Side Effects: Stores keys internally.
        """
        self._private_key = ec.generate_private_key(SECP384R1(), default_backend())
        self._public_key = self._private_key.public_key()
        priv_pem = self._private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        pub_pem = self._public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        logger.info("ECDSA P-384 key pair generated for %s", self.satellite_id)
        return priv_pem, pub_pem

    def get_public_key_fingerprint(self) -> str:
        """
        ID: SEC-005
        Purpose: Return SHA-256 fingerprint of the public key for key identification.
        Outputs: Hex string fingerprint.
        Preconditions: generate_signing_keypair() or load_private_key() called first.
        """
        if self._public_key is None:
            raise RuntimeError("No key pair loaded. Call generate_signing_keypair() first.")
        pub_bytes = self._public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return hashlib.sha256(pub_bytes).hexdigest()[:16]

    # ---------- Symmetric Encryption ----------

    def encrypt(self, plaintext: bytes, aad: bytes = b"") -> EncryptedPacket:
        """
        ID: SEC-006
        Requirement: Encrypt plaintext using AES-256-GCM with a random nonce.
                     Authenticate additional data (AAD) without encrypting it.
        Inputs:
          - plaintext: raw bytes to encrypt (max 64 GiB per nonce)
          - aad: unencrypted bytes included in the authentication tag
        Outputs: EncryptedPacket containing ciphertext, nonce, metadata.
        Preconditions: load_symmetric_key() or generate_symmetric_key() called.
        Postconditions: ciphertext is indistinguishable from random; tag verifies integrity.
        Failure Modes: RuntimeError if no key loaded.
        """
        if self._symmetric_key is None:
            raise RuntimeError("No symmetric key loaded. Call load_symmetric_key() first.")

        nonce = os.urandom(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(self._symmetric_key)

        # Build full AAD: provided aad + sequence number + satellite_id
        self._sequence_counter += 1
        seq_bytes = struct.pack(">Q", self._sequence_counter)
        full_aad = aad + seq_bytes + self.satellite_id.encode()

        ciphertext = aesgcm.encrypt(nonce, plaintext, full_aad)  # tag appended

        return EncryptedPacket(
            ciphertext=ciphertext,
            nonce=nonce,
            satellite_id=self.satellite_id,
            sequence_number=self._sequence_counter,
            timestamp=time.time(),
            aad=aad,
        )

    def decrypt(self, packet: EncryptedPacket) -> bytes:
        """
        ID: SEC-007
        Requirement: Decrypt and authenticate an EncryptedPacket. Reject
                     replayed packets via sequence number tracking.
        Inputs: packet - EncryptedPacket from the wire
        Outputs: plaintext bytes
        Preconditions: Symmetric key loaded and matches encryption key.
        Postconditions: Returned bytes are identical to original plaintext.
        Failure Modes:
          - InvalidTag: ciphertext was tampered with
          - ValueError: packet is a replay or too stale
        """
        if self._symmetric_key is None:
            raise RuntimeError("No symmetric key loaded.")

        # Replay detection
        if packet.sequence_number in self._seen_sequences:
            raise ValueError(
                f"Replay detected: sequence {packet.sequence_number} already processed."
            )
        if self._seen_sequences and packet.sequence_number < (
            max(self._seen_sequences) - self.replay_window
        ):
            raise ValueError(
                f"Sequence {packet.sequence_number} outside replay window."
            )

        # Staleness check - reject packets older than 5 minutes
        age = time.time() - packet.timestamp
        if age > 300:
            raise ValueError(f"Packet too stale: {age:.0f}s old (max 300s).")

        seq_bytes = struct.pack(">Q", packet.sequence_number)
        full_aad = packet.aad + seq_bytes + packet.satellite_id.encode()

        aesgcm = AESGCM(self._symmetric_key)
        try:
            plaintext = aesgcm.decrypt(packet.nonce, packet.ciphertext, full_aad)
        except InvalidTag as exc:
            logger.error(
                "Decryption authentication failure for packet seq=%d from %s",
                packet.sequence_number,
                packet.satellite_id,
            )
            raise

        self._seen_sequences.add(packet.sequence_number)
        # Bound memory usage of the seen-sequence set
        if len(self._seen_sequences) > self.replay_window * 2:
            min_seq = min(self._seen_sequences)
            self._seen_sequences.discard(min_seq)

        return plaintext

    # ---------- Command Signing ----------

    def sign_command(self, command_bytes: bytes) -> CommandSignature:
        """
        ID: SEC-008
        Requirement: Produce an ECDSA P-384 signature over a ground command
                     payload to prove ground-operator authority.
        Inputs: command_bytes - serialized command to be sent to satellite
        Outputs: CommandSignature with DER-encoded signature and metadata.
        Preconditions: Private key loaded via generate_signing_keypair().
        Failure Modes: RuntimeError if no private key loaded.
        """
        if self._private_key is None:
            raise RuntimeError("No private key loaded. Call generate_signing_keypair() first.")

        digest = hashlib.sha3_384(command_bytes).digest()
        signature = self._private_key.sign(command_bytes, ec.ECDSA(hashes.SHA384()))

        return CommandSignature(
            signature=signature,
            public_key_fingerprint=self.get_public_key_fingerprint(),
            command_hash=digest,
            signed_at=time.time(),
        )

    def verify_command(
        self, command_bytes: bytes, sig: CommandSignature, public_key_pem: bytes
    ) -> bool:
        """
        ID: SEC-009
        Requirement: Verify an ECDSA P-384 command signature on the satellite side.
        Inputs:
          - command_bytes: raw command payload received
          - sig: CommandSignature from the command frame
          - public_key_pem: trusted ground operator public key (pre-loaded)
        Outputs: True if signature is valid, False otherwise.
        Failure Modes: Returns False on any cryptographic failure without raising.
        Side Effects: Logs all verification failures with satellite_id.
        """
        try:
            pub_key: EllipticCurvePublicKey = serialization.load_pem_public_key(
                public_key_pem, backend=default_backend()
            )
            pub_key.verify(sig.signature, command_bytes, ec.ECDSA(hashes.SHA384()))

            # Additional hash integrity check
            expected_hash = hashlib.sha3_384(command_bytes).digest()
            if not hmac.compare_digest(expected_hash, sig.command_hash):
                logger.warning("Command hash mismatch on %s", self.satellite_id)
                return False

            return True
        except InvalidSignature:
            logger.error(
                "Invalid command signature on %s (key fingerprint: %s)",
                self.satellite_id,
                sig.public_key_fingerprint,
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error("Signature verification error on %s: %s", self.satellite_id, exc)
            return False

    # ---------- Key Derivation ----------

    @staticmethod
    def derive_session_key(
        master_key: bytes, satellite_id: str, session_nonce: bytes
    ) -> bytes:
        """
        ID: SEC-010
        Requirement: Derive a per-session AES-256 key from a long-term master key
                     using HKDF-SHA-384 to limit key exposure.
        Inputs:
          - master_key: 32-byte long-term shared secret
          - satellite_id: node identifier as context string
          - session_nonce: 16-byte random nonce for this session
        Outputs: 32-byte derived session key.
        Rationale: Using a fresh session key per communication window means
                   compromise of one session does not expose historical data
                   (forward secrecy approximation without full DH exchange).
        """
        hkdf = HKDF(
            algorithm=hashes.SHA384(),
            length=32,
            salt=session_nonce,
            info=f"iosct-session-{satellite_id}".encode(),
            backend=default_backend(),
        )
        return hkdf.derive(master_key)
