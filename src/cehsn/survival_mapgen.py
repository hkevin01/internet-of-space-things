"""
Survival Map Generator for CubeSat-Enabled Hybrid Survival Network (CEHSN)
Real-time map generator (hazard maps, resource maps, safe zone identification)
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class MapType(Enum):
    """Types of survival maps"""
    HAZARD = "hazard"
    RESOURCE = "resource"
    SAFE_ZONE = "safe_zone"
    EVACUATION_ROUTE = "evacuation_route"
    WEATHER = "weather"
    TERRAIN = "terrain"
    COMMUNICATION = "communication"
    COMPOSITE = "composite"


class HazardType(Enum):
    """Types of hazards to map"""
    FIRE = "fire"
    FLOOD = "flood"
    EARTHQUAKE = "earthquake"
    RADIATION = "radiation"
    TOXIC_GAS = "toxic_gas"
    EXTREME_WEATHER = "extreme_weather"
    UNSTABLE_TERRAIN = "unstable_terrain"
    WILDLIFE = "wildlife"


class ResourceType(Enum):
    """Types of resources to map"""
    WATER = "water"
    FOOD = "food"
    SHELTER = "shelter"
    MEDICAL = "medical"
    COMMUNICATION = "communication"
    FUEL = "fuel"
    TOOLS = "tools"
    EVACUATION_POINT = "evacuation_point"


class SafetyLevel(Enum):
    """Safety levels for zones"""
    SAFE = "safe"          # No known hazards
    CAUTION = "caution"    # Minor hazards present
    WARNING = "warning"    # Significant hazards
    DANGER = "danger"      # Major hazards
    CRITICAL = "critical"  # Life-threatening hazards


@dataclass
class GeographicBounds:
    """Geographic boundary definition"""
    north_lat: float
    south_lat: float
    east_lon: float
    west_lon: float
    
    def contains_point(self, lat: float, lon: float) -> bool:
        """Check if a point is within bounds"""
        return (self.south_lat <= lat <= self.north_lat and
                self.west_lon <= lon <= self.east_lon)
    
    def get_center(self) -> Tuple[float, float]:
        """Get center point of bounds"""
        center_lat = (self.north_lat + self.south_lat) / 2
        center_lon = (self.east_lon + self.west_lon) / 2
        return center_lat, center_lon


@dataclass
class MapPoint:
    """Individual point on a survival map"""
    latitude: float
    longitude: float
    elevation: Optional[float] = None
    value: float = 0.0  # Generic value (hazard level, resource quantity, etc.)
    attributes: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0  # 0.0-1.0 confidence in data accuracy
    source: str = "unknown"


@dataclass
class MapLayer:
    """A single layer of map data"""
    layer_id: str
    layer_type: MapType
    subtype: Optional[str] = None  # HazardType, ResourceType, etc.
    bounds: GeographicBounds = None
    resolution_meters: float = 100.0  # Grid resolution
    points: List[MapPoint] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    expiry_time: Optional[datetime] = None


@dataclass
class SurvivalMap:
    """Complete survival map with multiple layers"""
    map_id: str
    name: str
    bounds: GeographicBounds
    layers: Dict[str, MapLayer] = field(default_factory=dict)
    composite_score: Optional[np.ndarray] = None
    generation_parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def get_layer(self, layer_id: str) -> Optional[MapLayer]:
        """Get a specific layer"""
        return self.layers.get(layer_id)
    
    def add_layer(self, layer: MapLayer):
        """Add a layer to the map"""
        self.layers[layer.layer_id] = layer
        self.last_updated = datetime.utcnow()
    
    def remove_layer(self, layer_id: str) -> bool:
        """Remove a layer from the map"""
        if layer_id in self.layers:
            del self.layers[layer_id]
            self.last_updated = datetime.utcnow()
            return True
        return False


class SurvivalMapGenerator:
    """
    Real-time survival map generator
    Creates and maintains maps for emergency response and survival planning
    """
    
    def __init__(self, generator_id: str, data_sources: List[str] = None):
        self.generator_id = generator_id
        self.data_sources = data_sources or ["satellite", "ground_sensors", "crowd_source"]
        self.is_active = False
        
        # Map storage
        self.active_maps: Dict[str, SurvivalMap] = {}
        self.map_templates: Dict[str, Dict[str, Any]] = {}
        
        # Generation parameters
        self.default_resolution = 100.0  # meters
        self.default_bounds = GeographicBounds(
            north_lat=90.0, south_lat=-90.0,
            east_lon=180.0, west_lon=-180.0
        )
        self.max_maps = 100  # Maximum number of active maps
        
        # Cache for expensive operations
        self.terrain_cache: Dict[str, np.ndarray] = {}
        self.weather_cache: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.metrics = {
            "maps_generated": 0,
            "layers_created": 0,
            "updates_processed": 0,
            "cache_hits": 0,
            "average_generation_time_ms": 0.0
        }
        
        logger.info(f"Survival Map Generator {generator_id} initialized")
    
    async def start_generator(self) -> bool:
        """Start the map generator"""
        try:
            self.is_active = True
            await self._initialize_templates()
            await self._load_base_data()
            
            logger.info(f"Survival Map Generator {self.generator_id} started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start map generator: {e}")
            return False
    
    async def stop_generator(self) -> bool:
        """Stop the map generator"""
        self.is_active = False
        
        # Save active maps (if persistence is enabled)
        await self._save_active_maps()
        
        logger.info(f"Survival Map Generator {self.generator_id} stopped")
        return True
    
    async def generate_survival_map(self, bounds: GeographicBounds, 
                                  map_types: List[MapType],
                                  resolution_meters: float = None,
                                  name: str = None) -> Optional[str]:
        """Generate a new survival map"""
        if not self.is_active:
            logger.error("Map generator not active")
            return None
        
        start_time = datetime.utcnow()
        
        try:
            resolution = resolution_meters or self.default_resolution
            map_name = name or f"survival_map_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            map_id = f"map_{len(self.active_maps):04d}_{int(start_time.timestamp())}"
            
            # Create new survival map
            survival_map = SurvivalMap(
                map_id=map_id,
                name=map_name,
                bounds=bounds,
                generation_parameters={
                    "resolution_meters": resolution,
                    "requested_types": [t.value for t in map_types],
                    "data_sources": self.data_sources.copy()
                }
            )
            
            # Generate each requested layer
            for map_type in map_types:
                layer_id = f"{map_type.value}_layer"
                layer = await self._generate_layer(map_type, bounds, resolution, layer_id)
                if layer:
                    survival_map.add_layer(layer)
            
            # Generate composite score if multiple layers
            if len(survival_map.layers) > 1:
                survival_map.composite_score = await self._generate_composite_score(survival_map)
            
            # Store map
            self.active_maps[map_id] = survival_map
            
            # Cleanup old maps if needed
            if len(self.active_maps) > self.max_maps:
                await self._cleanup_old_maps()
            
            # Update metrics
            generation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_generation_metrics(generation_time)
            
            logger.info(f"Generated survival map {map_id} with {len(survival_map.layers)} layers "
                       f"in {generation_time:.1f}ms")
            
            return map_id
            
        except Exception as e:
            logger.error(f"Failed to generate survival map: {e}")
            return None
    
    async def update_map_layer(self, map_id: str, layer_id: str, 
                             new_data: List[MapPoint]) -> bool:
        """Update a specific layer with new data"""
        try:
            if map_id not in self.active_maps:
                logger.error(f"Map {map_id} not found")
                return False
            
            survival_map = self.active_maps[map_id]
            layer = survival_map.get_layer(layer_id)
            
            if not layer:
                logger.error(f"Layer {layer_id} not found in map {map_id}")
                return False
            
            # Update layer with new data
            layer.points.extend(new_data)
            layer.last_updated = datetime.utcnow()
            
            # Remove expired points if expiry is set
            if layer.expiry_time:
                current_time = datetime.utcnow()
                layer.points = [
                    point for point in layer.points
                    if current_time - point.timestamp < timedelta(hours=24)
                ]
            
            # Update composite score if needed
            if len(survival_map.layers) > 1:
                survival_map.composite_score = await self._generate_composite_score(survival_map)
            
            survival_map.last_updated = datetime.utcnow()
            self.metrics["updates_processed"] += 1
            
            logger.info(f"Updated layer {layer_id} in map {map_id} with {len(new_data)} new points")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update map layer: {e}")
            return False
    
    async def get_survival_map(self, map_id: str) -> Optional[SurvivalMap]:
        """Get a survival map by ID"""
        return self.active_maps.get(map_id)
    
    async def get_map_data_at_point(self, map_id: str, latitude: float, 
                                  longitude: float, radius_meters: float = 100.0) -> Dict[str, Any]:
        """Get map data at a specific point"""
        try:
            if map_id not in self.active_maps:
                return {}
            
            survival_map = self.active_maps[map_id]
            result = {"map_id": map_id, "query_point": {"lat": latitude, "lon": longitude}}
            
            # Get data from each layer
            for layer_id, layer in survival_map.layers.items():
                layer_data = self._get_layer_data_at_point(layer, latitude, longitude, radius_meters)
                result[layer_id] = layer_data
            
            # Include composite score if available
            if survival_map.composite_score is not None:
                composite_value = self._get_composite_score_at_point(
                    survival_map, latitude, longitude
                )
                result["composite_score"] = composite_value
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get map data at point: {e}")
            return {}
    
    async def find_safe_zones(self, map_id: str, min_safety_radius_meters: float = 500.0,
                            safety_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Find safe zones in the map"""
        try:
            if map_id not in self.active_maps:
                return []
            
            survival_map = self.active_maps[map_id]
            safe_zones = []
            
            # Use composite score if available, otherwise use hazard layers
            if survival_map.composite_score is not None:
                safe_zones = self._find_safe_zones_from_composite(
                    survival_map, min_safety_radius_meters, safety_threshold
                )
            else:
                # Find safe zones from hazard layers
                hazard_layers = [
                    layer for layer in survival_map.layers.values()
                    if layer.layer_type == MapType.HAZARD
                ]
                if hazard_layers:
                    safe_zones = self._find_safe_zones_from_hazards(
                        hazard_layers, survival_map.bounds, min_safety_radius_meters, safety_threshold
                    )
            
            logger.info(f"Found {len(safe_zones)} safe zones in map {map_id}")
            return safe_zones
            
        except Exception as e:
            logger.error(f"Failed to find safe zones: {e}")
            return []
    
    async def generate_evacuation_routes(self, map_id: str, start_points: List[Tuple[float, float]],
                                       end_points: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
        """Generate evacuation routes avoiding hazards"""
        try:
            if map_id not in self.active_maps:
                return []
            
            survival_map = self.active_maps[map_id]
            routes = []
            
            for start_lat, start_lon in start_points:
                for end_lat, end_lon in end_points:
                    route = await self._calculate_safe_route(
                        survival_map, start_lat, start_lon, end_lat, end_lon
                    )
                    if route:
                        routes.append(route)
            
            logger.info(f"Generated {len(routes)} evacuation routes for map {map_id}")
            return routes
            
        except Exception as e:
            logger.error(f"Failed to generate evacuation routes: {e}")
            return []
    
    def get_generator_status(self) -> Dict[str, Any]:
        """Get current status of the map generator"""
        return {
            "generator_id": self.generator_id,
            "is_active": self.is_active,
            "active_maps": len(self.active_maps),
            "data_sources": self.data_sources,
            "cache_size": {
                "terrain": len(self.terrain_cache),
                "weather": len(self.weather_cache)
            },
            "metrics": self.metrics.copy()
        }
    
    async def export_map(self, map_id: str, format_type: str = "geojson") -> Optional[str]:
        """Export map to various formats"""
        try:
            if map_id not in self.active_maps:
                logger.error(f"Map {map_id} not found")
                return None
            
            survival_map = self.active_maps[map_id]
            
            if format_type == "geojson":
                return self._export_to_geojson(survival_map)
            elif format_type == "json":
                return json.dumps(survival_map.__dict__, default=str, indent=2)
            else:
                logger.error(f"Unsupported export format: {format_type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to export map: {e}")
            return None
    
    # Private helper methods
    
    async def _generate_layer(self, map_type: MapType, bounds: GeographicBounds,
                            resolution: float, layer_id: str) -> Optional[MapLayer]:
        """Generate a single map layer"""
        try:
            if map_type == MapType.HAZARD:
                return await self._generate_hazard_layer(bounds, resolution, layer_id)
            elif map_type == MapType.RESOURCE:
                return await self._generate_resource_layer(bounds, resolution, layer_id)
            elif map_type == MapType.SAFE_ZONE:
                return await self._generate_safe_zone_layer(bounds, resolution, layer_id)
            elif map_type == MapType.TERRAIN:
                return await self._generate_terrain_layer(bounds, resolution, layer_id)
            elif map_type == MapType.WEATHER:
                return await self._generate_weather_layer(bounds, resolution, layer_id)
            else:
                logger.warning(f"Unknown map type: {map_type}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate {map_type.value} layer: {e}")
            return None
    
    async def _generate_hazard_layer(self, bounds: GeographicBounds, 
                                   resolution: float, layer_id: str) -> MapLayer:
        """Generate hazard map layer"""
        layer = MapLayer(
            layer_id=layer_id,
            layer_type=MapType.HAZARD,
            bounds=bounds,
            resolution_meters=resolution
        )
        
        # Generate grid points
        points = []
        lat_step = resolution / 111000.0  # Approximate degrees per meter
        lon_step = resolution / (111000.0 * np.cos(np.radians((bounds.north_lat + bounds.south_lat) / 2)))
        
        lat = bounds.south_lat
        while lat <= bounds.north_lat:
            lon = bounds.west_lon
            while lon <= bounds.east_lon:
                # Simulate hazard detection (in real implementation, use actual sensor data)
                hazard_level = self._simulate_hazard_at_point(lat, lon)
                
                if hazard_level > 0.1:  # Only include points with significant hazards
                    point = MapPoint(
                        latitude=lat,
                        longitude=lon,
                        value=hazard_level,
                        attributes={"hazard_types": self._identify_hazard_types(lat, lon)},
                        source="simulation"
                    )
                    points.append(point)
                
                lon += lon_step
            lat += lat_step
        
        layer.points = points
        self.metrics["layers_created"] += 1
        
        return layer
    
    async def _generate_resource_layer(self, bounds: GeographicBounds,
                                     resolution: float, layer_id: str) -> MapLayer:
        """Generate resource map layer"""
        layer = MapLayer(
            layer_id=layer_id,
            layer_type=MapType.RESOURCE,
            bounds=bounds,
            resolution_meters=resolution
        )
        
        # Simulate resource locations
        points = []
        num_resources = max(5, int((bounds.north_lat - bounds.south_lat) * 
                                 (bounds.east_lon - bounds.west_lon) * 100))
        
        for _ in range(num_resources):
            lat = np.random.uniform(bounds.south_lat, bounds.north_lat)
            lon = np.random.uniform(bounds.west_lon, bounds.east_lon)
            
            resource_types = np.random.choice(
                [rt.value for rt in ResourceType], 
                size=np.random.randint(1, 3), 
                replace=False
            )
            
            availability = np.random.uniform(0.1, 1.0)
            
            point = MapPoint(
                latitude=lat,
                longitude=lon,
                value=availability,
                attributes={
                    "resource_types": resource_types.tolist(),
                    "capacity": np.random.randint(10, 100)
                },
                source="simulation"
            )
            points.append(point)
        
        layer.points = points
        self.metrics["layers_created"] += 1
        
        return layer
    
    async def _generate_safe_zone_layer(self, bounds: GeographicBounds,
                                      resolution: float, layer_id: str) -> MapLayer:
        """Generate safe zone layer"""
        layer = MapLayer(
            layer_id=layer_id,
            layer_type=MapType.SAFE_ZONE,
            bounds=bounds,
            resolution_meters=resolution
        )
        
        # Find areas with low hazard levels
        points = []
        lat_step = resolution / 111000.0
        lon_step = resolution / (111000.0 * np.cos(np.radians((bounds.north_lat + bounds.south_lat) / 2)))
        
        lat = bounds.south_lat
        while lat <= bounds.north_lat:
            lon = bounds.west_lon
            while lon <= bounds.east_lon:
                safety_score = 1.0 - self._simulate_hazard_at_point(lat, lon)
                
                if safety_score > 0.6:  # Only include relatively safe areas
                    safety_level = self._determine_safety_level(safety_score)
                    
                    point = MapPoint(
                        latitude=lat,
                        longitude=lon,
                        value=safety_score,
                        attributes={
                            "safety_level": safety_level.value,
                            "capacity": int(safety_score * 100)
                        },
                        source="analysis"
                    )
                    points.append(point)
                
                lon += lon_step
            lat += lat_step
        
        layer.points = points
        self.metrics["layers_created"] += 1
        
        return layer
    
    async def _generate_terrain_layer(self, bounds: GeographicBounds,
                                     resolution: float, layer_id: str) -> MapLayer:
        """Generate terrain layer"""
        cache_key = f"{bounds.south_lat}_{bounds.north_lat}_{bounds.west_lon}_{bounds.east_lon}_{resolution}"
        
        if cache_key in self.terrain_cache:
            self.metrics["cache_hits"] += 1
        
        layer = MapLayer(
            layer_id=layer_id,
            layer_type=MapType.TERRAIN,
            bounds=bounds,
            resolution_meters=resolution
        )
        
        # Generate terrain data (simplified)
        points = []
        lat_step = resolution / 111000.0
        lon_step = resolution / (111000.0 * np.cos(np.radians((bounds.north_lat + bounds.south_lat) / 2)))
        
        lat = bounds.south_lat
        while lat <= bounds.north_lat:
            lon = bounds.west_lon
            while lon <= bounds.east_lon:
                elevation = self._simulate_elevation(lat, lon)
                slope = self._calculate_slope(lat, lon, lat_step, lon_step)
                
                point = MapPoint(
                    latitude=lat,
                    longitude=lon,
                    elevation=elevation,
                    value=slope,
                    attributes={
                        "terrain_type": self._classify_terrain(elevation, slope),
                        "traversability": self._calculate_traversability(slope)
                    },
                    source="simulation"
                )
                points.append(point)
                
                lon += lon_step
            lat += lat_step
        
        layer.points = points
        self.metrics["layers_created"] += 1
        
        return layer
    
    async def _generate_weather_layer(self, bounds: GeographicBounds,
                                     resolution: float, layer_id: str) -> MapLayer:
        """Generate weather layer"""
        layer = MapLayer(
            layer_id=layer_id,
            layer_type=MapType.WEATHER,
            bounds=bounds,
            resolution_meters=resolution,
            expiry_time=datetime.utcnow() + timedelta(hours=6)  # Weather data expires
        )
        
        # Generate weather data
        points = []
        lat_step = resolution * 2 / 111000.0  # Lower resolution for weather
        lon_step = resolution * 2 / (111000.0 * np.cos(np.radians((bounds.north_lat + bounds.south_lat) / 2)))
        
        lat = bounds.south_lat
        while lat <= bounds.north_lat:
            lon = bounds.west_lon
            while lon <= bounds.east_lon:
                weather_conditions = self._simulate_weather(lat, lon)
                
                point = MapPoint(
                    latitude=lat,
                    longitude=lon,
                    value=weather_conditions["severity"],
                    attributes=weather_conditions,
                    source="weather_simulation"
                )
                points.append(point)
                
                lon += lon_step
            lat += lat_step
        
        layer.points = points
        self.metrics["layers_created"] += 1
        
        return layer
    
    async def _generate_composite_score(self, survival_map: SurvivalMap) -> np.ndarray:
        """Generate composite survival score combining all layers"""
        # This is a simplified implementation
        # In reality, this would use sophisticated GIS algorithms
        
        bounds = survival_map.bounds
        resolution = min(layer.resolution_meters for layer in survival_map.layers.values())
        
        # Create grid
        lat_range = bounds.north_lat - bounds.south_lat
        lon_range = bounds.east_lon - bounds.west_lon
        
        grid_height = int(lat_range * 111000 / resolution)
        grid_width = int(lon_range * 111000 / resolution)
        
        composite_grid = np.zeros((grid_height, grid_width))
        
        # Combine layers with different weights
        layer_weights = {
            MapType.HAZARD: -0.4,  # Negative because hazards reduce safety
            MapType.RESOURCE: 0.3,
            MapType.SAFE_ZONE: 0.5,
            MapType.WEATHER: -0.2,
            MapType.TERRAIN: 0.1
        }
        
        for layer in survival_map.layers.values():
            weight = layer_weights.get(layer.layer_type, 0.1)
            
            for point in layer.points:
                # Convert lat/lon to grid coordinates
                grid_lat = int((point.latitude - bounds.south_lat) / lat_range * grid_height)
                grid_lon = int((point.longitude - bounds.west_lon) / lon_range * grid_width)
                
                if 0 <= grid_lat < grid_height and 0 <= grid_lon < grid_width:
                    composite_grid[grid_lat, grid_lon] += point.value * weight
        
        # Normalize to 0-1 range
        if composite_grid.max() > composite_grid.min():
            composite_grid = (composite_grid - composite_grid.min()) / (composite_grid.max() - composite_grid.min())
        
        return composite_grid
    
    # Simulation methods (replace with real data in production)
    
    def _simulate_hazard_at_point(self, lat: float, lon: float) -> float:
        """Simulate hazard level at a point"""
        # Use noise functions to create realistic hazard patterns
        noise_value = np.sin(lat * 10) * np.cos(lon * 10) + np.random.normal(0, 0.1)
        hazard_level = max(0.0, min(1.0, (noise_value + 1) / 2))
        return hazard_level
    
    def _identify_hazard_types(self, lat: float, lon: float) -> List[str]:
        """Identify types of hazards at a point"""
        hazards = []
        
        # Simulate different hazard types based on location
        if abs(lat) < 30:  # Tropical regions
            if np.random.random() < 0.3:
                hazards.append(HazardType.EXTREME_WEATHER.value)
        
        if lat > 50 or lat < -50:  # High latitudes
            if np.random.random() < 0.2:
                hazards.append(HazardType.EXTREME_WEATHER.value)
        
        # Random other hazards
        all_hazards = [h.value for h in HazardType]
        num_hazards = np.random.poisson(0.5)  # Average 0.5 hazards per point
        
        additional_hazards = np.random.choice(all_hazards, size=min(num_hazards, 3), replace=False)
        hazards.extend(additional_hazards)
        
        return list(set(hazards))  # Remove duplicates
    
    def _simulate_elevation(self, lat: float, lon: float) -> float:
        """Simulate elevation at a point"""
        # Simple elevation model
        base_elevation = 1000 * abs(np.sin(lat * 0.1) * np.cos(lon * 0.1))
        noise = np.random.normal(0, 100)
        return max(0, base_elevation + noise)
    
    def _calculate_slope(self, lat: float, lon: float, lat_step: float, lon_step: float) -> float:
        """Calculate terrain slope"""
        # Simplified slope calculation
        elev_center = self._simulate_elevation(lat, lon)
        elev_north = self._simulate_elevation(lat + lat_step, lon)
        elev_east = self._simulate_elevation(lat, lon + lon_step)
        
        slope_ns = abs(elev_north - elev_center) / (lat_step * 111000)
        slope_ew = abs(elev_east - elev_center) / (lon_step * 111000)
        
        return np.sqrt(slope_ns**2 + slope_ew**2)
    
    def _classify_terrain(self, elevation: float, slope: float) -> str:
        """Classify terrain type"""
        if elevation < 100:
            return "lowland"
        elif elevation < 1000:
            if slope < 0.1:
                return "hills"
            else:
                return "steep_hills"
        else:
            if slope < 0.2:
                return "plateau"
            else:
                return "mountains"
    
    def _calculate_traversability(self, slope: float) -> float:
        """Calculate how easily terrain can be traversed"""
        if slope < 0.05:
            return 1.0  # Easy
        elif slope < 0.15:
            return 0.7  # Moderate
        elif slope < 0.3:
            return 0.4  # Difficult
        else:
            return 0.1  # Very difficult
    
    def _simulate_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """Simulate weather conditions"""
        # Simplified weather simulation
        base_temp = 20 - abs(lat) * 0.5  # Colder at poles
        temperature = base_temp + np.random.normal(0, 5)
        
        humidity = np.random.uniform(0.2, 0.9)
        wind_speed = np.random.exponential(10)  # km/h
        precipitation = max(0, np.random.normal(0, 5))  # mm/h
        
        # Calculate severity based on extreme conditions
        severity = 0.0
        if temperature < -10 or temperature > 40:
            severity += 0.3
        if wind_speed > 50:
            severity += 0.4
        if precipitation > 20:
            severity += 0.3
        
        return {
            "temperature_c": temperature,
            "humidity": humidity,
            "wind_speed_kmh": wind_speed,
            "precipitation_mmh": precipitation,
            "severity": min(1.0, severity)
        }
    
    def _determine_safety_level(self, safety_score: float) -> SafetyLevel:
        """Determine safety level from score"""
        if safety_score >= 0.9:
            return SafetyLevel.SAFE
        elif safety_score >= 0.7:
            return SafetyLevel.CAUTION
        elif safety_score >= 0.5:
            return SafetyLevel.WARNING
        elif safety_score >= 0.3:
            return SafetyLevel.DANGER
        else:
            return SafetyLevel.CRITICAL
    
    # Helper methods for map operations
    
    def _get_layer_data_at_point(self, layer: MapLayer, lat: float, lon: float,
                               radius: float) -> Dict[str, Any]:
        """Get layer data near a specific point"""
        nearby_points = []
        
        for point in layer.points:
            distance = self._calculate_distance(lat, lon, point.latitude, point.longitude)
            if distance <= radius:
                nearby_points.append({
                    "distance_m": distance,
                    "value": point.value,
                    "attributes": point.attributes,
                    "timestamp": point.timestamp.isoformat()
                })
        
        if not nearby_points:
            return {"count": 0, "points": []}
        
        # Sort by distance
        nearby_points.sort(key=lambda p: p["distance_m"])
        
        return {
            "count": len(nearby_points),
            "closest_value": nearby_points[0]["value"],
            "average_value": sum(p["value"] for p in nearby_points) / len(nearby_points),
            "points": nearby_points[:10]  # Limit to 10 closest points
        }
    
    def _get_composite_score_at_point(self, survival_map: SurvivalMap, 
                                    lat: float, lon: float) -> Optional[float]:
        """Get composite score at a specific point"""
        if survival_map.composite_score is None:
            return None
        
        bounds = survival_map.bounds
        grid = survival_map.composite_score
        
        # Convert lat/lon to grid coordinates
        lat_ratio = (lat - bounds.south_lat) / (bounds.north_lat - bounds.south_lat)
        lon_ratio = (lon - bounds.west_lon) / (bounds.east_lon - bounds.west_lon)
        
        grid_lat = int(lat_ratio * grid.shape[0])
        grid_lon = int(lon_ratio * grid.shape[1])
        
        if 0 <= grid_lat < grid.shape[0] and 0 <= grid_lon < grid.shape[1]:
            return float(grid[grid_lat, grid_lon])
        
        return None
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters"""
        # Haversine formula
        R = 6371000  # Earth radius in meters
        
        lat1_rad = np.radians(lat1)
        lon1_rad = np.radians(lon1)
        lat2_rad = np.radians(lat2)
        lon2_rad = np.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        
        return R * c
    
    def _find_safe_zones_from_composite(self, survival_map: SurvivalMap,
                                      min_radius: float, threshold: float) -> List[Dict[str, Any]]:
        """Find safe zones from composite score"""
        safe_zones = []
        grid = survival_map.composite_score
        bounds = survival_map.bounds
        
        # Find local maxima above threshold
        for i in range(1, grid.shape[0] - 1):
            for j in range(1, grid.shape[1] - 1):
                if grid[i, j] >= threshold:
                    # Check if it's a local maximum
                    is_maximum = True
                    for di in [-1, 0, 1]:
                        for dj in [-1, 0, 1]:
                            if grid[i + di, j + dj] > grid[i, j]:
                                is_maximum = False
                                break
                        if not is_maximum:
                            break
                    
                    if is_maximum:
                        # Convert grid coordinates back to lat/lon
                        lat = bounds.south_lat + (i / grid.shape[0]) * (bounds.north_lat - bounds.south_lat)
                        lon = bounds.west_lon + (j / grid.shape[1]) * (bounds.east_lon - bounds.west_lon)
                        
                        safe_zones.append({
                            "latitude": lat,
                            "longitude": lon,
                            "safety_score": float(grid[i, j]),
                            "estimated_radius_m": min_radius,
                            "capacity_estimate": int(grid[i, j] * 100)
                        })
        
        return safe_zones
    
    def _find_safe_zones_from_hazards(self, hazard_layers: List[MapLayer],
                                    bounds: GeographicBounds, min_radius: float,
                                    threshold: float) -> List[Dict[str, Any]]:
        """Find safe zones by avoiding hazard areas"""
        # Simplified implementation - find areas with lowest hazard density
        safe_zones = []
        
        # Create a grid to accumulate hazard levels
        grid_size = 50
        hazard_grid = np.zeros((grid_size, grid_size))
        
        for layer in hazard_layers:
            for point in layer.points:
                # Convert to grid coordinates
                lat_idx = int((point.latitude - bounds.south_lat) / 
                            (bounds.north_lat - bounds.south_lat) * grid_size)
                lon_idx = int((point.longitude - bounds.west_lon) / 
                            (bounds.east_lon - bounds.west_lon) * grid_size)
                
                if 0 <= lat_idx < grid_size and 0 <= lon_idx < grid_size:
                    hazard_grid[lat_idx, lon_idx] += point.value
        
        # Find areas with low hazard levels
        safe_threshold = np.percentile(hazard_grid.flatten(), 20)  # Bottom 20%
        
        for i in range(grid_size):
            for j in range(grid_size):
                if hazard_grid[i, j] <= safe_threshold:
                    lat = bounds.south_lat + (i / grid_size) * (bounds.north_lat - bounds.south_lat)
                    lon = bounds.west_lon + (j / grid_size) * (bounds.east_lon - bounds.west_lon)
                    
                    safety_score = 1.0 - (hazard_grid[i, j] / hazard_grid.max())
                    
                    safe_zones.append({
                        "latitude": lat,
                        "longitude": lon,
                        "safety_score": safety_score,
                        "estimated_radius_m": min_radius,
                        "capacity_estimate": int(safety_score * 50)
                    })
        
        return safe_zones
    
    async def _calculate_safe_route(self, survival_map: SurvivalMap,
                                  start_lat: float, start_lon: float,
                                  end_lat: float, end_lon: float) -> Optional[Dict[str, Any]]:
        """Calculate a safe route between two points"""
        # Simplified A* pathfinding avoiding hazards
        # This is a basic implementation - production would use proper GIS routing
        
        route_points = []
        
        # Create waypoints along the route
        num_waypoints = 10
        for i in range(num_waypoints + 1):
            t = i / num_waypoints
            waypoint_lat = start_lat + t * (end_lat - start_lat)
            waypoint_lon = start_lon + t * (end_lon - start_lon)
            
            # Get safety score at this point
            safety_data = await self.get_map_data_at_point(
                survival_map.map_id, waypoint_lat, waypoint_lon, 100.0
            )
            
            composite_score = safety_data.get("composite_score", 0.5)
            
            route_points.append({
                "latitude": waypoint_lat,
                "longitude": waypoint_lon,
                "safety_score": composite_score,
                "estimated_travel_time_minutes": 5  # Simplified
            })
        
        # Calculate overall route metrics
        total_distance = sum(
            self._calculate_distance(
                route_points[i]["latitude"], route_points[i]["longitude"],
                route_points[i+1]["latitude"], route_points[i+1]["longitude"]
            )
            for i in range(len(route_points) - 1)
        )
        
        average_safety = sum(p["safety_score"] for p in route_points) / len(route_points)
        total_time = sum(p["estimated_travel_time_minutes"] for p in route_points)
        
        return {
            "start": {"latitude": start_lat, "longitude": start_lon},
            "end": {"latitude": end_lat, "longitude": end_lon},
            "waypoints": route_points,
            "total_distance_m": total_distance,
            "average_safety_score": average_safety,
            "estimated_total_time_minutes": total_time,
            "route_quality": "safe" if average_safety > 0.7 else "moderate" if average_safety > 0.4 else "risky"
        }
    
    def _export_to_geojson(self, survival_map: SurvivalMap) -> str:
        """Export map to GeoJSON format"""
        features = []
        
        for layer_id, layer in survival_map.layers.items():
            for point in layer.points:
                feature = {
                    "type": "Feature",
                    "properties": {
                        "layer_id": layer_id,
                        "layer_type": layer.layer_type.value,
                        "value": point.value,
                        "timestamp": point.timestamp.isoformat(),
                        "source": point.source,
                        **point.attributes
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [point.longitude, point.latitude]
                    }
                }
                features.append(feature)
        
        geojson = {
            "type": "FeatureCollection",
            "properties": {
                "map_id": survival_map.map_id,
                "name": survival_map.name,
                "created_at": survival_map.created_at.isoformat(),
                "bounds": {
                    "north": survival_map.bounds.north_lat,
                    "south": survival_map.bounds.south_lat,
                    "east": survival_map.bounds.east_lon,
                    "west": survival_map.bounds.west_lon
                }
            },
            "features": features
        }
        
        return json.dumps(geojson, indent=2)
    
    async def _initialize_templates(self):
        """Initialize map templates"""
        self.map_templates = {
            "emergency_response": {
                "types": [MapType.HAZARD, MapType.RESOURCE, MapType.SAFE_ZONE],
                "resolution": 50.0,
                "priority": "safety"
            },
            "evacuation_planning": {
                "types": [MapType.HAZARD, MapType.EVACUATION_ROUTE, MapType.SAFE_ZONE],
                "resolution": 100.0,
                "priority": "routes"
            },
            "resource_management": {
                "types": [MapType.RESOURCE, MapType.TERRAIN, MapType.WEATHER],
                "resolution": 200.0,
                "priority": "resources"
            }
        }
    
    async def _load_base_data(self):
        """Load base geographic and environmental data"""
        # In a real implementation, this would load:
        # - Digital elevation models
        # - Land use data
        # - Infrastructure maps
        # - Historical hazard data
        pass
    
    async def _save_active_maps(self):
        """Save active maps to persistent storage"""
        # Implementation would save to database or file system
        pass
    
    async def _cleanup_old_maps(self):
        """Remove old maps to free memory"""
        if len(self.active_maps) <= self.max_maps:
            return
        
        # Sort by last updated time and remove oldest
        sorted_maps = sorted(
            self.active_maps.items(),
            key=lambda x: x[1].last_updated
        )
        
        maps_to_remove = len(self.active_maps) - self.max_maps + 10  # Remove extra for buffer
        
        for i in range(maps_to_remove):
            map_id = sorted_maps[i][0]
            del self.active_maps[map_id]
            logger.info(f"Removed old map {map_id}")
    
    def _update_generation_metrics(self, generation_time_ms: float):
        """Update performance metrics"""
        self.metrics["maps_generated"] += 1
        
        # Update average generation time
        total_maps = self.metrics["maps_generated"]
        current_avg = self.metrics["average_generation_time_ms"]
        
        self.metrics["average_generation_time_ms"] = \
            (current_avg * (total_maps - 1) + generation_time_ms) / total_maps
