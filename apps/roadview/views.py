"""
Roadview Views - API endpoints for roadview services
"""

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import time
import requests
import os
from pathlib import Path

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

    # Verify roadview loader has at least one client
    loader = get_roadview_loader_from_env()
    if not loader.priority:
        return (
            jsonify(
                {
                    "message": "No roadview API clients configured. Please set API keys in environment variables.",
                    "required_keys": [
                        "GOOGLE_MAPS_API_KEY",
                        "KAKAO_REST_API_KEY",
                        "NAVER_CLIENT_ID + NAVER_CLIENT_SECRET",
                    ],
                }
            ),
            503,
        )

    # Track request
    start_time = time.time()

    # Convert provider name to enum
    preferred_provider_enum = None
    if preferred_provider:
        provider_map = {
            "google": RoadviewProvider.GOOGLE_STREET_VIEW,
            "kakao": RoadviewProvider.KAKAO_ROADVIEW,
            "naver": RoadviewProvider.NAVER_STREET_VIEW,
        }
        preferred_provider_enum = provider_map.get(preferred_provider.lower())

    rv_request = RoadviewRequest(
        user_id=user_id,
        latitude=latitude,
        longitude=longitude,
        preferred_provider=preferred_provider_enum,
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

        # Load roadview from APIs (reuse loader from above)
        result = loader.load_best_roadview(
            latitude, longitude, radius, preferred_provider
        )

        rv_request.providers_checked = result["providers_checked"]
        rv_request.api_calls_made = result["api_calls_made"]
        rv_request.response_time_ms = result["response_time_ms"]
        rv_request.success = result["success"]

        if result["success"]:
            # Create roadview record - convert provider name to enum
            provider_map_response = {
                "google": RoadviewProvider.GOOGLE_STREET_VIEW,
                "kakao": RoadviewProvider.KAKAO_ROADVIEW,
                "naver": RoadviewProvider.NAVER_STREET_VIEW,
            }
            provider_enum = provider_map_response.get(result["provider"])

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


@bp.route("/location-info", methods=["POST"])
@jwt_required()
def get_location_info():
    """
    Google Places API를 사용하여 위치의 상세 정보 조회

    Request JSON:
        {
            "latitude": 37.5665,
            "longitude": 126.9780
        }

    Response:
        {
            "name": "음식점 이름",
            "address": "주소",
            "rating": 4.5,
            "reviews_count": 123,
            "phone": "010-xxxx-xxxx",
            "website": "https://example.com",
            "opening_hours": {...},
            "types": ["restaurant", "food"],
            "reviews": [...],
            "photos": [...]
        }
    """
    data = request.get_json()

    if not data or "latitude" not in data or "longitude" not in data:
        return jsonify({"message": "latitude and longitude are required"}), 400

    latitude = float(data["latitude"])
    longitude = float(data["longitude"])

    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return jsonify({"message": "Google Maps API key not configured"}), 503

        # Nearby Search API 호출하여 가장 가까운 장소 찾기
        nearby_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        nearby_params = {
            "location": f"{latitude},{longitude}",
            "radius": 50,
            "key": api_key,
        }

        nearby_response = requests.get(nearby_url, params=nearby_params, timeout=10)
        nearby_response.raise_for_status()
        nearby_data = nearby_response.json()

        if nearby_data.get("status") != "OK":
            status = nearby_data.get("status")
            error_msg = nearby_data.get("error_message", "Unknown error")
            return (
                jsonify(
                    {
                        "message": f"Google Nearby Search failed: {status}",
                        "google_status": status,
                        "google_error": error_msg,
                    }
                ),
                500,
            )

        if not nearby_data.get("results"):
            return jsonify({"message": "No location found at this coordinates"}), 404

        # 가장 가까운 장소의 place_id 획득
        place_id = nearby_data["results"][0]["place_id"]

        # Place Details API 호출하여 상세 정보 조회
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,opening_hours,types,reviews,photos,geometry",
            "reviews_sort": "newest",
            "language": "ko",
            "key": api_key,
        }

        details_response = requests.get(details_url, params=details_params, timeout=10)
        details_response.raise_for_status()
        details_data = details_response.json()

        if details_data.get("status") != "OK":
            status = details_data.get("status")
            error_msg = details_data.get("error_message", "Unknown error")
            return (
                jsonify(
                    {
                        "message": f"Failed to fetch location details: {status}",
                        "google_status": status,
                        "google_error": error_msg,
                    }
                ),
                500,
            )

        result = details_data.get("result", {})

        # 응답 데이터 정리
        location_info = {
            "name": result.get("name"),
            "address": result.get("formatted_address"),
            "phone": result.get("formatted_phone_number"),
            "website": result.get("website"),
            "rating": result.get("rating"),
            "reviews_count": result.get("user_ratings_total"),
            "types": result.get("types", []),
            "opening_hours": result.get("opening_hours", {}),
            "coordinates": result.get("geometry", {}).get("location", {}),
            "reviews": [],
            "photos": [],
        }

        # 리뷰 정보 추출
        if "reviews" in result:
            for review in result["reviews"][:5]:  # 최근 5개 리뷰
                location_info["reviews"].append(
                    {
                        "author": review.get("author_name"),
                        "rating": review.get("rating"),
                        "text": review.get("text"),
                        "time": review.get("relative_time_description"),
                        "language": review.get("language"),
                    }
                )

        # 사진 정보 추출
        if "photos" in result:
            for photo in result["photos"][:5]:  # 최대 5개 사진
                location_info["photos"].append(
                    {
                        "attribution": photo.get("html_attributions", []),
                        "height": photo.get("height"),
                        "width": photo.get("width"),
                    }
                )

        return jsonify(location_info), 200

    except requests.exceptions.Timeout:
        return jsonify({"message": "Google API request timeout"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"message": f"Google API error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"message": f"Error fetching location info: {str(e)}"}), 500


@bp.route("/get-image", methods=["POST"])
@jwt_required()
def get_roadview_image():
    """
    Download Google Street View image and save to disk

    Request JSON:
        {
            "latitude": 37.5665,
            "longitude": 126.9780,
            "heading": 90,
            "pitch": 0,
            "fov": 90,
            "width": 640,
            "height": 640
        }

    Response:
        {
            "success": true,
            "file_path": "./downloads/roadview/2025-11-20/image_123456.jpg",
            "metadata": {...}
        }
    """
    data = request.get_json()

    if not data or "latitude" not in data or "longitude" not in data:
        return jsonify({"message": "latitude and longitude are required"}), 400

    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    heading = int(data.get("heading", 0))
    pitch = int(data.get("pitch", 0))
    fov = int(data.get("fov", 90))
    width = int(data.get("width", 640))
    height = int(data.get("height", 640))

    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return jsonify({"message": "Google Maps API key not configured"}), 503

        # Create directory structure
        today = datetime.now().strftime("%Y-%m-%d")
        download_dir = Path("downloads") / "roadview" / today
        download_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"roadview_{timestamp}.jpg"
        file_path = download_dir / filename

        # Build Street View Static API URL
        streetview_url = "https://maps.googleapis.com/maps/api/streetview"
        params = {
            "size": f"{width}x{height}",
            "location": f"{latitude},{longitude}",
            "heading": heading,
            "pitch": pitch,
            "fov": fov,
            "key": api_key,
        }

        # Download image
        response = requests.get(streetview_url, params=params, timeout=15)
        response.raise_for_status()

        # Check if valid image (not error page)
        if len(response.content) < 1000:
            return (
                jsonify({"message": "No Street View image available at this location"}),
                404,
            )

        # Save image to disk
        with open(file_path, "wb") as f:
            f.write(response.content)

        metadata = {
            "latitude": latitude,
            "longitude": longitude,
            "heading": heading,
            "pitch": pitch,
            "fov": fov,
            "width": width,
            "height": height,
            "file_size": len(response.content),
            "timestamp": datetime.now().isoformat(),
        }

        return (
            jsonify(
                {
                    "success": True,
                    "file_path": str(file_path),
                    "filename": filename,
                    "metadata": metadata,
                }
            ),
            200,
        )

    except requests.exceptions.Timeout:
        return jsonify({"message": "Google API request timeout"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"message": f"Google API error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"message": f"Error downloading roadview image: {str(e)}"}), 500
