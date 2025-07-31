# 🏗️ Internet of Space Things (IoST) - Reorganization Plan

## 📋 **Proposed Project Structure**

```
internet-of-space-things/
├── README.md
├── pyproject.toml                 # Modern Python packaging
├── requirements.txt               # Consolidated dependencies
├── requirements-dev.txt           # Development dependencies  
├── requirements-gui.txt           # GUI-specific dependencies
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── CHANGELOG.md
├── LICENSE
│
├── iosct/                         # Main package (renamed for clarity)
│   ├── __init__.py
│   ├── main.py                    # Single unified entry point
│   ├── cli.py                     # Command line interface
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── constants.py
│   │
│   ├── core/                      # Core space systems
│   │   ├── __init__.py
│   │   ├── mission_control.py
│   │   ├── satellite_manager.py
│   │   ├── space_network.py
│   │   └── exceptions.py
│   │
│   ├── communication/             # Communication protocols
│   │   ├── __init__.py
│   │   ├── protocols/
│   │   │   ├── __init__.py
│   │   │   └── deep_space_protocol.py
│   │   └── multiband_radio.py
│   │
│   ├── cubesat/                   # CubeSat systems
│   │   ├── __init__.py
│   │   ├── cubesat_network.py
│   │   └── sdn_controller.py
│   │
│   ├── cehsn/                     # Cognitive Emergency Network
│   │   ├── __init__.py
│   │   ├── orbital_infer.py
│   │   ├── rpa_comm_bridge.py
│   │   ├── ethics_engine.py
│   │   └── survival_mapgen.py
│   │
│   ├── sensors/                   # Sensor systems
│   │   ├── __init__.py
│   │   └── environmental/
│   │       ├── __init__.py
│   │       └── radiation_detector.py
│   │
│   ├── interfaces/                # User interfaces
│   │   ├── __init__.py
│   │   ├── gui/                   # PyQt6 GUI
│   │   │   ├── __init__.py
│   │   │   ├── main_window.py
│   │   │   ├── enhanced_widgets.py
│   │   │   ├── visualization_3d.py
│   │   │   ├── data_provider.py
│   │   │   └── widgets.py
│   │   └── web/                   # Web dashboard
│   │       ├── __init__.py
│   │       └── app.py
│   │
│   ├── utils/                     # Utility functions
│   │   ├── __init__.py
│   │   ├── logging_config.py
│   │   ├── data_processing.py
│   │   └── helpers.py
│   │
│   └── db/                        # Database models
│       ├── __init__.py
│       ├── models.py
│       └── migrations/
│
├── tests/                         # Comprehensive test suite
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_core/
│   │   ├── test_communication/
│   │   ├── test_cubesat/
│   │   └── test_cehsn/
│   ├── integration/
│   │   └── test_full_system.py
│   └── fixtures/
│       └── sample_data/
│
├── docs/                          # Documentation
│   ├── index.md
│   ├── architecture.md
│   ├── api_documentation.md
│   ├── user_manual.md
│   ├── deployment_guide.md
│   └── development/
│       ├── setup.md
│       └── contributing.md
│
├── scripts/                       # Utility scripts
│   ├── setup.py
│   ├── run_tests.py
│   └── deploy.py
│
└── data/                         # Data files
    ├── configs/
    ├── samples/
    └── exports/
```

## 🔄 **Key Reorganization Changes**

### **1. Package Naming & Structure**
- **Before:** Mixed `src/` and root-level files
- **After:** Clean `iosct/` package (Internet of Space Things Cognitive Technology)
- **Benefit:** Professional Python package structure, easier imports

### **2. Unified Entry Points**
- **Before:** Multiple `main.py` files with different purposes
- **After:** Single `iosct/main.py` with modular execution modes
- **Benefit:** Clear application entry, no confusion

### **3. GUI Integration**
- **Before:** Separate `gui/` directory with manual path manipulation
- **After:** `iosct/interfaces/gui/` as proper subpackage
- **Benefit:** Clean imports, no sys.path hacks

### **4. Configuration Management**
- **Before:** Scattered configuration
- **After:** Centralized `iosct/config/` module
- **Benefit:** Easy environment management, clear settings

### **5. Testing Structure**
- **Before:** Tests mixed with source code
- **After:** Dedicated `tests/` with organized structure
- **Benefit:** Clean separation, comprehensive test coverage

## 📦 **Dependencies Consolidation**

### **requirements.txt** (Core dependencies)
```
# Core IoST platform dependencies
fastapi>=0.104.0
uvicorn>=0.24.0
numpy>=1.24.0
scipy>=1.10.0
astropy>=5.3.0
skyfield>=1.47.0
tensorflow>=2.14.0
scikit-learn>=1.3.0
influxdb-client>=1.38.0
redis>=5.0.0
asyncio-mqtt>=0.13.0
```

### **requirements-gui.txt** (GUI-specific)
```
# PyQt6 GUI Requirements
PyQt6>=6.5.0
PyOpenGL>=3.1.7
matplotlib>=3.7.0
pyqtgraph>=0.13.0
plotly>=5.14.0
```

### **requirements-dev.txt** (Development tools)
```
# Development and testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
black>=23.9.0
flake8>=6.1.0
mypy>=1.6.0
```

## 🎯 **Implementation Strategy**

1. **Gradual Migration:** Move files systematically to avoid breaking changes
2. **Import Path Updates:** Use find-replace for consistent import updates  
3. **Testing at Each Step:** Verify functionality after each major change
4. **Rollback Safety:** Git checkpoints at each phase completion
