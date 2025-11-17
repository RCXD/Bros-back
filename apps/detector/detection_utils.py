"""
감지 유틸리티 - AI 서버 통신을 위한 헬퍼 함수들
"""
import requests
import time
from typing import Dict, List, Optional, Tuple
from PIL import Image
import io
import base64
import os
from dotenv import load_dotenv


class AIServerClient:
    """원격 AI 감지 서버와 통신하는 클라이언트"""
    
    def __init__(self, server_url: str, timeout: int = 30):
        """
        AI 서버 클라이언트 초기화
        
        Args:
            server_url: AI 서버의 기본 URL (예: "http://192.168.1.79:8888")
            timeout: 요청 타임아웃 (초)
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.model_attached = False
    
    def attach_model(self) -> Dict:
        """
        모델을 준비 (리모트 서버의 /attach-model 호출)
        
        Returns:
            응답 딕셔너리
        """
        try:
            response = requests.get(
                f"{self.server_url}/attach-model",
                timeout=self.timeout
            )
            response.raise_for_status()
            self.model_attached = True
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                'error': str(e),
                'status': 'failed'
            }
    
    def detach_model(self) -> Dict:
        """
        모델을 삭제 (리모트 서버의 /detach-model 호출)
        
        Returns:
            응답 딕셔너리
        """
        try:
            response = requests.delete(
                f"{self.server_url}/detach-model",
                timeout=self.timeout
            )
            response.raise_for_status()
            self.model_attached = False
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                'error': str(e),
                'status': 'failed'
            }
    
    def detect_objects(self, image_data: bytes, confidence: float = 0.5) -> Dict:
        """
        AI 서버로 이미지를 전송하여 객체 감지 수행
        
        Args:
            image_data: 이미지 바이트
            confidence: 신뢰도 임계값 (0.0 ~ 1.0)
            
        Returns:
            감지 결과 딕셔너리
        """
        try:
            start_time = time.time()
            
            # 모델이 준비되지 않았으면 먼저 준비
            if not self.model_attached:
                attach_result = self.attach_model()
                if 'error' in attach_result:
                    return attach_result
            
            # files로 이미지 전달
            files = {'files': ('image.jpg', image_data, 'image/jpeg')}
            
            response = requests.post(
                f"{self.server_url}/detect",
                files=files,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # TODO: 추가적인 분석 정보를 전송할 예정
            # 현재는 "분석 완료", 200 응답만 수신
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
        AI 서버로 이미지를 전송하여 의미론적 분할 수행
        
        Args:
            image_data: 이미지 바이트
            model: 사용할 모델 변형
            
        Returns:
            분할 결과 딕셔너리
        """
        try:
            start_time = time.time()
            
            # 모델이 준비되지 않았으면 먼저 준비
            if not self.model_attached:
                attach_result = self.attach_model()
                if 'error' in attach_result:
                    return attach_result
            
            # files로 이미지 전달
            files = {'files': ('image.jpg', image_data, 'image/jpeg')}
            
            response = requests.post(
                f"{self.server_url}/detect",
                files=files,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # TODO: 추가적인 분석 정보를 전송할 예정
            # 현재는 "분석 완료", 200 응답만 수신
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
        AI 서버로 이미지를 전송하여 도로 경계 감지 수행
        
        Args:
            image_data: 이미지 바이트
            
        Returns:
            도로 경계 결과 딕셔너리
        """
        try:
            start_time = time.time()
            
            # 모델이 준비되지 않았으면 먼저 준비
            if not self.model_attached:
                attach_result = self.attach_model()
                if 'error' in attach_result:
                    return attach_result
            
            # files로 이미지 전달
            files = {'files': ('image.jpg', image_data, 'image/jpeg')}
            
            response = requests.post(
                f"{self.server_url}/detect",
                files=files,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # TODO: 추가적인 분석 정보를 전송할 예정
            # 현재는 "분석 완료", 200 응답만 수신
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
        AI 서버가 사용 가능한지 확인
        
        Returns:
            서버가 정상이면 True, 아니면 False
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
    """다양한 AI 모델의 감지 결과를 처리하고 정규화"""
    
    @staticmethod
    def process_yolo_results(yolo_output: Dict) -> Tuple[List[Dict], Dict]:
        """
        YOLO 감지 출력 처리
        
        Args:
            yolo_output: YOLO 모델의 원본 출력
            
        Returns:
            (감지된_객체_리스트, 요약_딕셔너리) 튜플
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
            
            # 클래스 카운트
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
        의미론적 분할 출력 처리
        
        Args:
            seg_output: 분할 모델의 원본 출력
            
        Returns:
            (세그먼트_리스트, 요약_딕셔너리) 튜플
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
        바운딩 박스 좌표를 0-1 범위로 정규화
        
        Args:
            bbox: x, y, width, height를 포함한 바운딩 박스 딕셔너리
            img_width: 이미지 너비 (픽셀)
            img_height: 이미지 높이 (픽셀)
            is_normalized: 이미 정규화되었는지 여부
            
        Returns:
            정규화된 바운딩 박스 딕셔너리
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
    감지 유형에 따라 AI 서버 클라이언트 가져오기
    
    Args:
        detection_type: "object"는 의미론적 객체 감지 (8888),
                       "road"는 도로 분할 (8889)
        
    Returns:
        AIServerClient 인스턴스
    """
    # AI 서버 정의
    # 8888: 의미론적 객체 감지 (주요, 항상 사용)
    # 8889: 도로 분할 (선택사항, 오작동 시 건너뛸 수 있음)
    # 환경 변수 로드
    load_dotenv()
    
    servers = {
      'object': os.getenv('AI_SERVER_OBJECT_URL', 'http://192.168.1.79:8888'),
      'road': os.getenv('AI_SERVER_ROAD_URL', 'http://192.168.1.79:8889')
    }
    
    server_url = servers.get(detection_type, servers['object'])
    return AIServerClient(server_url)


def validate_image(image_data: bytes, max_size_mb: int = 10) -> Tuple[bool, Optional[str]]:
    """
    이미지 데이터 유효성 검사
    
    Args:
        image_data: 이미지 바이트
        max_size_mb: 최대 파일 크기 (MB)
        
    Returns:
        (유효한지_여부, 오류_메시지) 튜플
    """
    # 크기 확인
    size_mb = len(image_data) / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"이미지 크기 ({size_mb:.2f}MB)가 제한 ({max_size_mb}MB)을 초과했습니다"
    
    # 유효한 이미지인지 확인
    try:
        img = Image.open(io.BytesIO(image_data))
        img.verify()
        return True, None
    except Exception as e:
        return False, f"잘못된 이미지 형식: {str(e)}"


def encode_image_base64(image_data: bytes) -> str:
    """
    이미지 데이터를 base64 문자열로 인코딩
    
    Args:
        image_data: 이미지 바이트
        
    Returns:
        Base64 인코딩된 문자열
    """
    return base64.b64encode(image_data).decode('utf-8')


def decode_image_base64(base64_string: str) -> bytes:
    """
    base64 문자열을 이미지 바이트로 디코딩
    
    Args:
        base64_string: Base64 인코딩된 이미지
        
    Returns:
        이미지 바이트
    """
    return base64.b64decode(base64_string)
