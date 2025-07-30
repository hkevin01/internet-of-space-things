# 📡 Internet of Space Things (IoST) - API Documentation

**API Version:** v1.0  
**Last Updated:** July 30, 2025  
**Base URL:** `https://api.iost.space/v1`  
**Documentation Type:** OpenAPI 3.0 Specification

---

## 📋 Table of Contents

1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Core Services API](#core-services-api)
4. [CEHSN Modules API](#cehsn-modules-api)
5. [Telemetry & Monitoring API](#telemetry--monitoring-api)
6. [Mission Control API](#mission-control-api)
7. [WebSocket Endpoints](#websocket-endpoints)
8. [Error Handling](#error-handling)
9. [Rate Limiting](#rate-limiting)
10. [SDK and Client Libraries](#sdk-and-client-libraries)

---

## 🌟 API Overview

The IoST API provides programmatic access to all platform capabilities, designed for:

- **Mission Controllers**: Real-time spacecraft monitoring and control
- **Ground Stations**: Telemetry data ingestion and command relay
- **Third-Party Integrations**: External system connectivity
- **Mobile Applications**: Astronaut interface and emergency systems
- **Research Institutions**: Data analysis and mission planning

### API Design Principles

- **RESTful Architecture**: Standard HTTP methods and status codes
- **Real-time Capabilities**: WebSocket support for live data streams
- **Comprehensive**: Full platform functionality accessible via API
- **Secure**: OAuth 2.0 authentication with role-based access control
- **Versioned**: Backward compatibility with semantic versioning

---

## 🔐 Authentication

### OAuth 2.0 Implementation

**Authorization Endpoint**: `https://auth.iost.space/oauth/authorize`  
**Token Endpoint**: `https://auth.iost.space/oauth/token`  

#### Authorization Code Flow

```http
GET /oauth/authorize?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=YOUR_REDIRECT_URI&
  scope=mission:read mission:write telemetry:read&
  state=RANDOM_STATE_STRING
```

#### Token Request

```http
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=AUTHORIZATION_CODE&
client_id=YOUR_CLIENT_ID&
client_secret=YOUR_CLIENT_SECRET&
redirect_uri=YOUR_REDIRECT_URI
```

#### Token Response

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "def50200a54b8f3e2d...",
  "scope": "mission:read mission:write telemetry:read"
}
```

### API Key Authentication (Alternative)

For server-to-server communication:

```http
GET /api/v1/satellites
Authorization: Bearer YOUR_API_KEY
```

### Scopes and Permissions

| **Scope** | **Description** | **Access Level** |
|-----------|-----------------|------------------|
| `mission:read` | Read mission data and status | Read-only |
| `mission:write` | Create and modify missions | Read/Write |
| `telemetry:read` | Access telemetry data | Read-only |
| `telemetry:write` | Submit telemetry data | Write |
| `command:execute` | Execute spacecraft commands | Execute |
| `emergency:access` | Access emergency protocols | Critical |
| `admin:full` | Full system administration | Administrator |

---

## 🛰️ Core Services API

### Space Network Management

#### Get Network Status
```http
GET /api/v1/network/status
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "network_id": "net_001",
  "status": "operational",
  "nodes": 15,
  "active_links": 42,
  "topology": "mesh",
  "last_updated": "2025-07-30T10:30:00Z",
  "performance": {
    "avg_latency_ms": 45,
    "packet_loss_rate": 0.001,
    "throughput_mbps": 250.5
  }
}
```

#### Update Network Configuration
```http
PATCH /api/v1/network/config
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "routing_algorithm": "adaptive_shortest_path",
  "qos_enabled": true,
  "redundancy_level": 3,
  "auto_failover": true
}
```

### Satellite Management

#### List Satellites
```http
GET /api/v1/satellites
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `status` (optional): Filter by status (`active`, `inactive`, `maintenance`)
- `constellation` (optional): Filter by constellation name
- `limit` (optional): Maximum number of results (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "satellites": [
    {
      "id": "sat_001",
      "name": "ISS",
      "type": "space_station",
      "status": "active",
      "position": {
        "latitude": 51.6461,
        "longitude": -0.8061,
        "altitude": 408000
      },
      "orbital_elements": {
        "semi_major_axis": 6778000,
        "eccentricity": 0.0001,
        "inclination": 51.64,
        "raan": 125.2,
        "arg_periapsis": 0.0,
        "mean_anomaly": 180.5
      },
      "health": {
        "power_level": 95.5,
        "temperature": 22.3,
        "communication_status": "nominal"
      },
      "last_contact": "2025-07-30T10:25:00Z"
    }
  ],
  "total": 15,
  "limit": 50,
  "offset": 0
}
```

#### Get Satellite Details
```http
GET /api/v1/satellites/{satellite_id}
Authorization: Bearer {access_token}
```

#### Update Satellite Configuration
```http
PATCH /api/v1/satellites/{satellite_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "power_mode": "nominal",
  "communication_frequency": 2400,
  "orbital_adjustment": {
    "delta_v": 0.5,
    "direction": "prograde"
  }
}
```

### Mission Control

#### Get Active Missions
```http
GET /api/v1/missions
Authorization: Bearer {access_token}
```

#### Create New Mission
```http
POST /api/v1/missions
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Luna Gateway Resupply",
  "type": "resupply",
  "priority": "high",
  "spacecraft": ["sat_003", "sat_007"],
  "objectives": [
    {
      "id": "obj_001",
      "description": "Deliver supplies to Luna Gateway",
      "deadline": "2025-08-15T00:00:00Z",
      "status": "pending"
    }
  ],
  "emergency_protocols": ["emergency_001", "emergency_002"]
}
```

#### Execute Mission Command
```http
POST /api/v1/missions/{mission_id}/commands
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "command": "orbit_adjustment",
  "parameters": {
    "delta_v": 1.2,
    "burn_duration": 30,
    "direction": "radial_out"
  },
  "target_satellites": ["sat_003"],
  "execution_time": "immediate",
  "priority": "normal"
}
```

---

## 🤖 CEHSN Modules API

### Orbital Inference Engine

#### Get Anomaly Predictions
```http
GET /api/v1/cehsn/orbital-inference/predictions
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "predictions": [
    {
      "type": "radiation_spike",
      "probability": 0.87,
      "estimated_time": "2025-07-30T14:30:00Z",
      "affected_regions": [
        {
          "latitude_range": [45.0, 55.0],
          "longitude_range": [-10.0, 10.0]
        }
      ],
      "confidence": 0.92,
      "recommended_actions": [
        "Enable radiation shielding",
        "Reduce crew EVA activities"
      ]
    }
  ],
  "generated_at": "2025-07-30T10:30:00Z"
}
```

#### Submit Sensor Data for Analysis
```http
POST /api/v1/cehsn/orbital-inference/analyze
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "sensor_data": {
    "radiation_level": 0.15,
    "magnetic_field": [-25000, 5000, 45000],
    "particle_count": 1250,
    "timestamp": "2025-07-30T10:30:00Z"
  },
  "location": {
    "latitude": 51.6461,
    "longitude": -0.8061,
    "altitude": 408000
  }
}
```

### RPA Communication Bridge

#### Get Active Drone Fleets
```http
GET /api/v1/cehsn/rpa-bridge/fleets
Authorization: Bearer {access_token}
```

#### Deploy Autonomous Mission
```http
POST /api/v1/cehsn/rpa-bridge/missions/deploy
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "mission_type": "search_and_rescue",
  "area_of_interest": {
    "center": [40.7128, -74.0060],
    "radius_km": 50
  },
  "drone_count": 5,
  "mission_duration": 3600,
  "priorities": ["human_detection", "hazard_mapping"]
}
```

### Ethics Engine

#### Request Ethical Assessment
```http
POST /api/v1/cehsn/ethics/assess
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "scenario": {
    "type": "resource_allocation",
    "description": "Limited oxygen supply during emergency",
    "stakeholders": ["crew_member_1", "crew_member_2"],
    "available_resources": {
      "oxygen_hours": 6,
      "required_hours": 10
    },
    "constraints": ["medical_conditions", "mission_critical_roles"]
  },
  "frameworks": ["utilitarian", "deontological", "virtue_ethics"]
}
```

**Response:**
```json
{
  "assessment_id": "eth_001",
  "recommendations": [
    {
      "framework": "utilitarian",
      "decision": "prioritize_medical_need",
      "reasoning": "Maximizes overall well-being and survival probability",
      "confidence": 0.85
    }
  ],
  "transparency_report": {
    "factors_considered": ["medical_urgency", "mission_roles", "survival_probability"],
    "ethical_conflicts": ["fairness_vs_utility"],
    "decision_process": "Multi-criteria decision analysis with ethical constraints"
  }
}
```

### Survival Map Generator

#### Generate Hazard Map
```http
POST /api/v1/cehsn/survival-map/generate
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "area": {
    "bounds": {
      "north": 45.0,
      "south": 40.0,
      "east": -70.0,
      "west": -75.0
    }
  },
  "hazard_types": ["wildfire", "flood", "radiation"],
  "resolution": "high",
  "real_time": true
}
```

#### Get Safe Routes
```http
GET /api/v1/cehsn/survival-map/routes/safe
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `start_lat`, `start_lon`: Starting coordinates
- `end_lat`, `end_lon`: Destination coordinates
- `avoid_hazards`: Comma-separated list of hazards to avoid
- `max_distance`: Maximum route distance in kilometers

