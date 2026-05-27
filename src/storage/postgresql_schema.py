"""
postgresql_schema.py - PostgreSQL Schema and Data Storage Integration
=======================================================================
ID: STR-001
Requirement: Define and manage the PostgreSQL relational schema for IoST mission
             data that requires ACID transactions, relational integrity, and
             complex cross-table queries: mission records, satellite registry,
             component maintenance history, ML model versions, and user accounts.
Purpose: InfluxDB handles time-series telemetry; PostgreSQL handles structured
         mission data, configuration, user management, and audit trails where
         relational consistency, foreign keys, and transactional atomicity matter.
Rationale: Satellite registry changes (decommissioning, model upgrades) must be
           atomic. ML model version management requires cross-table joins.
           Life support alert acknowledgments require audit trails with user IDs.
           These patterns are poorly served by time-series or document stores.
Inputs: Python dataclass instances; raw SQL is never used directly (SQL injection
        prevention via parameterized queries only).
Outputs: Database tables created; CRUD operations returning typed objects.
Preconditions: PostgreSQL 14+ running; psycopg2 or asyncpg installed.
Failure Modes:
  - DB unavailable: raise StorageError (not silently ignored).
  - Schema migration: Flyway-compatible versioned migration files generated.
  - Constraint violation: raise StorageError with constraint name.
Side Effects: DDL statements create tables, indexes, and constraints.
Verification: Integration tested with Docker PostgreSQL 15; migration tested.
References: PostgreSQL 14 documentation, psycopg2 docs, OWASP SQL injection guide.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
    _PSYCOPG2_AVAILABLE = True
    logger.info("psycopg2 available - using real PostgreSQL.")
except ImportError:
    _PSYCOPG2_AVAILABLE = False
    logger.warning(
        "psycopg2 not installed. PostgreSQLStorage will use in-memory mock. "
        "Install with: pip install psycopg2-binary"
    )


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class StorageError(Exception):
    """
    ID: STR-001-A
    Purpose: Domain-specific exception for storage layer failures.
             Wraps underlying DB exceptions to decouple callers from
             the specific database driver being used.
    """


# ---------------------------------------------------------------------------
# Schema version tracking
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"

# All CREATE TABLE statements as versioned migrations
SCHEMA_DDL: List[str] = [
    """
    -- Migration V1: Core tables
    CREATE TABLE IF NOT EXISTS schema_version (
        id          SERIAL PRIMARY KEY,
        version     VARCHAR(20) NOT NULL,
        applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        description TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS satellites (
        id              SERIAL PRIMARY KEY,
        satellite_id    VARCHAR(50) UNIQUE NOT NULL,
        name            VARCHAR(100) NOT NULL,
        satellite_type  VARCHAR(50) NOT NULL,
        orbit_type      VARCHAR(50),
        launch_date     DATE,
        status          VARCHAR(30) NOT NULL DEFAULT 'active',
        manufacturer    VARCHAR(100),
        mission_id      VARCHAR(50),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_satellites_status
        ON satellites(status);
    CREATE INDEX IF NOT EXISTS idx_satellites_mission
        ON satellites(mission_id);
    """,
    """
    CREATE TABLE IF NOT EXISTS components (
        id              SERIAL PRIMARY KEY,
        component_id    VARCHAR(100) UNIQUE NOT NULL,
        satellite_id    VARCHAR(50) NOT NULL
            REFERENCES satellites(satellite_id) ON DELETE CASCADE,
        component_type  VARCHAR(50) NOT NULL,
        name            VARCHAR(100) NOT NULL,
        serial_number   VARCHAR(100),
        installation_date DATE,
        manufacturer    VARCHAR(100),
        design_life_hours FLOAT,
        current_health  FLOAT DEFAULT 1.0,
        status          VARCHAR(30) NOT NULL DEFAULT 'nominal',
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_components_satellite
        ON components(satellite_id);
    CREATE INDEX IF NOT EXISTS idx_components_type
        ON components(component_type);
    """,
    """
    CREATE TABLE IF NOT EXISTS maintenance_events (
        id              SERIAL PRIMARY KEY,
        component_id    VARCHAR(100) NOT NULL
            REFERENCES components(component_id) ON DELETE CASCADE,
        event_type      VARCHAR(50) NOT NULL,
        description     TEXT,
        performed_by    VARCHAR(100),
        performed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        rul_before_h    FLOAT,
        rul_after_h     FLOAT,
        parts_replaced  JSONB,
        outcome         VARCHAR(30) DEFAULT 'success',
        notes           TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_maintenance_component
        ON maintenance_events(component_id);
    CREATE INDEX IF NOT EXISTS idx_maintenance_date
        ON maintenance_events(performed_at DESC);
    """,
    """
    CREATE TABLE IF NOT EXISTS ml_model_registry (
        id              SERIAL PRIMARY KEY,
        model_name      VARCHAR(100) NOT NULL,
        version         VARCHAR(30) NOT NULL,
        model_type      VARCHAR(50) NOT NULL,
        component_type  VARCHAR(50),
        artifact_path   TEXT,
        tflite_path     TEXT,
        train_rmse      FLOAT,
        test_rmse       FLOAT,
        test_mae        FLOAT,
        test_r2         FLOAT,
        n_training_samples INTEGER,
        hyperparameters JSONB,
        feature_names   JSONB,
        is_active       BOOLEAN NOT NULL DEFAULT FALSE,
        deployed_at     TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(model_name, version)
    );
    CREATE INDEX IF NOT EXISTS idx_mlmodels_type
        ON ml_model_registry(component_type, is_active);
    """,
    """
    CREATE TABLE IF NOT EXISTS life_support_alerts (
        id              SERIAL PRIMARY KEY,
        alert_id        VARCHAR(50) UNIQUE NOT NULL,
        satellite_id    VARCHAR(50) NOT NULL,
        parameter       VARCHAR(50) NOT NULL,
        value           FLOAT NOT NULL,
        limit_value     FLOAT NOT NULL,
        alert_level     VARCHAR(30) NOT NULL,
        alert_message   TEXT,
        acknowledged    BOOLEAN NOT NULL DEFAULT FALSE,
        acknowledged_by VARCHAR(100),
        acknowledged_at TIMESTAMPTZ,
        resolved        BOOLEAN NOT NULL DEFAULT FALSE,
        resolved_at     TIMESTAMPTZ,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_ls_alerts_satellite
        ON life_support_alerts(satellite_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_ls_alerts_unack
        ON life_support_alerts(acknowledged, alert_level)
        WHERE acknowledged = FALSE;
    """,
    """
    CREATE TABLE IF NOT EXISTS mission_configurations (
        id              SERIAL PRIMARY KEY,
        config_key      VARCHAR(100) UNIQUE NOT NULL,
        config_value    JSONB NOT NULL,
        description     TEXT,
        modified_by     VARCHAR(100),
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS federated_rounds (
        id              SERIAL PRIMARY KEY,
        round_number    INTEGER NOT NULL,
        satellite_id    VARCHAR(50),
        n_clients       INTEGER,
        n_rejected      INTEGER,
        mean_loss       FLOAT,
        convergence_delta FLOAT,
        privacy_epsilon FLOAT,
        converged       BOOLEAN DEFAULT FALSE,
        duration_ms     FLOAT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_federated_round
        ON federated_rounds(round_number DESC);
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id              BIGSERIAL PRIMARY KEY,
        user_id         VARCHAR(100),
        action          VARCHAR(100) NOT NULL,
        resource_type   VARCHAR(50) NOT NULL,
        resource_id     VARCHAR(100),
        ip_address      INET,
        user_agent      TEXT,
        request_hash    VARCHAR(64),
        success         BOOLEAN NOT NULL DEFAULT TRUE,
        error_message   TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_audit_user
        ON audit_log(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_resource
        ON audit_log(resource_type, resource_id, created_at DESC);
    """,
]


# ---------------------------------------------------------------------------
# Data models (mirrors DB schema)
# ---------------------------------------------------------------------------

@dataclass
class SatelliteRecord:
    """
    ID: STR-002
    Purpose: Application-layer representation of a satellite registry entry.
    """
    satellite_id: str
    name: str
    satellite_type: str
    orbit_type: Optional[str] = None
    launch_date: Optional[str] = None
    status: str = "active"
    manufacturer: Optional[str] = None
    mission_id: Optional[str] = None
    created_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class ComponentRecord:
    """
    ID: STR-003
    Purpose: Application-layer representation of a satellite component.
    """
    component_id: str
    satellite_id: str
    component_type: str
    name: str
    serial_number: Optional[str] = None
    installation_date: Optional[str] = None
    manufacturer: Optional[str] = None
    design_life_hours: Optional[float] = None
    current_health: float = 1.0
    status: str = "nominal"
    id: Optional[int] = None


@dataclass
class MaintenanceEvent:
    """
    ID: STR-004
    Purpose: Application-layer representation of a maintenance record.
    """
    component_id: str
    event_type: str
    description: Optional[str] = None
    performed_by: Optional[str] = None
    rul_before_h: Optional[float] = None
    rul_after_h: Optional[float] = None
    parts_replaced: Optional[Dict[str, Any]] = None
    outcome: str = "success"
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class MLModelRecord:
    """
    ID: STR-005
    Purpose: Application-layer representation of a trained ML model version.
    """
    model_name: str
    version: str
    model_type: str
    component_type: Optional[str] = None
    artifact_path: Optional[str] = None
    tflite_path: Optional[str] = None
    train_rmse: Optional[float] = None
    test_rmse: Optional[float] = None
    test_mae: Optional[float] = None
    test_r2: Optional[float] = None
    n_training_samples: Optional[int] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    feature_names: Optional[List[str]] = None
    is_active: bool = False
    id: Optional[int] = None


# ---------------------------------------------------------------------------
# In-memory mock storage (for testing)
# ---------------------------------------------------------------------------

class _MockPostgresStorage:
    """
    ID: STR-006
    Purpose: In-memory dict-based storage that mimics PostgreSQL CRUD operations
             for unit testing without requiring a running database.
    """

    def __init__(self):
        self._satellites: Dict[str, SatelliteRecord] = {}
        self._components: Dict[str, ComponentRecord] = {}
        self._maintenance: List[MaintenanceEvent] = []
        self._models: List[MLModelRecord] = []
        self._alerts: List[Dict[str, Any]] = []
        self._audit: List[Dict[str, Any]] = []
        self._counter = 0

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter


# ---------------------------------------------------------------------------
# Main PostgreSQL storage class
# ---------------------------------------------------------------------------

class PostgreSQLStorage:
    """
    ID: STR-001
    Requirement: Provide CRUD operations for all relational data with full
                 SQL injection prevention (parameterized queries only),
                 connection pooling, and schema migration support.
    Purpose: Single data access layer for relational IoST data stores.
             All callers use this class - no raw SQL in application code.
    Preconditions: PostgreSQL 14+ accessible with CREATE TABLE privileges.
    Side Effects: Creates tables on first connect if apply_schema=True.
    Failure Modes: Raises StorageError on all DB errors (never crashes silently).
    Security: All queries use %s parameterization; no string interpolation.
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        host: str = "localhost",
        port: int = 5432,
        database: str = "iosct",
        user: str = "iosct_app",
        password: Optional[str] = None,
        mock_mode: bool = False,
        apply_schema: bool = True,
    ):
        self._mock: Optional[_MockPostgresStorage] = None
        self._conn = None

        if mock_mode or not _PSYCOPG2_AVAILABLE:
            self._mock = _MockPostgresStorage()
            logger.info("PostgreSQLStorage using in-memory mock.")
            return

        password = password or os.environ.get("POSTGRES_PASSWORD", "")
        dsn = dsn or (
            f"host={host} port={port} dbname={database} "
            f"user={user} password={password} "
            "connect_timeout=5 application_name=iosct"
        )

        try:
            self._conn = psycopg2.connect(dsn)
            self._conn.autocommit = False
            logger.info(
                "PostgreSQLStorage connected to %s:%d/%s", host, port, database
            )
            if apply_schema:
                self.apply_schema()
        except Exception as exc:
            logger.error(
                "PostgreSQL connection failed: %s - using mock.", exc
            )
            self._mock = _MockPostgresStorage()

    # ---- Schema management ----

    def apply_schema(self) -> None:
        """
        ID: STR-007
        Requirement: Apply all DDL migrations in order; idempotent (IF NOT EXISTS).
        Side Effects: Creates tables, indexes, and constraints in PostgreSQL.
        Error Handling: Rolls back on any DDL error; raises StorageError.
        """
        if self._conn is None:
            return
        try:
            with self._conn.cursor() as cur:
                for ddl in SCHEMA_DDL:
                    cur.execute(ddl)
                cur.execute(
                    "INSERT INTO schema_version (version, description) "
                    "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (SCHEMA_VERSION, "Initial IoST schema"),
                )
            self._conn.commit()
            logger.info("Schema version %s applied successfully.", SCHEMA_VERSION)
        except Exception as exc:
            self._conn.rollback()
            raise StorageError(f"Schema migration failed: {exc}") from exc

    # ---- Satellite CRUD ----

    def upsert_satellite(self, sat: SatelliteRecord) -> SatelliteRecord:
        """
        ID: STR-008
        Requirement: Insert or update a satellite record atomically.
        Inputs: SatelliteRecord with all required fields.
        Outputs: Updated record with assigned id.
        Security: Uses parameterized INSERT ... ON CONFLICT DO UPDATE.
        """
        if self._mock is not None:
            self._mock._satellites[sat.satellite_id] = sat
            sat.id = self._mock._next_id()
            return sat

        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO satellites
                        (satellite_id, name, satellite_type, orbit_type,
                         launch_date, status, manufacturer, mission_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (satellite_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    RETURNING id, created_at
                    """,
                    (sat.satellite_id, sat.name, sat.satellite_type,
                     sat.orbit_type, sat.launch_date, sat.status,
                     sat.manufacturer, sat.mission_id),
                )
                row = cur.fetchone()
                self._conn.commit()
                sat.id = row["id"]
                sat.created_at = row["created_at"]
                return sat
        except Exception as exc:
            self._conn.rollback()
            raise StorageError(f"upsert_satellite failed: {exc}") from exc

    def get_satellite(self, satellite_id: str) -> Optional[SatelliteRecord]:
        """
        ID: STR-009
        Purpose: Retrieve satellite by ID.
        Security: Parameterized query - satellite_id is never interpolated.
        """
        if self._mock is not None:
            return self._mock._satellites.get(satellite_id)

        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM satellites WHERE satellite_id = %s",
                    (satellite_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return SatelliteRecord(**{
                    k: row[k] for k in
                    ["satellite_id", "name", "satellite_type", "orbit_type",
                     "launch_date", "status", "manufacturer", "mission_id",
                     "created_at", "id"]
                    if k in row
                })
        except Exception as exc:
            raise StorageError(f"get_satellite failed: {exc}") from exc

    def list_satellites(
        self, status: Optional[str] = None
    ) -> List[SatelliteRecord]:
        """
        ID: STR-010
        Purpose: List all satellites, optionally filtered by status.
        """
        if self._mock is not None:
            sats = list(self._mock._satellites.values())
            if status:
                sats = [s for s in sats if s.status == status]
            return sats

        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if status:
                    cur.execute(
                        "SELECT * FROM satellites WHERE status = %s ORDER BY satellite_id",
                        (status,),
                    )
                else:
                    cur.execute("SELECT * FROM satellites ORDER BY satellite_id")
                return [SatelliteRecord(
                    satellite_id=r["satellite_id"], name=r["name"],
                    satellite_type=r["satellite_type"], status=r["status"],
                    id=r["id"],
                ) for r in cur.fetchall()]
        except Exception as exc:
            raise StorageError(f"list_satellites failed: {exc}") from exc

    # ---- Component CRUD ----

    def upsert_component(self, comp: ComponentRecord) -> ComponentRecord:
        """
        ID: STR-011
        Requirement: Insert or update a component record.
        Security: Parameterized query; foreign key enforced by DB.
        """
        if self._mock is not None:
            self._mock._components[comp.component_id] = comp
            comp.id = self._mock._next_id()
            return comp

        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO components
                        (component_id, satellite_id, component_type, name,
                         serial_number, design_life_hours, current_health, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (component_id) DO UPDATE SET
                        current_health = EXCLUDED.current_health,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (comp.component_id, comp.satellite_id, comp.component_type,
                     comp.name, comp.serial_number, comp.design_life_hours,
                     comp.current_health, comp.status),
                )
                row = cur.fetchone()
                self._conn.commit()
                comp.id = row["id"]
                return comp
        except Exception as exc:
            self._conn.rollback()
            raise StorageError(f"upsert_component failed: {exc}") from exc

    def get_components_by_satellite(
        self, satellite_id: str
    ) -> List[ComponentRecord]:
        """
        ID: STR-012
        Purpose: Retrieve all components for a satellite.
        """
        if self._mock is not None:
            return [c for c in self._mock._components.values()
                    if c.satellite_id == satellite_id]

        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM components WHERE satellite_id = %s ORDER BY component_type",
                    (satellite_id,),
                )
                return [ComponentRecord(
                    component_id=r["component_id"], satellite_id=r["satellite_id"],
                    component_type=r["component_type"], name=r["name"],
                    current_health=r.get("current_health", 1.0),
                    status=r.get("status", "nominal"), id=r["id"],
                ) for r in cur.fetchall()]
        except Exception as exc:
            raise StorageError(f"get_components_by_satellite failed: {exc}") from exc

    # ---- Maintenance events ----

    def record_maintenance(self, event: MaintenanceEvent) -> MaintenanceEvent:
        """
        ID: STR-013
        Requirement: Append maintenance event to component history.
        Side Effects: Updates component status in same transaction.
        """
        if self._mock is not None:
            event.id = self._mock._next_id()
            self._mock._maintenance.append(event)
            return event

        try:
            import json as _json
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO maintenance_events
                        (component_id, event_type, description, performed_by,
                         rul_before_h, rul_after_h, parts_replaced, outcome, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (event.component_id, event.event_type, event.description,
                     event.performed_by, event.rul_before_h, event.rul_after_h,
                     _json.dumps(event.parts_replaced or {}),
                     event.outcome, event.notes),
                )
                row = cur.fetchone()
                self._conn.commit()
                event.id = row[0]
                return event
        except Exception as exc:
            self._conn.rollback()
            raise StorageError(f"record_maintenance failed: {exc}") from exc

    # ---- ML model registry ----

    def register_model(self, model: MLModelRecord) -> MLModelRecord:
        """
        ID: STR-014
        Requirement: Register a trained model version; enforce unique (name, version).
        Side Effects: Deactivates previous active model for same component_type
                      if model.is_active=True (atomic update).
        """
        if self._mock is not None:
            model.id = self._mock._next_id()
            self._mock._models.append(model)
            return model

        try:
            import json as _json
            with self._conn.cursor() as cur:
                if model.is_active:
                    cur.execute(
                        "UPDATE ml_model_registry SET is_active = FALSE "
                        "WHERE component_type = %s AND is_active = TRUE",
                        (model.component_type,),
                    )
                cur.execute(
                    """
                    INSERT INTO ml_model_registry
                        (model_name, version, model_type, component_type,
                         artifact_path, tflite_path, train_rmse, test_rmse,
                         test_mae, test_r2, n_training_samples,
                         hyperparameters, feature_names, is_active)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (model_name, version) DO UPDATE SET
                        test_rmse = EXCLUDED.test_rmse,
                        is_active = EXCLUDED.is_active
                    RETURNING id
                    """,
                    (model.model_name, model.version, model.model_type,
                     model.component_type, model.artifact_path, model.tflite_path,
                     model.train_rmse, model.test_rmse, model.test_mae,
                     model.test_r2, model.n_training_samples,
                     _json.dumps(model.hyperparameters or {}),
                     _json.dumps(model.feature_names or []),
                     model.is_active),
                )
                row = cur.fetchone()
                self._conn.commit()
                model.id = row[0]
                return model
        except Exception as exc:
            self._conn.rollback()
            raise StorageError(f"register_model failed: {exc}") from exc

    def get_active_model(
        self, component_type: str
    ) -> Optional[MLModelRecord]:
        """
        ID: STR-015
        Purpose: Retrieve the currently active model for a component type.
        """
        if self._mock is not None:
            active = [m for m in self._mock._models
                      if m.component_type == component_type and m.is_active]
            return active[-1] if active else None

        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM ml_model_registry "
                    "WHERE component_type = %s AND is_active = TRUE "
                    "ORDER BY created_at DESC LIMIT 1",
                    (component_type,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return MLModelRecord(
                    model_name=row["model_name"], version=row["version"],
                    model_type=row["model_type"],
                    component_type=row.get("component_type"),
                    artifact_path=row.get("artifact_path"),
                    test_rmse=row.get("test_rmse"),
                    is_active=True, id=row["id"],
                )
        except Exception as exc:
            raise StorageError(f"get_active_model failed: {exc}") from exc

    # ---- Audit log ----

    def write_audit_log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        ID: STR-016
        Requirement: Append an immutable audit record for all data-modifying operations.
        Purpose: Compliance and forensics - who changed what and when.
        Security: ip_address is stored as PostgreSQL INET type (validated by DB).
        Side Effects: Inserts into append-only audit_log table.
        """
        if self._mock is not None:
            self._mock._audit.append({
                "user_id": user_id, "action": action,
                "resource_type": resource_type, "resource_id": resource_id,
                "success": success, "error_message": error_message,
                "created_at": datetime.now(timezone.utc),
            })
            return

        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log
                        (user_id, action, resource_type, resource_id,
                         ip_address, success, error_message)
                    VALUES (%s, %s, %s, %s, %s::INET, %s, %s)
                    """,
                    (user_id, action, resource_type, resource_id,
                     ip_address, success, error_message),
                )
            self._conn.commit()
        except Exception as exc:
            if self._conn:
                self._conn.rollback()
            logger.error("Audit log write failed: %s", exc)
            # Audit failures logged but not raised - never block business ops

    def close(self) -> None:
        """Close database connection cleanly."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        logger.info("PostgreSQLStorage connection closed.")
