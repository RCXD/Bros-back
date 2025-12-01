# Route Analysis API

## Overview

The Route Analysis API integrates OSRM routing, Google Street View (roadview), and AI detector services to analyze road conditions along a given route.

## Workflow

1. **OSRM Routing**: Client sends waypoints → OSRM returns route segments (legs)
2. **Point Generation**: For each segment, calculate heading and generate intermediate points at regular intervals
3. **Roadview Images**: Download Street View images for each point with calculated heading
4. **AI Detection**: Send images to detector service for object/hazard detection
5. **Response**: Return all data (coordinates, headings, images, detection results) to client

## Endpoint

```
POST /route/analyze
```

**Authentication**: JWT required (`Authorization: Bearer <token>`)

## Request Format

```json
{
  "points": [
    {"lat": 37.4980, "lon": 127.0276},
    {"lat": 37.5000, "lon": 127.0280},
    {"lat": 37.5050, "lon": 127.0300}
  ],
  "interval_meters": 50,
  "tag": "route_001",
  "profile": "driving"
}
```

### Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `points` | Array | Yes | - | List of waypoints (lat/lon objects), minimum 2 |
| `interval_meters` | Number | No | 50 | Distance between generated points (meters) |
| `tag` | String | No | UUID | Tag for organizing saved images |
| `profile` | String | No | "driving" | OSRM routing profile |

## Response Format

```json
{
  "route_id": "abc12345",
  "osrm_route": {
    "distance": 1234.5,
    "duration": 180.2,
    "legs_count": 2
  },
  "analyzed_points": [
    {
      "index": 0,
      "lat": 37.4980,
      "lon": 127.0276,
      "heading": 45.0,
      "roadview_image": "/static/roadviews/route_001/roadview_37.498000_127.027600_45.jpg",
      "roadview_success": true,
      "detection_result": {
        "detections": [
          {
            "class": "car",
            "confidence": 0.85,
            "bbox": {...}
          }
        ],
        "processing_time_ms": 120
      },
      "detection_image": "/static/roadviews/route_001/result_0.jpg",
      "detection_success": true,
      "danger_score": 7.25,
      "hazard_id": 1234,
      "score_analysis": {
        "combined_score": 7.25,
        "object_count": 3,
        "individual_scores": [...],
        "algorithm": "NHTSA + Vision Zero + CVPR 2022"
      }
    },
    {
      "index": 1,
      "lat": 37.4985,
      "lon": 127.0278,
      "heading": 47.5,
      "roadview_image": null,
      "roadview_success": false,
      "roadview_error": "No Street View available at this location",
      "detection_result": null,
      "detection_image": null,
      "detection_success": false
    }
  ],
  "hazards": [
    {
      "hazard_id": 1234,
      "lat": 37.4980,
      "lon": 127.0276,
      "danger_score": 7.25,
      "is_active": true,
      "edge_id": "osrm:37.49800:127.02760",
      "osm_edge_id": "osrm:37.49800:127.02760",
      "weight_penalty": 6.26,
      "created_at": "2025-11-28T10:30:00",
      "updated_at": "2025-11-28T10:30:00"
    }
  ],
  "summary": {
    "total_points": 25,
    "successful_roadviews": 23,
    "successful_detections": 22,
    "hazards_created": 8,
    "interval_meters": 50
  }
}
```

### Response Fields

#### `osrm_route`
- `distance`: Total route distance in meters
- `duration`: Estimated travel time in seconds
- `legs_count`: Number of route segments

#### `analyzed_points[]`
Each point contains:
- `index`: Point index in sequence
- `lat`, `lon`: GPS coordinates
- `heading`: Direction of travel in degrees (0-360, 0=North)
- `roadview_image`: Path to downloaded Street View image
- `roadview_success`: Whether image download succeeded
- `roadview_error`: Error message if download failed
- `detection_result`: Object detection results from AI service
- `detection_image`: Path to annotated result image (if available)
- `detection_success`: Whether detection succeeded
- `danger_score`: Calculated hazard danger score (0-10), null if no detection
- `hazard_id`: Created Hazard record ID (only if danger_score >= 3.0)
- `score_analysis`: Detailed danger score calculation breakdown

