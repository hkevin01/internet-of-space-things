# Timezone-Aware UTC Migration Plan

This document defines a separate, controlled migration to timezone-aware UTC timestamps across the project.

## Why This Is Separate

The current codebase uses naive datetimes for compatibility across modules and tests. Moving to timezone-aware UTC requires coordinated updates to avoid mixed-type arithmetic errors and serialization regressions.

## Target Standard

- Internal timestamp creation: datetime.now(datetime.UTC)
- Stored and transmitted format: ISO 8601 with explicit UTC offset
- API contracts: always include timezone information
- Persistence layer: normalized UTC in database and time-series records

## Migration Phases

1. Inventory and classification
- Enumerate all datetime creation and parsing points in src, gui, tests, and scripts.
- Classify by domain: core mission flow, telemetry, storage, communication, UI.

2. Compatibility utilities
- Add shared helpers in one module for UTC now, safe parsing, and normalization.
- Introduce conversion wrappers at boundaries (API, DB, message payloads).

3. Module-by-module rollout
- Migrate one subsystem at a time (core, telemetry, CEHSN, communication, UI).
- Update tests for explicit timezone expectations.
- Add guard tests to block new naive datetime usage in migrated modules.

4. Persistence and protocol alignment
- Validate PostgreSQL and InfluxDB write paths preserve UTC offsets.
- Validate protocol payload serializers include timezone-aware timestamps.

5. Final enforcement
- Add static checks to fail CI on naive datetime creation in migrated code.
- Remove temporary compatibility shims.

## Risk Controls

- Do not mix naive and aware datetimes in arithmetic.
- Preserve API compatibility by versioning payload schema if needed.
- Roll out with feature flags for high-risk modules.
- Keep migration commits small and subsystem-scoped.

## Acceptance Criteria

- No naive datetime creation in migrated modules.
- All timestamp fields in APIs and persisted records contain UTC offset.
- Full test suite passes with timezone-aware assertions.
- Documentation updated with timestamp contract examples.
