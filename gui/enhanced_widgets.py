#!/usr/bin/env python3
"""
Enhanced IoST GUI Components
Advanced widgets and visualization components for the IoST GUI
"""

from data_provider import data_provider
from PyQt6.QtCore import QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class MissionControlWidget(QWidget):
    """Enhanced mission control dashboard widget"""
    
    spacecraft_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.selected_spacecraft = "ISS"
        self.init_ui()
        self.init_timers()
    
    def init_ui(self):
        """Initialize the mission control UI"""
        layout = QVBoxLayout(self)
        
        # System overview
        overview_group = QGroupBox("System Overview")
        overview_layout = QGridLayout(overview_group)
        
        # Create status indicators
        self.total_spacecraft_label = QLabel("Total Spacecraft: 0")
        self.operational_label = QLabel("Operational: 0") 
        self.warning_label = QLabel("Warnings: 0")
        self.alerts_label = QLabel("Alerts: 0")
        
        overview_layout.addWidget(self.total_spacecraft_label, 0, 0)
        overview_layout.addWidget(self.operational_label, 0, 1)
        overview_layout.addWidget(self.warning_label, 1, 0)
        overview_layout.addWidget(self.alerts_label, 1, 1)
        
        layout.addWidget(overview_group)
        
        # Spacecraft table
        spacecraft_group = QGroupBox("Active Spacecraft")
        spacecraft_layout = QVBoxLayout(spacecraft_group)
        
        self.spacecraft_table = QTableWidget()
        self.spacecraft_table.setColumnCount(6)
        self.spacecraft_table.setHorizontalHeaderLabels([
            "Name", "Type", "Status", "Position", "Power", "Last Contact"
        ])
        
        # Make table responsive
        header = self.spacecraft_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.spacecraft_table.cellClicked.connect(self.on_spacecraft_selected)
        spacecraft_layout.addWidget(self.spacecraft_table)
        
        layout.addWidget(spacecraft_group)
        
        # Update display
        self.update_spacecraft_table()
    
    def init_timers(self):
        """Initialize update timers"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_displays)
        self.update_timer.start(5000)  # Update every 5 seconds
    
    def update_displays(self):
        """Update all display elements"""
        self.update_system_overview()
        self.update_spacecraft_table()
    
    def update_system_overview(self):
        """Update system overview statistics"""
        stats = data_provider.get_system_statistics()
        
        self.total_spacecraft_label.setText(
            f"Total Spacecraft: {stats['total_spacecraft']}"
        )
        self.operational_label.setText(
            f"Operational: {stats['operational_spacecraft']}"
        )
        self.warning_label.setText(
            f"Warnings: {stats['warning_spacecraft']}"
        )
        self.alerts_label.setText(
            f"Alerts: {stats['unacknowledged_alerts']}"
        )
    
    def update_spacecraft_table(self):
        """Update spacecraft table data"""
        spacecraft_list = data_provider.get_spacecraft_list()
        self.spacecraft_table.setRowCount(len(spacecraft_list))
        
        for i, spacecraft_id in enumerate(spacecraft_list):
            data = data_provider.get_spacecraft_data(spacecraft_id)
            
            # Name
            self.spacecraft_table.setItem(i, 0, QTableWidgetItem(data["name"]))
            
            # Type
            self.spacecraft_table.setItem(i, 1, QTableWidgetItem(data["type"]))
            
            # Status with color
            status_item = QTableWidgetItem(data["status"].title())
            if data["status"] == "operational":
                status_item.setBackground(QColor(0, 255, 0, 50))
            elif data["status"] == "warning":
                status_item.setBackground(QColor(255, 255, 0, 50))
            elif data["status"] == "error":
                status_item.setBackground(QColor(255, 0, 0, 50))
            self.spacecraft_table.setItem(i, 2, status_item)
            
            # Position
            pos = data["position"]
            pos_text = f"{pos['lat']:.2f}°, {pos['lon']:.2f}°"
            self.spacecraft_table.setItem(i, 3, QTableWidgetItem(pos_text))
            
            # Power
            power_text = f"{data['power_level']:.1f}%"
            self.spacecraft_table.setItem(i, 4, QTableWidgetItem(power_text))
            
            # Last contact
            last_contact = data["last_contact"]
            if hasattr(last_contact, 'strftime'):
                contact_text = last_contact.strftime("%H:%M:%S")
            else:
                contact_text = "Unknown"
            self.spacecraft_table.setItem(i, 5, QTableWidgetItem(contact_text))
    
    def on_spacecraft_selected(self, row, column):
        """Handle spacecraft selection"""
        spacecraft_list = data_provider.get_spacecraft_list()
        if 0 <= row < len(spacecraft_list):
            selected = spacecraft_list[row]
            self.selected_spacecraft = selected
            self.spacecraft_selected.emit(selected)


class TelemetryVisualizationWidget(QWidget):
    """Advanced telemetry visualization widget"""
    
    def __init__(self, spacecraft_id="ISS"):
        super().__init__()
        self.spacecraft_id = spacecraft_id
        self.current_category = "power"
        self.init_ui()
        self.init_timers()
    
    def init_ui(self):
        """Initialize telemetry visualization UI"""
        layout = QVBoxLayout(self)
        
        # Category selection
        category_layout = QHBoxLayout()
        
        self.power_btn = QPushButton("Power Systems")
        self.thermal_btn = QPushButton("Thermal")
        self.attitude_btn = QPushButton("Attitude")
        self.comm_btn = QPushButton("Communications")
        
        for btn in [self.power_btn, self.thermal_btn, self.attitude_btn, 
                   self.comm_btn]:
            btn.clicked.connect(self.on_category_changed)
            category_layout.addWidget(btn)
        
        layout.addLayout(category_layout)
        
        # Telemetry display area
        self.telemetry_area = QFrame()
        self.telemetry_layout = QGridLayout(self.telemetry_area)
        layout.addWidget(self.telemetry_area)
        
        # Initialize display
        self.update_telemetry_display()
    
    def init_timers(self):
        """Initialize update timers"""
        self.telemetry_timer = QTimer()
        self.telemetry_timer.timeout.connect(self.update_telemetry_values)
        self.telemetry_timer.start(2000)  # Update every 2 seconds
    
    def on_category_changed(self):
        """Handle category selection change"""
        sender = self.sender()
        
        if sender == self.power_btn:
            self.current_category = "power"
        elif sender == self.thermal_btn:
            self.current_category = "thermal"
        elif sender == self.attitude_btn:
            self.current_category = "attitude"
        elif sender == self.comm_btn:
            self.current_category = "communication"
        
        self.update_telemetry_display()
    
    def update_telemetry_display(self):
        """Update telemetry display for current category"""
        # Clear existing widgets
        for i in reversed(range(self.telemetry_layout.count())):
            self.telemetry_layout.itemAt(i).widget().setParent(None)
        
        # Get telemetry data for category
        telemetry_data = data_provider.get_telemetry_data(
            self.spacecraft_id, self.current_category
        )
        
        if not telemetry_data:
            return
        
        # Create parameter displays
        row, col = 0, 0
        for parameter, data_series in telemetry_data.items():
            if data_series:
                param_widget = TelemetryParameterWidget(
                    parameter, data_series, self.get_parameter_unit(parameter)
                )
                self.telemetry_layout.addWidget(param_widget, row, col)
                
                col += 1
                if col >= 2:  # 2 columns
                    col = 0
                    row += 1
    
    def update_telemetry_values(self):
        """Update telemetry values in real-time"""
        # Simulate telemetry updates
        data_provider.simulate_telemetry_update(self.spacecraft_id)
        
        # Update displays if they exist
        for i in range(self.telemetry_layout.count()):
            widget = self.telemetry_layout.itemAt(i).widget()
            if isinstance(widget, TelemetryParameterWidget):
                widget.update_data()
    
    def get_parameter_unit(self, parameter):
        """Get unit for telemetry parameter"""
        units = {
            "battery_voltage": "V",
            "solar_current": "A", 
            "power_consumption": "W",
            "charging_rate": "A",
            "cpu_temp": "°C",
            "battery_temp": "°C",
            "external_temp": "°C",
            "radiator_temp": "°C",
            "roll": "°",
            "pitch": "°",
            "yaw": "°",
            "angular_velocity": "°/s",
            "signal_strength": "dBm",
            "data_rate": "Mbps",
            "packet_loss": "%",
            "bandwidth_usage": "%"
        }
        return units.get(parameter, "")
    
    def set_spacecraft(self, spacecraft_id):
        """Set the spacecraft to monitor"""
        self.spacecraft_id = spacecraft_id
        self.update_telemetry_display()


class TelemetryParameterWidget(QWidget):
    """Widget for displaying individual telemetry parameter"""
    
    def __init__(self, parameter_name, data_series, unit=""):
        super().__init__()
        self.parameter_name = parameter_name
        self.data_series = data_series
        self.unit = unit
        self.setMinimumSize(200, 120)
        self.init_ui()
    
    def init_ui(self):
        """Initialize parameter widget UI"""
        layout = QVBoxLayout(self)
        
        # Parameter name
        name_label = QLabel(self.parameter_name.replace("_", " ").title())
        name_label.setStyleSheet("font-weight: bold; color: white;")
        layout.addWidget(name_label)
        
        # Current value
        current_value = self.data_series[-1] if self.data_series else 0
        self.value_label = QLabel(f"{current_value:.2f} {self.unit}")
        self.value_label.setStyleSheet("font-size: 16px; color: #00ff88;")
        layout.addWidget(self.value_label)
        
        # Mini chart
        self.chart_widget = MiniChartWidget(self.data_series)
        layout.addWidget(self.chart_widget)
    
    def update_data(self):
        """Update parameter data"""
        # Get fresh data from data provider
        telemetry_data = data_provider.get_telemetry_data("ISS")
        for category in telemetry_data.values():
            if self.parameter_name in category:
                self.data_series = category[self.parameter_name]
                break
        
        # Update displays
        if self.data_series:
            current_value = self.data_series[-1]
            self.value_label.setText(f"{current_value:.2f} {self.unit}")
            self.chart_widget.update_data(self.data_series)


class MiniChartWidget(QWidget):
    """Mini chart widget for telemetry parameters"""
    
    def __init__(self, data_series):
        super().__init__()
        self.data_series = data_series
        self.setMinimumSize(180, 60)
    
    def update_data(self, data_series):
        """Update chart data"""
        self.data_series = data_series
        self.update()
    
    def paintEvent(self, event):
        """Paint the mini chart"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(16, 33, 62))
        
        if len(self.data_series) < 2:
            return
        
        # Calculate chart area
        chart_rect = self.rect().adjusted(5, 5, -5, -5)
        
        # Find min/max values
        min_val = min(self.data_series[-20:])  # Show last 20 points
        max_val = max(self.data_series[-20:])
        
        if min_val == max_val:
            min_val -= 1
            max_val += 1
        
        # Draw data line
        painter.setPen(QPen(QColor(0, 255, 136), 2))
        
        recent_data = self.data_series[-20:]  # Show last 20 points
        for i in range(len(recent_data) - 1):
            x1 = chart_rect.left() + (chart_rect.width() * i / 
                                    (len(recent_data) - 1))
            y1 = chart_rect.bottom() - (chart_rect.height() * 
                                      (recent_data[i] - min_val) / 
                                      (max_val - min_val))
            
            x2 = chart_rect.left() + (chart_rect.width() * (i + 1) / 
                                    (len(recent_data) - 1))
            y2 = chart_rect.bottom() - (chart_rect.height() * 
                                      (recent_data[i + 1] - min_val) / 
                                      (max_val - min_val))
            
            painter.drawLine(x1, y1, x2, y2)


