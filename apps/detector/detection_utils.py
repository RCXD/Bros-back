"""
Detection utilities - Helper functions for AI server communication
"""
import requests
import time
from typing import Dict, List, Optional, Tuple
from PIL import Image
import io
import base64


class AIServerClient:
    """Client for communicating with remote AI detection servers"""
    
    def __init__(self, server_url: str, timeout: int = 30):
        """
        Initialize AI server client
        
        Args:
            server_url: Base URL of AI server (e.g., "http://192.168.1.79:8888")
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
    
    def detect_objects(self, image_data: bytes, confidence: float = 0.5) -> Dict:
        """
        Send image to AI server for object detection
        
        Args:
            image_data: Image bytes
            confidence: Confidence threshold (0.0 to 1.0)
            
        Returns:
            Detection results dictionary
        """
        try:
            start_time = time.time()
            
            files = {'image': ('image.jpg', image_data, 'image/jpeg')}
            data = {'confidence': confidence}
            
            response = requests.post(
                f"{self.server_url}/detect/objects",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            result['processing_time_ms'] = int((time.time() - start_time) * 1000)
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {
                'error': str(e),
                'status': 'failed'
            }
    
    def semantic_segmentation(self, image_data: bytes, model: str = "default") -> Dict:
        """
        Send image to AI server for semantic segmentation
        
        Args:
            image_data: Image bytes
            model: Model variant to use
            
        Returns:
            Segmentation results dictionary
        """
        try:
            start_time = time.time()
            
            files = {'image': ('image.jpg', image_data, 'image/jpeg')}
            data = {'model': model}
            
            response = requests.post(
                f"{self.server_url}/segment/semantic",
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            result['processing_time_ms'] = int((time.time() - start_time) * 1000)
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {
                'error': str(e),
                'status': 'failed'
            }
    
    def detect_road_boundary(self, image_data: bytes) -> Dict:
        """
        Send image to AI server for road boundary detection
        
        Args:
            image_data: Image bytes
            
        Returns:
            Road boundary results dictionary
        """
        try:
            start_time = time.time()
            
            files = {'image': ('image.jpg', image_data, 'image/jpeg')}
            
            response = requests.post(
                f"{self.server_url}/detect/road-boundary",
                files=files,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            result['processing_time_ms'] = int((time.time() - start_time) * 1000)
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {
                'error': str(e),
                'status': 'failed'
            }
    
    def health_check(self) -> bool:
        """
        Check if AI server is available
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False


class DetectionResultProcessor:
    """Process and normalize detection results from different AI models"""
    
    @staticmethod
    def process_yolo_results(yolo_output: Dict) -> Tuple[List[Dict], Dict]:
        """
        Process YOLO detection output
        
        Args:
            yolo_output: Raw YOLO model output
            
        Returns:
            Tuple of (detected_objects_list, summary_dict)
        """
        objects = []
        class_counts = {}
        
        for detection in yolo_output.get('detections', []):
            obj = {
                'class_name': detection.get('class', 'unknown'),
                'class_id': detection.get('class_id'),
                'confidence': detection.get('confidence', 0.0),
                'bbox_x': detection.get('bbox', {}).get('x', 0),
                'bbox_y': detection.get('bbox', {}).get('y', 0),
                'bbox_width': detection.get('bbox', {}).get('width', 0),
                'bbox_height': detection.get('bbox', {}).get('height', 0),
                'attributes': detection.get('attributes', {})
            }
            objects.append(obj)
            
            # Count classes
            class_name = obj['class_name']
            class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        summary = {
            'total_objects': len(objects),
            'class_counts': class_counts,
            'model_info': yolo_output.get('model_info', {})
        }
        
        return objects, summary
    
    @staticmethod
    def process_segmentation_results(seg_output: Dict) -> Tuple[List[Dict], Dict]:
        """
        Process semantic segmentation output
        
        Args:
            seg_output: Raw segmentation model output
            
        Returns:
            Tuple of (segments_list, summary_dict)
        """
        segments = []
        total_pixels = seg_output.get('image_size', {}).get('total_pixels', 1)
        
        for segment in seg_output.get('segments', []):
            seg = {
                'class_name': segment.get('class', 'unknown'),
                'class_id': segment.get('class_id'),
                'color_code': segment.get('color', '#000000'),
                'pixel_count': segment.get('pixel_count', 0),
                'percentage': (segment.get('pixel_count', 0) / total_pixels * 100) if total_pixels > 0 else 0,
                'confidence': segment.get('confidence', 0.0),
                'mask_path': segment.get('mask_path'),
                'polygon_data': segment.get('polygons', []),
                'centroid_x': segment.get('centroid', {}).get('x'),
                'centroid_y': segment.get('centroid', {}).get('y'),
                'area': segment.get('area', 0)
            }
            segments.append(seg)
        
        summary = {
            'total_segments': len(segments),
            'classes_found': [s['class_name'] for s in segments],
            'image_size': seg_output.get('image_size', {})
        }
        
        return segments, summary
    
    @staticmethod
    def normalize_bbox(bbox: Dict, img_width: int, img_height: int, 
                      is_normalized: bool = False) -> Dict:
        """
        Normalize bounding box coordinates to 0-1 range
        
        Args:
            bbox: Bounding box dict with x, y, width, height
            img_width: Image width in pixels
            img_height: Image height in pixels
            is_normalized: Whether bbox is already normalized
            
        Returns:
            Normalized bbox dict
        """
        if is_normalized:
            return bbox
        
        return {
            'x': bbox['x'] / img_width,
            'y': bbox['y'] / img_height,
            'width': bbox['width'] / img_width,
            'height': bbox['height'] / img_height
        }


def get_ai_server_client(detection_type: str = "object") -> AIServerClient:
    """
    Get AI server client based on detection type
    
    Args:
        detection_type: "object" for semantic object detection (8888),
                       "road" for road segmentation (8889)
        
    Returns:
        AIServerClient instance
    """
    # Define your AI servers
    # 8888: Semantic object detection (primary, always used)
    # 8889: Road segmentation (optional, can be skipped if malfunctioning)
    servers = {
        'object': 'http://192.168.1.79:8888',  # Semantic object detection
        'road': 'http://192.168.1.79:8889'     # Road segmentation (optional)
    }
    
    server_url = servers.get(detection_type, servers['object'])
    return AIServerClient(server_url)


def validate_image(image_data: bytes, max_size_mb: int = 10) -> Tuple[bool, Optional[str]]:
    """
    Validate image data
    
    Args:
        image_data: Image bytes
        max_size_mb: Maximum file size in MB
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check size
    size_mb = len(image_data) / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"Image size ({size_mb:.2f}MB) exceeds limit ({max_size_mb}MB)"
    
    # Check if valid image
    try:
        img = Image.open(io.BytesIO(image_data))
        img.verify()
        return True, None
    except Exception as e:
        return False, f"Invalid image format: {str(e)}"


def encode_image_base64(image_data: bytes) -> str:
    """
    Encode image data to base64 string
    
    Args:
        image_data: Image bytes
        
    Returns:
        Base64 encoded string
    """
    return base64.b64encode(image_data).decode('utf-8')


def decode_image_base64(base64_string: str) -> bytes:
    """
    Decode base64 string to image bytes
    
    Args:
        base64_string: Base64 encoded image
        
    Returns:
        Image bytes
    """
    return base64.b64decode(base64_string)
