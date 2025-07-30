#!/usr/bin/env python3
"""
Enhanced IoST GUI Launcher Script
Advanced launcher with dependency management and multiple GUI modes
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    return True


def check_package_availability(package_name, import_name=None):
    """Check if a package is available for import"""
    if import_name is None:
        import_name = package_name.lower().replace("-", "_")
    
    try:
        if package_name == "PyOpenGL":
            import OpenGL.GL
        else:
            importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def install_package(package_spec):
    """Install a Python package using pip"""
    package_name = package_spec.split(">=")[0]
    try:
        print(f"Installing {package_name}...")
        subprocess.run([
            sys.executable, "-m", "pip", "install", package_spec
        ], check=True)
        print(f"✓ {package_name} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install {package_name}: {e}")
        return False


def install_requirements():
    """Install all requirements from requirements.txt"""
    print("Installing from requirements.txt...")
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ], check=True)
        print("✓ All requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install requirements: {e}")
        return False


def check_dependencies():
    """Check and report on dependency availability"""
    dependencies = {
        "required": [
            ("PyQt6", "PyQt6>=6.5.0"),
        ],
        "optional": [
            ("numpy", "numpy>=1.24.0"),
            ("matplotlib", "matplotlib>=3.7.0"),
            ("PyOpenGL", "PyOpenGL>=3.1.7"),
            ("scipy", "scipy>=1.10.0"),
            ("pandas", "pandas>=2.0.0"),
            ("psutil", "psutil>=5.9.0"),
            ("pyqtgraph", "pyqtgraph>=0.13.0"),
        ]
    }
    
    available = {"required": [], "optional": []}
    missing = {"required": [], "optional": []}
    
    # Check required dependencies
    for name, spec in dependencies["required"]:
        if check_package_availability(name):
            available["required"].append(name)
            print(f"✓ {name} (required) - Available")
        else:
            missing["required"].append((name, spec))
            print(f"✗ {name} (required) - Missing")
    
    # Check optional dependencies
    for name, spec in dependencies["optional"]:
        if check_package_availability(name):
            available["optional"].append(name)
            print(f"✓ {name} (optional) - Available")
        else:
            missing["optional"].append((name, spec))
            print(f"- {name} (optional) - Missing")
    
    return available, missing


def determine_gui_mode(available_packages):
    """Determine which GUI mode to use based on available packages"""
    enhanced_requirements = ["numpy", "matplotlib"]
    
    if all(pkg in available_packages["optional"] for pkg in enhanced_requirements):
        return "enhanced"
    else:
        return "standard"


def launch_gui(mode="auto"):
    """Launch the appropriate GUI application"""
    try:
        if mode == "enhanced" or mode == "auto":
            try:
                # Try enhanced GUI first
                print("🚀 Attempting to launch Enhanced IoST GUI...")
                from enhanced_main import main as enhanced_main
                print("✓ Enhanced GUI modules loaded")
                print("Features: Advanced visualization, 3D tracking, real-time analysis")
                return enhanced_main()
            except ImportError as e:
                if mode == "enhanced":
                    print(f"✗ Enhanced GUI not available: {e}")
                    return 1
                else:
                    print(f"⚠ Enhanced GUI not available: {e}")
                    print("Falling back to standard GUI...")
        
        # Launch standard GUI
        print("🚀 Launching Standard IoST GUI...")
        from main import main as standard_main
        print("✓ Standard GUI modules loaded")
        print("Features: Mission control, telemetry, system monitoring")
        return standard_main()
        
    except ImportError as e:
        print(f"✗ Failed to import GUI modules: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure you're running from the gui/ directory")
        print("2. Check that PyQt6 is installed")
        print("3. Verify all GUI modules are present")
        return 1
    except Exception as e:
        print(f"✗ Error starting GUI: {e}")
        return 1


def main():
    """Main launcher function"""
    print("🌌 Internet of Space Things (IoST) - Enhanced GUI Launcher")
    print("=" * 65)
    
    # Parse command line arguments
    mode = "auto"
    install_deps = False
    
    for arg in sys.argv[1:]:
        if arg == "--enhanced":
            mode = "enhanced"
        elif arg == "--standard":
            mode = "standard"
        elif arg == "--install-deps":
            install_deps = True
        elif arg == "--help":
            print("Usage: python launch.py [OPTIONS]")
            print("\nOptions:")
            print("  --enhanced     Force enhanced GUI mode")
            print("  --standard     Force standard GUI mode")
            print("  --install-deps Install all dependencies")
            print("  --help         Show this help message")
            return 0
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Install dependencies if requested
    if install_deps:
        print("\nInstalling all dependencies...")
        if not install_requirements():
            print("✗ Failed to install dependencies")
            return 1
        print("✓ Dependencies installed")
    
    # Check dependencies
    print("\nChecking dependencies...")
    available, missing = check_dependencies()
    
    # Install missing required dependencies
    if missing["required"]:
        print("\nInstalling missing required dependencies...")
        for name, spec in missing["required"]:
            if not install_package(spec):
                print(f"✗ Failed to install required dependency: {name}")
                return 1
        
        # Re-check after installation
        print("Re-checking dependencies...")
        available, missing = check_dependencies()
        
        if missing["required"]:
            print("✗ Still missing required dependencies")
            return 1
    
    # Determine GUI mode if auto
    if mode == "auto":
        mode = determine_gui_mode(available)
        print(f"\nAuto-selected GUI mode: {mode}")
    
    # Report on optional dependencies
    if missing["optional"]:
        print(f"\nOptional dependencies missing: {len(missing['optional'])}")
        print("These provide enhanced features. Install with:")
        print("  python launch.py --install-deps")
    
    # Launch GUI
    print(f"\nLaunching GUI in {mode} mode...")
    return launch_gui(mode)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)
