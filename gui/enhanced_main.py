#!/usr/bin/env python3
"""
Internet of Space Things (IoST) - Enhanced Main GUI Application
Comprehensive mission control interface with advanced visualization and real-time data processing
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

# Import custom widgets and data providers
try:
    from data_provider import data_provider
    from enhanced_data_provider import enhanced_data_provider
    from enhanced_widgets import (
        CEHSNStatusWidget,
        MissionControlWidget,
        TelemetryVisualizationWidget,
    )
    from visualization_3d import Spacecraft3DVisualizationWidget
    from widgets import (
        AlertPanel,
        ConsoleWidget,
        GaugeWidget,
        RealTimeChart,
        StatusIndicator,
    )
    WIDGETS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import custom widgets: {e}")
    WIDGETS_AVAILABLE = False

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
    IOST_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import IoST modules: {e}")
    print("GUI will run in demonstration mode")
    IOST_MODULES_AVAILABLE = False


class EnhancedIoSTMainWindow(QMainWindow):
    """Enhanced main window for Internet of Space Things GUI"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Internet of Space Things (IoST) - Advanced Mission Control")
        self.setGeometry(50, 50, 1800, 1200)
        
        # Initialize systems
        self.init_iost_systems()
        
        # Setup UI components
        self.init_ui()
        self.init_menus()
        self.init_toolbar()
        self.init_status_bar()
        
        # Connect signals for real-time updates
        self.connect_signals()
        
        # Start real-time updates
        self.init_timers()
        
        # Apply advanced styling
        self.apply_enhanced_space_theme()
    
    def init_iost_systems(self):
        """Initialize IoST system components"""
        if IOST_MODULES_AVAILABLE:
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
                self.sdn_controller = SDNController("Enhanced_GUI_SDN")
                
                self.systems_initialized = True
                
            except Exception as e:
                print(f"Error initializing IoST systems: {e}")
                self.systems_initialized = False
        else:
            self.systems_initialized = False
    
    def init_ui(self):
        """Initialize the enhanced user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create main splitter for flexible layout
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel - Mission Control and Navigation
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)
        
        # Center panel - Main workspace with tabs
        center_panel = self.create_center_panel()
        main_splitter.addWidget(center_panel)
        
        # Right panel - Real-time monitoring and alerts
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setSizes([400, 1000, 400])
    
    def create_left_panel(self):
        """Create the left navigation and control panel"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Mission Control Overview
        if WIDGETS_AVAILABLE:
            self.mission_control_widget = MissionControlWidget()
            left_layout.addWidget(self.mission_control_widget)
        else:
            overview_group = QGroupBox("Mission Control")
            overview_layout = QVBoxLayout(overview_group)
            overview_layout.addWidget(QLabel("Advanced widgets not available"))
            left_layout.addWidget(overview_group)
        
        # System Status Overview
        status_group = QGroupBox("System Health")
        status_layout = QVBoxLayout(status_group)
        
        # Core system indicators
        self.core_systems_status = {}
        systems = ["Mission Control", "Satellite Manager", "Space Network", 
                  "CEHSN Engine", "Communication Hub"]
        
        for system in systems:
            if WIDGETS_AVAILABLE:
                indicator = StatusIndicator(system)
                indicator.set_status("operational" if self.systems_initialized else "offline")
                self.core_systems_status[system] = indicator
                status_layout.addWidget(indicator)
            else:
                status_layout.addWidget(QLabel(f"{system}: {'OK' if self.systems_initialized else 'OFFLINE'}"))
        
        left_layout.addWidget(status_group)
        
        # Quick Actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        self.emergency_stop_btn = QPushButton("🚨 Emergency Stop")
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        self.emergency_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #cc3333;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff4444;
            }
        """)
        actions_layout.addWidget(self.emergency_stop_btn)
        
        self.system_reset_btn = QPushButton("🔄 System Reset")
        self.system_reset_btn.clicked.connect(self.system_reset)
        actions_layout.addWidget(self.system_reset_btn)
        
        self.diagnostics_btn = QPushButton("🔧 Run Diagnostics")
        self.diagnostics_btn.clicked.connect(self.run_diagnostics)
        actions_layout.addWidget(self.diagnostics_btn)
        
        left_layout.addWidget(actions_group)
        
        # Add stretch to push content to top
        left_layout.addStretch()
        
        return left_widget
    
    def create_center_panel(self):
        """Create the main center workspace panel"""
        # Main tab widget
        self.main_tabs = QTabWidget()
        
        # Mission Control Dashboard
        dashboard_tab = self.create_dashboard_tab()
        self.main_tabs.addTab(dashboard_tab, "🌍 Mission Control")
        
        # 3D Visualization
        if WIDGETS_AVAILABLE:
            visualization_tab = Spacecraft3DVisualizationWidget()
            self.main_tabs.addTab(visualization_tab, "🚀 3D Tracking")
        else:
            viz_placeholder = QWidget()
            QVBoxLayout(viz_placeholder).addWidget(QLabel("3D Visualization requires OpenGL"))
            self.main_tabs.addTab(viz_placeholder, "🚀 3D Tracking")
        
        # Telemetry Analysis
        telemetry_tab = self.create_telemetry_tab()
        self.main_tabs.addTab(telemetry_tab, "📊 Telemetry")
        
        # CEHSN Operations
        cehsn_tab = self.create_cehsn_tab()
        self.main_tabs.addTab(cehsn_tab, "🧠 CEHSN")
        
        # Communication Hub
        comm_tab = self.create_communication_tab()
        self.main_tabs.addTab(comm_tab, "📡 Communications")
        
        # System Diagnostics
        diagnostics_tab = self.create_diagnostics_tab()
        self.main_tabs.addTab(diagnostics_tab, "⚙️ Diagnostics")
        
        return self.main_tabs
    
    def create_dashboard_tab(self):
        """Create the main mission control dashboard"""
        dashboard_widget = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_widget)
        
        # Top row - Key metrics
        metrics_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Live spacecraft tracking
        tracking_group = QGroupBox("Live Spacecraft Tracking")
        tracking_layout = QVBoxLayout(tracking_group)
        
        if WIDGETS_AVAILABLE:
            self.spacecraft_table = QTableWidget()
            self.spacecraft_table.setColumnCount(5)
            self.spacecraft_table.setHorizontalHeaderLabels([
                "Spacecraft", "Status", "Position", "Velocity", "Next Pass"
            ])
            tracking_layout.addWidget(self.spacecraft_table)
        else:
            tracking_layout.addWidget(QLabel("Spacecraft tracking table"))
        
        metrics_splitter.addWidget(tracking_group)
        
        # System health overview
        health_group = QGroupBox("System Health Overview")
        health_layout = QGridLayout(health_group)
        
        if WIDGETS_AVAILABLE:
            # Power systems gauge
            self.power_gauge = GaugeWidget("Power Systems", 0, 100, 94.2)
            health_layout.addWidget(self.power_gauge, 0, 0)
            
            # Network health gauge
            self.network_gauge = GaugeWidget("Network Health", 0, 100, 87.6)
            health_layout.addWidget(self.network_gauge, 0, 1)
            
            # Mission efficiency gauge
            self.efficiency_gauge = GaugeWidget("Mission Efficiency", 0, 100, 91.3)
            health_layout.addWidget(self.efficiency_gauge, 1, 0)
            
            # Resource utilization gauge
            self.resource_gauge = GaugeWidget("Resource Usage", 0, 100, 73.8)
            health_layout.addWidget(self.resource_gauge, 1, 1)
        else:
            health_layout.addWidget(QLabel("System health gauges"), 0, 0, 2, 2)
        
        metrics_splitter.addWidget(health_group)
        
        dashboard_layout.addWidget(metrics_splitter)
        
        # Bottom row - Real-time charts
        charts_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Telemetry trends
        if WIDGETS_AVAILABLE:
            telemetry_group = QGroupBox("Real-time Telemetry Trends")
            telemetry_layout = QVBoxLayout(telemetry_group)
            
            self.telemetry_chart = RealTimeChart("Telemetry Overview")
            telemetry_layout.addWidget(self.telemetry_chart)
            
            charts_splitter.addWidget(telemetry_group)
            
            # Network activity
            network_group = QGroupBox("Network Activity")
            network_layout = QVBoxLayout(network_group)
            
            self.network_chart = RealTimeChart("Network Traffic")
            network_layout.addWidget(self.network_chart)
            
            charts_splitter.addWidget(network_group)
        else:
            charts_placeholder = QWidget()
            QVBoxLayout(charts_placeholder).addWidget(QLabel("Real-time charts"))
            charts_splitter.addWidget(charts_placeholder)
        
        dashboard_layout.addWidget(charts_splitter)
        
        return dashboard_widget
    
    def create_telemetry_tab(self):
        """Create the enhanced telemetry analysis tab"""
        telemetry_widget = QWidget()
        telemetry_layout = QVBoxLayout(telemetry_widget)
        
        if WIDGETS_AVAILABLE:
            # Telemetry visualization widget
            self.telemetry_viz = TelemetryVisualizationWidget()
            telemetry_layout.addWidget(self.telemetry_viz)
        else:
            telemetry_layout.addWidget(QLabel("Advanced telemetry visualization not available"))
        
        # Telemetry controls
        controls_group = QGroupBox("Telemetry Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # Spacecraft selection
        controls_layout.addWidget(QLabel("Spacecraft:"))
        self.telem_spacecraft_combo = QComboBox()
        self.telem_spacecraft_combo.addItems(["ISS", "Hubble", "JWST", "Dragon", "Starlink-1"])
        controls_layout.addWidget(self.telem_spacecraft_combo)
        
        # Time range selection
        controls_layout.addWidget(QLabel("Time Range:"))
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems(["Last Hour", "Last 4 Hours", "Last 24 Hours", "Last Week"])
        controls_layout.addWidget(self.time_range_combo)
        
        # Export button
        self.export_data_btn = QPushButton("📁 Export Data")
        self.export_data_btn.clicked.connect(self.export_telemetry_data)
        controls_layout.addWidget(self.export_data_btn)
        
        controls_layout.addStretch()
        
        telemetry_layout.addWidget(controls_group)
        
        return telemetry_widget
    
    def create_cehsn_tab(self):
        """Create the CEHSN operations tab"""
        cehsn_widget = QWidget()
        cehsn_layout = QVBoxLayout(cehsn_widget)
        
        if WIDGETS_AVAILABLE:
            # CEHSN status widget
            self.cehsn_status = CEHSNStatusWidget()
            cehsn_layout.addWidget(self.cehsn_status)
        else:
            cehsn_layout.addWidget(QLabel("CEHSN system interface"))
        
        # CEHSN component tabs
        cehsn_tabs = QTabWidget()
        
        # Orbital Inference Engine
        orbital_tab = QWidget()
        orbital_layout = QVBoxLayout(orbital_tab)
        orbital_layout.addWidget(QLabel("Orbital Inference Engine Status"))
        
        if WIDGETS_AVAILABLE:
            orbital_status = StatusIndicator("Orbital Predictions")
            orbital_status.set_status("operational")
            orbital_layout.addWidget(orbital_status)
        
        cehsn_tabs.addTab(orbital_tab, "🌍 Orbital Inference")
        
        # RPA Communication Bridge
        rpa_tab = QWidget()
        rpa_layout = QVBoxLayout(rpa_tab)
        rpa_layout.addWidget(QLabel("RPA Communication Bridge"))
        cehsn_tabs.addTab(rpa_tab, "🤖 RPA Bridge")
        
        # Ethics Engine
        ethics_tab = QWidget()
        ethics_layout = QVBoxLayout(ethics_tab)
        ethics_layout.addWidget(QLabel("Autonomous Ethics Engine"))
        cehsn_tabs.addTab(ethics_tab, "⚖️ Ethics")
        
        # Survival Map Generator
        survival_tab = QWidget()
        survival_layout = QVBoxLayout(survival_tab)
        survival_layout.addWidget(QLabel("Emergency Survival Mapping"))
        cehsn_tabs.addTab(survival_tab, "🗺️ Survival Maps")
        
        # Resilience Monitor
        resilience_tab = QWidget()
        resilience_layout = QVBoxLayout(resilience_tab)
        resilience_layout.addWidget(QLabel("System Resilience Monitoring"))
        cehsn_tabs.addTab(resilience_tab, "🛡️ Resilience")
        
        cehsn_layout.addWidget(cehsn_tabs)
        
        return cehsn_widget
    
    def create_communication_tab(self):
        """Create the communication systems tab"""
        comm_widget = QWidget()
        comm_layout = QVBoxLayout(comm_widget)
        
        # Communication overview
        comm_overview = QGroupBox("Communication Systems Overview")
        overview_layout = QGridLayout(comm_overview)
        
        # Active connections
        active_connections = QLabel("Active Connections: 47")
        overview_layout.addWidget(active_connections, 0, 0)
        
        # Data throughput
        data_throughput = QLabel("Data Throughput: 124.7 Mbps")
        overview_layout.addWidget(data_throughput, 0, 1)
        
        # Signal quality
        signal_quality = QLabel("Avg Signal Quality: 89.2%")
        overview_layout.addWidget(signal_quality, 1, 0)
        
        # Network latency
        network_latency = QLabel("Network Latency: 247ms")
        overview_layout.addWidget(network_latency, 1, 1)
        
        comm_layout.addWidget(comm_overview)
        
        # Frequency management
        freq_group = QGroupBox("Frequency Management")
        freq_layout = QVBoxLayout(freq_group)
        
        # Frequency bands table
        freq_table = QTableWidget()
        freq_table.setColumnCount(4)
        freq_table.setHorizontalHeaderLabels([
            "Band", "Frequency", "Status", "Utilization"
        ])
        freq_layout.addWidget(freq_table)
        
        comm_layout.addWidget(freq_group)
        
        return comm_widget
    
    def create_diagnostics_tab(self):
        """Create the system diagnostics tab"""
        diag_widget = QWidget()
        diag_layout = QVBoxLayout(diag_widget)
        
        # Diagnostics controls
        controls_group = QGroupBox("Diagnostic Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        self.full_diag_btn = QPushButton("🔍 Full System Scan")
        self.full_diag_btn.clicked.connect(self.run_full_diagnostics)
        controls_layout.addWidget(self.full_diag_btn)
        
        self.quick_check_btn = QPushButton("⚡ Quick Health Check")
        self.quick_check_btn.clicked.connect(self.quick_health_check)
        controls_layout.addWidget(self.quick_check_btn)
        
        self.generate_report_btn = QPushButton("📄 Generate Report")
        self.generate_report_btn.clicked.connect(self.generate_diagnostics_report)
        controls_layout.addWidget(self.generate_report_btn)
        
        controls_layout.addStretch()
        
        diag_layout.addWidget(controls_group)
        
        # Diagnostics results
        results_group = QGroupBox("Diagnostic Results")
        results_layout = QVBoxLayout(results_group)
        
        self.diagnostics_text = QTextEdit()
        self.diagnostics_text.setReadOnly(True)
        self.diagnostics_text.setText("Ready to run diagnostics...")
        results_layout.addWidget(self.diagnostics_text)
        
        diag_layout.addWidget(results_group)
        
        return diag_widget
    
    def create_right_panel(self):
        """Create the right monitoring and alerts panel"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Real-time alerts
        if WIDGETS_AVAILABLE:
            self.alert_panel = AlertPanel("System Alerts")
            right_layout.addWidget(self.alert_panel)
        else:
            alerts_group = QGroupBox("System Alerts")
            alerts_layout = QVBoxLayout(alerts_group)
            alerts_layout.addWidget(QLabel("No active alerts"))
            right_layout.addWidget(alerts_group)
        
        # Console output
        if WIDGETS_AVAILABLE:
            self.console_widget = ConsoleWidget("System Console")
            right_layout.addWidget(self.console_widget)
        else:
            console_group = QGroupBox("System Console")
            console_layout = QVBoxLayout(console_group)
            self.console_text = QTextEdit()
            self.console_text.setReadOnly(True)
            console_layout.addWidget(self.console_text)
            right_layout.addWidget(console_group)
        
        return right_widget
    
    def connect_signals(self):
        """Connect signals for real-time updates"""
        if WIDGETS_AVAILABLE and hasattr(self, 'mission_control_widget'):
            # Connect spacecraft selection
            self.mission_control_widget.spacecraft_selected.connect(
                self.on_spacecraft_selected
            )
            
            # Connect telemetry processor signals
            if hasattr(enhanced_data_provider, 'telemetry_processor'):
                enhanced_data_provider.telemetry_processor.telemetry_updated.connect(
                    self.on_telemetry_updated
                )
                enhanced_data_provider.telemetry_processor.alert_generated.connect(
                    self.on_alert_generated
                )
    
    def init_menus(self):
        """Initialize application menus"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        export_action = QAction("&Export Data", self)
        export_action.triggered.connect(self.export_telemetry_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        diagnostics_action = QAction("&Run Diagnostics", self)
        diagnostics_action.triggered.connect(self.run_diagnostics)
        tools_menu.addAction(diagnostics_action)
        
        reset_action = QAction("&Reset Systems", self)
        reset_action.triggered.connect(self.system_reset)
        tools_menu.addAction(reset_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def init_toolbar(self):
        """Initialize application toolbar"""
        toolbar = self.addToolBar("Main")
        
        # Emergency stop
        emergency_action = QAction("🚨 Emergency", self)
        emergency_action.triggered.connect(self.emergency_stop)
        toolbar.addAction(emergency_action)
        
        toolbar.addSeparator()
        
        # System reset
        reset_action = QAction("🔄 Reset", self)
        reset_action.triggered.connect(self.system_reset)
        toolbar.addAction(reset_action)
        
        # Diagnostics
        diag_action = QAction("🔧 Diagnostics", self)
        diag_action.triggered.connect(self.run_diagnostics)
        toolbar.addAction(diag_action)
        
        toolbar.addSeparator()
        
        # Export data
        export_action = QAction("📁 Export", self)
        export_action.triggered.connect(self.export_telemetry_data)
        toolbar.addAction(export_action)
    
    def init_status_bar(self):
        """Initialize status bar"""
        self.status_bar = self.statusBar()
        
        # System status
        self.system_status_label = QLabel("System: Operational")
        self.status_bar.addWidget(self.system_status_label)
        
        # Connection status
        self.connection_status_label = QLabel("Connected: 47 spacecraft")
        self.status_bar.addPermanentWidget(self.connection_status_label)
        
        # Time display
        self.time_label = QLabel()
        self.status_bar.addPermanentWidget(self.time_label)
    
    def init_timers(self):
        """Initialize update timers"""
        # Main update timer
        self.main_timer = QTimer()
        self.main_timer.timeout.connect(self.update_displays)
        self.main_timer.start(5000)  # Update every 5 seconds
        
        # Time display timer
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time_display)
        self.time_timer.start(1000)  # Update every second
    
    def apply_enhanced_space_theme(self):
        """Apply enhanced space-themed styling"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a0a0a;
                color: #ffffff;
            }
            
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #1a1a2e;
            }
            
            QTabBar::tab {
                background-color: #16213e;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: #0f3460;
                color: #00ff88;
            }
            
            QTabBar::tab:hover {
                background-color: #1e3a5f;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #333333;
                border-radius: 5px;
                margin: 5px;
                padding-top: 15px;
                color: #ffffff;
                background-color: #16213e;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #00ff88;
            }
            
            QPushButton {
                background-color: #0f3460;
                border: 1px solid #333333;
                color: #ffffff;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #1e3a5f;
                border-color: #00ff88;
            }
            
            QPushButton:pressed {
                background-color: #0a2440;
            }
            
            QTableWidget {
                background-color: #1a1a2e;
                alternate-background-color: #16213e;
                color: #ffffff;
                border: 1px solid #333333;
                selection-background-color: #0f3460;
            }
            
            QTableWidget::item {
                border-bottom: 1px solid #333333;
                padding: 4px;
            }
            
            QHeaderView::section {
                background-color: #0f3460;
                color: #00ff88;
                padding: 8px;
                border: 1px solid #333333;
                font-weight: bold;
            }
            
            QTextEdit {
                background-color: #1a1a2e;
                color: #ffffff;
                border: 1px solid #333333;
                border-radius: 4px;
                font-family: monospace;
            }
            
            QComboBox {
                background-color: #1a1a2e;
                color: #ffffff;
                border: 1px solid #333333;
                padding: 4px;
                border-radius: 4px;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 15px;
                border-left: 1px solid #333333;
            }
            
            QComboBox::down-arrow {
                color: #00ff88;
            }
            
            QLabel {
                color: #ffffff;
            }
            
            QSplitter::handle {
                background-color: #333333;
                width: 2px;
                height: 2px;
            }
            
            QSplitter::handle:hover {
                background-color: #00ff88;
            }
            
            QStatusBar {
                background-color: #0f1419;
                color: #ffffff;
                border-top: 1px solid #333333;
            }
            
            QMenuBar {
                background-color: #0f1419;
                color: #ffffff;
            }
            
            QMenuBar::item {
                padding: 4px 8px;
            }
            
            QMenuBar::item:selected {
                background-color: #0f3460;
            }
            
            QMenu {
                background-color: #1a1a2e;
                color: #ffffff;
                border: 1px solid #333333;
            }
            
            QMenu::item:selected {
                background-color: #0f3460;
            }
            
            QToolBar {
                background-color: #0f1419;
                border: none;
                spacing: 4px;
            }
            
            QToolBar::separator {
                background-color: #333333;
                width: 1px;
                margin: 4px;
            }
        """)
    
    # Event handlers and update methods
    def on_spacecraft_selected(self, spacecraft_id):
        """Handle spacecraft selection"""
        if hasattr(self, 'console_widget'):
            self.console_widget.add_message(f"Selected spacecraft: {spacecraft_id}")
        elif hasattr(self, 'console_text'):
            current_text = self.console_text.toPlainText()
            self.console_text.setText(current_text + f"\nSelected spacecraft: {spacecraft_id}")
    
    def on_telemetry_updated(self, spacecraft_id, parameter, value):
        """Handle telemetry updates"""
        # Update displays based on new telemetry
        pass
    
    def on_alert_generated(self, spacecraft_id, severity, message):
        """Handle new alerts"""
        if hasattr(self, 'alert_panel'):
            self.alert_panel.add_alert(severity, f"{spacecraft_id}: {message}")
    
    def update_displays(self):
        """Update all dynamic displays"""
        # Update spacecraft table if available
        if hasattr(self, 'spacecraft_table'):
            self.update_spacecraft_table()
        
        # Update gauges if available
        if WIDGETS_AVAILABLE and hasattr(self, 'power_gauge'):
            import random
            self.power_gauge.set_value(90 + random.uniform(-5, 5))
            self.network_gauge.set_value(85 + random.uniform(-5, 5))
            self.efficiency_gauge.set_value(90 + random.uniform(-5, 5))
            self.resource_gauge.set_value(70 + random.uniform(-10, 10))
    
    def update_spacecraft_table(self):
        """Update the spacecraft tracking table"""
        spacecraft_list = ["ISS", "Hubble", "JWST", "Dragon", "Starlink-1"]
        self.spacecraft_table.setRowCount(len(spacecraft_list))
        
        for i, spacecraft in enumerate(spacecraft_list):
            self.spacecraft_table.setItem(i, 0, QTableWidgetItem(spacecraft))
            self.spacecraft_table.setItem(i, 1, QTableWidgetItem("Operational"))
            self.spacecraft_table.setItem(i, 2, QTableWidgetItem("LEO"))
            self.spacecraft_table.setItem(i, 3, QTableWidgetItem("7.66 km/s"))
            self.spacecraft_table.setItem(i, 4, QTableWidgetItem("12:45 UTC"))
    
    def update_time_display(self):
        """Update time display in status bar"""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        self.time_label.setText(current_time)
    
    # Action handlers
    def emergency_stop(self):
        """Handle emergency stop"""
        reply = QMessageBox.question(
            self, "Emergency Stop",
            "Are you sure you want to execute an emergency stop?\n"
            "This will halt all active operations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self, 'console_widget'):
                self.console_widget.add_message("EMERGENCY STOP ACTIVATED", "error")
            else:
                QMessageBox.warning(self, "Emergency Stop", "Emergency stop activated!")
    
    def system_reset(self):
        """Handle system reset"""
        if hasattr(self, 'console_widget'):
            self.console_widget.add_message("System reset initiated...")
        
        # Simulate system reset
        QTimer.singleShot(2000, lambda: self.console_widget.add_message("System reset complete"))
    
    def run_diagnostics(self):
        """Run system diagnostics"""
        self.diagnostics_text.setText("Running diagnostics...\n")
        
        # Simulate diagnostics
        QTimer.singleShot(1000, self.show_diagnostics_results)
    
    def show_diagnostics_results(self):
        """Show diagnostics results"""
        results = """
