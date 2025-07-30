#!/usr/bin/env python3
"""
IoST GUI Widgets
Additional custom widgets for the Internet of Space Things GUI
"""

import math
import sys

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class RealTimeChart(QWidget):
    """Real-time data visualization widget"""
    
    def __init__(self, title="Chart", max_points=100):
        super().__init__()
        self.title = title
        self.max_points = max_points
        self.data_points = []
        self.setMinimumSize(300, 200)
        
        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.add_sample_data)
        self.timer.start(1000)  # Update every second
    
    def add_data_point(self, value):
        """Add a new data point"""
        self.data_points.append(value)
        if len(self.data_points) > self.max_points:
            self.data_points.pop(0)
        self.update()
    
    def add_sample_data(self):
        """Add sample data for demonstration"""
        import random
        value = 50 + random.uniform(-10, 10)
        self.add_data_point(value)
    
    def paintEvent(self, event):
        """Paint the chart"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(16, 33, 62))
        
        # Draw title
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(10, 20, self.title)
        
        if len(self.data_points) < 2:
            return
        
        # Calculate chart area
        chart_rect = self.rect().adjusted(20, 30, -20, -20)
        
        # Find min/max values
        min_val = min(self.data_points)
        max_val = max(self.data_points)
        if min_val == max_val:
            min_val -= 1
            max_val += 1
        
        # Draw grid
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        for i in range(5):
            y = chart_rect.top() + (chart_rect.height() * i / 4)
            painter.drawLine(chart_rect.left(), y, chart_rect.right(), y)
        
        # Draw data line
        painter.setPen(QPen(QColor(0, 255, 136), 2))
        for i in range(len(self.data_points) - 1):
            x1 = chart_rect.left() + (chart_rect.width() * i / (len(self.data_points) - 1))
            y1 = chart_rect.bottom() - (chart_rect.height() * (self.data_points[i] - min_val) / (max_val - min_val))
            
            x2 = chart_rect.left() + (chart_rect.width() * (i + 1) / (len(self.data_points) - 1))
            y2 = chart_rect.bottom() - (chart_rect.height() * (self.data_points[i + 1] - min_val) / (max_val - min_val))
            
            painter.drawLine(x1, y1, x2, y2)


class StatusIndicator(QWidget):
    """Status indicator widget with color-coded states"""
    
    def __init__(self, label="Status", status="unknown"):
        super().__init__()
        self.label = label
        self.status = status
        self.setMinimumSize(100, 30)
    
    def set_status(self, status):
        """Set the status and update display"""
        self.status = status
        self.update()
    
    def paintEvent(self, event):
        """Paint the status indicator"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Status colors
        colors = {
            "operational": QColor(0, 255, 0),
            "warning": QColor(255, 255, 0),
            "error": QColor(255, 0, 0),
            "offline": QColor(128, 128, 128),
            "unknown": QColor(128, 128, 128)
        }
        
        color = colors.get(self.status, colors["unknown"])
        
        # Draw status circle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawEllipse(5, 5, 20, 20)
        
        # Draw label
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(30, 20, f"{self.label}: {self.status.title()}")


class GaugeWidget(QWidget):
    """Circular gauge widget for displaying values"""
    
    def __init__(self, title="Gauge", min_val=0, max_val=100, value=0):
        super().__init__()
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self.setMinimumSize(150, 150)
    
    def set_value(self, value):
        """Set the gauge value"""
        self.value = max(self.min_val, min(self.max_val, value))
        self.update()
    
    def paintEvent(self, event):
        """Paint the gauge"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate gauge dimensions
        side = min(self.width(), self.height())
        center = QPoint(self.width() // 2, self.height() // 2)
        radius = side // 2 - 10
        
        # Draw gauge background
        painter.setPen(QPen(QColor(100, 100, 100), 3))
        painter.drawEllipse(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        
        # Draw value arc
        painter.setPen(QPen(QColor(0, 255, 136), 5))
        start_angle = 225 * 16  # Start at bottom-left
        span_angle = int((270 * (self.value - self.min_val) / (self.max_val - self.min_val)) * 16)
        painter.drawArc(center.x() - radius, center.y() - radius, radius * 2, radius * 2, start_angle, span_angle)
        
        # Draw center circle
        painter.setBrush(QBrush(QColor(16, 33, 62)))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawEllipse(center.x() - 20, center.y() - 20, 40, 40)
        
        # Draw value text
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        value_text = f"{self.value:.1f}"
        painter.drawText(center.x() - 15, center.y() + 5, value_text)
        
        # Draw title
        painter.setFont(QFont("Arial", 10))
        painter.drawText(center.x() - 30, center.y() + 40, self.title)


class AlertPanel(QFrame):
    """Alert panel widget for displaying system alerts"""
    
    alert_acknowledged = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.alerts = []
        self.init_ui()
    
    def init_ui(self):
        """Initialize the alert panel UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("System Alerts")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px; color: white;")
        layout.addWidget(header_label)
        
        # Scroll area for alerts
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)
    
    def add_alert(self, level, message, timestamp=None):
        """Add a new alert"""
        if timestamp is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
        
        alert_widget = AlertWidget(level, message, timestamp)
        alert_widget.acknowledged.connect(self.on_alert_acknowledged)
        
        self.scroll_layout.insertWidget(0, alert_widget)  # Add to top
        self.alerts.append(alert_widget)
        
        # Limit number of alerts
        if len(self.alerts) > 20:
            old_alert = self.alerts.pop(0)
            old_alert.deleteLater()
    
    def on_alert_acknowledged(self, alert_id):
        """Handle alert acknowledgment"""
        self.alert_acknowledged.emit(alert_id)


