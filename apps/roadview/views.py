"""
Roadview Views - API endpoints for roadview services
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import time

from .models import RoadviewProvider, RoadviewStatus, init_models
from .utils import (
    RoadviewLoader,
    get_roadview_loader_from_env,
    round_coordinates,
    RoadviewAPIError,
)

bp = Blueprint("roadview", __name__)

# Initialize models (will be set up when app context is available)
Roadview = None
RoadviewCache = None
RoadviewRequest = None
RoadviewAPIUsage = None


def init_roadview_models(db):
    """Initialize roadview models with db instance"""
    global Roadview, RoadviewCache, RoadviewRequest, RoadviewAPIUsage
    Roadview, RoadviewCache, RoadviewRequest, RoadviewAPIUsage = init_models(db)


@bp.route("/check", methods=["POST"])
@jwt_required()
def check_roadview():
    """
    Check roadview availability at a location

    Request JSON:
        {
            "latitude": 37.5665,
            "longitude": 126.9780,
            "radius": 50,
            "provider": "google" // optional: "google", "kakao", "naver"
        }

    Response:
        {
            "available": true,
            "provider": "google",
            "roadview_id": 123,
            "metadata": {...},
            "cache_hit": false
        }
    """
    user_id = get_jwt_identity()
    data = request.get_json()

    if not data or "latitude" not in data or "longitude" not in data:
        return jsonify({"message": "latitude and longitude are required"}), 400

    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    radius = int(data.get("radius", 50))
    preferred_provider = data.get("provider")

    from apps.config.server import db

    # Track request
    start_time = time.time()
    rv_request = RoadviewRequest(
        user_id=user_id,
        latitude=latitude,
        longitude=longitude,
        preferred_provider=(
            RoadviewProvider[preferred_provider.upper().replace(" ", "_")]
            if preferred_provider
            else None
        ),
    )
    db.session.add(rv_request)
    db.session.commit()

    try:
        # Check cache first
        lat_rounded, lng_rounded = round_coordinates(latitude, longitude, precision=3)
        cache = RoadviewCache.query.filter_by(
            lat_rounded=lat_rounded, lng_rounded=lng_rounded
        ).first()

        cache_hit = False
        if cache and cache.last_checked > datetime.now() - timedelta(days=30):
            # Cache is valid
            cache_hit = True
            rv_request.cache_hit = True

            # Use cached best provider
            if cache.best_provider:
                provider_map = {
                    "google": cache.google_available,
                    "kakao": cache.kakao_available,
                    "naver": cache.naver_available,
                }
                provider_name = cache.best_provider.value.replace("_", " ").split()[0]

                if provider_map.get(provider_name):
                    rv_request.provider_used = cache.best_provider
                    rv_request.success = True
                    rv_request.response_time_ms = int((time.time() - start_time) * 1000)
                    db.session.commit()

                    return (
                        jsonify(
                            {
                                "available": True,
                                "provider": provider_name,
                                "cache_hit": True,
                                "response_time_ms": rv_request.response_time_ms,
                            }
                        ),
                        200,
                    )

        # Load roadview from APIs
        loader = get_roadview_loader_from_env()
        result = loader.load_best_roadview(
            latitude, longitude, radius, preferred_provider
        )

        rv_request.providers_checked = result["providers_checked"]
        rv_request.api_calls_made = result["api_calls_made"]
        rv_request.response_time_ms = result["response_time_ms"]
        rv_request.success = result["success"]

        if result["success"]:
            # Create roadview record
            provider_enum = (
                RoadviewProvider[
                    result["provider"].upper().replace(" ", "_") + "_STREET_VIEW"
                ]
                if result["provider"] == "google"
                else RoadviewProvider[
                    f"{result['provider'].upper()}_{'ROADVIEW' if result['provider'] == 'kakao' else 'STREET_VIEW'}"
                ]
            )

            metadata = result["metadata"]
            roadview = Roadview(
                latitude=latitude,
                longitude=longitude,
                provider=provider_enum,
                status=RoadviewStatus.AVAILABLE,
                pano_id=metadata.get("pano_id"),
                heading=metadata.get("heading"),
                pitch=metadata.get("pitch") or metadata.get("tilt"),
                distance_from_location=metadata.get("distance"),
                user_id=user_id,
                provider_data=metadata,
            )

            # Parse image date if available
            if metadata.get("date"):
                try:
                    date_str = metadata["date"]
                    if len(date_str) == 7:  # YYYY-MM format
                        roadview.image_date = datetime.strptime(
                            date_str, "%Y-%m"
                        ).date()
                except:
                    pass

            db.session.add(roadview)
            db.session.commit()

            rv_request.roadview_id = roadview.roadview_id
            rv_request.provider_used = provider_enum

            # Update cache
            if cache:
                cache.check_count += 1
                cache.last_checked = datetime.now()
            else:
                cache = RoadviewCache(lat_rounded=lat_rounded, lng_rounded=lng_rounded)
                db.session.add(cache)

            # Update provider availability
            if result["provider"] == "google":
                cache.google_available = True
                cache.best_provider = RoadviewProvider.GOOGLE_STREET_VIEW
            elif result["provider"] == "kakao":
                cache.kakao_available = True
                cache.best_provider = RoadviewProvider.KAKAO_ROADVIEW
            elif result["provider"] == "naver":
                cache.naver_available = True
                cache.best_provider = RoadviewProvider.NAVER_STREET_VIEW

            db.session.commit()

            # Update API usage
            update_api_usage(db, provider_enum, success=True)

            return (
                jsonify(
                    {
                        "available": True,
                        "provider": result["provider"],
                        "roadview_id": roadview.roadview_id,
                        "metadata": roadview.to_dict(),
                        "cache_hit": cache_hit,
                        "response_time_ms": result["response_time_ms"],
                    }
                ),
                200,
            )

        else:
            # No roadview available
            rv_request.error_message = str(result.get("errors", {}))
            db.session.commit()

            # Update cache with unavailability
            if cache:
                cache.check_count += 1
                cache.last_checked = datetime.now()
            else:
                cache = RoadviewCache(lat_rounded=lat_rounded, lng_rounded=lng_rounded)
                db.session.add(cache)

            # Mark all as unavailable
            cache.google_available = False
            cache.kakao_available = False
            cache.naver_available = False
            db.session.commit()

            return (
                jsonify(
                    {
                        "available": False,
                        "providers_checked": result["providers_checked"],
                        "errors": result["errors"],
                        "response_time_ms": result["response_time_ms"],
                    }
                ),
                404,
            )

    except Exception as e:
        rv_request.error_message = str(e)
        rv_request.success = False
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Failed to check roadview",
                }
            ),
            500,
        )


@bp.route("/check-all", methods=["POST"])
@jwt_required()
def check_all_providers():
    """
    Check roadview availability across all providers

    Request JSON:
        {
            "latitude": 37.5665,
            "longitude": 126.9780,
            "radius": 50
        }

    Response:
        {
            "google": {"available": true, "metadata": {...}},
            "kakao": {"available": false},
            "naver": {"available": true, "metadata": {...}}
        }
    """
    data = request.get_json()

    if not data or "latitude" not in data or "longitude" not in data:
        return jsonify({"message": "latitude and longitude are required"}), 400

    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    radius = int(data.get("radius", 50))

    try:
        loader = get_roadview_loader_from_env()
        results = loader.check_all_providers(latitude, longitude, radius)

        return jsonify(results), 200

    except Exception as e:
        return jsonify({"message": "Failed to check providers"}), 500


@bp.route("/roadview/<int:roadview_id>", methods=["GET"])
@jwt_required()
def get_roadview(roadview_id):
    """Get roadview details by ID"""
    from ..config.common import db

    roadview = db.session.get(Roadview, roadview_id)

    if not roadview:
        return jsonify({"message": "Roadview not found"}), 404

    return jsonify(roadview.to_dict()), 200


@bp.route("/history", methods=["GET"])
@jwt_required()
def get_user_history():
    """
    Get user's roadview request history

    Query params:
        limit: Max results (default 50)
        offset: Pagination offset
    """
    user_id = get_jwt_identity()

    limit = min(int(request.args.get("limit", 50)), 100)
    offset = int(request.args.get("offset", 0))

    from ..config.common import db

    requests_query = RoadviewRequest.query.filter_by(user_id=user_id).order_by(
        RoadviewRequest.created_at.desc()
    )

    total = requests_query.count()
    requests_list = requests_query.limit(limit).offset(offset).all()

    return (
        jsonify(
            {
                "total": total,
                "limit": limit,
                "offset": offset,
                "requests": [req.to_dict() for req in requests_list],
            }
        ),
        200,
    )


@bp.route("/cache/stats", methods=["GET"])
def get_cache_stats():
    """Get cache statistics"""
    from ..config.common import db

    total_cached = RoadviewCache.query.count()
    google_available = RoadviewCache.query.filter_by(google_available=True).count()
    kakao_available = RoadviewCache.query.filter_by(kakao_available=True).count()
    naver_available = RoadviewCache.query.filter_by(naver_available=True).count()

    return (
        jsonify(
            {
                "total_locations_cached": total_cached,
                "google_available_count": google_available,
                "kakao_available_count": kakao_available,
                "naver_available_count": naver_available,
            }
        ),
        200,
    )


@bp.route("/usage/stats", methods=["GET"])
def get_usage_stats():
    """
    Get API usage statistics

    Query params:
        days: Number of days to look back (default 7)
    """
    days = int(request.args.get("days", 7))
    start_date = datetime.now().date() - timedelta(days=days)

    from ..config.common import db

    usage_records = RoadviewAPIUsage.query.filter(
        RoadviewAPIUsage.date >= start_date
    ).all()

    stats = {
        "start_date": start_date.isoformat(),
        "end_date": datetime.now().date().isoformat(),
        "providers": {},
    }

    for usage in usage_records:
        provider = usage.provider.value
        if provider not in stats["providers"]:
            stats["providers"][provider] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "cached_requests": 0,
                "estimated_cost": 0.0,
            }

        stats["providers"][provider]["total_requests"] += usage.total_requests
        stats["providers"][provider]["successful_requests"] += usage.successful_requests
        stats["providers"][provider]["failed_requests"] += usage.failed_requests
        stats["providers"][provider]["cached_requests"] += usage.cached_requests
        stats["providers"][provider]["estimated_cost"] += usage.estimated_cost

    return jsonify(stats), 200


def update_api_usage(
    db, provider: RoadviewProvider, success: bool = True, cached: bool = False
):
    """Update API usage statistics"""
    today = datetime.now().date()

    usage = RoadviewAPIUsage.query.filter_by(provider=provider, date=today).first()

    if not usage:
        usage = RoadviewAPIUsage(provider=provider, date=today)
        db.session.add(usage)

    usage.total_requests += 1
    if success:
        usage.successful_requests += 1
    else:
        usage.failed_requests += 1

    if cached:
        usage.cached_requests += 1

    # Estimate cost (customize based on actual API pricing)
    if provider == RoadviewProvider.GOOGLE_STREET_VIEW and not cached:
        usage.estimated_cost += 0.007  # $7 per 1000 requests

    db.session.commit()