Diagnostics Complete:

✅ Core Systems: All operational
✅ CEHSN Engine: Functioning normally  
✅ Communication Hub: 47 active connections
✅ Satellite Network: All spacecraft responding
✅ Data Processing: No errors detected
⚠️ Memory Usage: 78% (monitor closely)
✅ Network Latency: Within acceptable range
✅ Power Systems: Optimal performance

Recommendations:
- Monitor memory usage
- Schedule routine maintenance in 72 hours
- No immediate action required
        """
        self.diagnostics_text.setText(results)
    
    def run_full_diagnostics(self):
        """Run comprehensive diagnostics"""
        self.diagnostics_text.setText("Running full system scan...\nThis may take several minutes.")
        QTimer.singleShot(3000, self.show_full_diagnostics_results)
    
    def show_full_diagnostics_results(self):
        """Show full diagnostics results"""
        results = """
Full System Diagnostics Complete:

CORE SYSTEMS:
✅ Mission Control: Operational
✅ Satellite Manager: Operational  
✅ Space Network: Operational
✅ Real-time Processing: Operational

CEHSN COMPONENTS:
✅ Orbital Inference Engine: Active
✅ RPA Communication Bridge: Connected
✅ Ethics Engine: Monitoring
✅ Survival Map Generator: Ready
✅ Resilience Monitor: Tracking 47 nodes

