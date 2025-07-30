#!/usr/bin/env python3
"""
3D Visualization Module for IoST GUI
Real-time 3D spacecraft tracking and orbital visualization
"""

import math

import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMatrix4x4, QQuaternion, QVector3D
from PyQt6.QtOpenGL import QOpenGLBuffer, QOpenGLShaderProgram, QOpenGLVertexArrayObject
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:
    import OpenGL.GL.shaders as shaders
    from OpenGL.GL import *
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False

from data_provider import data_provider


class Spacecraft3DVisualizationWidget(QWidget):
    """3D spacecraft visualization control widget"""
    
    spacecraft_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_spacecraft = "ISS"
        self.tracking_enabled = True
        self.init_ui()
        self.init_timers()
    
    def init_ui(self):
        """Initialize 3D visualization UI"""
        layout = QVBoxLayout(self)
        
        # Controls panel
        controls_group = QGroupBox("3D View Controls")
        controls_layout = QVBoxLayout(controls_group)
        
        # Spacecraft selection
        spacecraft_layout = QHBoxLayout()
        spacecraft_layout.addWidget(QLabel("Spacecraft:"))
        
        self.spacecraft_combo = QComboBox()
        self.spacecraft_combo.addItems(data_provider.get_spacecraft_list())
        self.spacecraft_combo.currentTextChanged.connect(self.on_spacecraft_changed)
        spacecraft_layout.addWidget(self.spacecraft_combo)
        
        controls_layout.addLayout(spacecraft_layout)
        
        # View controls
        view_controls_layout = QHBoxLayout()
        
        self.tracking_checkbox = QCheckBox("Auto Track")
        self.tracking_checkbox.setChecked(True)
        self.tracking_checkbox.toggled.connect(self.on_tracking_toggled)
        view_controls_layout.addWidget(self.tracking_checkbox)
        
        self.reset_view_btn = QPushButton("Reset View")
        self.reset_view_btn.clicked.connect(self.reset_camera_view)
        view_controls_layout.addWidget(self.reset_view_btn)
        
        controls_layout.addLayout(view_controls_layout)
        
        # Zoom control
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 100)
        self.zoom_slider.setValue(50)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        
        controls_layout.addLayout(zoom_layout)
        
        # Display options
        display_options_layout = QHBoxLayout()
        
        self.show_orbit_checkbox = QCheckBox("Show Orbit")
        self.show_orbit_checkbox.setChecked(True)
        display_options_layout.addWidget(self.show_orbit_checkbox)
        
        self.show_earth_checkbox = QCheckBox("Show Earth")
        self.show_earth_checkbox.setChecked(True)
        display_options_layout.addWidget(self.show_earth_checkbox)
        
        self.show_grid_checkbox = QCheckBox("Grid")
        self.show_grid_checkbox.setChecked(False)
        display_options_layout.addWidget(self.show_grid_checkbox)
        
        controls_layout.addLayout(display_options_layout)
        
        layout.addWidget(controls_group)
        
        # 3D viewport
        if OPENGL_AVAILABLE:
            self.viewport_3d = OpenGL3DViewport()
        else:
            self.viewport_3d = Mock3DViewport()
        
        layout.addWidget(self.viewport_3d, 1)  # Take most of the space
        
        # Status display
        status_group = QGroupBox("Orbital Information")
        status_layout = QVBoxLayout(status_group)
        
        self.altitude_label = QLabel("Altitude: --")
        self.velocity_label = QLabel("Velocity: --")
        self.orbital_period_label = QLabel("Period: --")
        self.inclination_label = QLabel("Inclination: --")
        
        status_layout.addWidget(self.altitude_label)
        status_layout.addWidget(self.velocity_label)
        status_layout.addWidget(self.orbital_period_label)
        status_layout.addWidget(self.inclination_label)
        
        layout.addWidget(status_group)
    
    def init_timers(self):
        """Initialize update timers"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_visualization)
        self.update_timer.start(1000)  # Update every second
    
    def on_spacecraft_changed(self, spacecraft_id):
        """Handle spacecraft selection change"""
        self.current_spacecraft = spacecraft_id
        self.spacecraft_selected.emit(spacecraft_id)
        self.viewport_3d.set_spacecraft(spacecraft_id)
    
    def on_tracking_toggled(self, enabled):
        """Handle tracking toggle"""
        self.tracking_enabled = enabled
        self.viewport_3d.set_tracking(enabled)
    
    def on_zoom_changed(self, value):
        """Handle zoom change"""
        zoom_factor = value / 50.0  # Normalize to 0.02 - 2.0
        self.viewport_3d.set_zoom(zoom_factor)
    
    def reset_camera_view(self):
        """Reset camera to default view"""
        self.viewport_3d.reset_camera()
        self.zoom_slider.setValue(50)
    
    def update_visualization(self):
        """Update 3D visualization and orbital data"""
        spacecraft_data = data_provider.get_spacecraft_data(self.current_spacecraft)
        
        # Update orbital information display
        position = spacecraft_data.get("position", {})
        velocity = spacecraft_data.get("velocity", {})
        orbital_data = spacecraft_data.get("orbital_data", {})
        
        altitude = position.get("altitude", 0)
        self.altitude_label.setText(f"Altitude: {altitude:.1f} km")
        
        speed = (velocity.get("x", 0)**2 + velocity.get("y", 0)**2 + 
                velocity.get("z", 0)**2)**0.5
        self.velocity_label.setText(f"Velocity: {speed:.2f} km/s")
        
        period = orbital_data.get("period", 0)
        self.orbital_period_label.setText(f"Period: {period:.1f} min")
        
        inclination = orbital_data.get("inclination", 0)
        self.inclination_label.setText(f"Inclination: {inclination:.1f}°")
        
        # Update 3D viewport
        self.viewport_3d.update_spacecraft_data(spacecraft_data)


class OpenGL3DViewport(QOpenGLWidget):
    """OpenGL-based 3D viewport for spacecraft visualization"""
    
    def __init__(self):
        super().__init__()
        self.spacecraft_id = "ISS"
        self.tracking_enabled = True
        self.zoom_factor = 1.0
        self.camera_rotation_x = 0
        self.camera_rotation_y = 0
        self.mouse_last_pos = None
        
        # Spacecraft data
        self.spacecraft_position = [0, 0, 400]  # km from Earth center
        self.spacecraft_velocity = [0, 0, 0]
        self.orbital_trail = []
        
        # Earth parameters
        self.earth_radius = 6371  # km
        
        # Display options
        self.show_orbit = True
        self.show_earth = True
        self.show_grid = False
    
    def initializeGL(self):
        """Initialize OpenGL context"""
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.0, 0.0, 0.1, 1.0)  # Dark blue space background
        
        # Initialize shaders
        self.init_shaders()
        
        # Initialize geometry
        self.init_geometry()
    
    def init_shaders(self):
        """Initialize OpenGL shaders"""
        # Simple vertex shader
        vertex_shader = """
        #version 330 core
        layout (location = 0) in vec3 position;
        layout (location = 1) in vec3 color;
        
        uniform mat4 mvp_matrix;
        
        out vec3 vertex_color;
        
        void main()
        {
            gl_Position = mvp_matrix * vec4(position, 1.0);
            vertex_color = color;
        }
        """
        
        # Simple fragment shader
        fragment_shader = """
        #version 330 core
        in vec3 vertex_color;
        out vec4 FragColor;
        
        void main()
        {
            FragColor = vec4(vertex_color, 1.0);
        }
        """
        
        try:
            self.shader_program = shaders.compileProgram(
                shaders.compileShader(vertex_shader, GL_VERTEX_SHADER),
                shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER)
            )
        except Exception as e:
            print(f"Shader compilation failed: {e}")
            self.shader_program = None
    
    def init_geometry(self):
        """Initialize 3D geometry"""
        # Create Earth sphere vertices
        self.earth_vertices = self.create_sphere_vertices(self.earth_radius, 32, 16)
        
        # Create spacecraft vertices (simple cube for now)
        self.spacecraft_vertices = self.create_cube_vertices(10)  # 10km cube
        
        # Create grid vertices
        self.grid_vertices = self.create_grid_vertices(20000, 100)  # 20,000km grid
    
    def create_sphere_vertices(self, radius, lon_segments, lat_segments):
        """Create vertices for a sphere"""
        vertices = []
        
        for lat in range(lat_segments + 1):
            lat_angle = math.pi * lat / lat_segments - math.pi / 2
            
            for lon in range(lon_segments + 1):
                lon_angle = 2 * math.pi * lon / lon_segments
                
                x = radius * math.cos(lat_angle) * math.cos(lon_angle)
                y = radius * math.cos(lat_angle) * math.sin(lon_angle)
                z = radius * math.sin(lat_angle)
                
                # Earth-like coloring
                if lat_angle > 0:
                    color = [0.3, 0.7, 0.3]  # Green for land
                else:
                    color = [0.2, 0.4, 0.8]  # Blue for oceans
                
                vertices.extend([x, y, z] + color)
        
        return np.array(vertices, dtype=np.float32)
    
    def create_cube_vertices(self, size):
        """Create vertices for a cube (spacecraft)"""
        half_size = size / 2
        vertices = [
            # Front face (red)
            -half_size, -half_size,  half_size,  1.0, 0.0, 0.0,
             half_size, -half_size,  half_size,  1.0, 0.0, 0.0,
             half_size,  half_size,  half_size,  1.0, 0.0, 0.0,
            -half_size,  half_size,  half_size,  1.0, 0.0, 0.0,
            
            # Back face (green)
            -half_size, -half_size, -half_size,  0.0, 1.0, 0.0,
             half_size, -half_size, -half_size,  0.0, 1.0, 0.0,
             half_size,  half_size, -half_size,  0.0, 1.0, 0.0,
            -half_size,  half_size, -half_size,  0.0, 1.0, 0.0,
        ]
        
        return np.array(vertices, dtype=np.float32)
    
    def create_grid_vertices(self, size, spacing):
        """Create vertices for a 3D grid"""
        vertices = []
        half_size = size / 2
        
        # Grid lines in X direction
        for y in range(-int(half_size), int(half_size) + 1, spacing):
            for z in range(-int(half_size), int(half_size) + 1, spacing):
                vertices.extend([-half_size, y, z, 0.2, 0.2, 0.2])
                vertices.extend([half_size, y, z, 0.2, 0.2, 0.2])
        
        # Grid lines in Y direction
        for x in range(-int(half_size), int(half_size) + 1, spacing):
            for z in range(-int(half_size), int(half_size) + 1, spacing):
                vertices.extend([x, -half_size, z, 0.2, 0.2, 0.2])
                vertices.extend([x, half_size, z, 0.2, 0.2, 0.2])
        
        # Grid lines in Z direction
        for x in range(-int(half_size), int(half_size) + 1, spacing):
            for y in range(-int(half_size), int(half_size) + 1, spacing):
                vertices.extend([x, y, -half_size, 0.2, 0.2, 0.2])
                vertices.extend([x, y, half_size, 0.2, 0.2, 0.2])
        
        return np.array(vertices, dtype=np.float32)
    
    def paintGL(self):
        """Render the 3D scene"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        if not self.shader_program:
            return
        
        glUseProgram(self.shader_program)
        
        # Set up camera and projection matrices
        projection_matrix = self.get_projection_matrix()
        view_matrix = self.get_view_matrix()
        mvp_matrix = projection_matrix * view_matrix
        
        # Upload MVP matrix to shader
        mvp_location = glGetUniformLocation(self.shader_program, "mvp_matrix")
        if mvp_location != -1:
            glUniformMatrix4fv(mvp_location, 1, GL_FALSE, mvp_matrix.data())
        
        # Render Earth
        if self.show_earth:
            self.render_earth()
        
        # Render spacecraft
        self.render_spacecraft()
        
        # Render orbital trail
        if self.show_orbit:
            self.render_orbital_trail()
        
        # Render grid
        if self.show_grid:
            self.render_grid()
    
    def get_projection_matrix(self):
        """Get projection matrix"""
        aspect_ratio = self.width() / max(self.height(), 1)
        projection = QMatrix4x4()
        projection.perspective(45.0, aspect_ratio, 1.0, 100000.0)
        return projection
    
    def get_view_matrix(self):
        """Get view matrix"""
        view = QMatrix4x4()
        
        # Apply zoom
        camera_distance = 15000 / self.zoom_factor
        
        # Apply rotations
        view.translate(0, 0, -camera_distance)
        view.rotate(self.camera_rotation_x, 1, 0, 0)
        view.rotate(self.camera_rotation_y, 0, 1, 0)
        
        # Track spacecraft if enabled
        if self.tracking_enabled:
            view.translate(-self.spacecraft_position[0], 
                         -self.spacecraft_position[1], 
                         -self.spacecraft_position[2])
        
        return view
    
    def render_earth(self):
        """Render Earth sphere"""
        # Implementation would use vertex buffers to render Earth
        pass
    
    def render_spacecraft(self):
        """Render spacecraft"""
        # Implementation would render spacecraft at current position
        pass
    
    def render_orbital_trail(self):
        """Render orbital trail"""
        # Implementation would render orbital trail as line strip
        pass
    
    def render_grid(self):
        """Render reference grid"""
        # Implementation would render grid lines
        pass
    
    def resizeGL(self, width, height):
        """Handle viewport resize"""
        glViewport(0, 0, width, height)
    
    def mousePressEvent(self, event):
        """Handle mouse press for camera control"""
        self.mouse_last_pos = event.position().toPoint()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for camera rotation"""
        if self.mouse_last_pos is not None:
            dx = event.position().x() - self.mouse_last_pos.x()
            dy = event.position().y() - self.mouse_last_pos.y()
            
            self.camera_rotation_y += dx * 0.5
            self.camera_rotation_x += dy * 0.5
            
            # Clamp vertical rotation
            self.camera_rotation_x = max(-90, min(90, self.camera_rotation_x))
            
            self.mouse_last_pos = event.position().toPoint()
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.mouse_last_pos = None
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zoom"""
        delta = event.angleDelta().y()
        zoom_change = 1.1 if delta > 0 else 0.9
        self.zoom_factor *= zoom_change
        self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))
        self.update()
    
    def set_spacecraft(self, spacecraft_id):
        """Set current spacecraft"""
        self.spacecraft_id = spacecraft_id
        self.update_spacecraft_data()
    
    def set_tracking(self, enabled):
        """Set tracking mode"""
        self.tracking_enabled = enabled
        self.update()
    
    def set_zoom(self, zoom_factor):
        """Set zoom factor"""
        self.zoom_factor = zoom_factor
        self.update()
    
    def reset_camera(self):
        """Reset camera to default position"""
        self.camera_rotation_x = 0
        self.camera_rotation_y = 0
        self.zoom_factor = 1.0
        self.update()
    
    def update_spacecraft_data(self, spacecraft_data=None):
        """Update spacecraft position and orbital data"""
        if spacecraft_data is None:
            spacecraft_data = data_provider.get_spacecraft_data(self.spacecraft_id)
        
        # Update spacecraft position
        position = spacecraft_data.get("position", {})
        self.spacecraft_position = [
            position.get("x", 0),
            position.get("y", 0), 
            position.get("z", 400)  # Default altitude
        ]
        
        # Update orbital trail
        self.orbital_trail.append(self.spacecraft_position.copy())
        if len(self.orbital_trail) > 100:  # Keep last 100 positions
            self.orbital_trail.pop(0)
        
        self.update()


