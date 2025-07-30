#!/usr/bin/env python3
"""
Internet of Space Things (IoST) - Main GUI Application
PyQt6-based comprehensive interface for mission control and system monitoring
"""

import os
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QDate,
    QDateTime,
    QEasingCurve,
    QMutex,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRunnable,
    QSize,
    Qt,
    QThread,
    QThreadPool,
    QTime,
    QTimer,
    QWaitCondition,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QDoubleValidator,
    QFont,
    QIcon,
    QIntValidator,
    QKeySequence,
    QLinearGradient,
    QMovie,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
    QRadialGradient,
    QRegularExpressionValidator,
    QValidator,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDial,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QTimeEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Add src to Python path for importing IoST modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import IoST system components
try:
    from cehsn.ethics_engine import EthicsEngine
    from cehsn.orbital_infer import OrbitalInferenceEngine
    from cehsn.resilience_monitor import ResilienceMonitor
    from cehsn.rpa_comm_bridge import RPACommunicationBridge
    from cehsn.survival_mapgen import SurvivalMapGenerator
    from communication.multiband_radio import FrequencyBand, MultibandRadio
    from core.mission_control import MissionControl
    from core.satellite_manager import SatelliteManager
    from core.space_network import SpaceNetwork
    from cubesat.cubesat_network import CubeSat, CubeSatSize
    from cubesat.sdn_controller import SDNController
except ImportError as e:
    print(f"Warning: Could not import IoST modules: {e}")
    print("GUI will run in demonstration mode")