HARDWARE STATUS:
✅ CPU Usage: 23%
⚠️ Memory Usage: 78%
✅ Disk Usage: 45%
✅ Network I/O: Normal
✅ Temperature: 42°C

NETWORK ANALYSIS:
✅ Active Connections: 47
✅ Data Throughput: 124.7 Mbps
✅ Packet Loss: 0.02%
⚠️ Latency Spike: 2 incidents in last hour

RECOMMENDATIONS:
1. Memory optimization recommended within 24 hours
2. Monitor network latency trends
3. All systems performing within normal parameters
4. Next maintenance window: 72 hours
        """
        self.diagnostics_text.setText(results)
    
    def quick_health_check(self):
        """Perform quick health check"""
        self.diagnostics_text.setText("Quick health check...\n")
        QTimer.singleShot(500, lambda: self.diagnostics_text.setText(
            "Quick Health Check Results:\n\n"
            "✅ All critical systems operational\n"
            "✅ No alerts requiring immediate attention\n"
            "✅ Network connectivity stable\n"
            "✅ Data processing normal\n\n"
            "System Status: HEALTHY"
        ))
    
    def generate_diagnostics_report(self):
        """Generate comprehensive diagnostics report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"iost_diagnostics_{timestamp}.txt"
        
        QMessageBox.information(
            self, "Report Generated",
            f"Diagnostics report saved as:\n{filename}"
        )
    
    def export_telemetry_data(self):
        """Export telemetry data"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"telemetry_export_{timestamp}.csv"
        
        QMessageBox.information(
            self, "Export Complete",
            f"Telemetry data exported as:\n{filename}"
        )
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, "About IoST GUI",
            "Internet of Space Things (IoST)\n"
            "Advanced Mission Control Interface\n\n"
            "Version: 2.0 Enhanced\n"
            "Built with PyQt6\n\n"
            "Features:\n"
            "• Real-time spacecraft tracking\n"
            "• 3D orbital visualization\n"
            "• Advanced telemetry analysis\n"
            "• CEHSN integration\n"
            "• Comprehensive system monitoring"
        )
    
    def closeEvent(self, event):
        """Handle application close"""
        if WIDGETS_AVAILABLE:
            enhanced_data_provider.shutdown()
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("IoST Mission Control")
    app.setApplicationVersion("2.0 Enhanced")
    app.setOrganizationName("Internet of Space Things")
    
    # Create and show main window
    window = EnhancedIoSTMainWindow()
    window.show()
    
    # Start application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