#### `hazards[]`
Array of Hazard records created for high-risk locations (danger_score >= 3.0):
- `hazard_id`: Database ID of the hazard
- `lat`, `lon`: GPS coordinates
- `danger_score`: Risk score (3.0 - 10.0)
- `is_active`: Whether hazard is currently active
- `edge_id`, `osm_edge_id`: OSRM edge identifiers
- `weight_penalty`: OSRM routing penalty factor
- `created_at`, `updated_at`: Timestamps

#### `summary`
- `total_points`: Total number of analyzed points
- `successful_roadviews`: Number of successful image downloads
- `successful_detections`: Number of successful AI detections
- `hazards_created`: Number of Hazard records created (danger_score >= 3.0)
- `interval_meters`: Configured interval distance

## Example Usage

### Python

```python
import requests

BASE_URL = "http://localhost:8002"
token = "your_jwt_token"

# Define route
payload = {
    "points": [
        {"lat": 37.4980, "lon": 127.0276},
        {"lat": 37.5050, "lon": 127.0300}
    ],
    "interval_meters": 100,
    "tag": "my_route"
}

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.post(
    f"{BASE_URL}/route/analyze",
    json=payload,
    headers=headers,
    timeout=120
)

if response.status_code == 200:
    data = response.json()
    print(f"Total points analyzed: {data['summary']['total_points']}")
    
    for point in data['analyzed_points']:
        if point['detection_success']:
            detections = point['detection_result'].get('detections', [])
            print(f"Point {point['index']}: Found {len(detections)} objects")
```

### cURL

```bash
curl -X POST http://localhost:8002/route/analyze \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "points": [
      {"lat": 37.4980, "lon": 127.0276},
      {"lat": 37.5050, "lon": 127.0300}
    ],
    "interval_meters": 100,
    "tag": "test_route"
  }'
```

## Service Dependencies

### OSRM Server
- **URL**: `http://192.168.1.79:8890`
- **Purpose**: Route calculation and geometry
- **Endpoint**: `/route/v1/{profile}/{coordinates}`

### Google Street View
- **API**: Google Maps Street View Static API
- **Purpose**: Download roadview images
- **Configuration**: Set `GOOGLE_MAPS_API_KEY` in environment

### Detector Service
- **URL**: `http://192.168.1.79:8888`
- **Purpose**: Object detection in roadview images
- **Endpoint**: `/detect`

## Error Handling

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Invalid request (missing/invalid parameters) |
| 401 | Unauthorized (missing/invalid JWT token) |
| 404 | Route not found (OSRM returned no route) |
| 502 | External service unavailable (OSRM/Detector/Google API) |

### Common Errors

**"At least 2 points are required"**
- Provide at least 2 waypoints in the `points` array

**"Invalid point format"**
- Each point must have both `lat` and `lon` fields

**"OSRM request failed"**
- OSRM server is unreachable or returned an error
- Check OSRM server is running at configured URL

**"Google Maps API key not configured"**
- Set `GOOGLE_MAPS_API_KEY` environment variable

**"No Street View available at this location"**
- Google Street View doesn't have coverage at that point
- Point will still be included in response with `roadview_success: false`

## Configuration

Environment variables:

```bash
# OSRM Server
OSRM_BASE_URL=http://192.168.1.79:8890

# Google Street View
GOOGLE_MAPS_API_KEY=your_api_key_here

# Detector Service
AI_SERVER_OBJECT_URL=http://192.168.1.79:8888
```

## Roadview Caching

To reduce API costs and improve performance, the system implements intelligent caching:

### Cache Strategy

1. **Location-based Cache**: Roadviews are cached by coordinates (rounded to ~10m precision) and heading (±5°)

