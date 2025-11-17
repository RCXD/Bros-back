# Roadview Module Documentation

## Overview

The Roadview module provides unified access to multiple map roadview services:
- **Google Street View API**
- **Kakao Roadview API** 
- **Naver Street View (Panorama) API**

Features:
- Automatic fallback between providers
- Intelligent caching to reduce API costs
- Usage tracking and quota management
- Support for all three major Korean map providers

## Database Models

### Roadview
Main table storing roadview data and metadata.

**Fields:**
- `roadview_id`: Primary key
- `latitude`, `longitude`: Location coordinates
- `provider`: Which service provided the data (Google/Kakao/Naver)
- `status`: Availability status
- `pano_id`: Provider's panorama ID
- `heading`, `pitch`, `fov`: Camera parameters
- `thumbnail_url`, `panorama_url`: Image URLs
- `image_date`: When the roadview image was captured
- `distance_from_location`: Distance from requested location
- `provider_data`: Provider-specific metadata (JSON)

### RoadviewCache
Cache table to reduce API calls.

**Fields:**
- `lat_rounded`, `lng_rounded`: Rounded coordinates (~100m precision)
- `google_available`, `kakao_available`, `naver_available`: Availability flags
- `best_provider`: Recommended provider for this location
- `last_checked`: Cache freshness timestamp

### RoadviewRequest
Track all user requests for analytics.

**Fields:**
- `user_id`: User who made the request
- `latitude`, `longitude`: Requested location
- `providers_checked`: List of providers queried
- `provider_used`: Which provider was used
- `response_time_ms`: Request duration
- `cache_hit`: Whether cache was used
- `success`: Request success status

### RoadviewAPIUsage
Daily API usage statistics per provider.

**Fields:**
- `provider`: Google/Kakao/Naver
- `date`: Usage date
- `total_requests`, `successful_requests`, `failed_requests`: Counts
- `cached_requests`: Cache hit count
- `estimated_cost`: Cost estimate based on API pricing

## API Endpoints

### POST /roadview/check
Check roadview availability at a location.

**Request:**
```json
{
  "latitude": 37.5665,
  "longitude": 126.9780,
  "radius": 50,
  "provider": "google"  // optional: "google", "kakao", "naver"
}
```

**Response (Success):**
```json
{
  "available": true,
  "provider": "google",
  "roadview_id": 123,
  "metadata": {
    "pano_id": "CAoSLEFGMVFpcE...",
    "latitude": 37.5665,
    "longitude": 126.9780,
    "heading": 90.0,
    "pitch": 0.0,
    "image_date": "2023-08-01",
    "distance": 15.5
  },
  "cache_hit": false,
  "response_time_ms": 245
}
```

**Response (Not Available):**
```json
{
  "available": false,
  "providers_checked": ["google", "kakao", "naver"],
  "errors": {
    "google": "No coverage at this location",
    "kakao": "API error",
    "naver": "No coverage"
  },
  "response_time_ms": 890
}
```

### POST /roadview/check-all
Check availability across all providers simultaneously.

**Request:**
```json
{
  "latitude": 37.5665,
  "longitude": 126.9780,
  "radius": 50
}
```

**Response:**
```json
{
  "google": {
    "available": true,
    "metadata": {...}
  },
  "kakao": {
    "available": false,
    "error": "No coverage"
  },
  "naver": {
    "available": true,
    "metadata": {...}
  }
}
```

### GET /roadview/roadview/<roadview_id>
Get detailed roadview information by ID.

**Response:**
```json
{
  "roadview_id": 123,
  "provider": "google_street_view",
  "latitude": 37.5665,
  "longitude": 126.9780,
  "pano_id": "CAoSLEFGMVFpcE...",
  "heading": 90.0,
  "pitch": 0.0,
  "thumbnail_url": "https://...",
  "panorama_url": "https://...",
  ...
}
```

### GET /roadview/history
Get user's roadview request history.

**Query Parameters:**
- `limit`: Max results (default 50, max 100)
- `offset`: Pagination offset (default 0)

### GET /roadview/cache/stats
Get cache statistics.

**Response:**
```json
{
  "total_locations_cached": 1523,
  "google_available_count": 1250,
  "kakao_available_count": 980,
  "naver_available_count": 1100
}
```

### GET /roadview/usage/stats
Get API usage statistics.

**Query Parameters:**
- `days`: Number of days to look back (default 7)

**Response:**
```json
{
  "start_date": "2025-11-10",
  "end_date": "2025-11-17",
  "providers": {
    "google_street_view": {
      "total_requests": 450,
      "successful_requests": 380,
      "failed_requests": 70,
      "cached_requests": 120,
      "estimated_cost": 2.31
    },
    "kakao_roadview": {...},
    "naver_street_view": {...}
  }
}
```

## Configuration

### Environment Variables

Create a `.env` file or set these environment variables:

```bash
# Google Street View
GOOGLE_MAPS_API_KEY=your_google_api_key_here

# Kakao Roadview
KAKAO_REST_API_KEY=your_kakao_rest_api_key
KAKAO_JAVASCRIPT_KEY=your_kakao_javascript_key  # Optional

# Naver Street View
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
```

### API Key Setup

#### Google Street View
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable "Street View Static API" and "Maps JavaScript API"
3. Create API key with Street View enabled
4. Set billing (required for production use)

