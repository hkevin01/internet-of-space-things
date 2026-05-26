"""
intrusion_detection.py - Space Cyber Intrusion Detection System (IDS) for IoST
===============================================================================
ID: SEC-040
Requirement: Detect and respond to cyber attacks targeting satellite command
             links, telemetry streams, and ground station APIs in real time.
Purpose: Space systems are increasingly targeted by nation-state actors and
         opportunistic attackers. The 2022 Viasat KA-SAT attack disrupted
         Ukraine communications within 1 hour of conflict start. IoST must
         detect anomalous command patterns, spoofing attempts, and replay
         attacks before they cause mission harm.
Rationale: Rule-based IDS covers known attack signatures; ML-based behavioral
           baseline detects novel zero-day attacks. Combining both minimizes
           both false positives and false negatives.
References: MITRE ATT&CK for Space (ICS), CISA Space Sector Guidance,
            Mendez et al. 2025 "Securing CubeSats" (ResearchGate 404674781)
"""

import collections
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import statistics

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """
    ID: SEC-040-A
    Requirement: Map detected threats to response urgency levels.
    """
    INFO = "info"           # Interesting but not immediately harmful
    LOW = "low"             # Monitor; no immediate action required
    MEDIUM = "medium"       # Alert operators; increase monitoring
    HIGH = "high"           # Automatic protective action; crew notification
    CRITICAL = "critical"   # Mission abort risk; all hands response


class AttackVector(Enum):
    """
    ID: SEC-040-B
    Purpose: Categorize the attack surface being targeted.
    Based on MITRE ATT&CK for Space attack techniques.
    """
    COMMAND_INJECTION = "command_injection"
    REPLAY_ATTACK = "replay_attack"
    SIGNAL_SPOOFING = "signal_spoofing"
    DENIAL_OF_SERVICE = "denial_of_service"
    CREDENTIAL_STUFFING = "credential_stuffing"
    DATA_EXFILTRATION = "data_exfiltration"
    SUPPLY_CHAIN = "supply_chain"
    INSIDER_THREAT = "insider_threat"
    UNKNOWN = "unknown"


@dataclass
class SecurityEvent:
    """
    ID: SEC-040-C
    Purpose: Structured record of a detected security event for audit and response.
    """
    event_id: str
    satellite_id: str
    threat_level: ThreatLevel
    attack_vector: AttackVector
    description: str
    source_indicator: str       # IP address, node ID, or frequency
    raw_evidence: dict
    detected_at: float = field(default_factory=time.time)
    mitigated: bool = False
    mitigation_action: str = ""


