# Detector Module Configuration

## AI Server Setup

The detector module uses two specialized AI servers on `192.168.1.79`:

### Server 8888 (Required) - Semantic Object Detection
- **Purpose**: Semantic object detection and segmentation
- **Status**: Required - must be online
- **Endpoints**:
  - `POST /detect/objects` - Object detection with bounding boxes
  - `POST /segment/semantic` - Semantic segmentation
  - `GET /health` - Health check
- **Used by**:
  - `POST /detector/objects`
  - `POST /detector/semantic`

### Server 8889 (Optional) - Road Segmentation
- **Purpose**: Road boundary and lane detection
- **Status**: Optional - can be skipped if malfunctioning
- **Endpoints**:
  - `POST /detect/road-boundary` - Road boundary detection
  - `GET /health` - Health check
- **Used by**:
  - `POST /detector/road-boundary`
- **Behavior**: Returns 503 error if unavailable, but system continues working

## Configuration in Code

### Server URLs (detection_utils.py)
```python
def get_ai_server_client(detection_type: str = "object") -> AIServerClient:
    servers = {
        'object': 'http://192.168.1.79:8888',  # Semantic object detection (required)
        'road': 'http://192.168.1.79:8889'     # Road segmentation (optional)
    }
    server_url = servers.get(detection_type, servers['object'])
    return AIServerClient(server_url)
```

### Usage in Endpoints
```python
# For object detection and semantic segmentation (uses 8888)
ai_client = get_ai_server_client("object")

# For road boundary detection (uses 8889)
ai_client = get_ai_server_client("road")
```

## API Response Examples

### Check Server Status
```bash
GET /detector/models
```

Response when both servers are online:
```json
{
  "models": [
    {
      "server": "http://192.168.1.79:8888",
      "port": "8888",
      "type": "semantic_object_detection",
      "status": "online",
      "required": true,
      "capabilities": ["object_detection", "semantic_segmentation"]
    },
    {
      "server": "http://192.168.1.79:8889",
      "port": "8889",
      "type": "road_segmentation",
      "status": "online",
      "required": false,
      "note": "Optional - can be skipped if malfunctioning",
      "capabilities": ["road_boundary_detection", "lane_detection"]
    }
  ]
}
```

Response when 8889 is down (acceptable):
```json
{
  "models": [
    {
      "server": "http://192.168.1.79:8888",
      "port": "8888",
      "type": "semantic_object_detection",
      "status": "online",
      "required": true,
      "capabilities": ["object_detection", "semantic_segmentation"]
    },
    {
      "server": "http://192.168.1.79:8889",
      "port": "8889",
      "type": "road_segmentation",
      "status": "offline",
      "required": false,
      "note": "Optional - can be skipped if malfunctioning"
    }
  ]
}
```

### Road Boundary Detection When Server is Down
```bash
POST /detector/road-boundary
```

Response (503 Service Unavailable):
```json
{
  "detection_id": 123,
  "status": "failed",
  "message": "Road segmentation server is currently unavailable",
  "note": "Server 8889 can be skipped when malfunctioning"
}
```

## Testing Server Connectivity

### Manual Testing
```bash
# Test semantic object detection server (8888 - required)
curl http://192.168.1.79:8888/health

# Test road segmentation server (8889 - optional)
curl http://192.168.1.79:8889/health
```

### From Python
```python
from apps.detector.detection_utils import get_ai_server_client

# Test object detection server
object_client = get_ai_server_client("object")
print(f"Object server (8888): {'online' if object_client.health_check() else 'offline'}")

# Test road segmentation server
road_client = get_ai_server_client("road")
print(f"Road server (8889): {'online' if road_client.health_check() else 'offline'}")
```

## Deployment Checklist

- [ ] Server 8888 is running and accessible
- [ ] Server 8888 responds to `/health` endpoint
- [ ] Server 8888 implements `/detect/objects` endpoint
- [ ] Server 8888 implements `/segment/semantic` endpoint
- [ ] Server 8889 is running (optional, but recommended)
- [ ] Server 8889 responds to `/health` endpoint (if running)
- [ ] Server 8889 implements `/detect/road-boundary` endpoint (if running)
- [ ] Firewall allows connections to 192.168.1.79:8888
- [ ] Firewall allows connections to 192.168.1.79:8889 (optional)
- [ ] Network connectivity is stable

## Troubleshooting

### Server 8888 is offline (Critical)
**Problem**: Object detection and semantic segmentation won't work
**Solution**:
1. Check if server is running: `curl http://192.168.1.79:8888/health`
2. Verify firewall settings
3. Check server logs
4. Restart AI server on port 8888

### Server 8889 is offline (Non-Critical)
**Problem**: Road boundary detection returns 503 errors
**Impact**: Limited - only affects `/detector/road-boundary` endpoint
**Solution**:
- Can be ignored if road detection is not needed
- System will continue working for object detection and semantic segmentation
- Check server logs if road detection is needed
- Restart AI server on port 8889 when convenient

### Connection Timeout
**Problem**: Requests to AI servers timeout
**Solution**:
1. Increase timeout in `detection_utils.py`:
   ```python
   client = AIServerClient("http://...", timeout=60)  # Default is 30
   ```
2. Check network latency
3. Verify AI server is not overloaded

### Wrong Server for Detection Type
**Problem**: Getting unexpected errors or wrong results
**Solution**:
- Verify you're using correct detection type:
  - `get_ai_server_client("object")` for object detection/segmentation
  - `get_ai_server_client("road")` for road boundary detection
- Check AI server logs to verify correct model is loaded

## Production Recommendations

1. **Monitor Server 8888**: Set up monitoring/alerts since it's critical
2. **Server 8889 is Optional**: Don't alert on 8889 downtime unless road detection is mission-critical
3. **Graceful Degradation**: System is designed to work even if 8889 is down
4. **Load Balancing**: Consider adding multiple instances of 8888 if traffic is high
5. **Health Checks**: Periodically check both servers via `/detector/models` endpoint