### Resilience Monitor

#### Get Network Health Status
```http
GET /api/v1/cehsn/resilience/health
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "overall_health": 0.94,
  "network_segments": [
    {
      "segment_id": "seg_001",
      "health_score": 0.98,
      "node_count": 15,
      "active_nodes": 14,
      "fault_tolerance": 0.85
    }
  ],
  "recent_incidents": [
    {
      "incident_id": "inc_001",
      "type": "node_failure",
      "severity": "low",
      "auto_resolved": true,
      "resolution_time": 45
    }
  ],
  "predictive_alerts": [
    {
      "alert_type": "potential_failure",
      "affected_node": "node_025",
      "probability": 0.23,
      "estimated_time": "2025-07-31T08:00:00Z"
    }
  ]
}
```

---

## 📊 Telemetry & Monitoring API

### Real-time Telemetry

#### Get Latest Telemetry
```http
GET /api/v1/telemetry/latest
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `satellites`: Comma-separated list of satellite IDs
- `parameters`: Specific telemetry parameters to retrieve
- `time_range`: Time range in seconds (default: 300)

#### Historical Telemetry Data
```http
GET /api/v1/telemetry/historical
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `start_time`: ISO 8601 timestamp
- `end_time`: ISO 8601 timestamp
- `resolution`: Data resolution (`1m`, `5m`, `1h`, `1d`)
- `aggregation`: Aggregation method (`avg`, `min`, `max`, `sum`)

