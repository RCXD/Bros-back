"""
Roadview Models - Store roadview data from Google, Kakao, and Naver APIs
"""

from datetime import datetime
from sqlalchemy import Enum as SQLEnum
import enum


class RoadviewProvider(enum.Enum):
    """Road view service providers"""

    GOOGLE_STREET_VIEW = "google_street_view"
    KAKAO_ROADVIEW = "kakao_roadview"
    NAVER_STREET_VIEW = "naver_street_view"


class RoadviewStatus(enum.Enum):
    """Status of roadview data"""

    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"
    PENDING = "pending"
    ERROR = "error"


# Cache for initialized models
_initialized_models = None


def init_models(db):
    """Initialize roadview models with db instance (singleton pattern)"""
    global _initialized_models

    # Return cached models if already initialized
    if _initialized_models is not None:
        return _initialized_models

    class Roadview(db.Model):
        """
        Main roadview record - stores metadata about roadview requests and availability
        """

        __tablename__ = "roadviews"

        roadview_id = db.Column(db.Integer, primary_key=True)

        # Location information
        latitude = db.Column(db.Float, nullable=False, index=True)
        longitude = db.Column(db.Float, nullable=False, index=True)
        address = db.Column(db.String(500))  # Human-readable address

        # Provider information
        provider = db.Column(SQLEnum(RoadviewProvider), nullable=False)
        status = db.Column(SQLEnum(RoadviewStatus), default=RoadviewStatus.PENDING)

        # Roadview metadata
        pano_id = db.Column(db.String(255))  # Panorama ID (Google/Kakao/Naver specific)
        heading = db.Column(db.Float)  # Camera heading direction (0-360 degrees)
        pitch = db.Column(db.Float)  # Camera pitch angle (-90 to 90 degrees)
        fov = db.Column(db.Float, default=90.0)  # Field of view
        zoom = db.Column(db.Integer, default=1)  # Zoom level

        # Image URLs
        thumbnail_url = db.Column(db.String(1000))  # Thumbnail image URL
        panorama_url = db.Column(db.String(1000))  # Full panorama URL
        image_width = db.Column(db.Integer)  # Image dimensions
        image_height = db.Column(db.Integer)

        # Provider-specific data
        provider_data = db.Column(db.JSON)  # Store provider-specific metadata

        # Quality metrics
        image_date = db.Column(db.Date)  # When the roadview image was captured
        distance_from_location = db.Column(
            db.Float
        )  # Distance in meters from requested location

        # Error handling
        error_message = db.Column(db.Text)
        retry_count = db.Column(db.Integer, default=0)

        # Relationships
        user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
        location_id = db.Column(
            db.Integer, nullable=True
        )  # Removed FK - locations table doesn't exist

        # Timestamps
        created_at = db.Column(db.DateTime, default=datetime.now, index=True)
        updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
        expires_at = db.Column(db.DateTime)  # URL expiration time

        def to_dict(self):
            """Convert to dictionary for JSON response"""
            return {
                "roadview_id": self.roadview_id,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "address": self.address,
                "provider": self.provider.value if self.provider else None,
                "status": self.status.value if self.status else None,
                "pano_id": self.pano_id,
                "heading": self.heading,
                "pitch": self.pitch,
                "fov": self.fov,
                "zoom": self.zoom,
                "thumbnail_url": self.thumbnail_url,
                "panorama_url": self.panorama_url,
                "image_width": self.image_width,
                "image_height": self.image_height,
                "image_date": self.image_date.isoformat() if self.image_date else None,
                "distance_from_location": self.distance_from_location,
                "provider_data": self.provider_data,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            }

        @staticmethod
        def needs_refresh(
            image_date, last_requested_at, image_age_years=10, request_age_years=1
        ):
            """
            Check if cached roadview needs to be refreshed.

            Criteria for refresh:
            1. Image capture date is older than image_age_years (default: 10 years)
            2. Last request date is older than request_age_years (default: 1 year)

            Args:
                image_date: Date when the roadview image was captured
                last_requested_at: DateTime when this roadview was last requested
                image_age_years: Maximum age of image in years (default 10)
                request_age_years: Maximum age of last request in years (default 1)

            Returns:
                bool: True if refresh is needed, False if cache is still valid
            """
            from datetime import datetime, timedelta

            now = datetime.now()

            # Check if image is too old (captured more than N years ago)
            if image_date:
                if isinstance(image_date, str):
                    # Parse string date (YYYY-MM format from Google)
                    try:
                        if len(image_date) == 7:  # YYYY-MM
                            image_datetime = datetime.strptime(
                                image_date + "-01", "%Y-%m-%d"
                            )
                        else:
                            image_datetime = datetime.fromisoformat(image_date)
                    except:
                        image_datetime = None
                else:
                    # Assume it's a date object
                    image_datetime = datetime.combine(image_date, datetime.min.time())

                if image_datetime:
                    image_age = now - image_datetime
                    if image_age.days > (image_age_years * 365):
                        return True

            # Check if last request is too old
            if last_requested_at:
                request_age = now - last_requested_at
                if request_age.days > (request_age_years * 365):
                    return True

            # If no date information, don't refresh
            return False

    class RoadviewCache(db.Model):
        """
        Cache roadview availability and metadata to reduce API calls
        """

        __tablename__ = "roadview_cache"

        cache_id = db.Column(db.Integer, primary_key=True)

        # Location (rounded for cache efficiency)
        lat_rounded = db.Column(
            db.Float, nullable=False, index=True
        )  # Rounded to ~100m
        lng_rounded = db.Column(db.Float, nullable=False, index=True)

        # Provider availability
        google_available = db.Column(db.Boolean, default=None)
        kakao_available = db.Column(db.Boolean, default=None)
        naver_available = db.Column(db.Boolean, default=None)

        # Best provider (based on quality/availability)
        best_provider = db.Column(SQLEnum(RoadviewProvider))

        # Cache metadata
        check_count = db.Column(db.Integer, default=1)
        last_checked = db.Column(db.DateTime, default=datetime.now)
        created_at = db.Column(db.DateTime, default=datetime.now)

        # Composite index for efficient lookup
        __table_args__ = (db.Index("idx_location_cache", "lat_rounded", "lng_rounded"),)

        def to_dict(self):
            """Convert to dictionary"""
            return {
                "cache_id": self.cache_id,
                "lat_rounded": self.lat_rounded,
                "lng_rounded": self.lng_rounded,
                "google_available": self.google_available,
                "kakao_available": self.kakao_available,
                "naver_available": self.naver_available,
                "best_provider": (
                    self.best_provider.value if self.best_provider else None
                ),
                "check_count": self.check_count,
                "last_checked": (
                    self.last_checked.isoformat() if self.last_checked else None
                ),
            }

    class RoadviewRequest(db.Model):
        """
        Track user requests for roadview data
        """

        __tablename__ = "roadview_requests"

        request_id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)

        # Request details
        latitude = db.Column(db.Float, nullable=False)
        longitude = db.Column(db.Float, nullable=False)
        preferred_provider = db.Column(SQLEnum(RoadviewProvider))

        # Results
        providers_checked = db.Column(db.JSON)  # List of providers checked
        provider_used = db.Column(SQLEnum(RoadviewProvider))
        roadview_id = db.Column(db.Integer, db.ForeignKey("roadviews.roadview_id"))

        # Metrics
        response_time_ms = db.Column(db.Integer)  # Time to get result
        api_calls_made = db.Column(db.Integer, default=0)  # Number of API calls
        cache_hit = db.Column(db.Boolean, default=False)

        # Status
        success = db.Column(db.Boolean, default=False)
        error_message = db.Column(db.Text)

        created_at = db.Column(db.DateTime, default=datetime.now, index=True)

        def to_dict(self):
            """Convert to dictionary"""
            return {
                "request_id": self.request_id,
                "user_id": self.user_id,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "preferred_provider": (
                    self.preferred_provider.value if self.preferred_provider else None
                ),
                "providers_checked": self.providers_checked,
                "provider_used": (
                    self.provider_used.value if self.provider_used else None
                ),
                "roadview_id": self.roadview_id,
                "response_time_ms": self.response_time_ms,
                "api_calls_made": self.api_calls_made,
                "cache_hit": self.cache_hit,
                "success": self.success,
                "error_message": self.error_message,
                "created_at": self.created_at.isoformat() if self.created_at else None,
            }

    class RoadviewAPIUsage(db.Model):
        """
        Track API usage and quotas for each provider
        """

        __tablename__ = "roadview_api_usage"

        usage_id = db.Column(db.Integer, primary_key=True)

        provider = db.Column(SQLEnum(RoadviewProvider), nullable=False)
        date = db.Column(
            db.Date, nullable=False, default=datetime.now().date, index=True
        )

        # Usage counts
        total_requests = db.Column(db.Integer, default=0)
        successful_requests = db.Column(db.Integer, default=0)
        failed_requests = db.Column(db.Integer, default=0)
        cached_requests = db.Column(db.Integer, default=0)

        # Cost tracking (if applicable)
        estimated_cost = db.Column(db.Float, default=0.0)

        # Quota management
        daily_limit = db.Column(db.Integer)
        quota_exceeded = db.Column(db.Boolean, default=False)

        updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

        # Composite unique constraint
        __table_args__ = (
            db.UniqueConstraint("provider", "date", name="unique_provider_date"),
        )

        def to_dict(self):
            """Convert to dictionary"""
            return {
                "usage_id": self.usage_id,
                "provider": self.provider.value if self.provider else None,
                "date": self.date.isoformat() if self.date else None,
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "cached_requests": self.cached_requests,
                "estimated_cost": self.estimated_cost,
                "daily_limit": self.daily_limit,
                "quota_exceeded": self.quota_exceeded,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            }

    # Cache the initialized models
    _initialized_models = (Roadview, RoadviewCache, RoadviewRequest, RoadviewAPIUsage)
    return _initialized_models
