"""
Deep Space Communication Protocol
Optimized for long-distance, high-latency space communications
Handles error correction, adaptive routing, and delay-tolerant networking
"""

import asyncio
import hashlib
import logging
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class PacketType(Enum):
    DATA = 0x01
    ACK = 0x02
    NACK = 0x03
    HEARTBEAT = 0x04
    EMERGENCY = 0x05
    ROUTING_UPDATE = 0x06
    TIME_SYNC = 0x07


class Priority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class DeepSpacePacket:
    """Deep space communication packet structure"""
    packet_id: str
    source_id: str
    destination_id: str
    packet_type: PacketType
    priority: Priority
    payload: bytes
    sequence_number: int = 0
    timestamp: float = field(default_factory=time.time)
    ttl: int = 86400  # Time to live in seconds (24 hours)
    route_history: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    
    def __post_init__(self):
        if self.checksum is None:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate packet checksum"""
        data = (
            self.packet_id.encode() +
            self.source_id.encode() +
            self.destination_id.encode() +
            struct.pack('B', self.packet_type.value) +
            struct.pack('B', self.priority.value) +
            self.payload +
            struct.pack('I', self.sequence_number) +
            struct.pack('d', self.timestamp)
        )
        return hashlib.sha256(data).hexdigest()
    
    def is_valid(self) -> bool:
        """Verify packet integrity"""
        return self.checksum == self._calculate_checksum()
    
    def serialize(self) -> bytes:
        """Serialize packet for transmission"""
        header = struct.pack(
            '!32s32s32sBBIId',
            self.packet_id.encode()[:32],
            self.source_id.encode()[:32], 
            self.destination_id.encode()[:32],
            self.packet_type.value,
            self.priority.value,
            self.sequence_number,
            len(self.payload),
            self.timestamp
        )
        
        route_data = b''.join(node.encode()[:32].ljust(32, b'\x00') 
                             for node in self.route_history[:10])  # Max 10 hops
        route_header = struct.pack('!B', len(self.route_history))
        
        checksum_data = self.checksum.encode()[:64].ljust(64, b'\x00')
        
        return header + route_header + route_data + checksum_data + self.payload


class DeepSpaceProtocol:
    """
    Deep Space Communication Protocol Implementation
    Handles reliable communication across vast distances with high latency
    """
    
    def __init__(self, node_id: str, max_retries: int = 5, 
                 ack_timeout: float = 300.0):
        self.node_id = node_id
        self.max_retries = max_retries
        self.ack_timeout = ack_timeout
        
        # Sequence tracking
        self.sequence_counter = 0
        self.pending_acks: Dict[str, DeepSpacePacket] = {}
        self.received_packets: Dict[str, DeepSpacePacket] = {}
        self.duplicate_filter: Dict[str, float] = {}
        
        # Routing and topology
        self.routing_table: Dict[str, str] = {}  # destination -> next_hop
        self.neighbor_nodes: Dict[str, float] = {}  # node_id -> last_seen
        self.link_qualities: Dict[str, float] = {}  # link_id -> quality (0-1)
        
        # Statistics
        self.packets_sent = 0
        self.packets_received = 0
        self.packets_dropped = 0
        self.bytes_transmitted = 0
        self.bytes_received = 0
        
        # Configuration
        self.packet_cache_duration = 3600  # 1 hour
        self.neighbor_timeout = 600  # 10 minutes
        self.max_packet_size = 65536  # 64KB
        
        logger.info(f"Deep Space Protocol initialized for node {node_id}")
    
    async def send_packet(self, destination: str, payload: bytes, 
                         packet_type: PacketType = PacketType.DATA,
                         priority: Priority = Priority.NORMAL) -> bool:
        """Send packet with reliability guarantees"""
        try:
            if len(payload) > self.max_packet_size:
                logger.error(f"Payload too large: {len(payload)} bytes")
                return False
            
            # Create packet
            packet = DeepSpacePacket(
                packet_id=f"{self.node_id}_{self.sequence_counter}_{time.time()}",
                source_id=self.node_id,
                destination_id=destination,
                packet_type=packet_type,
                priority=priority,
                payload=payload,
                sequence_number=self.sequence_counter
            )
            
            self.sequence_counter += 1
            
            # For reliable delivery, store for ACK tracking
            if packet_type == PacketType.DATA:
                self.pending_acks[packet.packet_id] = packet
                
                # Start ACK timeout timer
                asyncio.create_task(self._handle_ack_timeout(packet.packet_id))
            
            # Route packet
            success = await self._route_packet(packet)
            
            if success:
                self.packets_sent += 1
                self.bytes_transmitted += len(packet.serialize())
                logger.debug(f"Sent packet {packet.packet_id} to {destination}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send packet: {e}")
            return False
    
    async def receive_packet(self, packet_data: bytes) -> Optional[DeepSpacePacket]:
        """Process received packet"""
        try:
            packet = self._deserialize_packet(packet_data)
            if not packet:
                return None
            
            # Verify packet integrity
            if not packet.is_valid():
                logger.warning(f"Invalid packet received: {packet.packet_id}")
                self.packets_dropped += 1
                return None
            
            # Check for duplicates
            if self._is_duplicate(packet):
                logger.debug(f"Duplicate packet filtered: {packet.packet_id}")
                return None
            
            # Update route history
            if self.node_id not in packet.route_history:
                packet.route_history.append(self.node_id)
            
            # Process based on packet type
            if packet.packet_type == PacketType.ACK:
                await self._handle_ack(packet)
            elif packet.packet_type == PacketType.NACK:
                await self._handle_nack(packet)
            elif packet.packet_type == PacketType.HEARTBEAT:
                await self._handle_heartbeat(packet)
            elif packet.packet_type == PacketType.ROUTING_UPDATE:
                await self._handle_routing_update(packet)
            elif packet.destination_id == self.node_id:
                # Packet is for this node
                await self._handle_received_packet(packet)
            else:
                # Forward packet
                await self._forward_packet(packet)
            
            self.packets_received += 1
            self.bytes_received += len(packet_data)
            
            return packet
            
        except Exception as e:
            logger.error(f"Failed to process received packet: {e}")
            return None
    
    async def send_heartbeat(self) -> bool:
        """Send heartbeat to all neighbors"""
        try:
            heartbeat_data = struct.pack('!d', time.time())
            
            # Send to all known neighbors
            tasks = []
            for neighbor_id in self.neighbor_nodes:
                task = self.send_packet(
                    neighbor_id, 
                    heartbeat_data, 
                    PacketType.HEARTBEAT,
                    Priority.LOW
                )
                tasks.append(task)
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success_count = sum(1 for r in results if r is True)
                logger.debug(f"Sent heartbeat to {success_count}/{len(tasks)} neighbors")
                return success_count > 0
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False
    
    async def update_routing_table(self, topology_data: Dict[str, Any]):
        """Update routing table based on network topology"""
        try:
            # Simple distance-vector routing algorithm
            # In practice, this would be more sophisticated
            
            self.routing_table.clear()
            
            # Direct neighbors
            for neighbor in topology_data.get('neighbors', []):
                self.routing_table[neighbor] = neighbor
            
            # Multi-hop routes
            for destination, route_info in topology_data.get('routes', {}).items():
                if destination != self.node_id:
                    next_hop = route_info.get('next_hop')
                    if next_hop:
                        self.routing_table[destination] = next_hop
            
            logger.debug(f"Updated routing table with {len(self.routing_table)} routes")
            
        except Exception as e:
            logger.error(f"Failed to update routing table: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get protocol statistics"""
        return {
            "node_id": self.node_id,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "packets_dropped": self.packets_dropped,
            "bytes_transmitted": self.bytes_transmitted,
            "bytes_received": self.bytes_received,
            "pending_acks": len(self.pending_acks),
            "known_neighbors": len(self.neighbor_nodes),
            "routing_table_size": len(self.routing_table),
            "sequence_counter": self.sequence_counter
        }
    
    async def _route_packet(self, packet: DeepSpacePacket) -> bool:
        """Route packet to destination"""
        try:
            # Check if destination is directly reachable
            if packet.destination_id in self.neighbor_nodes:
                return await self._transmit_to_neighbor(packet.destination_id, packet)
            
            # Use routing table
            next_hop = self.routing_table.get(packet.destination_id)
            if next_hop:
                return await self._transmit_to_neighbor(next_hop, packet)
            
            # No route found
            logger.warning(f"No route to destination: {packet.destination_id}")
            return False
            
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            return False
    
    async def _transmit_to_neighbor(self, neighbor_id: str, 
                                   packet: DeepSpacePacket) -> bool:
        """Transmit packet to specific neighbor"""
        # This would interface with the actual radio/communication hardware
        # For simulation, we'll just log the transmission
        
        try:
            # Simulate transmission delay based on distance
            transmission_delay = self._calculate_transmission_delay(neighbor_id)
            await asyncio.sleep(transmission_delay)
            
            # Update link quality based on successful transmission
            link_id = f"{self.node_id}-{neighbor_id}"
            current_quality = self.link_qualities.get(link_id, 1.0)
            self.link_qualities[link_id] = min(1.0, current_quality + 0.01)
            
            logger.debug(f"Transmitted packet {packet.packet_id} to {neighbor_id}")
            return True
            
        except Exception as e:
            logger.error(f"Transmission to {neighbor_id} failed: {e}")
            
            # Degrade link quality on failure
            link_id = f"{self.node_id}-{neighbor_id}"
            current_quality = self.link_qualities.get(link_id, 1.0)
            self.link_qualities[link_id] = max(0.0, current_quality - 0.1)
            
            return False
    
    async def _handle_ack(self, ack_packet: DeepSpacePacket):
        """Handle ACK packet"""
        # Extract original packet ID from ACK payload
        if len(ack_packet.payload) >= 64:
            original_packet_id = ack_packet.payload[:64].decode().strip('\x00')
            
            if original_packet_id in self.pending_acks:
                del self.pending_acks[original_packet_id]
                logger.debug(f"Received ACK for packet {original_packet_id}")
    
    async def _handle_nack(self, nack_packet: DeepSpacePacket):
        """Handle NACK packet"""
        # Extract original packet ID and retransmit
        if len(nack_packet.payload) >= 64:
            original_packet_id = nack_packet.payload[:64].decode().strip('\x00')
            
            if original_packet_id in self.pending_acks:
                original_packet = self.pending_acks[original_packet_id]
                await self._route_packet(original_packet)
                logger.debug(f"Retransmitted packet {original_packet_id} due to NACK")
    
    async def _handle_heartbeat(self, heartbeat_packet: DeepSpacePacket):
        """Handle heartbeat packet"""
        # Update neighbor information
        self.neighbor_nodes[heartbeat_packet.source_id] = time.time()
        logger.debug(f"Received heartbeat from {heartbeat_packet.source_id}")
    
    async def _handle_routing_update(self, routing_packet: DeepSpacePacket):
        """Handle routing update packet"""
        try:
            # Parse routing information from payload
            # This would contain network topology updates
            routing_data = routing_packet.payload.decode()
            logger.debug(f"Received routing update from {routing_packet.source_id}")
            
        except Exception as e:
            logger.error(f"Failed to process routing update: {e}")
    
    async def _handle_received_packet(self, packet: DeepSpacePacket):
        """Handle packet destined for this node"""
        # Send ACK if required
        if packet.packet_type == PacketType.DATA:
            ack_payload = packet.packet_id.encode().ljust(64, b'\x00')
            await self.send_packet(
                packet.source_id,
                ack_payload,
                PacketType.ACK,
                Priority.HIGH
            )
        
        # Store packet for application processing
        self.received_packets[packet.packet_id] = packet
        logger.debug(f"Received packet {packet.packet_id} from {packet.source_id}")
    
    async def _forward_packet(self, packet: DeepSpacePacket):
        """Forward packet to next hop"""
        # Check TTL
        if time.time() - packet.timestamp > packet.ttl:
            logger.warning(f"Packet {packet.packet_id} expired, dropping")
            self.packets_dropped += 1
            return
        
        # Check for routing loops
        if self.node_id in packet.route_history:
            logger.warning(f"Routing loop detected for packet {packet.packet_id}")
            self.packets_dropped += 1
            return
        
        # Forward packet
        await self._route_packet(packet)
    
    async def _handle_ack_timeout(self, packet_id: str):
        """Handle ACK timeout"""
        await asyncio.sleep(self.ack_timeout)
        
        if packet_id in self.pending_acks:
            packet = self.pending_acks[packet_id]
            
            # Implement exponential backoff for retries
            retry_count = getattr(packet, 'retry_count', 0)
            
            if retry_count < self.max_retries:
                packet.retry_count = retry_count + 1
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                await self._route_packet(packet)
                
                # Restart timeout timer
                asyncio.create_task(self._handle_ack_timeout(packet_id))
                
                logger.debug(f"Retransmitting packet {packet_id} (attempt {retry_count + 1})")
            else:
                # Max retries reached, give up
                del self.pending_acks[packet_id]
                logger.error(f"Packet {packet_id} delivery failed after {self.max_retries} retries")
    
    def _deserialize_packet(self, data: bytes) -> Optional[DeepSpacePacket]:
        """Deserialize packet from bytes"""
        try:
            if len(data) < 142:  # Minimum header size
                return None
            
            # Parse header
            header_data = struct.unpack('!32s32s32sBBIId', data[:142])
            
            packet_id = header_data[0].decode().rstrip('\x00')
            source_id = header_data[1].decode().rstrip('\x00')
            destination_id = header_data[2].decode().rstrip('\x00')
            packet_type = PacketType(header_data[3])
            priority = Priority(header_data[4])
            sequence_number = header_data[5]
            payload_length = header_data[6]
            timestamp = header_data[7]
            
            # Parse route history
            route_count = struct.unpack('!B', data[142:143])[0]
            route_data = data[143:143 + route_count * 32]
            route_history = []
            
            for i in range(route_count):
                node_id = route_data[i*32:(i+1)*32].decode().rstrip('\x00')
                if node_id:
                    route_history.append(node_id)
            
            # Parse checksum
            checksum_start = 143 + route_count * 32
            checksum = data[checksum_start:checksum_start+64].decode().rstrip('\x00')
            
            # Extract payload
            payload_start = checksum_start + 64
            payload = data[payload_start:payload_start + payload_length]
            
            packet = DeepSpacePacket(
                packet_id=packet_id,
                source_id=source_id,
                destination_id=destination_id,
                packet_type=packet_type,
                priority=priority,
                payload=payload,
                sequence_number=sequence_number,
                timestamp=timestamp,
                route_history=route_history,
                checksum=checksum
            )
            
            return packet
            
        except Exception as e:
            logger.error(f"Failed to deserialize packet: {e}")
            return None
    
    def _is_duplicate(self, packet: DeepSpacePacket) -> bool:
        """Check if packet is a duplicate"""
        packet_key = f"{packet.source_id}_{packet.sequence_number}"
        current_time = time.time()
        
        # Clean old entries
        expired_keys = [key for key, timestamp in self.duplicate_filter.items()
                       if current_time - timestamp > self.packet_cache_duration]
        for key in expired_keys:
            del self.duplicate_filter[key]
        
        # Check for duplicate
        if packet_key in self.duplicate_filter:
            return True
        
        # Record this packet
        self.duplicate_filter[packet_key] = current_time
        return False
    
    def _calculate_transmission_delay(self, neighbor_id: str) -> float:
        """Calculate transmission delay to neighbor"""
        # This would be based on actual distance and signal propagation
        # For simulation, use a small random delay
        base_delay = 0.1  # 100ms base delay
        random_component = np.random.exponential(0.05)  # Variable delay
        return base_delay + random_component