#### Submit Telemetry Data
```http
POST /api/v1/telemetry/submit
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "satellite_id": "sat_001",
  "timestamp": "2025-07-30T10:30:00Z",
  "data": {
    "power": {
      "battery_level": 95.5,
      "solar_panel_output": 450.2,
      "power_consumption": 380.7
    },
    "thermal": {
      "cpu_temperature": 45.3,
      "battery_temperature": 18.7,
      "external_temperature": -157.2
    },
    "attitude": {
      "roll": 0.5,
      "pitch": -1.2,
      "yaw": 180.7
    }
  }
}
```

### System Monitoring

#### Get System Metrics
```http
GET /api/v1/monitoring/metrics
Authorization: Bearer {access_token}
```

#### Get Alert Status
```http
GET /api/v1/monitoring/alerts
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `severity`: Filter by severity (`low`, `medium`, `high`, `critical`)
- `status`: Filter by status (`active`, `resolved`, `acknowledged`)
- `time_range`: Time range in hours (default: 24)

---

## 🎮 Mission Control API

### Command Execution

#### Execute Immediate Command
```http
POST /api/v1/commands/execute
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "target": "sat_001",
  "command": "attitude_adjustment",
  "parameters": {
    "target_orientation": {
      "roll": 0.0,
      "pitch": 0.0,
      "yaw": 90.0
    },
    "execution_mode": "immediate"
  },
  "priority": "high",
  "timeout_seconds": 300
}
```

#### Schedule Command
```http
POST /api/v1/commands/schedule
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "target": "sat_001",
  "command": "orbit_maintenance",
  "parameters": {
    "delta_v": 0.5,
    "burn_duration": 15
  },
  "scheduled_time": "2025-07-31T02:30:00Z",
  "window_duration": 600
}
```

### Emergency Protocols

#### Trigger Emergency Response
```http
POST /api/v1/emergency/trigger
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "emergency_type": "life_support_failure",
  "severity": "critical",
  "affected_systems": ["oxygen_generation", "co2_scrubbing"],
  "affected_crew": ["crew_001", "crew_002"],
  "immediate_actions": [
    "activate_backup_oxygen",
    "initiate_emergency_descent"
  ]
}
```

#### Get Emergency Protocols
```http
GET /api/v1/emergency/protocols
Authorization: Bearer {access_token}
```

---

## 🔌 WebSocket Endpoints

### Real-time Data Streams

#### Connect to Telemetry Stream
```javascript
const ws = new WebSocket('wss://api.iost.space/v1/ws/telemetry');

