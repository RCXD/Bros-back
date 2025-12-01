# Roadview Caching System

## Overview

The Roadview Caching System reduces Google Street View API costs by intelligently caching roadview images and metadata in the database.

## Architecture

### Components

1. **Roadview Model** (`apps/roadview/models.py`)
   - Stores roadview metadata and image references
   - Includes `needs_refresh()` method for cache validation
   - Fields: `pano_id`, `image_date`, `thumbnail_url`, `created_at`, etc.

2. **Cache Logic** (`apps/route/views.py::_get_roadview_image()`)
   - Checks cache before API calls
   - Validates cache freshness
   - Auto-refreshes stale data

3. **Database Tables**
   - `roadviews`: Main cache storage
   - `roadview_cache`: Aggregate availability cache (for future use)
   - `roadview_requests`: Request tracking
   - `roadview_api_usage`: API quota monitoring

## Cache Strategy

### Cache Key

Roadviews are cached using:
- **Latitude** (rounded to 4 decimals ≈ 10m precision)
- **Longitude** (rounded to 4 decimals ≈ 10m precision)
- **Heading** (±5° tolerance)
- **Provider** (Google/Kakao/Naver)

### Cache Validity Rules

A cached roadview is considered **VALID** if:
1. Image capture date < 10 years old (default)
2. Last request < 1 year old (default)
3. Image file still exists on disk

A cached roadview is **REFRESHED** if:
1. Image capture date >= 10 years (outdated street view)
2. Last request >= 1 year (check for updates)
3. `force_refresh=True` parameter

### Negative Caching

Failed lookups (no Street View available) are also cached to prevent repeated API calls:
- Status: `NOT_AVAILABLE`
- Cached for 1 year
- Re-checked after expiration

## Usage

### Basic Usage (Automatic Caching)

```python
from apps.route.views import _get_roadview_image

result = _get_roadview_image(
    lat=37.4980,
    lon=127.0276,
    heading=45,
    tag="route_001"
)

if result['success']:
    print(f"Image: {result['file_path']}")
    print(f"Cached: {result.get('cached', False)}")
    if result.get('cached'):
        print(f"Cache age: {result['cache_age_days']} days")
```

### Custom Cache Parameters

```python
result = _get_roadview_image(
    lat=37.4980,
    lon=127.0276,
    heading=45,
    tag="route_001",
    image_age_years=5,      # Refresh if image > 5 years old
    request_age_years=0.5,  # Refresh if last request > 6 months
    force_refresh=False     # Set True to bypass cache
)
```

### Force Refresh

```python
# Force API call even if cached
result = _get_roadview_image(
    lat=37.4980,
    lon=127.0276,
    heading=45,
    force_refresh=True
)
```

## Cache Statistics

### Query Cache Records

```python
from apps.roadview.models import init_models
from apps.config.server import db

Roadview, _, _, _ = init_models(db)

# Get all cached roadviews
cached = Roadview.query.filter_by(
    provider='GOOGLE_STREET_VIEW',
    status='AVAILABLE'
).all()

print(f"Total cached: {len(cached)}")
```

### Cache Hit Rate

```python
from apps.roadview.models import init_models
from datetime import datetime, timedelta

Roadview, _, RoadviewRequest, _ = init_models(db)

# Recent requests (last 24 hours)
since = datetime.now() - timedelta(days=1)
requests = RoadviewRequest.query.filter(
    RoadviewRequest.created_at >= since
).all()

cache_hits = sum(1 for r in requests if r.cache_hit)
total = len(requests)
hit_rate = (cache_hits / total * 100) if total > 0 else 0

print(f"Cache hit rate: {hit_rate:.1f}%")
print(f"Cache hits: {cache_hits}/{total}")
```

### Clear Old Cache

```python
from apps.roadview.models import init_models
from datetime import datetime, timedelta

Roadview, _, _, _ = init_models(db)

# Delete roadviews older than 10 years
cutoff = datetime.now() - timedelta(days=365*10)
old_records = Roadview.query.filter(
    Roadview.created_at < cutoff
).delete()

db.session.commit()
print(f"Deleted {old_records} old records")
```

