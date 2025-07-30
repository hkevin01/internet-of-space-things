#!/usr/bin/env python3
"""
Quick test to check if required packages are available
"""

try:
    import pytest
    print("✅ pytest is available")
except ImportError:
    print("❌ pytest not found")

try:
    import fastapi
    print("✅ fastapi is available")
except ImportError:
    print("❌ fastapi not found")

try:
    import asyncio
    print("✅ asyncio is available")
except ImportError:
    print("❌ asyncio not found")

try:
    import numpy
    print("✅ numpy is available")
except ImportError:
    print("❌ numpy not found")

print("\nAttempting to run a simple test...")

# Run a basic test
def test_basic():
    assert 1 + 1 == 2
    print("✅ Basic test passed")

test_basic()
print("Package check complete!")