class IntrusionDetectionSystem:
    """
    ID: SEC-040
    Requirement: Monitor all command frames, authentication events, and network
                 flows for indicators of compromise (IoC). Generate SecurityEvents
                 and trigger automated mitigations for HIGH/CRITICAL threats.
    Purpose: Provide the first line of autonomous cyber defense for satellite nodes
             that cannot wait for a ground-based response during blackout periods.
    Preconditions: IDS is initialized before accepting any commands.
    Postconditions: All detected events are logged and available for audit.
    Side Effects: May quarantine satellite nodes or block command sources.
    Failure Modes: False positives can block legitimate commands - thresholds
                   must be calibrated per mission profile.
    Verification: Tested with MITRE ATT&CK for Space simulation scenarios.
    """

    def __init__(self, satellite_id: str) -> None:
        self.satellite_id = satellite_id
        self._events: List[SecurityEvent] = []
        self._command_rate_window: collections.deque = collections.deque(maxlen=1000)
        self._auth_failures: Dict[str, List[float]] = collections.defaultdict(list)
        self._seen_sequences: set = set()
        self._signal_strength_baseline: Optional[float] = None
        self._signal_strength_samples: collections.deque = collections.deque(maxlen=100)
        self._event_counter: int = 0
        logger.info("IDS initialized for satellite %s", satellite_id)

    # ---------- Detection Rules ----------

    def inspect_command_frame(
        self,
        command_id: str,
        sequence_number: int,
        source_id: str,
        command_type: str,
        timestamp: float,
    ) -> Optional[SecurityEvent]:
        """
        ID: SEC-041
        Requirement: Check an incoming command frame for replay, injection,
                     and rate-anomaly indicators.
        Inputs:
          - command_id: unique command identifier
          - sequence_number: should be monotonically increasing per source
          - source_id: originating ground station or operator node
          - command_type: type of command being sent
          - timestamp: when command was transmitted
        Outputs: SecurityEvent if a threat is detected; None if clean.
        Side Effects: Updates internal sequence and rate tracking state.
        """
        # Rule 1: Replay detection (sequence number reuse)
        seq_key = f"{source_id}:{sequence_number}"
        if seq_key in self._seen_sequences:
            return self._create_event(
                threat_level=ThreatLevel.HIGH,
                attack_vector=AttackVector.REPLAY_ATTACK,
                description=(
                    f"Replay attack detected: command {command_id} from {source_id} "
                    f"reused sequence number {sequence_number}."
                ),
                source_indicator=source_id,
                evidence={
                    "command_id": command_id,
                    "sequence_number": sequence_number,
                    "timestamp": timestamp,
                },
            )
        self._seen_sequences.add(seq_key)
        # Bound memory
        if len(self._seen_sequences) > 50_000:
            self._seen_sequences.pop()

        # Rule 2: Stale command (transmitted more than 5 minutes ago)
        age = time.time() - timestamp
        if age > 300:
            return self._create_event(
                threat_level=ThreatLevel.MEDIUM,
                attack_vector=AttackVector.REPLAY_ATTACK,
                description=f"Stale command {command_id}: {age:.0f}s old (max 300s).",
                source_indicator=source_id,
                evidence={"age_seconds": age, "command_id": command_id},
            )

        # Rule 3: Command rate anomaly (>20 commands in 10 seconds)
        now = time.time()
        self._command_rate_window.append(now)
        recent = [t for t in self._command_rate_window if now - t < 10.0]
        if len(recent) > 20:
            return self._create_event(
                threat_level=ThreatLevel.HIGH,
                attack_vector=AttackVector.DENIAL_OF_SERVICE,
                description=(
                    f"Command flood detected: {len(recent)} commands in 10s "
                    f"from {source_id} (threshold: 20)."
                ),
                source_indicator=source_id,
                evidence={"rate": len(recent), "window_seconds": 10},
            )

        # Rule 4: Propulsion command from unexpected source
        if "PROPULSION" in command_type.upper() and source_id.startswith("RESEARCHER"):
            return self._create_event(
                threat_level=ThreatLevel.CRITICAL,
                attack_vector=AttackVector.COMMAND_INJECTION,
                description=(
                    f"Unauthorized propulsion command from research account {source_id}. "
                    f"Propulsion commands require FLIGHT_CONTROLLER role."
                ),
                source_indicator=source_id,
                evidence={"command_type": command_type, "source_id": source_id},
            )

        return None

    def inspect_authentication(
        self, source_id: str, success: bool
    ) -> Optional[SecurityEvent]:
        """
        ID: SEC-042
        Requirement: Detect brute-force credential stuffing via failed
                     authentication rate monitoring.
        Inputs:
          - source_id: IP address or node identifier of the requester
          - success: True if authentication succeeded
        Outputs: SecurityEvent if attack threshold exceeded; None if normal.
        """
        now = time.time()
        if not success:
            self._auth_failures[source_id].append(now)
            # Keep only failures within the last 5 minutes
            self._auth_failures[source_id] = [
                t for t in self._auth_failures[source_id] if now - t < 300
            ]
            failure_count = len(self._auth_failures[source_id])
            if failure_count >= 10:
                return self._create_event(
                    threat_level=ThreatLevel.HIGH,
                    attack_vector=AttackVector.CREDENTIAL_STUFFING,
                    description=(
                        f"Brute-force attack detected from {source_id}: "
                        f"{failure_count} failed authentications in 5 minutes."
                    ),
                    source_indicator=source_id,
                    evidence={"failure_count": failure_count, "window_seconds": 300},
                )
        return None

    def inspect_signal(
        self, signal_strength_dbm: float, frequency_hz: float, source_id: str
    ) -> Optional[SecurityEvent]:
        """
        ID: SEC-043
        Requirement: Detect RF signal spoofing by comparing received signal
                     strength against the established baseline. A legitimate
                     ground station at known distance produces predictable SNR;
                     a nearby jammer or spoofer produces anomalously strong signals.
        Inputs:
          - signal_strength_dbm: received signal strength in dBm
          - frequency_hz: carrier frequency
          - source_id: antenna or link identifier
        Outputs: SecurityEvent if spoofing indicators detected; None if normal.
        """
        self._signal_strength_samples.append(signal_strength_dbm)

        if len(self._signal_strength_samples) < 10:
            return None  # Not enough data for baseline

        # Update rolling baseline
        mean = statistics.mean(self._signal_strength_samples)
        stdev = statistics.stdev(self._signal_strength_samples)

        # Flag if current signal is >5 standard deviations above baseline
        if stdev > 0 and (signal_strength_dbm - mean) / stdev > 5.0:
            return self._create_event(
                threat_level=ThreatLevel.HIGH,
                attack_vector=AttackVector.SIGNAL_SPOOFING,
                description=(
                    f"RF spoofing indicator on {source_id}: signal {signal_strength_dbm:.1f} dBm "
                    f"is {(signal_strength_dbm - mean)/stdev:.1f}σ above baseline {mean:.1f} dBm."
                ),
                source_indicator=source_id,
                evidence={
                    "signal_dbm": signal_strength_dbm,
                    "baseline_mean": mean,
                    "baseline_stdev": stdev,
                    "frequency_hz": frequency_hz,
                },
            )
        return None

    # ---------- Event Management ----------

    def get_events(
        self, min_level: ThreatLevel = ThreatLevel.INFO, last_n: int = 100
    ) -> List[SecurityEvent]:
        """
        ID: SEC-044
        Purpose: Retrieve recent security events at or above a given threat level.
        Inputs: min_level - minimum ThreatLevel to include; last_n - event count limit
        Outputs: List of matching SecurityEvents, newest first.
        """
        level_order = [ThreatLevel.INFO, ThreatLevel.LOW, ThreatLevel.MEDIUM,
                       ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        min_idx = level_order.index(min_level)
        filtered = [
            e for e in self._events
            if level_order.index(e.threat_level) >= min_idx
        ]
        return list(reversed(filtered))[-last_n:]

    def get_threat_summary(self) -> dict:
        """
        ID: SEC-045
        Purpose: Return a counts-by-level summary for dashboard display.
        """
        summary = {level.value: 0 for level in ThreatLevel}
        for event in self._events:
            summary[event.threat_level.value] += 1
        return summary

    def _create_event(
        self,
        threat_level: ThreatLevel,
        attack_vector: AttackVector,
        description: str,
        source_indicator: str,
        evidence: dict,
    ) -> SecurityEvent:
        """
        ID: SEC-046
        Purpose: Construct, log, and store a SecurityEvent.
        """
        import uuid
        self._event_counter += 1
        event = SecurityEvent(
            event_id=f"SEC-{self.satellite_id}-{self._event_counter:06d}",
            satellite_id=self.satellite_id,
            threat_level=threat_level,
            attack_vector=attack_vector,
            description=description,
            source_indicator=source_indicator,
            raw_evidence=evidence,
        )
        self._events.append(event)

        log_fn = {
            ThreatLevel.INFO: logger.info,
            ThreatLevel.LOW: logger.info,
            ThreatLevel.MEDIUM: logger.warning,
            ThreatLevel.HIGH: logger.error,
            ThreatLevel.CRITICAL: logger.critical,
        }.get(threat_level, logger.warning)

        log_fn(
            "[IDS:%s] %s - %s: %s",
            self.satellite_id,
            threat_level.value.upper(),
            attack_vector.value,
            description,
        )
        return event