class CEHSNStatusWidget(QWidget):
    """CEHSN system status overview widget"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_timers()
    
    def init_ui(self):
        """Initialize CEHSN status UI"""
        layout = QVBoxLayout(self)
        
        # CEHSN overview
        overview_group = QGroupBox("CEHSN System Health")
        overview_layout = QGridLayout(overview_group)
        
        # Component status indicators
        self.orbital_inference_status = StatusIndicatorWidget(
            "Orbital Inference Engine", "operational"
        )
        overview_layout.addWidget(self.orbital_inference_status, 0, 0)
        
        self.rpa_bridge_status = StatusIndicatorWidget(
            "RPA Communication Bridge", "operational"
        )
        overview_layout.addWidget(self.rpa_bridge_status, 0, 1)
        
        self.ethics_engine_status = StatusIndicatorWidget(
            "Ethics Engine", "operational"
        )
        overview_layout.addWidget(self.ethics_engine_status, 1, 0)
        
        self.survival_maps_status = StatusIndicatorWidget(
            "Survival Map Generator", "operational"
        )
        overview_layout.addWidget(self.survival_maps_status, 1, 1)
        
        self.resilience_monitor_status = StatusIndicatorWidget(
            "Resilience Monitor", "operational"
        )
        overview_layout.addWidget(self.resilience_monitor_status, 2, 0)
        
        layout.addWidget(overview_group)
        
        # Performance metrics
        metrics_group = QGroupBox("Performance Metrics")
        metrics_layout = QGridLayout(metrics_group)
        
        # Network health gauge
        self.network_health_gauge = CircularGaugeWidget(
            "Network Health", 0, 100, 94.2
        )
        metrics_layout.addWidget(self.network_health_gauge, 0, 0)
        
        # Active nodes gauge
        self.active_nodes_gauge = CircularGaugeWidget(
            "Active Nodes", 0, 50, 47
        )
        metrics_layout.addWidget(self.active_nodes_gauge, 0, 1)
        
        layout.addWidget(metrics_group)
    
    def init_timers(self):
        """Initialize update timers"""
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(10000)  # Update every 10 seconds
    
    def update_status(self):
        """Update CEHSN status displays"""
        cehsn_data = data_provider.get_cehsn_data()
        
        # Update network health
        resilience_data = cehsn_data.get("resilience_monitor", {})
        network_health = resilience_data.get("network_health", 94.2)
        self.network_health_gauge.set_value(network_health)
        
        active_nodes = resilience_data.get("active_nodes", 47)
        self.active_nodes_gauge.set_value(active_nodes)


class StatusIndicatorWidget(QWidget):
    """Status indicator with icon and text"""
    
    def __init__(self, label, status="unknown"):
        super().__init__()
        self.label = label
        self.status = status
        self.init_ui()
    
    def init_ui(self):
        """Initialize status indicator UI"""
        layout = QHBoxLayout(self)
        
        # Status icon
        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.status_icon)
        
        # Label
        label_widget = QLabel(self.label)
        label_widget.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(label_widget)
        
        self.update_status_display()
    
    def set_status(self, status):
        """Set the status"""
        self.status = status
        self.update_status_display()
    
    def update_status_display(self):
        """Update status display colors"""
        colors = {
            "operational": "#00ff00",
            "warning": "#ffaa00",
            "error": "#ff0000", 
            "offline": "#888888",
            "unknown": "#888888"
        }
        
        color = colors.get(self.status, colors["unknown"])
        self.status_icon.setStyleSheet(f"color: {color}; font-size: 16px;")


class CircularGaugeWidget(QWidget):
    """Circular gauge widget for metrics"""
    
    def __init__(self, label, min_val, max_val, value):
        super().__init__()
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self.setMinimumSize(120, 120)
    
    def set_value(self, value):
        """Set gauge value"""
        self.value = max(self.min_val, min(self.max_val, value))
        self.update()
    
    def paintEvent(self, event):
        """Paint the circular gauge"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate dimensions
        side = min(self.width(), self.height())
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = side // 2 - 15
        
        # Draw background circle
        painter.setPen(QPen(QColor(100, 100, 100), 3))
        painter.drawEllipse(center_x - radius, center_y - radius, 
                          radius * 2, radius * 2)
        
        # Draw value arc
        painter.setPen(QPen(QColor(0, 255, 136), 4))
        start_angle = 225 * 16  # Start at bottom-left
        span_angle = int((270 * (self.value - self.min_val) / 
                        (self.max_val - self.min_val)) * 16)
        painter.drawArc(center_x - radius, center_y - radius,
                       radius * 2, radius * 2, start_angle, span_angle)
        
        # Draw center circle
        painter.setBrush(QBrush(QColor(16, 33, 62)))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawEllipse(center_x - 25, center_y - 25, 50, 50)
        
        # Draw value text
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        value_text = f"{self.value:.1f}"
        painter.drawText(center_x - 15, center_y + 3, value_text)
        
        # Draw label
        painter.setFont(QFont("Arial", 8))
        painter.drawText(center_x - 30, center_y + 40, self.label)