2. **Auto-Refresh Triggers**:
   - Image captured > 10 years ago (outdated street view)
   - Last request > 1 year ago (check for updates)
   - Manual force refresh

3. **Cache Benefits**:
   - Reduced Google API calls (cost savings)
   - Faster response times
   - Historical data preservation

### Cache Behavior

**First Request** (Cache Miss):
```
User → API → Google Street View → Download Image → Save to Cache + File → Response
API Calls: 2 (metadata + image)
```

**Subsequent Request** (Cache Hit):
```
User → API → Check Cache → Return Cached File → Response
API Calls: 0
```

**Stale Cache** (Auto Refresh):
```
User → API → Check Cache (outdated) → Google Street View → Update Cache → Response
API Calls: 2 (metadata + image)
```

### Cache Fields

Cached roadview records include:
- `pano_id`: Unique panorama ID
- `image_date`: When the image was captured (YYYY-MM)
- `created_at`: When first cached
- `thumbnail_url`: Path to saved image file
- `provider_data`: Full metadata from Google API

### Cost Optimization

With caching enabled:
- **Same location within 1 year**: 0 API calls (100% saving)
- **Different locations**: Normal API calls
- **Old images (>10 years)**: Automatic refresh

Example: Analyzing 100 points on a frequently-used route
- Without cache: 200 API calls ($0.014/call = $2.80)
- With cache (80% hit rate): 40 API calls = $0.56 (80% saving)

## Performance Considerations

- **Timeout**: Long routes with many points may take 1-2 minutes
- **Rate Limits**: Google Street View API has daily quotas
- **Storage**: Images are saved to `static/roadviews/<tag>/`
- **Optimization**: Use larger `interval_meters` for faster processing
- **Caching**: Reduces API calls by 50-90% on frequently-analyzed routes

## Testing

Run the test suite:

```bash
python apps/test/functional/test_route_analysis.py
```

This tests:
1. Basic 2-point route analysis
2. Multi-waypoint routes
3. Invalid input handling

## Danger Score Algorithm

### Overview

The danger score calculation uses a weighted algorithm based on:
- **NHTSA** (National Highway Traffic Safety Administration) accident risk analysis
- **Vision Zero** traffic safety research
- **CVPR 2020-2023** deep learning-based road hazard detection papers

### Calculation Method

For each detected object:

```
danger_score = base_weight × position_factor × size_factor × confidence_factor × 10
```

**Components:**

1. **Base Weight** (0.0 - 1.0)
   - High-risk objects (person, bicycle, motorcycle, debris, accident): 0.85 - 1.0
   - Medium-risk objects (car, truck, construction): 0.5 - 0.8
   - Low-risk objects (traffic signs, poles): 0.2 - 0.5

2. **Position Factor** (0.5 - 1.5)
   - Objects near road center: higher risk (1.5)
   - Objects at edges: lower risk (0.5)

3. **Size Factor** (0.7 - 1.3)
   - Larger objects (closer or bigger): higher risk (1.3)
   - Smaller objects (farther): lower risk (0.7)

4. **Confidence Factor** (0.5 - 1.0)
   - Based on AI detection confidence
   - Minimum 0.5 applied to prevent over-penalizing low-confidence detections

### Multi-Object Scoring

When multiple objects are detected, scores are combined non-linearly:

```
combined_score = 10 × (1 - ∏(1 - individual_score/10))
```

This prevents excessive risk inflation while still reflecting cumulative danger.

### Hazard Record Creation

Hazard records are automatically created when:
- Danger score >= 3.0
- Detection is successful
- OSM edge can be resolved

Created hazards:
- Are stored in the `hazards` database table
- Include weight penalties for OSRM routing
- Trigger automatic OSRM customize updates
- Are included in hazard-aware route calculations

## File Storage

Generated files are organized as:

```
static/
  roadviews/
    <tag>/
      roadview_<lat>_<lon>_<heading>.jpg
      result_<index>.jpg (if detector returns annotated images)
```

Files persist on disk for later retrieval and analysis.
