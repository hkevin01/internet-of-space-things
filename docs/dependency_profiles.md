# Dependency Profiles and Lockfile Workflow

This project uses profile-based dependency sets to keep development environments reproducible.

## Profiles

- core: Service runtime dependencies without heavy ML frameworks.
- ml: Model training and inference dependencies.
- full-stack: Core + ML + test and quality tooling.

Profile files are stored in requirements/profiles.

## Bootstrap Script

Use scripts/bootstrap_env.sh to create a controlled interpreter and install dependencies.

Examples:

```bash
scripts/bootstrap_env.sh --profile core
scripts/bootstrap_env.sh --profile ml
scripts/bootstrap_env.sh --profile full-stack --relock
```

Behavior:

1. Creates virtual environment (default: .venv).
2. Installs from existing lockfile when available.
3. If lockfile is missing or --relock is used, installs from profile and generates a lockfile.
4. Runs scripts/check_packages.py for the selected profile.

## Lockfiles

Lockfiles are written to requirements/locks:

- requirements/locks/core.lock
- requirements/locks/ml.lock
- requirements/locks/full-stack.lock

Commit lockfile updates together with dependency changes.

## Dependency Verification

Run profile checks directly:

```bash
python scripts/check_packages.py --profile core
python scripts/check_packages.py --profile ml
python scripts/check_packages.py --profile full-stack
```

The checker parses requirements files directly (including nested -r includes), validates installed versions against specifiers, and runs pip check for metadata conflicts.
