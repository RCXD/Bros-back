"""
이미지 API 업로드 헬퍼
프로덕션 환경에서 /post/write 또는 /post/edit 엔드포인트를 통해 이미지를 업로드
"""
import requests
import io
import time
from pathlib import Path
from PIL import Image as PILImage


class ImageAPIUploader:
    """API를 통한 이미지 업로드 처리"""
    
    def __init__(self, base_url, auth_token=None, timeout=120, max_retries=3):
        """
        Args:
            base_url: API 서버 주소 (예: http://192.168.1.86:8000)
            auth_token: JWT 인증 토큰 (필요시)
            timeout: 요청 타임아웃 (초, 기본값: 120)
            max_retries: 최대 재시도 횟수 (기본값: 3)
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.timeout = timeout
        self.max_retries = max_retries
        
    def upload_post_with_images(self, user_token, content, category_id, image_paths, 
                                 latitude=None, longitude=None, location_name=None):
        """
        /post/write 엔드포인트를 통해 게시글과 이미지 업로드
        
        Args:
            user_token: 사용자 JWT 토큰
            content: 게시글 내용
            category_id: 카테고리 ID
            image_paths: 업로드할 이미지 파일 경로 리스트
            latitude: 위도 (선택)
            longitude: 경도 (선택)
            location_name: 장소명 (선택)
            
        Returns:
            dict: API 응답 (post_id, uploaded_images 등)
        """
        url = f"{self.base_url}/post/write"
        
        headers = {
            'Authorization': f'Bearer {user_token}'
        }
        
        # 폼 데이터
        data = {
            'content': content,
            'category_id': category_id
        }
        
        if latitude is not None:
            data['latitude'] = latitude
        if longitude is not None:
            data['longitude'] = longitude
        if location_name:
            data['location_name'] = location_name
        
        # 이미지 파일 준비
        files = []
        try:
            for img_path in image_paths:
                img_path = Path(img_path)
                if not img_path.exists():
                    print(f"⚠️ 이미지 파일 없음: {img_path}")
                    continue
                
                # PNG 형식으로 메모리에 로드 및 리사이즈
                with PILImage.open(img_path) as img:
                    # RGBA 또는 RGB 모드로 변환
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')
                    
                    # 리사이즈 (최대 1024px)
                    max_width = 1024
                    if img.width > max_width:
                        ratio = max_width / img.width
                        new_height = int(img.height * ratio)
                        img = img.resize((max_width, new_height), PILImage.Resampling.LANCZOS)
                    
                    # 메모리 버퍼에 PNG로 저장 (압축)
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='PNG', optimize=True, compress_level=6)
                    img_buffer.seek(0)
                    
                    # 파일 튜플 추가 (field_name, (filename, file_object, content_type))
                    files.append(('images', (img_path.stem + '.png', img_buffer, 'image/png')))
            
            if not files:
                print("⚠️ 업로드할 이미지 없음")
                return None
            
            # POST 요청 (재시도 로직)
            for attempt in range(self.max_retries):
                try:
                    response = requests.post(url, headers=headers, data=data, files=files, timeout=self.timeout)
                    
                    if response.status_code == 200:
                        return response.json()
                    else:
                        print(f"❌ API 오류: {response.status_code}")
                        print(f"   응답: {response.text}")
                        if attempt < self.max_retries - 1:
                            print(f"   재시도 {attempt + 1}/{self.max_retries}...")
                            time.sleep(2)
                            continue
                        return None
                except requests.exceptions.Timeout:
                    print(f"⏱️ 타임아웃 (시도 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        print(f"   {self.timeout}초 후 재시도...")
                        time.sleep(5)
                        continue
                    print(f"❌ 최대 재시도 횟수 초과")
                    return None
                except Exception as e:
                    print(f"❌ 업로드 예외 (시도 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2)
                        continue
                    return None
                
        except Exception as e:
            print(f"❌ 이미지 준비 실패: {e}")
            return None
        finally:
            # 버퍼 닫기
            for _, (_, buf, _) in files:
                buf.close()
    
    def update_post_images(self, user_token, post_id, new_image_paths=None, delete_uuids=None):
        """
        /post/edit/<post_id> 엔드포인트를 통해 이미지 추가/삭제
        
        Args:
            user_token: 사용자 JWT 토큰
            post_id: 게시글 ID
            new_image_paths: 추가할 이미지 파일 경로 리스트 (선택)
            delete_uuids: 삭제할 이미지 UUID 리스트 (선택)
            
        Returns:
            dict: API 응답
        """
        url = f"{self.base_url}/post/edit/{post_id}"
        
        headers = {
            'Authorization': f'Bearer {user_token}'
        }
        
        # 폼 데이터
        data = {}
        
        if delete_uuids:
            # 리스트로 여러 UUID 전달
            data['delete_images'] = delete_uuids
        
        # 새 이미지 파일 준비
        files = []
        
        if new_image_paths:
            try:
                for img_path in new_image_paths:
                    img_path = Path(img_path)
                    if not img_path.exists():
                        print(f"⚠️ 이미지 파일 없음: {img_path}")
                        continue
                    
                    # PNG 형식으로 메모리에 로드 및 리사이즈
                    with PILImage.open(img_path) as img:
                        if img.mode not in ('RGB', 'RGBA'):
                            img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')
                        
                        # 리사이즈 (최대 1024px)
                        max_width = 1024
                        if img.width > max_width:
                            ratio = max_width / img.width
                            new_height = int(img.height * ratio)
                            img = img.resize((max_width, new_height), PILImage.Resampling.LANCZOS)
                        
                        img_buffer = io.BytesIO()
                        img.save(img_buffer, format='PNG', optimize=True, compress_level=6)
                        img_buffer.seek(0)
                        
                        files.append(('new_images', (img_path.stem + '.png', img_buffer, 'image/png')))
                
                # PUT 요청 (재시도 로직)
                for attempt in range(self.max_retries):
                    try:
                        response = requests.put(url, headers=headers, data=data, files=files, timeout=self.timeout)
                        
                        if response.status_code == 200:
                            return response.json()
                        else:
                            print(f"❌ API 오류: {response.status_code}")
                            print(f"   응답: {response.text}")
                            if attempt < self.max_retries - 1:
                                print(f"   재시도 {attempt + 1}/{self.max_retries}...")
                                time.sleep(2)
                                continue
                            return None
                    except requests.exceptions.Timeout:
                        print(f"⏱️ 타임아웃 (시도 {attempt + 1}/{self.max_retries})")
                        if attempt < self.max_retries - 1:
                            print(f"   {self.timeout}초 후 재시도...")
                            time.sleep(5)
                            continue
                        print(f"❌ 최대 재시도 횟수 초과")
                        return None
                    except Exception as e:
                        print(f"❌ 업로드 예외 (시도 {attempt + 1}/{self.max_retries}): {e}")
                        if attempt < self.max_retries - 1:
                            time.sleep(2)
                            continue
                        return None
                    
            except Exception as e:
                print(f"❌ 이미지 준비 실패: {e}")
                return None
            finally:
                for _, (_, buf, _) in files:
                    buf.close()
        else:
            # 이미지 없이 삭제만 하는 경우
            for attempt in range(self.max_retries):
                try:
                    response = requests.put(url, headers=headers, data=data, timeout=self.timeout)
                    if response.status_code == 200:
                        return response.json()
                    else:
                        print(f"❌ API 오류: {response.status_code}")
                        if attempt < self.max_retries - 1:
                            time.sleep(2)
                            continue
                        return None
                except requests.exceptions.Timeout:
                    print(f"⏱️ 타임아웃 (시도 {attempt + 1}/{self.max_retries})")
                    if attempt < self.max_retries - 1:
                        time.sleep(5)
                        continue
                    return None
                except Exception as e:
                    print(f"❌ 요청 예외 (시도 {attempt + 1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2)
                        continue
                    return None
    
    def upload_profile_image(self, user_token, image_path):
        """
        /auth/update 엔드포인트를 통해 프로필 이미지 업로드
        
        Args:
            user_token: 사용자 JWT 토큰
            image_path: 업로드할 이미지 파일 경로
            
        Returns:
            dict: API 응답
        """
        url = f"{self.base_url}/auth/update"
        
        headers = {
            'Authorization': f'Bearer {user_token}'
        }
        
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                print(f"⚠️ 이미지 파일 없음: {image_path}")
                return None
            
            # PNG 형식으로 메모리에 로드 및 리사이즈 (512x512 정사각형)
            with PILImage.open(image_path) as img:
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                # 정사각형으로 중앙 크롭
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
                
                # 파일 업로드
                files = {
                    'profile_img': (image_path.stem + '.png', img_buffer, 'image/png')
                }
                
                # PUT 요청 (재시도 로직)
                for attempt in range(self.max_retries):
                    try:
                        response = requests.put(url, headers=headers, files=files, timeout=self.timeout)
                        
                        if response.status_code == 200:
                            return response.json()
                        else:
                            print(f"❌ API 오류: {response.status_code}")
                            print(f"   응답: {response.text}")
                            if attempt < self.max_retries - 1:
                                print(f"   재시도 {attempt + 1}/{self.max_retries}...")
                                time.sleep(2)
                                continue
                            return None
                    except requests.exceptions.Timeout:
                        print(f"⏱️ 타임아웃 (시도 {attempt + 1}/{self.max_retries})")
                        if attempt < self.max_retries - 1:
                            print(f"   {self.timeout}초 후 재시도...")
                            time.sleep(5)
                            continue
                        print(f"❌ 최대 재시도 횟수 초과")
                        return None
                    except Exception as e:
                        print(f"❌ 업로드 예외 (시도 {attempt + 1}/{self.max_retries}): {e}")
                        if attempt < self.max_retries - 1:
                            time.sleep(2)
                            continue
                        return None
                    
        except Exception as e:
            print(f"❌ 이미지 준비 실패: {e}")
            return None
        finally:
            if 'img_buffer' in locals():
                img_buffer.close()
