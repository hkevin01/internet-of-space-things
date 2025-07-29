"""
Space Network Core Management System
Handles network topology, routing, and communication coordination for spacecraft constellation
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class NetworkStatus(Enum):
    ACTIVE = "active"
    DEGRADED = "degraded" 
    OFFLINE = "offline"
    EMERGENCY = "emergency"


class CommunicationMode(Enum):
    DEEP_SPACE = "deep_space"
    INTER_SATELLITE = "inter_satellite"
    GROUND_STATION = "ground_station"
    EMERGENCY_BEACON = "emergency_beacon"


@dataclass
class NetworkNode:
    """Represents a node in the space network"""
    node_id: str
    name: str
    node_type: str  # "spacecraft", "satellite", "ground_station"
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    status: NetworkStatus = NetworkStatus.ACTIVE
    communication_modes: List[CommunicationMode] = field(default_factory=list)
    last_contact: Optional[datetime] = None
    signal_strength: float = 0.0
    bandwidth_capacity: float = 0.0  # Mbps
    current_load: float = 0.0
    priority_level: int = 1  # 1-10, higher is more critical


@dataclass
class CommunicationLink:
    """Represents a communication link between two nodes"""
    link_id: str
    source_node: str
    target_node: str
    link_type: CommunicationMode
    established_at: datetime
    signal_strength: float
    bandwidth: float
    latency: float  # milliseconds
    packet_loss: float  # percentage
    is_encrypted: bool = True
    quality_score: float = 1.0


class SpaceNetwork:
    """
    Core space network management system for IoST platform
    Manages constellation topology, routing, and communication coordination
    """
    
    def __init__(self, network_name: str = "IoST-Network"):
        self.network_name = network_name
        self.nodes: Dict[str, NetworkNode] = {}
        self.links: Dict[str, CommunicationLink] = {}
        self.routing_table: Dict[str, Dict[str, str]] = {}
        self.network_status = NetworkStatus.ACTIVE
        self.emergency_protocols_active = False
        self.total_data_transmitted = 0.0  # GB
        self.network_uptime = datetime.utcnow()
        
        # Configuration
        self.max_hop_count = 5
        self.link_timeout = timedelta(minutes=30)
        self.health_check_interval = 60  # seconds
        
        logger.info(f"Space Network '{network_name}' initialized")
    
    async def add_node(self, node: NetworkNode) -> bool:
        """Add a new node to the space network"""
        try:
            if node.node_id in self.nodes:
                logger.warning(f"Node {node.node_id} already exists in network")
                return False
            
            self.nodes[node.node_id] = node
            node.last_contact = datetime.utcnow()
            
            # Initialize routing for new node
            await self._update_routing_table()
            
            logger.info(f"Added node {node.node_id} ({node.name}) to network")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add node {node.node_id}: {e}")
            return False
    
    async def establish_link(self, source_id: str, target_id: str, 
                           link_type: CommunicationMode) -> Optional[CommunicationLink]:
        """Establish communication link between two nodes"""
        try:
            if source_id not in self.nodes or target_id not in self.nodes:
                logger.error(f"Cannot establish link: node not found")
                return None
            
            source_node = self.nodes[source_id]
            target_node = self.nodes[target_id]
            
            # Calculate link parameters based on distance and node capabilities
            distance = np.linalg.norm(source_node.position - target_node.position)
            signal_strength = self._calculate_signal_strength(distance, link_type)
            bandwidth = self._calculate_bandwidth(signal_strength, link_type)
            latency = self._calculate_latency(distance, link_type)
            
            link = CommunicationLink(
                link_id=f"{source_id}-{target_id}-{link_type.value}",
                source_node=source_id,
                target_node=target_id,
                link_type=link_type,
                established_at=datetime.utcnow(),
                signal_strength=signal_strength,
                bandwidth=bandwidth,
                latency=latency,
                packet_loss=0.0,
                quality_score=signal_strength
            )
            
            self.links[link.link_id] = link
            
            # Update routing table
            await self._update_routing_table()
            
            logger.info(f"Established {link_type.value} link: {source_id} -> {target_id}")
            return link
            
        except Exception as e:
            logger.error(f"Failed to establish link {source_id}->{target_id}: {e}")
            return None
    
    async def find_optimal_route(self, source_id: str, target_id: str) -> List[str]:
        """Find optimal communication route between nodes using Dijkstra's algorithm"""
        if source_id not in self.nodes or target_id not in self.nodes:
            return []
        
        if source_id == target_id:
            return [source_id]
        
        # Dijkstra's algorithm implementation for space network routing
        distances = {node_id: float('infinity') for node_id in self.nodes}
        distances[source_id] = 0
        previous = {}
        unvisited = set(self.nodes.keys())
        
        while unvisited:
            current = min(unvisited, key=lambda x: distances[x])
            
            if distances[current] == float('infinity'):
                break
                
            if current == target_id:
                break
            
            unvisited.remove(current)
            
            # Check all links from current node
            for link in self.links.values():
                if link.source_node == current and link.target_node in unvisited:
                    # Weight based on latency and quality
                    weight = link.latency * (2 - link.quality_score)
                    alt = distances[current] + weight
                    
                    if alt < distances[link.target_node]:
                        distances[link.target_node] = alt
                        previous[link.target_node] = current
        
        # Reconstruct path
        if target_id not in previous and target_id != source_id:
            return []  # No path found
        
        path = []
        current = target_id
        while current is not None:
            path.append(current)
            current = previous.get(current)
        
        return path[::-1]  # Reverse to get source->target path
    
    async def transmit_data(self, source_id: str, target_id: str, 
                          data: Dict[str, Any], priority: int = 1) -> bool:
        """Transmit data through the space network"""
        try:
            route = await self.find_optimal_route(source_id, target_id)
            if not route:
                logger.error(f"No route found from {source_id} to {target_id}")
                return False
            
            # Simulate data transmission through route
            data_size = len(json.dumps(data).encode()) / (1024 * 1024)  # MB
            transmission_time = datetime.utcnow()
            
            for i in range(len(route) - 1):
                current_node = route[i]
                next_node = route[i + 1]
                
                # Find link between nodes
                link = None
                for l in self.links.values():
                    if l.source_node == current_node and l.target_node == next_node:
                        link = l
                        break
                
                if not link:
                    logger.error(f"No link found between {current_node} and {next_node}")
                    return False
                
                # Update link statistics
                link.packet_loss = min(link.packet_loss + 0.001, 0.1)  # Slight degradation
                
                # Update node load
                if current_node in self.nodes:
                    self.nodes[current_node].current_load += data_size
            
            self.total_data_transmitted += data_size
            
            logger.info(f"Data transmitted from {source_id} to {target_id} via {len(route)} hops")
            return True
            
        except Exception as e:
            logger.error(f"Data transmission failed: {e}")
            return False
    
    async def activate_emergency_protocol(self, emergency_type: str, affected_nodes: List[str]):
        """Activate emergency communication protocols"""
        self.emergency_protocols_active = True
        self.network_status = NetworkStatus.EMERGENCY
        
        logger.critical(f"Emergency protocol activated: {emergency_type}")
        
        # Prioritize emergency communications
        for node_id in affected_nodes:
            if node_id in self.nodes:
                self.nodes[node_id].priority_level = 10
        
        # Establish emergency beacon links
        for node_id in affected_nodes:
            for other_id in self.nodes:
                if other_id != node_id and other_id not in affected_nodes:
                    await self.establish_link(node_id, other_id, CommunicationMode.EMERGENCY_BEACON)
    
    async def monitor_network_health(self) -> Dict[str, Any]:
        """Monitor overall network health and performance"""
        active_nodes = sum(1 for node in self.nodes.values() if node.status == NetworkStatus.ACTIVE)
        total_nodes = len(self.nodes)
        active_links = sum(1 for link in self.links.values() if 
                          datetime.utcnow() - link.established_at < self.link_timeout)
        total_links = len(self.links)
        
        avg_signal_strength = np.mean([link.signal_strength for link in self.links.values()]) if self.links else 0
        avg_latency = np.mean([link.latency for link in self.links.values()]) if self.links else 0
        total_bandwidth = sum(link.bandwidth for link in self.links.values())
        
        uptime_hours = (datetime.utcnow() - self.network_uptime).total_seconds() / 3600
        
        health_metrics = {
            "network_status": self.network_status.value,
            "active_nodes": active_nodes,
            "total_nodes": total_nodes,
            "node_availability": active_nodes / total_nodes if total_nodes > 0 else 0,
            "active_links": active_links,
            "total_links": total_links,
            "link_availability": active_links / total_links if total_links > 0 else 0,
            "avg_signal_strength": avg_signal_strength,
            "avg_latency_ms": avg_latency,
            "total_bandwidth_mbps": total_bandwidth,
            "data_transmitted_gb": self.total_data_transmitted / 1024,
            "uptime_hours": uptime_hours,
            "emergency_active": self.emergency_protocols_active
        }
        
        return health_metrics
    
    def _calculate_signal_strength(self, distance: float, link_type: CommunicationMode) -> float:
        """Calculate signal strength based on distance and communication type"""
        # Space communication signal strength calculation (simplified)
        base_strength = {
            CommunicationMode.DEEP_SPACE: 0.6,
            CommunicationMode.INTER_SATELLITE: 0.9,
            CommunicationMode.GROUND_STATION: 0.8,
            CommunicationMode.EMERGENCY_BEACON: 0.7
        }
        
        # Signal degrades with distance (free space path loss)
        distance_km = distance / 1000  # Convert to km
        if distance_km == 0:
            return base_strength.get(link_type, 0.5)
        
        path_loss_db = 20 * np.log10(distance_km) + 20 * np.log10(2.4e9) - 147.55  # 2.4 GHz
        strength = base_strength.get(link_type, 0.5) * (10 ** (-path_loss_db / 20))
        
        return max(0.1, min(1.0, strength))
    
    def _calculate_bandwidth(self, signal_strength: float, link_type: CommunicationMode) -> float:
        """Calculate available bandwidth based on signal strength"""
        max_bandwidth = {
            CommunicationMode.DEEP_SPACE: 10.0,  # Mbps
            CommunicationMode.INTER_SATELLITE: 100.0,
            CommunicationMode.GROUND_STATION: 50.0,
            CommunicationMode.EMERGENCY_BEACON: 5.0
        }
        
        return max_bandwidth.get(link_type, 10.0) * signal_strength
    
    def _calculate_latency(self, distance: float, link_type: CommunicationMode) -> float:
        """Calculate communication latency based on distance"""
        # Speed of light: ~300,000 km/s
        light_speed = 3e8  # m/s
        propagation_delay = (distance / light_speed) * 1000  # Convert to milliseconds
        
        # Add processing delays
        processing_delay = {
            CommunicationMode.DEEP_SPACE: 100,  # ms
            CommunicationMode.INTER_SATELLITE: 10,
            CommunicationMode.GROUND_STATION: 50,
            CommunicationMode.EMERGENCY_BEACON: 20
        }
        
        return propagation_delay + processing_delay.get(link_type, 50)
    
    async def _update_routing_table(self):
        """Update network routing table using current topology"""
        # Clear existing routing table
        self.routing_table = {node_id: {} for node_id in self.nodes}
        
        # Floyd-Warshall algorithm for all-pairs shortest paths
        nodes = list(self.nodes.keys())
        n = len(nodes)
        
        # Initialize distance matrix
        dist = [[float('infinity')] * n for _ in range(n)]
        next_hop = [[None] * n for _ in range(n)]
        
        # Set distances for direct links
        for i, node_i in enumerate(nodes):
            dist[i][i] = 0
            for j, node_j in enumerate(nodes):
                if i != j:
                    # Check if direct link exists
                    for link in self.links.values():
                        if link.source_node == node_i and link.target_node == node_j:
                            weight = link.latency * (2 - link.quality_score)
                            if weight < dist[i][j]:
                                dist[i][j] = weight
                                next_hop[i][j] = node_j
        
        # Floyd-Warshall main algorithm
        for k in range(n):
            for i in range(n):
                for j in range(n):
                    if dist[i][k] + dist[k][j] < dist[i][j]:
                        dist[i][j] = dist[i][k] + dist[k][j]
                        next_hop[i][j] = next_hop[i][k]
        
        # Update routing table
        for i, source in enumerate(nodes):
            for j, target in enumerate(nodes):
                if i != j and next_hop[i][j] is not None:
                    self.routing_table[source][target] = next_hop[i][j]
