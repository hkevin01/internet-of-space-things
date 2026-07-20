#!/usr/bin/env python3
"""Dependency health check for IoST development environments.

This script validates package versions against profile requirements and
checks package metadata consistency via ``pip check``.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
from pathlib import Path
from typing import Dict
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Set, Tuple

try:
	from packaging.requirements import InvalidRequirement, Requirement
	from packaging.utils import canonicalize_name
except ModuleNotFoundError:  # pragma: no cover - depends on interpreter setup
	from pip._vendor.packaging.requirements import InvalidRequirement, Requirement
	from pip._vendor.packaging.utils import canonicalize_name


@dataclass
class PackageCheckResult:
	name: str
	specifier: str
	required: bool
	installed_version: str = ""
	ok: bool = False
	details: str = ""
	source_file: str = ""


ROOT_DIR = Path(__file__).resolve().parents[1]
PROFILE_TO_FILE: Dict[str, Path] = {
	"core": ROOT_DIR / "requirements" / "profiles" / "core.txt",
	"ml": ROOT_DIR / "requirements" / "profiles" / "ml.txt",
	"full-stack": ROOT_DIR / "requirements" / "profiles" / "full-stack.txt",
}


def _parse_requirements_file(req_file: Path, visited: Set[Path]) -> List[Tuple[Requirement, Path]]:
	if req_file in visited:
		return []

	visited.add(req_file)
	parsed: List[Tuple[Requirement, Path]] = []

	for raw_line in req_file.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#"):
			continue

		if line.startswith(("-r", "--requirement")):
			tokens = line.split(maxsplit=1)
			if len(tokens) != 2:
				continue
			nested_path = (req_file.parent / tokens[1].strip()).resolve()
			parsed.extend(_parse_requirements_file(nested_path, visited))
			continue

		if line.startswith(("-c", "--constraint")):
			# Constraints are ignored here; specifier checks are performed on direct requirements.
			continue

		try:
			requirement = Requirement(line)
		except InvalidRequirement as exc:
			raise ValueError(f"Invalid requirement '{line}' in {req_file}: {exc}") from exc

		if requirement.marker and not requirement.marker.evaluate():
			continue

		parsed.append((requirement, req_file))

	return parsed


def _load_profile_requirements(profile: str) -> List[Tuple[Requirement, Path]]:
	req_file = PROFILE_TO_FILE[profile]
	if not req_file.exists():
		raise FileNotFoundError(f"Profile file not found: {req_file}")
	return _parse_requirements_file(req_file.resolve(), visited=set())


def _check_versions(profile: str) -> List[PackageCheckResult]:
	results: List[PackageCheckResult] = []
	seen: Set[str] = set()

	for requirement, source_file in _load_profile_requirements(profile):
		package_key = canonicalize_name(requirement.name)
		if package_key in seen:
			continue
		seen.add(package_key)

		specifier = str(requirement.specifier) if requirement.specifier else "(any)"
		result = PackageCheckResult(
			name=requirement.name,
			specifier=specifier,
			required=True,
			source_file=os.path.relpath(source_file, ROOT_DIR),
		)

		try:
			installed_version = importlib.metadata.version(requirement.name)
			result.installed_version = installed_version
			if not requirement.specifier or requirement.specifier.contains(installed_version, prereleases=True):
				result.ok = True
				result.details = "version matches"
			else:
				result.ok = False
				result.details = "version mismatch"
		except importlib.metadata.PackageNotFoundError:
			result.ok = False
			result.details = "package not installed"

		results.append(result)

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


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Validate dependency profile for IoST.")
	parser.add_argument(
		"--profile",
		choices=sorted(PROFILE_TO_FILE.keys()),
		default="core",
		help="Requirements profile to validate.",
	)
	parser.add_argument(
		"--skip-pip-check",
		action="store_true",
		help="Skip pip metadata conflict check.",
	)
	return parser


def main() -> int:
	parser = _build_parser()
	args = parser.parse_args()

	print("IoST dependency health check")
	print("=" * 32)
	print(f"Profile: {args.profile}")

	results = _check_versions(args.profile)
	failures = 0

	for result in results:
		if result.ok:
			print(
				f"[OK]   {result.name:<20} required {result.specifier:<12} "
				f"installed {result.installed_version:<12} ({result.source_file})"
			)
			continue

		failures += 1
		installed = result.installed_version or "not-installed"
		print(
			f"[FAIL] {result.name:<20} required {result.specifier:<12} "
			f"installed {installed:<12} -> {result.details} ({result.source_file})"
		)

	pip_ok = True
	pip_output = ""
	if not args.skip_pip_check:
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
	print(f"Dependency mismatches: {failures}")
	print(f"Pip metadata conflicts: {'no' if pip_ok else 'yes'}")

	if failures or (not pip_ok):
		return 1
	return 0


if __name__ == "__main__":
    raise SystemExit(main())