ws.onopen = function(event) {
    // Subscribe to specific satellites
    ws.send(JSON.stringify({
        action: 'subscribe',
        satellites: ['sat_001', 'sat_002'],
        parameters: ['power', 'thermal', 'attitude']
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Telemetry update:', data);
};
```

#### Mission Control Events
```javascript
const ws = new WebSocket('wss://api.iost.space/v1/ws/mission-control');

ws.onmessage = function(event) {
    const event_data = JSON.parse(event.data);
    switch(event_data.type) {
        case 'command_executed':
            handleCommandResult(event_data);
            break;
        case 'emergency_alert':
            handleEmergency(event_data);
            break;
        case 'mission_update':
            updateMissionStatus(event_data);
            break;
    }
};
```

### WebSocket Message Format

**Subscription Message:**
```json
{
  "action": "subscribe",
  "channel": "telemetry",
  "filters": {
    "satellites": ["sat_001"],
    "parameters": ["power", "thermal"]
  }
}
```

**Data Message:**
```json
{
  "type": "telemetry_update",
  "timestamp": "2025-07-30T10:30:00Z",
  "satellite_id": "sat_001",
  "data": {
    "power": {
      "battery_level": 95.5,
      "solar_panel_output": 450.2
    }
  }
}
```

---

## ⚠️ Error Handling

### Standard Error Response Format

```json
{
  "error": {
    "code": "SATELLITE_NOT_FOUND",
    "message": "The specified satellite could not be found",
    "details": {
      "satellite_id": "sat_999",
      "suggestion": "Check the satellite ID and try again"
    },
    "timestamp": "2025-07-30T10:30:00Z",
    "request_id": "req_12345"
  }
}
```

### HTTP Status Codes

| **Status Code** | **Description** | **Usage** |
|-----------------|-----------------|-----------|
| 200 | OK | Successful GET, PATCH requests |
| 201 | Created | Successful POST requests |
| 204 | No Content | Successful DELETE requests |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict (e.g., duplicate) |
| 422 | Unprocessable Entity | Validation errors |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |
| 503 | Service Unavailable | Temporary service unavailability |

### Common Error Codes

| **Error Code** | **Description** | **Resolution** |
|----------------|-----------------|----------------|
| `INVALID_TOKEN` | Authentication token is invalid | Refresh or obtain new token |
| `INSUFFICIENT_SCOPE` | Token lacks required permissions | Request token with appropriate scopes |
| `SATELLITE_OFFLINE` | Target satellite is not responding | Check satellite status and retry |
| `COMMAND_TIMEOUT` | Command execution timed out | Check satellite connectivity |
| `RESOURCE_LIMIT_EXCEEDED` | API usage limits exceeded | Reduce request frequency |
| `VALIDATION_ERROR` | Request data validation failed | Check request format and parameters |

---

## 🚦 Rate Limiting

### Rate Limit Policies

| **Endpoint Category** | **Rate Limit** | **Window** | **Burst Limit** |
|-----------------------|----------------|------------|-----------------|
| Authentication | 10 requests | 1 minute | 20 |
| Telemetry Read | 1000 requests | 1 hour | 100 |
| Telemetry Write | 100 requests | 1 minute | 20 |
| Commands | 50 requests | 1 hour | 10 |
| Emergency | 20 requests | 1 minute | 50 |
| WebSocket Connections | 10 connections | 1 minute | 20 |

### Rate Limit Headers

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1627640400
X-RateLimit-Window: 3600
```

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "API rate limit exceeded",
    "details": {
      "limit": 1000,
      "window": 3600,
      "reset_time": "2025-07-30T11:00:00Z"
    }
  }
}
```

---

## 🛠️ SDK and Client Libraries

### Official SDKs

#### Python SDK
```bash
pip install iost-python-sdk
```

```python
from iost import IoSTClient

client = IoSTClient(
    base_url='https://api.iost.space/v1',
    access_token='your_access_token'
)

# Get satellite status
satellites = client.satellites.list(status='active')

# Execute command
result = client.commands.execute(
    target='sat_001',
    command='attitude_adjustment',
    parameters={'roll': 0.0, 'pitch': 0.0, 'yaw': 90.0}
)
```

#### JavaScript SDK
```bash
npm install @iost/javascript-sdk
```

```javascript
import { IoSTClient } from '@iost/javascript-sdk';

const client = new IoSTClient({
    baseURL: 'https://api.iost.space/v1',
    accessToken: 'your_access_token'
});

// Get telemetry data
const telemetry = await client.telemetry.getLatest({
    satellites: ['sat_001'],
    parameters: ['power', 'thermal']
});

// Subscribe to real-time updates
const stream = client.telemetry.stream({
    satellites: ['sat_001'],
    onUpdate: (data) => console.log('Telemetry update:', data)
});
```

### Community SDKs

- **Go SDK**: [github.com/iost/go-sdk](https://github.com/iost/go-sdk)
- **Java SDK**: [github.com/iost/java-sdk](https://github.com/iost/java-sdk)
- **C# SDK**: [github.com/iost/csharp-sdk](https://github.com/iost/csharp-sdk)

---

## 📚 API Resources

### Additional Documentation

- **OpenAPI Specification**: [https://api.iost.space/v1/openapi.json](https://api.iost.space/v1/openapi.json)
- **Postman Collection**: [https://documenter.getpostman.com/view/iost-api](https://documenter.getpostman.com/view/iost-api)
- **GraphQL Playground**: [https://api.iost.space/graphql](https://api.iost.space/graphql)

### Support and Community

- **API Support**: [api-support@iost.space](mailto:api-support@iost.space)
- **Developer Forum**: [https://community.iost.space](https://community.iost.space)
- **GitHub Issues**: [https://github.com/iost/api-issues](https://github.com/iost/api-issues)
- **Status Page**: [https://status.iost.space](https://status.iost.space)

### Changelog and Versioning

- **API Changelog**: [https://docs.iost.space/api/changelog](https://docs.iost.space/api/changelog)
- **Deprecation Policy**: [https://docs.iost.space/api/deprecation](https://docs.iost.space/api/deprecation)
- **Migration Guides**: [https://docs.iost.space/api/migrations](https://docs.iost.space/api/migrations)

---

*This API documentation is continuously updated. For the latest version and interactive documentation, visit our [API Explorer](https://api.iost.space/docs).*

**Document Control**:
- **Version**: 1.0
- **Last Updated**: July 30, 2025
- **Next Review**: August 30, 2025