#### Kakao Roadview
1. Go to [Kakao Developers](https://developers.kakao.com/)
2. Create application
3. Get REST API key from app settings
4. Enable "지도" (Map) service

#### Naver Street View
1. Go to [Naver Cloud Platform](https://www.ncloud.com/)
2. Create application
3. Enable "Maps" service
4. Get Client ID and Secret

## Usage Examples

### Python Client
```python
from apps.roadview.utils import get_roadview_loader_from_env

# Initialize loader with environment variables
loader = get_roadview_loader_from_env()

# Check best available roadview
result = loader.load_best_roadview(
    latitude=37.5665,
    longitude=126.9780,
    radius=50
)

if result['success']:
    print(f"Found roadview from {result['provider']}")
    print(f"Pano ID: {result['metadata']['pano_id']}")
    print(f"Distance: {result['metadata']['distance']}m")
else:
    print("No roadview available")
    print(f"Errors: {result['errors']}")
```

### Direct API Client Usage
```python
from apps.roadview.utils import GoogleStreetViewClient

# Initialize client
client = GoogleStreetViewClient(api_key="your_api_key")

# Check availability
available, metadata = client.check_availability(37.5665, 126.9780)

if available:
    # Get image URL
    image_url = client.get_image_url(
        latitude=37.5665,
        longitude=126.9780,
        heading=90,
        pitch=0,
        width=640,
        height=480
    )
    print(f"Image URL: {image_url}")
```

### JavaScript/Frontend Example
```javascript
// Check roadview availability
async function checkRoadview(lat, lng) {
  const response = await fetch('/roadview/check', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({
      latitude: lat,
      longitude: lng,
      radius: 50,
      provider: 'google'  // optional
    })
  });
  
  const result = await response.json();
  
  if (result.available) {
    console.log(`Roadview available from ${result.provider}`);
    displayRoadview(result.metadata);
  } else {
    console.log('No roadview available at this location');
  }
}

// Check all providers
async function checkAllProviders(lat, lng) {
  const response = await fetch('/roadview/check-all', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${jwtToken}`
    },
    body: JSON.stringify({
      latitude: lat,
      longitude: lng,
      radius: 50
    })
  });
  
  const results = await response.json();
  
  console.log('Google:', results.google.available);
  console.log('Kakao:', results.kakao.available);
  console.log('Naver:', results.naver.available);
}
```

## Integration Steps

### 1. Initialize Database Models
```python
# In your Flask app initialization
from apps.roadview import init_roadview_models
from apps.config.common import db

app = Flask(__name__)
# ... configure app ...

with app.app_context():
    init_roadview_models(db)
```

### 2. Register Blueprint
```python
from apps.roadview import bp as roadview_bp

app.register_blueprint(roadview_bp, url_prefix='/roadview')
```

### 3. Run Database Migration
```bash
flask db migrate -m "Add roadview models"
flask db upgrade
```

### 4. Set Environment Variables
```bash
# In .env file or environment
GOOGLE_MAPS_API_KEY=your_key
KAKAO_REST_API_KEY=your_key
NAVER_CLIENT_ID=your_id
NAVER_CLIENT_SECRET=your_secret
```

## Provider Comparison

| Feature | Google Street View | Kakao Roadview | Naver Street View |
|---------|-------------------|----------------|-------------------|
| **Coverage** | Global | Korea-focused | Korea-focused |
| **Quality** | High | High | High |
| **Freshness** | Regular updates | Frequent in Korea | Frequent in Korea |
| **Cost** | $7 per 1000 requests | Free tier available | Pay-per-use |
| **Static Images** | ✅ Yes | ⚠️ Limited | ✅ Yes |
| **Panorama ID** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Best For** | International | Korean cities | Korean cities |

## Best Practices

### 1. Use Caching
The module automatically caches results for 30 days. This reduces API costs significantly.

### 2. Set Appropriate Radius
- Use 50m for urban areas
- Use 100m for suburban areas
- Use 200m+ for rural areas

### 3. Provider Priority
For Korean locations:
1. Kakao (free tier)
2. Naver (good Korean coverage)
3. Google (fallback for international)

### 4. Monitor API Usage
Check `/roadview/usage/stats` regularly to track costs and identify optimization opportunities.

### 5. Handle Unavailability
Always provide fallback UI when roadview is not available:
```python
if not result['success']:
    # Show regular map view or satellite imagery
    return fallback_view()
```

## Troubleshooting

### "API key not valid"
- Verify API key is correct in environment variables
- Check API is enabled in provider console
- Verify billing is set up (for Google)

### "No coverage at location"
- Try larger radius
- Check all providers with `/check-all`
- Location may genuinely have no coverage

### High API Costs
- Increase cache precision in `round_coordinates()`
- Use cache stats to identify frequently accessed areas
- Consider pre-caching popular locations

### Slow Response Times
- Check network connectivity to API servers
- Monitor response times via RoadviewRequest table
- Consider implementing background processing for non-critical requests

## Cost Estimation

### Google Street View
- Free: 28,000 requests/month
- Paid: $7 per 1000 requests after free tier
- Annual cost for 100k requests: ~$504

### Kakao Roadview
- Free tier: Check Kakao documentation
- Generally more generous for Korean locations

### Naver Street View
- Pay-per-use model
- Check Naver Cloud Platform pricing

## Security Considerations

1. **Never expose API keys in frontend code**
2. **Use JWT authentication for all endpoints**
3. **Implement rate limiting per user**
4. **Monitor for unusual usage patterns**
5. **Rotate API keys regularly**

## Performance Tips

1. **Pre-cache popular locations** during off-peak hours
2. **Use rounded coordinates** for cache efficiency
3. **Implement request debouncing** on frontend
4. **Consider CDN** for static roadview images
5. **Monitor and optimize** slow queries using database indexes