class Mock3DViewport(QWidget):
    """Mock 3D viewport when OpenGL is not available"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize mock UI"""
        layout = QVBoxLayout(self)
        
        error_label = QLabel("3D Visualization Unavailable")
        error_label.setStyleSheet("""
            QLabel {
                color: #ff6666;
                font-size: 16px;
                font-weight: bold;
                text-align: center;
            }
        """)
        layout.addWidget(error_label)
        
        info_label = QLabel("OpenGL libraries not found.\nInstall PyOpenGL to enable 3D visualization.")
        info_label.setStyleSheet("color: #cccccc; text-align: center;")
        layout.addWidget(info_label)
    
    def set_spacecraft(self, spacecraft_id):
        """Mock method"""
        pass
    
    def set_tracking(self, enabled):
        """Mock method"""
        pass
    
    def set_zoom(self, zoom_factor):
        """Mock method"""
        pass
    
    def reset_camera(self):
        """Mock method"""
        pass
    
    def update_spacecraft_data(self, spacecraft_data):
        """Mock method"""
        pass


class OrbitalMechanicsCalculator:
    """Utility class for orbital mechanics calculations"""
    
    @staticmethod
    def calculate_orbital_period(altitude):
        """Calculate orbital period for given altitude"""
        earth_radius = 6371  # km
        gravitational_parameter = 398600.4418  # km³/s²
        
        semi_major_axis = earth_radius + altitude
        period_seconds = 2 * math.pi * math.sqrt(
            semi_major_axis**3 / gravitational_parameter
        )
        
        return period_seconds / 60  # Convert to minutes
    
    @staticmethod
    def calculate_orbital_velocity(altitude):
        """Calculate orbital velocity for given altitude"""
        earth_radius = 6371  # km
        gravitational_parameter = 398600.4418  # km³/s²
        
        orbital_radius = earth_radius + altitude
        velocity = math.sqrt(gravitational_parameter / orbital_radius)
        
        return velocity  # km/s
    
    @staticmethod
    def eci_to_geographic(x, y, z, timestamp):
        """Convert ECI coordinates to geographic coordinates"""
        # Simplified conversion - would need GMST for accurate conversion
        longitude = math.atan2(y, x) * 180 / math.pi
        latitude = math.asin(z / math.sqrt(x*x + y*y + z*z)) * 180 / math.pi
        altitude = math.sqrt(x*x + y*y + z*z) - 6371
        
        return latitude, longitude, altitude
