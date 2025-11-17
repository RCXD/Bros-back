"""
Roadview Utilities - API clients for Google, Kakao, and Naver roadview services
"""
import requests
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
import os
import math


class RoadviewAPIError(Exception):
    """Custom exception for roadview API errors"""
    pass


class GoogleStreetViewClient:
    """
    Client for Google Street View API
    Docs: https://developers.google.com/maps/documentation/streetview/overview
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Google Street View client
        
        Args:
            api_key: Google Maps API key with Street View enabled
        """
        self.api_key = api_key
        self.metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
        self.image_url = "https://maps.googleapis.com/maps/api/streetview"
        self.timeout = 10
    
    def check_availability(self, latitude: float, longitude: float, 
                          radius: int = 50) -> Tuple[bool, Optional[Dict]]:
        """
        Check if Street View is available at location
        
        Args:
            latitude: Latitude
            longitude: Longitude
            radius: Search radius in meters (default 50)
            
        Returns:
            Tuple of (is_available, metadata_dict)
        """
        try:
            params = {
                'location': f"{latitude},{longitude}",
                'radius': radius,
                'key': self.api_key,
                'source': 'outdoor'  # Prefer outdoor imagery
            }
            
            response = requests.get(self.metadata_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'OK':
                metadata = {
                    'pano_id': data.get('pano_id'),
                    'latitude': data['location']['lat'],
                    'longitude': data['location']['lng'],
                    'heading': data.get('heading', 0),
                    'pitch': data.get('pitch', 0),
                    'date': data.get('date'),  # Format: YYYY-MM
                    'distance': self._calculate_distance(
                        latitude, longitude,
                        data['location']['lat'], data['location']['lng']
                    )
                }
                return True, metadata
            
            return False, None
            
        except requests.exceptions.RequestException as e:
            raise RoadviewAPIError(f"Google Street View API error: {str(e)}")
    
    def get_image_url(self, latitude: float, longitude: float,
                     heading: float = 0, pitch: float = 0,
                     fov: int = 90, width: int = 640, height: int = 480,
                     pano_id: Optional[str] = None) -> str:
        """
        Generate Street View image URL
        
        Args:
            latitude: Latitude
            longitude: Longitude
            heading: Camera heading (0-360)
            pitch: Camera pitch (-90 to 90)
            fov: Field of view (0-120)
            width: Image width in pixels (max 640)
            height: Image height in pixels (max 640)
            pano_id: Optional panorama ID for specific view
            
        Returns:
            Image URL
        """
        params = {
            'size': f"{width}x{height}",
            'heading': heading,
            'pitch': pitch,
            'fov': fov,
            'key': self.api_key,
            'source': 'outdoor'
        }
        
        if pano_id:
            params['pano'] = pano_id
        else:
            params['location'] = f"{latitude},{longitude}"
        
        # Construct URL with parameters
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.image_url}?{query_string}"
    
    def download_image(self, image_url: str, save_path: str) -> bool:
        """
        Download Street View image
        
        Args:
            image_url: URL from get_image_url()
            save_path: Path to save image
            
        Returns:
            Success boolean
        """
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
        except Exception as e:
            raise RoadviewAPIError(f"Failed to download image: {str(e)}")
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula"""
        R = 6371000  # Earth's radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


class KakaoRoadviewClient:
    """
    Client for Kakao Roadview API
    Docs: https://apis.map.kakao.com/web/documentation/#Roadview
    """
    
    def __init__(self, rest_api_key: str, javascript_key: Optional[str] = None):
        """
        Initialize Kakao Roadview client
        
        Args:
            rest_api_key: Kakao REST API key
            javascript_key: Optional JavaScript key for web integration
        """
        self.rest_api_key = rest_api_key
        self.javascript_key = javascript_key
        self.base_url = "https://dapi.kakao.com"
        self.timeout = 10
    
    def check_availability(self, latitude: float, longitude: float,
                          radius: int = 50) -> Tuple[bool, Optional[Dict]]:
        """
        Check if Kakao Roadview is available at location
        
        Args:
            latitude: Latitude (WGS84)
            longitude: Longitude (WGS84)
            radius: Search radius in meters
            
        Returns:
            Tuple of (is_available, metadata_dict)
        """
        try:
            # Note: Kakao Roadview API endpoint
            # This is a simplified version - check official Kakao docs for exact endpoint
            url = f"{self.base_url}/v2/local/geo/roadview.json"
            
            headers = {
                'Authorization': f'KakaoAK {self.rest_api_key}'
            }
            
            params = {
                'x': longitude,  # Kakao uses x=longitude, y=latitude
                'y': latitude,
                'radius': radius
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if roadview is available
            if data.get('documents') and len(data['documents']) > 0:
                rv = data['documents'][0]
                metadata = {
                    'pano_id': rv.get('panoId') or rv.get('pano_id'),
                    'latitude': rv.get('y'),
                    'longitude': rv.get('x'),
                    'heading': rv.get('pan', 0),  # Kakao uses 'pan' for heading
                    'tilt': rv.get('tilt', 0),  # Kakao uses 'tilt' for pitch
                    'date': rv.get('date'),
                    'distance': self._calculate_distance(
                        latitude, longitude,
                        rv.get('y', latitude), rv.get('x', longitude)
                    )
                }
                return True, metadata
            
            return False, None
            
        except requests.exceptions.RequestException as e:
            raise RoadviewAPIError(f"Kakao Roadview API error: {str(e)}")
    
    def get_roadview_url(self, latitude: float, longitude: float,
                        heading: float = 0, pitch: float = 0,
                        zoom: int = 0) -> str:
        """
        Generate Kakao Roadview URL for web embedding
        
        Args:
            latitude: Latitude
            longitude: Longitude
            heading: Camera heading (pan)
            pitch: Camera pitch (tilt)
            zoom: Zoom level (0-3)
            
        Returns:
            Roadview URL
        """
        # Kakao Roadview is typically embedded using JavaScript
        # Return a web URL that can be used in iframe or link
        base = "https://map.kakao.com/link/roadview"
        return f"{base}/{latitude},{longitude}"
    
    def get_static_image_url(self, latitude: float, longitude: float,
                            width: int = 600, height: int = 400,
                            heading: float = 0, pitch: float = 0) -> str:
        """
        Generate static roadview image URL (if supported)
        
        Note: Kakao may require JavaScript API for actual image rendering
        Check Kakao documentation for static image API availability
        
        Args:
            latitude: Latitude
            longitude: Longitude
            width: Image width
            height: Image height
            heading: Camera heading
            pitch: Camera pitch
            
        Returns:
            Image URL or placeholder
        """
        # This is a placeholder - check Kakao docs for actual static image API
        return f"https://map.kakao.com/roadview/{latitude},{longitude}/{width}/{height}"
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters"""
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


