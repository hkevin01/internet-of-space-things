"""
audit_logger.py - Tamper-Evident Audit Log for IoST
====================================================
ID: SEC-050
Requirement: Maintain an immutable, tamper-evident audit trail of all
             security-relevant events: command executions, authentications,
             configuration changes, and access control decisions.
Purpose: Post-incident forensic analysis requires a trustworthy record of
         what happened and when. Space missions often have regulatory or
         contractual requirements for audit logging (e.g., NASA NPR 2810.1).
Rationale: Hash-chaining (similar to blockchain without distributed consensus)
           makes it computationally infeasible to alter historical log entries
           without detection, because each entry includes the SHA-256 hash of
           the previous entry.
References: NIST SP 800-92 (Log Management), NASA NPR 2810.1 Security
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """
    ID: SEC-050-A
    Requirement: Categorize audit events for filtering and reporting.
    """
    AUTHENTICATION_SUCCESS = "auth_success"
    AUTHENTICATION_FAILURE = "auth_failure"
    AUTHORIZATION_GRANTED = "authz_granted"
    AUTHORIZATION_DENIED = "authz_denied"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_REJECTED = "command_rejected"
    CONFIGURATION_CHANGED = "config_changed"
    SECURITY_EVENT_DETECTED = "security_event"
    KEY_GENERATED = "key_generated"
    KEY_ROTATED = "key_rotated"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    DATA_EXPORTED = "data_exported"
    USER_CREATED = "user_created"
    USER_MODIFIED = "user_modified"


@dataclass
class AuditEvent:
    """
    ID: SEC-050-B
    Purpose: Immutable record of a single auditable action.
    Fields:
      - sequence: monotonically increasing sequence number
      - event_type: category from AuditEventType
      - actor: user_id or system identifier that took the action
      - target: resource acted upon (satellite_id, command_id, etc.)
      - action: short description of the action taken
      - outcome: "success", "failure", or "blocked"
      - metadata: arbitrary key-value pairs for context
      - timestamp: UTC epoch seconds
      - previous_hash: SHA-256 of the previous AuditEvent's content hash
      - content_hash: SHA-256 of this event's content (for chain integrity)
    """
    sequence: int
    event_type: AuditEventType
    actor: str
    target: str
    action: str
    outcome: str
    metadata: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    previous_hash: str = ""
    content_hash: str = ""

    def compute_hash(self) -> str:
        """
        ID: SEC-050-C
        Purpose: Compute SHA-256 over the event fields (excluding content_hash itself).
        """
        payload = {
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "actor": self.actor,
            "target": self.target,
            "action": self.action,
            "outcome": self.outcome,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(canonical.encode()).hexdigest()


class AuditLogger:
    """
    ID: SEC-050
    Requirement: Append audit events to a hash-chained log. Provide
                 methods to verify chain integrity and export events.
    Purpose: Support forensic investigation and regulatory compliance
             for space mission operations.
    Preconditions: AuditLogger is initialized with a satellite/system ID.
    Postconditions: Every logged event is part of an unbroken hash chain.
    Side Effects: Events are kept in memory; persisted to structured log file.
    Failure Modes: Memory limits may require periodic archival to cold storage.
    Verification: Chain integrity verified by verify_chain() after each mission.
    """

    def __init__(self, system_id: str, log_file: Optional[str] = None) -> None:
        self.system_id = system_id
        self._events: List[AuditEvent] = []
        self._sequence: int = 0
        self._last_hash: str = hashlib.sha256(f"GENESIS:{system_id}".encode()).hexdigest()
        self._log_file = log_file
        logger.info("AuditLogger initialized for system %s", system_id)

    def log(
        self,
        event_type: AuditEventType,
        actor: str,
        target: str,
        action: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """
        ID: SEC-051
        Requirement: Append a new event to the hash-chained audit log.
        Inputs:
          - event_type: category of the event
          - actor: who performed the action
          - target: what was acted upon
          - action: description of the action
          - outcome: "success", "failure", or "blocked"
          - metadata: optional contextual key-value pairs
        Outputs: The finalized AuditEvent with computed content_hash.
        Side Effects: Writes to log file if configured; logs via standard logging.
        """
        self._sequence += 1
        event = AuditEvent(
            sequence=self._sequence,
            event_type=event_type,
            actor=actor,
            target=target,
            action=action,
            outcome=outcome,
            metadata=metadata or {},
            previous_hash=self._last_hash,
        )
        event.content_hash = event.compute_hash()
        self._last_hash = event.content_hash
        self._events.append(event)

        # Write to log file
        if self._log_file:
            try:
                with open(self._log_file, "a") as f:
                    f.write(json.dumps({
                        "seq": event.sequence,
                        "type": event.event_type.value,
                        "actor": event.actor,
                        "target": event.target,
                        "action": event.action,
                        "outcome": event.outcome,
                        "ts": event.timestamp,
                        "hash": event.content_hash,
                    }) + "\n")
            except OSError as exc:
                logger.error("Failed to write audit log entry: %s", exc)

        log_level = logging.WARNING if outcome == "failure" else logging.INFO
        logger.log(
            log_level,
            "[AUDIT] seq=%d actor=%s target=%s action=%s outcome=%s",
            event.sequence, event.actor, event.target, event.action, event.outcome,
        )
        return event

    def verify_chain(self) -> bool:
        """
        ID: SEC-052
        Requirement: Verify the integrity of the entire audit log hash chain.
                     Detect any tampering with historical records.
        Outputs: True if the chain is intact; False if tampering detected.
        Side Effects: Logs the sequence number of the first broken link.
        """
        if not self._events:
            return True

        genesis_hash = hashlib.sha256(f"GENESIS:{self.system_id}".encode()).hexdigest()
        expected_previous = genesis_hash

        for event in self._events:
            if event.previous_hash != expected_previous:
                logger.critical(
                    "AUDIT CHAIN INTEGRITY VIOLATION at sequence %d! "
                    "Expected previous hash %s but got %s.",
                    event.sequence,
                    expected_previous[:16],
                    event.previous_hash[:16],
                )
                return False
            recomputed = event.compute_hash()
            if recomputed != event.content_hash:
                logger.critical(
                    "AUDIT ENTRY TAMPERED at sequence %d! "
                    "Stored hash %s, recomputed %s.",
                    event.sequence,
                    event.content_hash[:16],
                    recomputed[:16],
                )
                return False
            expected_previous = event.content_hash

        logger.info(
            "Audit chain integrity verified: %d events, all valid.", len(self._events)
        )
        return True

    def get_events(
        self,
        event_type: Optional[AuditEventType] = None,
        actor: Optional[str] = None,
        last_n: int = 100,
    ) -> List[AuditEvent]:
        """
        ID: SEC-053
        Purpose: Retrieve audit events with optional filtering.
        Inputs:
          - event_type: filter to a specific event type (None = all)
          - actor: filter to a specific actor (None = all)
          - last_n: maximum events to return (newest first)
        """
        results = list(reversed(self._events))
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if actor:
            results = [e for e in results if e.actor == actor]
        return results[:last_n]

    def export_json(self) -> str:
        """
        ID: SEC-054
        Purpose: Export the full audit log as a JSON string for archival.
        Outputs: JSON array of all audit events.
        """
        return json.dumps(
            [
                {
                    "sequence": e.sequence,
                    "event_type": e.event_type.value,
                    "actor": e.actor,
                    "target": e.target,
                    "action": e.action,
                    "outcome": e.outcome,
                    "metadata": e.metadata,
                    "timestamp": e.timestamp,
                    "content_hash": e.content_hash,
                    "previous_hash": e.previous_hash,
                }
                for e in self._events
            ],
            indent=2,
        )