class IoSTMainWindow(QMainWindow):
    """Main window for Internet of Space Things GUI"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Internet of Space Things (IoST) - Mission Control")
        self.setGeometry(100, 100, 1600, 1000)
        
        # Initialize IoST system components
        self.init_iost_systems()
        
        # Setup UI components
        self.init_ui()
        self.init_menus()
        self.init_toolbar()
        self.init_status_bar()
        
        # Start real-time updates
        self.init_timers()
        
        # Apply styling
        self.apply_space_theme()
    
    def init_iost_systems(self):
        """Initialize IoST system components"""
        try:
            # Core systems
            self.mission_control = MissionControl()
            self.satellite_manager = SatelliteManager()
            self.space_network = SpaceNetwork()
            
            # CEHSN components
            self.orbital_inference = OrbitalInferenceEngine()
            self.rpa_bridge = RPACommunicationBridge()
            self.ethics_engine = EthicsEngine()
            self.survival_mapgen = SurvivalMapGenerator()
            self.resilience_monitor = ResilienceMonitor()
            
            # Communication systems
            self.sdn_controller = SDNController("GUI_SDN")
            
            self.systems_initialized = True
            
        except Exception as e:
            print(f"Error initializing IoST systems: {e}")
            self.systems_initialized = False
    
    def init_ui(self):
        """Initialize the main user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_mission_control_tab()
        self.create_satellite_management_tab()
        self.create_cehsn_operations_tab()
        self.create_telemetry_monitoring_tab()
        self.create_emergency_response_tab()
        self.create_system_diagnostics_tab()
    
    def create_mission_control_tab(self):
        """Create mission control dashboard tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Top status panel
        status_group = QGroupBox("System Status Overview")
        status_layout = QGridLayout(status_group)
        
        # System status indicators
        self.system_status_label = QLabel("🟢 All Systems Nominal")
        self.system_status_label.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        status_layout.addWidget(self.system_status_label, 0, 0)
        
        self.spacecraft_count_label = QLabel("Active Spacecraft: 15")
        status_layout.addWidget(self.spacecraft_count_label, 0, 1)
        
        self.communication_status_label = QLabel("Communication Links: 🟢 Strong")
        status_layout.addWidget(self.communication_status_label, 0, 2)
        
        layout.addWidget(status_group)
        
        # Mission control map and controls
        control_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - spacecraft map
        map_group = QGroupBox("Real-time Spacecraft Tracking")
        map_layout = QVBoxLayout(map_group)
        
        self.spacecraft_map = SpacecraftMapWidget()
        map_layout.addWidget(self.spacecraft_map)
        
        control_splitter.addWidget(map_group)
        
        # Right side - control panels
        control_group = QGroupBox("Mission Control Operations")
        control_layout = QVBoxLayout(control_group)
        
        # Quick action buttons
        quick_actions_group = QGroupBox("Quick Actions")
        quick_layout = QGridLayout(quick_actions_group)
        
        self.emergency_btn = QPushButton("🚨 Emergency Protocol")
        self.emergency_btn.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        quick_layout.addWidget(self.emergency_btn, 0, 0)
        
        self.manual_command_btn = QPushButton("💻 Manual Command")
        quick_layout.addWidget(self.manual_command_btn, 0, 1)
        
        self.ground_contact_btn = QPushButton("📞 Ground Contact")
        quick_layout.addWidget(self.ground_contact_btn, 1, 0)
        
        self.generate_report_btn = QPushButton("📊 Generate Report")
        quick_layout.addWidget(self.generate_report_btn, 1, 1)
        
        control_layout.addWidget(quick_actions_group)
        
        # Active alerts panel
        alerts_group = QGroupBox("Active Alerts")
        alerts_layout = QVBoxLayout(alerts_group)
        
        self.alerts_list = QListWidget()
        self.alerts_list.addItem("⚠️ Minor thermal variance detected - ISS Solar Panel 3")
        self.alerts_list.addItem("ℹ️ Scheduled maintenance window - Dragon Capsule")
        self.alerts_list.addItem("ℹ️ Communication window opening - Mars Perseverance")
        alerts_layout.addWidget(self.alerts_list)
        
        control_layout.addWidget(alerts_group)
        
        control_splitter.addWidget(control_group)
        layout.addWidget(control_splitter)
        
        self.tab_widget.addTab(tab, "🏠 Mission Control")
    
    def create_satellite_management_tab(self):
        """Create satellite management tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Satellite selection and overview
        selection_group = QGroupBox("Spacecraft Selection")
        selection_layout = QHBoxLayout(selection_group)
        
        self.satellite_combo = QComboBox()
        self.satellite_combo.addItems([
            "ISS (International Space Station)",
            "Luna Gateway",
            "Crew Dragon DM-2",
            "Starship SN-15",
            "CubeSat Constellation Alpha",
            "Mars Perseverance Rover",
            "Hubble Space Telescope"
        ])
        selection_layout.addWidget(QLabel("Select Spacecraft:"))
        selection_layout.addWidget(self.satellite_combo)
        
        self.refresh_satellites_btn = QPushButton("🔄 Refresh")
        selection_layout.addWidget(self.refresh_satellites_btn)
        
        layout.addWidget(selection_group)
        
        # Satellite details splitter
        details_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - satellite info
        info_group = QGroupBox("Spacecraft Information")
        info_layout = QVBoxLayout(info_group)
        
        # Status display
        self.satellite_status_widget = SatelliteStatusWidget()
        info_layout.addWidget(self.satellite_status_widget)
        
        details_splitter.addWidget(info_group)
        
        # Right side - controls
        controls_group = QGroupBox("Spacecraft Operations")
        controls_layout = QVBoxLayout(controls_group)
        
        # Configuration controls
        config_group = QGroupBox("Configuration")
        config_layout = QGridLayout(config_group)
        
        config_layout.addWidget(QLabel("Power Mode:"), 0, 0)
        self.power_mode_combo = QComboBox()
        self.power_mode_combo.addItems(["Normal", "Power Save", "High Performance"])
        config_layout.addWidget(self.power_mode_combo, 0, 1)
        
        config_layout.addWidget(QLabel("Communication Freq:"), 1, 0)
        self.comm_freq_spin = QDoubleSpinBox()
        self.comm_freq_spin.setRange(2.0, 40.0)
        self.comm_freq_spin.setValue(8.4)
        self.comm_freq_spin.setSuffix(" GHz")
        config_layout.addWidget(self.comm_freq_spin, 1, 1)
        
        controls_layout.addWidget(config_group)
        
        # Command execution
        command_group = QGroupBox("Command Execution")
        command_layout = QVBoxLayout(command_group)
        
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command...")
        command_layout.addWidget(self.command_input)
        
        command_buttons_layout = QHBoxLayout()
        self.execute_command_btn = QPushButton("▶️ Execute")
        self.queue_command_btn = QPushButton("📋 Queue")
        self.abort_command_btn = QPushButton("❌ Abort")
        
        command_buttons_layout.addWidget(self.execute_command_btn)
        command_buttons_layout.addWidget(self.queue_command_btn)
        command_buttons_layout.addWidget(self.abort_command_btn)
        command_layout.addLayout(command_buttons_layout)
        
        controls_layout.addWidget(command_group)
        
        details_splitter.addWidget(controls_group)
        layout.addWidget(details_splitter)
        
        self.tab_widget.addTab(tab, "🛰️ Satellites")
    
    def create_cehsn_operations_tab(self):
        """Create CEHSN operations tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # CEHSN overview
        overview_group = QGroupBox("CubeSat-Enabled Hybrid Survival Network (CEHSN)")
        overview_layout = QHBoxLayout(overview_group)
        
        # CEHSN status indicators
        status_grid = QGridLayout()
        
        self.orbital_inference_status = QLabel("🔍 Orbital Inference: 🟢 Active")
        status_grid.addWidget(self.orbital_inference_status, 0, 0)
        
        self.rpa_bridge_status = QLabel("🚁 RPA Bridge: 🟢 Connected")
        status_grid.addWidget(self.rpa_bridge_status, 0, 1)
        
        self.ethics_engine_status = QLabel("⚖️ Ethics Engine: 🟢 Operational")
        status_grid.addWidget(self.ethics_engine_status, 1, 0)
        
        self.survival_map_status = QLabel("🗺️ Survival Maps: 🟢 Generating")
        status_grid.addWidget(self.survival_map_status, 1, 1)
        
        self.resilience_monitor_status = QLabel("🛡️ Resilience Monitor: 🟢 Monitoring")
        status_grid.addWidget(self.resilience_monitor_status, 2, 0)
        
        overview_layout.addLayout(status_grid)
        layout.addWidget(overview_group)
        
        # CEHSN component tabs
        cehsn_tabs = QTabWidget()
        
        # Orbital Inference tab
        self.create_orbital_inference_tab(cehsn_tabs)
        
        # RPA Communication Bridge tab
        self.create_rpa_bridge_tab(cehsn_tabs)
        
        # Ethics Engine tab
        self.create_ethics_engine_tab(cehsn_tabs)
        
        # Survival Map Generator tab
        self.create_survival_map_tab(cehsn_tabs)
        
        # Resilience Monitor tab
        self.create_resilience_monitor_tab(cehsn_tabs)
        
        layout.addWidget(cehsn_tabs)
        
        self.tab_widget.addTab(tab, "⚡ CEHSN")
    
    def create_orbital_inference_tab(self, parent_tabs):
        """Create orbital inference engine tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Prediction results
        predictions_group = QGroupBox("AI Predictions")
        predictions_layout = QVBoxLayout(predictions_group)
        
        self.predictions_table = QTableWidget(5, 4)
        self.predictions_table.setHorizontalHeaderLabels([
            "Event Type", "Confidence", "Time to Event", "Recommended Action"
        ])
        
        # Sample predictions
        predictions = [
            ("Solar Particle Event", "94.7%", "8h 23m", "Activate radiation shielding"),
            ("Equipment Failure - OGS", "96.8%", "72h", "Schedule maintenance"),
            ("Debris Collision Risk", "12.3%", "4d 12h", "Monitor trajectory"),
            ("Communication Blackout", "8.1%", "2d 6h", "Prepare backup channels"),
            ("Thermal Anomaly", "67.2%", "1d 14h", "Adjust cooling system")
        ]
        
        for i, (event, conf, time, action) in enumerate(predictions):
            self.predictions_table.setItem(i, 0, QTableWidgetItem(event))
            self.predictions_table.setItem(i, 1, QTableWidgetItem(conf))
            self.predictions_table.setItem(i, 2, QTableWidgetItem(time))
            self.predictions_table.setItem(i, 3, QTableWidgetItem(action))
        
        predictions_layout.addWidget(self.predictions_table)
        layout.addWidget(predictions_group)
        
        # Controls
        controls_group = QGroupBox("Inference Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        self.update_predictions_btn = QPushButton("🔄 Update Predictions")
        self.export_predictions_btn = QPushButton("📊 Export Report")
        self.configure_thresholds_btn = QPushButton("⚙️ Configure Thresholds")
        
        controls_layout.addWidget(self.update_predictions_btn)
        controls_layout.addWidget(self.export_predictions_btn)
        controls_layout.addWidget(self.configure_thresholds_btn)
        
        layout.addWidget(controls_group)
        
        parent_tabs.addTab(tab, "🔍 Orbital Inference")
    
    def create_rpa_bridge_tab(self, parent_tabs):
        """Create RPA communication bridge tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Mission deployment
        mission_group = QGroupBox("RPA Mission Deployment")
        mission_layout = QGridLayout(mission_group)
        
        mission_layout.addWidget(QLabel("Mission Type:"), 0, 0)
        self.mission_type_combo = QComboBox()
        self.mission_type_combo.addItems([
            "Search and Rescue",
            "Environmental Survey",
            "Supply Delivery",
            "Communication Relay"
        ])
        mission_layout.addWidget(self.mission_type_combo, 0, 1)
        
        mission_layout.addWidget(QLabel("Area of Interest:"), 1, 0)
        self.area_input = QLineEdit("Emergency Zone Alpha")
        mission_layout.addWidget(self.area_input, 1, 1)
        
        mission_layout.addWidget(QLabel("Drone Count:"), 2, 0)
        self.drone_count_spin = QSpinBox()
        self.drone_count_spin.setRange(1, 50)
        self.drone_count_spin.setValue(3)
        mission_layout.addWidget(self.drone_count_spin, 2, 1)
        
        self.deploy_mission_btn = QPushButton("🚀 Deploy Mission")
        mission_layout.addWidget(self.deploy_mission_btn, 3, 0, 1, 2)
        
        layout.addWidget(mission_group)
        
        # Active missions
        active_group = QGroupBox("Active RPA Missions")
        active_layout = QVBoxLayout(active_group)
        
        self.active_missions_list = QListWidget()
        self.active_missions_list.addItem("🔍 Search Mission: Sector 7 - 3 drones active")
        self.active_missions_list.addItem("📦 Supply Drop: Base Camp Delta - 1 drone en route")
        self.active_missions_list.addItem("📡 Comm Relay: Mountain Ridge - 2 drones deployed")
        active_layout.addWidget(self.active_missions_list)
        
        layout.addWidget(active_group)
        
        parent_tabs.addTab(tab, "🚁 RPA Bridge")
    
    def create_ethics_engine_tab(self, parent_tabs):
        """Create ethics engine tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Scenario input
        scenario_group = QGroupBox("Ethical Decision Scenario")
        scenario_layout = QVBoxLayout(scenario_group)
        
        self.scenario_input = QTextEdit()
        self.scenario_input.setPlaceholderText(
            "Describe the ethical dilemma or critical decision scenario..."
        )
        scenario_layout.addWidget(self.scenario_input)
        
        # Framework selection
        framework_layout = QHBoxLayout()
        framework_layout.addWidget(QLabel("Ethical Frameworks:"))
        
        self.utilitarian_cb = QCheckBox("Utilitarian")
        self.utilitarian_cb.setChecked(True)
        framework_layout.addWidget(self.utilitarian_cb)
        
        self.deontological_cb = QCheckBox("Deontological")
        self.deontological_cb.setChecked(True)
        framework_layout.addWidget(self.deontological_cb)
        
        self.virtue_ethics_cb = QCheckBox("Virtue Ethics")
        framework_layout.addWidget(self.virtue_ethics_cb)
        
        self.care_ethics_cb = QCheckBox("Care Ethics")
        framework_layout.addWidget(self.care_ethics_cb)
        
        scenario_layout.addLayout(framework_layout)
        
        self.analyze_ethics_btn = QPushButton("⚖️ Analyze Ethics")
        scenario_layout.addWidget(self.analyze_ethics_btn)
        
        layout.addWidget(scenario_group)
        
        # Ethics analysis results
        results_group = QGroupBox("Ethical Analysis Results")
        results_layout = QVBoxLayout(results_group)
        
        self.ethics_results = QTextBrowser()
        self.ethics_results.setHtml("""
        <h3>Sample Ethical Analysis</h3>
        <p><strong>Scenario:</strong> Resource allocation during emergency</p>
        <h4>Utilitarian Analysis (Score: 8.7/10)</h4>
        <p>Maximize overall well-being by prioritizing actions that save the most lives.</p>
        <h4>Deontological Analysis (Score: 7.2/10)</h4>
        <p>Follow duty-based ethical rules regardless of consequences.</p>
        <h4>Recommendation:</h4>
        <p>Based on multi-framework analysis, prioritize immediate life support systems
        while maintaining communication with affected personnel.</p>
        """)
        results_layout.addWidget(self.ethics_results)
        
        layout.addWidget(results_group)
        
        parent_tabs.addTab(tab, "⚖️ Ethics Engine")
    
    def create_survival_map_tab(self, parent_tabs):
        """Create survival map generator tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Map generation controls
        controls_group = QGroupBox("Survival Map Generation")
        controls_layout = QGridLayout(controls_group)
        
        controls_layout.addWidget(QLabel("Area of Interest:"), 0, 0)
        self.map_area_input = QLineEdit("Coordinate: 34.0522°N, 118.2437°W")
        controls_layout.addWidget(self.map_area_input, 0, 1)
        
        controls_layout.addWidget(QLabel("Hazard Types:"), 1, 0)
        hazard_layout = QHBoxLayout()
        
        self.fire_hazard_cb = QCheckBox("Fire")
        self.fire_hazard_cb.setChecked(True)
        hazard_layout.addWidget(self.fire_hazard_cb)
        
        self.flood_hazard_cb = QCheckBox("Flood")
        hazard_layout.addWidget(self.flood_hazard_cb)
        
        self.radiation_hazard_cb = QCheckBox("Radiation")
        hazard_layout.addWidget(self.radiation_hazard_cb)
        
        self.toxic_hazard_cb = QCheckBox("Toxic Gas")
        hazard_layout.addWidget(self.toxic_hazard_cb)
        
        controls_layout.addLayout(hazard_layout, 1, 1)
        
        self.generate_map_btn = QPushButton("🗺️ Generate Survival Map")
        controls_layout.addWidget(self.generate_map_btn, 2, 0, 1, 2)
        
        layout.addWidget(controls_group)
        
        # Map display
        map_group = QGroupBox("Hazard Map and Safe Routes")
        map_layout = QVBoxLayout(map_group)
        
        self.survival_map_view = SurvivalMapWidget()
        map_layout.addWidget(self.survival_map_view)
        
        layout.addWidget(map_group)
        
        parent_tabs.addTab(tab, "🗺️ Survival Maps")
    
    def create_resilience_monitor_tab(self, parent_tabs):
        """Create resilience monitor tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Network health overview
        health_group = QGroupBox("Network Health Status")
        health_layout = QGridLayout(health_group)
        
        self.network_health_score = QProgressBar()
        self.network_health_score.setValue(94)
        self.network_health_score.setFormat("Network Health: 94%")
        health_layout.addWidget(QLabel("Overall Health:"), 0, 0)
        health_layout.addWidget(self.network_health_score, 0, 1)
        
        self.node_count_label = QLabel("Active Nodes: 47/50")
        health_layout.addWidget(self.node_count_label, 1, 0)
        
        self.uptime_label = QLabel("System Uptime: 99.97%")
        health_layout.addWidget(self.uptime_label, 1, 1)
        
        layout.addWidget(health_group)
        
        # Self-healing operations
        healing_group = QGroupBox("Self-Healing Operations")
        healing_layout = QVBoxLayout(healing_group)
        
        self.healing_log = QTextBrowser()
        self.healing_log.setHtml("""
        <h4>Recent Self-Healing Activities</h4>
        <p><span style="color: green;">[14:23]</span> Node failure detected: SAT-042</p>
        <p><span style="color: blue;">[14:24]</span> Automatic rerouting initiated</p>
        <p><span style="color: green;">[14:25]</span> Network topology optimized</p>
        <p><span style="color: blue;">[14:26]</span> Backup systems activated</p>
        <p><span style="color: green;">[14:27]</span> Service restored - 0 data loss</p>
        """)
        healing_layout.addWidget(self.healing_log)
        
        layout.addWidget(healing_group)
        
        parent_tabs.addTab(tab, "🛡️ Resilience Monitor")
    
    def create_telemetry_monitoring_tab(self):
        """Create telemetry monitoring tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Real-time telemetry display
        telemetry_group = QGroupBox("Real-time Telemetry Streams")
        telemetry_layout = QVBoxLayout(telemetry_group)
        
        # Telemetry selection
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Spacecraft:"))
        
        self.telemetry_spacecraft_combo = QComboBox()
        self.telemetry_spacecraft_combo.addItems([
            "ISS", "Luna Gateway", "Crew Dragon", "Starship"
        ])
        selection_layout.addWidget(self.telemetry_spacecraft_combo)
        
        selection_layout.addWidget(QLabel("Parameters:"))
        self.telemetry_params_combo = QComboBox()
        self.telemetry_params_combo.addItems([
            "Power Systems", "Thermal Management", "Attitude Control", "Life Support"
        ])
        selection_layout.addWidget(self.telemetry_params_combo)
        
        self.refresh_telemetry_btn = QPushButton("🔄 Refresh")
        selection_layout.addWidget(self.refresh_telemetry_btn)
        
        telemetry_layout.addLayout(selection_layout)
        
        # Telemetry charts
        self.telemetry_widget = TelemetryWidget()
        telemetry_layout.addWidget(self.telemetry_widget)
        
        layout.addWidget(telemetry_group)
        
        self.tab_widget.addTab(tab, "📊 Telemetry")
    
    def create_emergency_response_tab(self):
        """Create emergency response tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Emergency status
        emergency_group = QGroupBox("Emergency Control Center")
        emergency_layout = QVBoxLayout(emergency_group)
        
        # Emergency alert
        alert_frame = QFrame()
        alert_frame.setStyleSheet("background-color: #ff4444; color: white; padding: 10px; border-radius: 5px;")
        alert_layout = QHBoxLayout(alert_frame)
        
        alert_layout.addWidget(QLabel("🚨 EMERGENCY STATUS: NO ACTIVE EMERGENCIES"))
        
        self.emergency_test_btn = QPushButton("🧪 Test Emergency")
        alert_layout.addWidget(self.emergency_test_btn)
        
        emergency_layout.addWidget(alert_frame)
        
        # Emergency protocols
        protocols_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - emergency types
        types_group = QGroupBox("Emergency Protocols")
        types_layout = QVBoxLayout(types_group)
        
        self.emergency_types_list = QListWidget()
        self.emergency_types_list.addItems([
            "🫁 Life Support Emergency",
            "⚡ Power System Failure",
            "📡 Communication Loss",
            "🛰️ Orbital Emergency",
            "🔥 Fire Emergency",
            "💨 Atmospheric Breach",
            "🩺 Medical Emergency"
        ])
        types_layout.addWidget(self.emergency_types_list)
        
        protocols_splitter.addWidget(types_group)
        
        # Right side - emergency actions
        actions_group = QGroupBox("Emergency Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        # Quick action buttons
        action_grid = QGridLayout()
        
        self.evac_btn = QPushButton("🚀 Emergency Evacuation")
        self.evac_btn.setStyleSheet("background-color: #ff6600; color: white; font-weight: bold;")
        action_grid.addWidget(self.evac_btn, 0, 0)
        
        self.override_btn = QPushButton("🔧 System Override")
        action_grid.addWidget(self.override_btn, 0, 1)
        
        self.ground_contact_emergency_btn = QPushButton("📞 Emergency Contact")
        action_grid.addWidget(self.ground_contact_emergency_btn, 1, 0)
        
        self.medical_protocol_btn = QPushButton("🩺 Medical Protocol")
        action_grid.addWidget(self.medical_protocol_btn, 1, 1)
        
        actions_layout.addLayout(action_grid)
        
        # Emergency log
        log_group = QGroupBox("Emergency Response Log")
        log_layout = QVBoxLayout(log_group)
        
        self.emergency_log = QTextBrowser()
        self.emergency_log.setHtml("""
        <h4>Emergency Response History</h4>
        <p><span style="color: gray;">[2025-07-29 14:23]</span> 
        Emergency drill completed successfully - All personnel accounted for</p>
        <p><span style="color: gray;">[2025-07-28 09:15]</span> 
        Minor thermal anomaly resolved - No crew action required</p>
        <p><span style="color: gray;">[2025-07-27 16:45]</span> 
        Communication blackout test - Backup systems activated</p>
        """)
        log_layout.addWidget(self.emergency_log)
        
        actions_layout.addWidget(log_group)
        
        protocols_splitter.addWidget(actions_group)
        emergency_layout.addWidget(protocols_splitter)
        
        layout.addWidget(emergency_group)
        
        self.tab_widget.addTab(tab, "🚨 Emergency")
    
    def create_system_diagnostics_tab(self):
        """Create system diagnostics tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # System overview
        overview_group = QGroupBox("System Diagnostics Overview")
        overview_layout = QGridLayout(overview_group)
        
        # Performance metrics
        self.cpu_usage = QProgressBar()
        self.cpu_usage.setValue(23)
        self.cpu_usage.setFormat("CPU: 23%")
        overview_layout.addWidget(QLabel("CPU Usage:"), 0, 0)
        overview_layout.addWidget(self.cpu_usage, 0, 1)
        
        self.memory_usage = QProgressBar()
        self.memory_usage.setValue(67)
        self.memory_usage.setFormat("Memory: 67%")
        overview_layout.addWidget(QLabel("Memory Usage:"), 1, 0)
        overview_layout.addWidget(self.memory_usage, 1, 1)
        
        self.network_usage = QProgressBar()
        self.network_usage.setValue(45)
        self.network_usage.setFormat("Network: 45%")
        overview_layout.addWidget(QLabel("Network Usage:"), 2, 0)
        overview_layout.addWidget(self.network_usage, 2, 1)
        
        layout.addWidget(overview_group)
        
        # Component status
        components_group = QGroupBox("Component Status")
        components_layout = QVBoxLayout(components_group)
        
        self.components_table = QTableWidget(8, 3)
        self.components_table.setHorizontalHeaderLabels(["Component", "Status", "Last Check"])
        
        components = [
            ("Mission Control Core", "🟢 Operational", "30 sec ago"),
            ("Satellite Manager", "🟢 Operational", "30 sec ago"),
            ("CEHSN System", "🟢 Operational", "1 min ago"),
            ("Communication Hub", "🟢 Operational", "45 sec ago"),
            ("Database System", "🟡 Warning", "2 min ago"),
            ("Backup Systems", "🟢 Standby", "5 min ago"),
            ("Security Monitor", "🟢 Active", "15 sec ago"),
            ("User Interface", "🟢 Operational", "Now")
        ]
        
        for i, (component, status, check) in enumerate(components):
            self.components_table.setItem(i, 0, QTableWidgetItem(component))
            self.components_table.setItem(i, 1, QTableWidgetItem(status))
            self.components_table.setItem(i, 2, QTableWidgetItem(check))
        
        components_layout.addWidget(self.components_table)
        layout.addWidget(components_group)
        
        self.tab_widget.addTab(tab, "🔧 Diagnostics")
    
    def init_menus(self):
        """Initialize menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        export_action = QAction('Export Report', self)
        export_action.triggered.connect(self.export_report)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        fullscreen_action = QAction('Fullscreen', self)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        settings_action = QAction('Settings', self)
        settings_action.triggered.connect(self.open_settings)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About IoST', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def init_toolbar(self):
        """Initialize toolbar"""
        toolbar = self.addToolBar('Main')
        
        # Emergency button
        emergency_action = QAction('🚨 Emergency', self)
        emergency_action.triggered.connect(self.trigger_emergency)
        toolbar.addAction(emergency_action)
        
        toolbar.addSeparator()
        
        # Refresh button
        refresh_action = QAction('🔄 Refresh', self)
        refresh_action.triggered.connect(self.refresh_all_data)
        toolbar.addAction(refresh_action)
        
        # Screenshot button
        screenshot_action = QAction('📸 Screenshot', self)
        screenshot_action.triggered.connect(self.take_screenshot)
        toolbar.addAction(screenshot_action)
    
    def init_status_bar(self):
        """Initialize status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("IoST System Ready - All Systems Nominal")
        
        # Add status indicators
        self.connection_status = QLabel("🟢 Connected")
        self.status_bar.addPermanentWidget(self.connection_status)
        
        self.time_label = QLabel()
        self.status_bar.addPermanentWidget(self.time_label)
    
    def init_timers(self):
        """Initialize update timers"""
        # Main update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_displays)
        self.update_timer.start(1000)  # Update every second
        
        # Time display timer
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
    
    def apply_space_theme(self):
        """Apply space-themed styling"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            
            QTabWidget::pane {
                border: 2px solid #3a3a5c;
                background-color: #16213e;
            }
            
            QTabBar::tab {
                background-color: #0f3460;
                color: #ffffff;
                padding: 8px 16px;
                margin: 2px;
                border-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #e94560;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3a3a5c;
                border-radius: 8px;
                margin: 5px;
                padding-top: 10px;
                background-color: #16213e;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }
            
            QPushButton {
                background-color: #0f3460;
                color: #ffffff;
                border: 2px solid #3a3a5c;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #e94560;
            }
            
            QPushButton:pressed {
                background-color: #c73650;
            }
            
            QProgressBar {
                border: 2px solid #3a3a5c;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }
            
            QProgressBar::chunk {
                background-color: #00ff88;
                border-radius: 3px;
            }
            
            QTableWidget {
                background-color: #16213e;
                color: #ffffff;
                gridline-color: #3a3a5c;
                border: 1px solid #3a3a5c;
            }
            
            QHeaderView::section {
                background-color: #0f3460;
                color: #ffffff;
                padding: 6px;
                border: 1px solid #3a3a5c;
                font-weight: bold;
            }
            
            QListWidget {
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #3a3a5c;
            }
            
            QTextEdit, QTextBrowser {
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #3a3a5c;
            }
            
            QComboBox {
                background-color: #0f3460;
                color: #ffffff;
                border: 1px solid #3a3a5c;
                padding: 4px;
            }
            
            QLineEdit {
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #3a3a5c;
                padding: 4px;
            }
            
            QSpinBox, QDoubleSpinBox {
                background-color: #16213e;
                color: #ffffff;
                border: 1px solid #3a3a5c;
            }
        """)
    
    def update_displays(self):
        """Update all display elements"""
        # This would update real-time data in a full implementation
        pass
    
    def update_time(self):
        """Update time display"""
        current_time = QDateTime.currentDateTime()
        self.time_label.setText(current_time.toString("yyyy-MM-dd hh:mm:ss UTC"))
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def trigger_emergency(self):
        """Trigger emergency protocol"""
        reply = QMessageBox.question(
            self, 'Emergency Protocol',
            'Are you sure you want to trigger emergency protocols?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.status_bar.showMessage("🚨 EMERGENCY PROTOCOL ACTIVATED", 5000)
    
    def refresh_all_data(self):
        """Refresh all data displays"""
        self.status_bar.showMessage("Refreshing all data...", 2000)
    
    def take_screenshot(self):
        """Take screenshot of current view"""
        self.status_bar.showMessage("Screenshot saved", 2000)
    
    def export_report(self):
        """Export system report"""
        self.status_bar.showMessage("Report exported successfully", 2000)
    
    def open_settings(self):
        """Open settings dialog"""
        self.status_bar.showMessage("Settings opened", 1000)
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, 'About IoST',
            'Internet of Space Things (IoST)\n'
            'Advanced Space Communication and Survival Network\n\n'
            'Version 1.0\n'
            'Built with PyQt6'
        )


class SpacecraftMapWidget(QWidget):
    """Widget for displaying real-time spacecraft positions"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 400)
        self.spacecraft_positions = [
            {"name": "ISS", "x": 150, "y": 100, "status": "operational"},
            {"name": "Luna Gateway", "x": 400, "y": 200, "status": "operational"},
            {"name": "Crew Dragon", "x": 200, "y": 150, "status": "operational"},
            {"name": "CubeSat-1", "x": 300, "y": 80, "status": "operational"},
            {"name": "CubeSat-2", "x": 500, "y": 120, "status": "warning"}
        ]
    
    def paintEvent(self, event):
        """Paint the spacecraft map"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw space background
        painter.fillRect(self.rect(), QColor(10, 10, 30))
        
        # Draw orbital paths
        painter.setPen(QPen(QColor(100, 100, 150), 2))
        for i in range(3):
            radius = 100 + i * 80
            painter.drawEllipse(
                self.width() // 2 - radius,
                self.height() // 2 - radius,
                radius * 2,
                radius * 2
            )
        
        # Draw Earth
        painter.setBrush(QBrush(QColor(100, 150, 255)))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        earth_radius = 50
        painter.drawEllipse(
            self.width() // 2 - earth_radius,
            self.height() // 2 - earth_radius,
            earth_radius * 2,
            earth_radius * 2
        )
        
        # Draw spacecraft
        for spacecraft in self.spacecraft_positions:
            color = QColor(0, 255, 0) if spacecraft["status"] == "operational" else QColor(255, 255, 0)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            
            x, y = spacecraft["x"], spacecraft["y"]
            painter.drawEllipse(x - 5, y - 5, 10, 10)
            
            # Draw spacecraft name
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(x + 10, y + 5, spacecraft["name"])


class SatelliteStatusWidget(QWidget):
    """Widget for displaying detailed satellite status"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize the satellite status display"""
        layout = QVBoxLayout(self)
        
        # Satellite info
        info_group = QGroupBox("Satellite Information")
        info_layout = QGridLayout(info_group)
        
        info_layout.addWidget(QLabel("ID:"), 0, 0)
        info_layout.addWidget(QLabel("ISS"), 0, 1)
        
        info_layout.addWidget(QLabel("Status:"), 1, 0)
        status_label = QLabel("🟢 Operational")
        status_label.setStyleSheet("color: green; font-weight: bold;")
        info_layout.addWidget(status_label, 1, 1)
        
        info_layout.addWidget(QLabel("Position:"), 2, 0)
        info_layout.addWidget(QLabel("51.6461°N, 0.8061°W"), 2, 1)
        
        info_layout.addWidget(QLabel("Altitude:"), 3, 0)
        info_layout.addWidget(QLabel("408.2 km"), 3, 1)
        
        info_layout.addWidget(QLabel("Velocity:"), 4, 0)
        info_layout.addWidget(QLabel("7.66 km/s"), 4, 1)
        
        layout.addWidget(info_group)
        
        # System status
        systems_group = QGroupBox("System Status")
        systems_layout = QGridLayout(systems_group)
        
        # Power system
        systems_layout.addWidget(QLabel("Power:"), 0, 0)
        power_bar = QProgressBar()
        power_bar.setValue(95)
        power_bar.setFormat("95.5%")
        systems_layout.addWidget(power_bar, 0, 1)
        
        # Thermal system
        systems_layout.addWidget(QLabel("Thermal:"), 1, 0)
        thermal_label = QLabel("🟢 22.3°C")
        thermal_label.setStyleSheet("color: green;")
        systems_layout.addWidget(thermal_label, 1, 1)
        
        # Attitude system
        systems_layout.addWidget(QLabel("Attitude:"), 2, 0)
        attitude_label = QLabel("🟢 Stable")
        attitude_label.setStyleSheet("color: green;")
        systems_layout.addWidget(attitude_label, 2, 1)
        
        # Communications
        systems_layout.addWidget(QLabel("Comms:"), 3, 0)
        comms_label = QLabel("🟢 Strong")
        comms_label.setStyleSheet("color: green;")
        systems_layout.addWidget(comms_label, 3, 1)
        
        layout.addWidget(systems_group)


class SurvivalMapWidget(QWidget):
    """Widget for displaying survival maps with hazards and safe routes"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(500, 400)
    
    def paintEvent(self, event):
        """Paint the survival map"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw map background
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        
        # Draw hazard zones (red areas)
        painter.setBrush(QBrush(QColor(255, 100, 100, 128)))
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.drawEllipse(50, 50, 100, 100)
        painter.drawEllipse(300, 200, 80, 80)
        
        # Draw safe zones (green areas)
        painter.setBrush(QBrush(QColor(100, 255, 100, 128)))
        painter.setPen(QPen(QColor(0, 255, 0), 2))
        painter.drawEllipse(400, 50, 120, 120)
        painter.drawEllipse(100, 300, 100, 100)
        
        # Draw safe route (blue line)
        painter.setPen(QPen(QColor(0, 100, 255), 4))
        painter.drawLine(20, 20, 450, 100)
        painter.drawLine(450, 100, 150, 350)
        
        # Draw labels
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.drawText(70, 105, "Fire Zone")
        painter.drawText(320, 245, "Flood Risk")
        painter.drawText(430, 115, "Safe Zone")
        painter.drawText(125, 355, "Shelter")


class TelemetryWidget(QWidget):
    """Widget for displaying telemetry charts and data"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize telemetry display"""
        layout = QVBoxLayout(self)
        
        # Telemetry charts area
        charts_group = QGroupBox("Live Telemetry Data")
        charts_layout = QGridLayout(charts_group)
        
        # Power system chart
        power_chart = TelemetryChart("Power System", "Watts", 450)
        charts_layout.addWidget(power_chart, 0, 0)
        
        # Temperature chart
        temp_chart = TelemetryChart("Temperature", "°C", 22)
        charts_layout.addWidget(temp_chart, 0, 1)
        
        # Attitude chart
        attitude_chart = TelemetryChart("Attitude", "°", 0)
        charts_layout.addWidget(attitude_chart, 1, 0)
        
        # Communication chart
        comm_chart = TelemetryChart("Signal Strength", "dBm", -65)
        charts_layout.addWidget(comm_chart, 1, 1)
        
        layout.addWidget(charts_group)


class TelemetryChart(QWidget):
    """Individual telemetry chart widget"""
    
    def __init__(self, title, unit, value):
        super().__init__()
        self.title = title
        self.unit = unit
        self.value = value
        self.setMinimumSize(200, 150)
    
    def paintEvent(self, event):
        """Paint the telemetry chart"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(22, 33, 62))
        
        # Draw title
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(10, 20, self.title)
        
        # Draw value
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        value_text = f"{self.value} {self.unit}"
        painter.drawText(10, 50, value_text)
        
        # Draw simple trend line
        painter.setPen(QPen(QColor(0, 255, 136), 2))
        points = [
            QPoint(10, 100),
            QPoint(50, 95),
            QPoint(90, 90),
            QPoint(130, 85),
            QPoint(170, 80)
        ]
        
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Internet of Space Things")
    app.setApplicationVersion("1.0")
    
    # Set application icon (if available)
    # app.setWindowIcon(QIcon("icon.png"))
    
    # Create and show main window
    window = IoSTMainWindow()
    window.show()
    
    # Start application event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