class NaverStreetViewClient:
    """
    Client for Naver Street View (Panorama) API
    Docs: https://www.ncloud.com/product/applicationService/maps
    """
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize Naver Street View client
        
        Args:
            client_id: Naver Cloud Platform Client ID
            client_secret: Naver Cloud Platform Client Secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://naveropenapi.apigw.ntruss.com"
        self.timeout = 10
    
    def check_availability(self, latitude: float, longitude: float,
                          radius: int = 50) -> Tuple[bool, Optional[Dict]]:
        """
        Check if Naver Street View is available at location
        
        Args:
            latitude: Latitude
            longitude: Longitude
            radius: Search radius in meters
            
        Returns:
            Tuple of (is_available, metadata_dict)
        """
        try:
            # Naver Panorama API endpoint
            url = f"{self.base_url}/map-panorama/v1/metadata"
            
            headers = {
                'X-NCP-APIGW-API-KEY-ID': self.client_id,
                'X-NCP-APIGW-API-KEY': self.client_secret
            }
            
            params = {
                'coords': f"{longitude},{latitude}",  # Naver uses lon,lat format
                'radius': radius
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'OK' or data.get('panorama'):
                pano = data.get('panorama', {})
                metadata = {
                    'pano_id': pano.get('panoId') or pano.get('id'),
                    'latitude': pano.get('lat', latitude),
                    'longitude': pano.get('lon', longitude),
                    'heading': pano.get('heading', 0),
                    'pitch': pano.get('pitch', 0),
                    'date': pano.get('captureDate'),
                    'distance': self._calculate_distance(
                        latitude, longitude,
                        pano.get('lat', latitude), pano.get('lon', longitude)
                    )
                }
                return True, metadata
            
            return False, None
            
        except requests.exceptions.RequestException as e:
            raise RoadviewAPIError(f"Naver Street View API error: {str(e)}")
    
    def get_panorama_url(self, pano_id: str, heading: float = 0, 
                        pitch: float = 0, fov: int = 90) -> str:
        """
        Generate Naver Panorama viewer URL
        
        Args:
            pano_id: Panorama ID
            heading: Camera heading
            pitch: Camera pitch
            fov: Field of view
            
        Returns:
            Panorama URL
        """
        return f"https://panorama.map.naver.com/panorama/{pano_id}"
    
    def get_static_image_url(self, pano_id: str, width: int = 600, 
                            height: int = 400, heading: float = 0,
                            pitch: float = 0, fov: int = 90) -> str:
        """
        Generate static panorama image URL
        
        Args:
            pano_id: Panorama ID
            width: Image width
            height: Image height
            heading: Camera heading
            pitch: Camera pitch
            fov: Field of view
            
        Returns:
            Image URL
        """
        # This endpoint may vary - check Naver Cloud Platform documentation
        url = f"{self.base_url}/map-panorama/v1/image"
        params = {
            'panoId': pano_id,
            'width': width,
            'height': height,
            'heading': heading,
            'pitch': pitch,
            'fov': fov
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{url}?{query_string}"
    
    def _calculate_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters"""
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


class RoadviewLoader:
    """
    Unified loader that tries multiple providers to get best available roadview
    """
    
    def __init__(self, google_client: Optional[GoogleStreetViewClient] = None,
                 kakao_client: Optional[KakaoRoadviewClient] = None,
                 naver_client: Optional[NaverStreetViewClient] = None):
        """
        Initialize roadview loader with available clients
        
        Args:
            google_client: Google Street View client
            kakao_client: Kakao Roadview client
            naver_client: Naver Street View client
        """
        self.google = google_client
        self.kakao = kakao_client
        self.naver = naver_client
        
        # Priority order (can be customized)
        self.priority = []
        if google_client:
            self.priority.append(('google', google_client))
        if kakao_client:
            self.priority.append(('kakao', kakao_client))
        if naver_client:
            self.priority.append(('naver', naver_client))
    
    def load_best_roadview(self, latitude: float, longitude: float,
                          radius: int = 50, preferred_provider: Optional[str] = None
                          ) -> Dict:
        """
        Try to load roadview from available providers
        
        Args:
            latitude: Latitude
            longitude: Longitude
            radius: Search radius
            preferred_provider: Preferred provider ('google', 'kakao', 'naver')
            
        Returns:
            Dict with roadview data and provider info
        """
        start_time = time.time()
        results = {
            'success': False,
            'provider': None,
            'metadata': None,
            'providers_checked': [],
            'api_calls_made': 0,
            'response_time_ms': 0,
            'errors': {}
        }
        
        # Reorder priority if preferred provider specified
        check_order = self.priority.copy()
        if preferred_provider:
            check_order = [p for p in check_order if p[0] == preferred_provider] + \
                         [p for p in check_order if p[0] != preferred_provider]
        
        # Try each provider in order
        for provider_name, client in check_order:
            results['providers_checked'].append(provider_name)
            results['api_calls_made'] += 1
            
            try:
                available, metadata = client.check_availability(latitude, longitude, radius)
                
                if available and metadata:
                    results['success'] = True
                    results['provider'] = provider_name
                    results['metadata'] = metadata
                    results['response_time_ms'] = int((time.time() - start_time) * 1000)
                    return results
                    
            except RoadviewAPIError as e:
                results['errors'][provider_name] = str(e)
                continue
        
        results['response_time_ms'] = int((time.time() - start_time) * 1000)
        return results
    
    def check_all_providers(self, latitude: float, longitude: float,
                           radius: int = 50) -> Dict:
        """
        Check availability across all providers
        
        Args:
            latitude: Latitude
            longitude: Longitude
            radius: Search radius
            
        Returns:
            Dict with availability for each provider
        """
        results = {
            'google': None,
            'kakao': None,
            'naver': None
        }
        
        for provider_name, client in self.priority:
            try:
                available, metadata = client.check_availability(latitude, longitude, radius)
                results[provider_name] = {
                    'available': available,
                    'metadata': metadata
                }
            except RoadviewAPIError as e:
                results[provider_name] = {
                    'available': False,
                    'error': str(e)
                }
        
        return results


def get_roadview_loader_from_env() -> RoadviewLoader:
    """
    Create RoadviewLoader with clients from environment variables
    
    Environment variables:
        GOOGLE_MAPS_API_KEY
        KAKAO_REST_API_KEY
        KAKAO_JAVASCRIPT_KEY (optional)
        NAVER_CLIENT_ID
        NAVER_CLIENT_SECRET
    
    Returns:
        RoadviewLoader instance
    """
    google_client = None
    kakao_client = None
    naver_client = None
    
    # Initialize Google client
    google_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if google_key:
        google_client = GoogleStreetViewClient(google_key)
    
    # Initialize Kakao client
    kakao_rest_key = os.getenv('KAKAO_REST_API_KEY')
    kakao_js_key = os.getenv('KAKAO_JAVASCRIPT_KEY')
    if kakao_rest_key:
        kakao_client = KakaoRoadviewClient(kakao_rest_key, kakao_js_key)
    
    # Initialize Naver client
    naver_id = os.getenv('NAVER_CLIENT_ID')
    naver_secret = os.getenv('NAVER_CLIENT_SECRET')
    if naver_id and naver_secret:
        naver_client = NaverStreetViewClient(naver_id, naver_secret)
    
    return RoadviewLoader(google_client, kakao_client, naver_client)


def round_coordinates(latitude: float, longitude: float, 
                     precision: int = 3) -> Tuple[float, float]:
    """
    Round coordinates for cache efficiency
    
    Args:
        latitude: Latitude
        longitude: Longitude
        precision: Decimal places (3 = ~100m, 4 = ~10m)
        
    Returns:
        Tuple of (rounded_lat, rounded_lng)
    """
    return (round(latitude, precision), round(longitude, precision))