class AlertWidget(QWidget):
    """Individual alert widget"""
    
    acknowledged = pyqtSignal(str)
    
    def __init__(self, level, message, timestamp):
        super().__init__()
        self.level = level
        self.message = message
        self.timestamp = timestamp
        self.alert_id = f"{timestamp}_{level}_{hash(message)}"
        self.init_ui()
    
    def init_ui(self):
        """Initialize alert widget UI"""
        layout = QHBoxLayout(self)
        
        # Alert level indicator
        level_colors = {
            "critical": "#ff4444",
            "warning": "#ffaa00", 
            "info": "#4488ff",
            "success": "#44ff44"
        }
        
        level_indicator = QLabel("●")
        level_indicator.setStyleSheet(f"color: {level_colors.get(self.level, '#888888')}; font-size: 16px;")
        layout.addWidget(level_indicator)
        
        # Alert message
        message_label = QLabel(f"[{self.timestamp}] {self.message}")
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: white;")
        layout.addWidget(message_label, 1)
        
        # Acknowledge button
        ack_button = QPushButton("✓")
        ack_button.setMaximumSize(30, 30)
        ack_button.clicked.connect(self.acknowledge)
        layout.addWidget(ack_button)
    
    def acknowledge(self):
        """Acknowledge this alert"""
        self.acknowledged.emit(self.alert_id)
        self.setStyleSheet("background-color: rgba(100, 100, 100, 50);")


class ConsoleWidget(QWidget):
    """Console widget for command input and output"""
    
    command_executed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.command_history = []
        self.history_index = -1
        self.init_ui()
    
    def init_ui(self):
        """Initialize console UI"""
        layout = QVBoxLayout(self)
        
        # Output area
        from PyQt6.QtWidgets import QLineEdit, QTextEdit
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setStyleSheet("""
            background-color: #000000;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        """)
        layout.addWidget(self.output_area)
        
        # Command input
        input_layout = QHBoxLayout()
        
        prompt_label = QLabel(">>> ")
        prompt_label.setStyleSheet("color: white; font-family: 'Courier New', monospace;")
        input_layout.addWidget(prompt_label)
        
        self.command_input = QLineEdit()
        self.command_input.setStyleSheet("""
            background-color: #000000;
            color: #ffffff;
            font-family: 'Courier New', monospace;
            border: 1px solid #444444;
        """)
        self.command_input.returnPressed.connect(self.execute_command)
        input_layout.addWidget(self.command_input)
        
        layout.addLayout(input_layout)
        
        # Add welcome message
        self.add_output("IoST Command Console v1.0")
        self.add_output("Type 'help' for available commands")
        self.add_output("=" * 40)
    
    def add_output(self, text):
        """Add text to output area"""
        self.output_area.append(text)
    
    def execute_command(self):
        """Execute the entered command"""
        command = self.command_input.text().strip()
        if not command:
            return
        
        # Add to history
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        
        # Display command
        self.add_output(f">>> {command}")
        
        # Process command
        self.process_command(command)
        
        # Clear input
        self.command_input.clear()
    
    def process_command(self, command):
        """Process the command and show output"""
        parts = command.lower().split()
        
        if not parts:
            return
        
        cmd = parts[0]
        
        if cmd == "help":
            self.add_output("Available commands:")
            self.add_output("  help - Show this help")
            self.add_output("  status - Show system status")
            self.add_output("  satellites - List satellites")
            self.add_output("  clear - Clear console")
            self.add_output("  exit - Close console")
        
        elif cmd == "status":
            self.add_output("System Status: Operational")
            self.add_output("Active Satellites: 15")
            self.add_output("CEHSN Status: Active")
            self.add_output("Network Health: 94%")
        
        elif cmd == "satellites":
            satellites = [
                "ISS - Operational",
                "Luna Gateway - Operational", 
                "Crew Dragon - In Transit",
                "CubeSat-Alpha - Active",
                "CubeSat-Beta - Active"
            ]
            for sat in satellites:
                self.add_output(f"  {sat}")
        
        elif cmd == "clear":
            self.output_area.clear()
        
        elif cmd == "exit":
            self.add_output("Console closed.")
        
        else:
            self.add_output(f"Unknown command: {command}")
            self.add_output("Type 'help' for available commands")
        
        # Emit signal for external handling
        self.command_executed.emit(command)