## Performance Impact

### API Call Reduction

**Scenario**: 100-point route analysis

| Cache State | API Calls | Cost (USD) | Time (sec) |
|------------|-----------|------------|------------|
| Cold (0% hit) | 200 | $2.80 | 120 |
| Warm (50% hit) | 100 | $1.40 | 65 |
| Hot (90% hit) | 20 | $0.28 | 25 |

**Cost Calculation**: Google Street View = $0.007/image + $0.007/metadata = $0.014/point

### Storage Requirements

- **Database**: ~1KB per roadview record
- **Image files**: ~50-150KB per 640x640 image
- **1000 cached roadviews**: ~1MB DB + ~100MB images

## Configuration

### Environment Variables

```bash
# Google Street View API
GOOGLE_MAPS_API_KEY=your_api_key

# Cache tuning (optional)
ROADVIEW_IMAGE_AGE_YEARS=10
ROADVIEW_REQUEST_AGE_YEARS=1
```

### Database Indexes

Optimized queries with indexes:
```sql
-- Location lookup
CREATE INDEX idx_roadview_location ON roadviews (latitude, longitude);

-- Provider + status lookup
CREATE INDEX idx_roadview_provider_status ON roadviews (provider, status);

-- Heading lookup
CREATE INDEX idx_roadview_heading ON roadviews (heading);

-- Created date for expiration
CREATE INDEX idx_roadview_created ON roadviews (created_at);
```

## Maintenance

### Periodic Cleanup Task

Run weekly to remove expired cache:

```python
from apps.roadview.models import init_models
from datetime import datetime, timedelta
from apps.config.server import db

Roadview, _, _, _ = init_models(db)

# Remove roadviews with no file
orphaned = Roadview.query.all()
removed = 0
for rv in orphaned:
    if rv.thumbnail_url:
        file_path = rv.thumbnail_url.lstrip('/')
        if not os.path.exists(file_path):
            db.session.delete(rv)
            removed += 1

db.session.commit()
print(f"Removed {removed} orphaned records")
```

### Monitor API Usage

```python
from apps.roadview.models import init_models
from datetime import date

_, _, _, RoadviewAPIUsage = init_models(db)

# Today's usage
today = date.today()
usage = RoadviewAPIUsage.query.filter_by(
    provider='GOOGLE_STREET_VIEW',
    date=today
).first()

if usage:
    print(f"Total requests: {usage.total_requests}")
    print(f"Cached: {usage.cached_requests}")
    print(f"API calls: {usage.total_requests - usage.cached_requests}")
    print(f"Estimated cost: ${usage.estimated_cost:.2f}")
```

## Best Practices

1. **Use appropriate precision**: 4 decimal places (10m) is sufficient for most use cases
2. **Set reasonable expiration**: 10 years for image age, 1 year for request age
3. **Monitor storage**: Implement periodic cleanup for old files
4. **Track costs**: Monitor API usage and cache hit rates
5. **Handle errors gracefully**: Continue on cache failures, fall back to API

## Troubleshooting

### Cache Not Working

1. Check database connection
2. Verify Roadview table exists
3. Check file permissions on static/roadviews/
4. Review logs for cache errors

### High API Costs

1. Check cache hit rate (should be > 50% for repeated routes)
2. Verify cache expiration settings
3. Look for `force_refresh` usage
4. Check for coordinate precision issues

### Stale Images

1. Decrease `image_age_years` parameter
2. Force refresh specific locations
3. Clear cache for affected areas

## Future Enhancements

- [ ] Add LRU eviction for storage limits
- [ ] Implement distributed cache (Redis)
- [ ] Add cache warming for popular routes
- [ ] Support multiple image resolutions
- [ ] Automatic quality assessment
- [ ] Cross-provider fallback (Google → Kakao → Naver)
