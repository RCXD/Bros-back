# Quick Reference - Detector Module

## ✅ What's Been Updated

Your detector module now correctly handles:
- **Port 8888**: Semantic object detection (required)
- **Port 8889**: Road segmentation (optional - can be skipped)

## Server Configuration

```python
# detection_utils.py - get_ai_server_client()
servers = {
    'object': 'http://192.168.1.79:8888',  # Required
    'road': 'http://192.168.1.79:8889'     # Optional
}
```

## API Endpoints

### Object Detection (uses 8888)
```bash
POST /detector/objects
Form-data: image, confidence
```

### Semantic Segmentation (uses 8888)
```bash
POST /detector/semantic
Form-data: image, model
```

### Road Boundary Detection (uses 8889 - optional)
```bash
POST /detector/road-boundary
Form-data: image
# Returns 503 if server unavailable - this is OK!
```

### Check Server Status
```bash
GET /detector/models
# Shows status of both servers
# Marks 8888 as required=true
# Marks 8889 as required=false
```

## Quick Test

```python
from apps.detector.detection_utils import get_ai_server_client

# Test required server (8888)
client = get_ai_server_client("object")
print(f"8888 (required): {client.health_check()}")  # Should be True

# Test optional server (8889)
client = get_ai_server_client("road")
print(f"8889 (optional): {client.health_check()}")  # Can be False
```

## Usage Notes

✅ **System works if 8888 is online** (even if 8889 is down)
❌ **System won't work if 8888 is offline** (required server)
⚠️  **8889 being down only affects road boundary detection**

## Files Modified

1. `detection_utils.py` - Updated server configuration
2. `views.py` - Updated all endpoints to use correct servers
3. `models.py` - Added server documentation
4. `CONFIG.md` - Comprehensive configuration guide (NEW)
5. `QUICK_REFERENCE.md` - This file (NEW)
