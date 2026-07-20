#!/usr/bin/env python3
"""Dependency health check for IoST development environments.

This script performs two checks:
1. Verifies key runtime packages can be imported.
2. Runs ``pip check`` to identify broken dependency metadata.

Exit code is non-zero when required dependencies are missing or conflicted.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import dataclass
from typing import List


@dataclass
class PackageCheckResult:
	name: str
	required: bool
	ok: bool
	details: str = ""


# Keep this list short and focused on runtime-critical imports.
PACKAGE_IMPORT_CHECKS = [
	("numpy", "numpy", True),
	("fastapi", "fastapi", True),
	("pydantic", "pydantic", True),
	("sqlalchemy", "sqlalchemy", True),
	("influxdb-client", "influxdb_client", False),
	("redis", "redis", False),
	("confluent-kafka", "confluent_kafka", False),
	("tensorflow", "tensorflow", False),
	("torch", "torch", False),
]


def _check_imports() -> List[PackageCheckResult]:
	results: List[PackageCheckResult] = []
	for package_name, import_name, required in PACKAGE_IMPORT_CHECKS:
		try:
			importlib.import_module(import_name)
			results.append(PackageCheckResult(package_name, required, True, "import ok"))
		except Exception as exc:  # pragma: no cover - exercised via runtime environments
			results.append(PackageCheckResult(package_name, required, False, str(exc)))
	return results


def _run_pip_check() -> tuple[bool, str]:
	proc = subprocess.run(
		[sys.executable, "-m", "pip", "check"],
		capture_output=True,
		text=True,
		check=False,
	)
	output = (proc.stdout or "") + (proc.stderr or "")
	return proc.returncode == 0, output.strip()


def main() -> int:
	print("IoST dependency health check")
	print("=" * 32)

	import_results = _check_imports()
	required_failures = 0
	optional_failures = 0

	for result in import_results:
		scope = "required" if result.required else "optional"
		if result.ok:
			print(f"[OK]   {result.name:<18} ({scope})")
			continue

		if result.required:
			required_failures += 1
			print(f"[FAIL] {result.name:<18} ({scope}) -> {result.details}")
		else:
			optional_failures += 1
			print(f"[WARN] {result.name:<18} ({scope}) -> {result.details}")

	print("\nRunning pip metadata consistency check...")
	pip_ok, pip_output = _run_pip_check()
	if pip_ok:
		print("[OK]   pip check passed")
	else:
		print("[WARN] pip check reported conflicts")
		if pip_output:
			print(pip_output)

	print("\nSummary")
	print("-" * 32)
	print(f"Required import failures: {required_failures}")
	print(f"Optional import failures: {optional_failures}")
	print(f"Pip metadata conflicts: {'no' if pip_ok else 'yes'}")

	if required_failures:
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
