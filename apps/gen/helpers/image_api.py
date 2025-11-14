"""
프로덕션 환경용 이미지 업로드 API 클라이언트
"""
import requests
import io
import time
from pathlib import Path
from PIL import Image as PILImage


class ImageAPIClient:
    """이미지 업로드 작업을 위한 API 클라이언트"""
    
    def __init__(self, base_url, timeout=120, max_retries=3):
        """
        API 클라이언트 초기화
        
        Args:
            base_url: API 서버 URL (예: http://192.168.1.86:8000)
            timeout: 요청 타임아웃 초 단위 (기본값: 120)
            max_retries: 최대 재시도 횟수 (기본값: 3)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
    
    def _prepare_image(self, image_path, max_width=1024):
        """
        업로드를 위한 이미지 준비: 리사이즈 및 PNG 변환
        
        Args:
            image_path: 이미지 파일 경로
            max_width: 최대 이미지 너비
            
        Returns:
            PNG 이미지가 담긴 BytesIO 버퍼 또는 None
        """
        try:
            with PILImage.open(image_path) as img:
                # RGB/RGBA로 변환
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')
                
                # 필요시 리사이즈
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), PILImage.Resampling.LANCZOS)
                
                # 버퍼에 저장
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG', optimize=True, compress_level=6)
                img_buffer.seek(0)
                return img_buffer
                
        except Exception:
            return None
    
    def _retry_request(self, method, url, **kwargs):
        """
        재시도 로직을 포함한 HTTP 요청 실행
        
        Args:
            method: HTTP 메서드 ('post', 'put' 등)
            url: 요청 URL
            **kwargs: 추가 요청 파라미터
            
        Returns:
            응답 JSON 또는 None
        """
        for attempt in range(self.max_retries):
            try:
                response = getattr(requests, method)(url, timeout=self.timeout, **kwargs)
                
                if response.status_code == 200:
                    return response.json()
                
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                    continue
                return None
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(5)
                    continue
                return None
                
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                    continue
                return None
        
        return None
    
    def upload_post_with_images(self, user_token, content, category_id, image_paths, 
                                 latitude=None, longitude=None, location_name=None):
        """
        /post/write 엔드포인트를 통해 이미지와 함께 게시글 업로드
        
        Args:
            user_token: 사용자 JWT 토큰
            content: 게시글 내용
            category_id: 카테고리 ID
            image_paths: 이미지 파일 경로 리스트
            latitude: 위도 (선택)
            longitude: 경도 (선택)
            location_name: 장소명 (선택)
            
        Returns:
            API 응답 dict 또는 None
        """
        url = f"{self.base_url}/post/write"
        headers = {'Authorization': f'Bearer {user_token}'}
        
        data = {'content': content, 'category_id': category_id}
        if latitude is not None:
            data['latitude'] = latitude
        if longitude is not None:
            data['longitude'] = longitude
        if location_name:
            data['location_name'] = location_name
        
        files = []
        buffers = []
        
        try:
            for img_path in image_paths:
                img_buffer = self._prepare_image(Path(img_path))
                if img_buffer:
                    filename = Path(img_path).stem + '.png'
                    files.append(('images', (filename, img_buffer, 'image/png')))
                    buffers.append(img_buffer)
            
            if not files:
                return None
            
            return self._retry_request('post', url, headers=headers, data=data, files=files)
            
        finally:
            for buf in buffers:
                buf.close()
    
    def update_post_images(self, user_token, post_id, new_image_paths=None, delete_uuids=None):
        """
        /post/edit/<post_id> 엔드포인트를 통해 게시글 이미지 업데이트
        
        Args:
            user_token: 사용자 JWT 토큰
            post_id: 게시글 ID
            new_image_paths: 추가할 이미지 경로 리스트 (선택)
            delete_uuids: 삭제할 이미지 UUID 리스트 (선택)
            
        Returns:
            API 응답 dict 또는 None
        """
        url = f"{self.base_url}/post/edit/{post_id}"
        headers = {'Authorization': f'Bearer {user_token}'}
        
        data = {}
        if delete_uuids:
            data['delete_images'] = delete_uuids
        
        files = []
        buffers = []
        
        try:
            if new_image_paths:
                for img_path in new_image_paths:
                    img_buffer = self._prepare_image(Path(img_path))
                    if img_buffer:
                        filename = Path(img_path).stem + '.png'
                        files.append(('new_images', (filename, img_buffer, 'image/png')))
                        buffers.append(img_buffer)
            
            return self._retry_request('put', url, headers=headers, data=data, files=files or None)
            
        finally:
            for buf in buffers:
                buf.close()
    
    def upload_profile_image(self, user_token, image_path):
        """
        /auth/update 엔드포인트를 통해 프로필 이미지 업로드
        
        Args:
            user_token: 사용자 JWT 토큰
            image_path: 이미지 파일 경로
            
        Returns:
            API 응답 dict 또는 None
        """
        url = f"{self.base_url}/auth/update"
        headers = {'Authorization': f'Bearer {user_token}'}
        
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                return None
            
            # 정사각형 프로필 이미지 준비 (512x512)
            with PILImage.open(image_path) as img:
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                # 중앙 크롭으로 정사각형 만들기
                width, height = img.size
                if width > height:
                    left = (width - height) // 2
                    img = img.crop((left, 0, left + height, height))
                elif height > width:
                    top = (height - width) // 2
                    img = img.crop((0, top, width, top + width))
                
                # 512x512로 리사이즈
                img = img.resize((512, 512), PILImage.Resampling.LANCZOS)
                
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG', optimize=True, compress_level=6)
                img_buffer.seek(0)
                
                files = {'profile_img': (image_path.stem + '.png', img_buffer, 'image/png')}
                
                result = self._retry_request('put', url, headers=headers, files=files)
                img_buffer.close()
                return result
                
        except Exception:
            return None
