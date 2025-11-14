"""
이미지 리사이즈 및 형식 변환 유틸리티
"""
from pathlib import Path
from PIL import Image as PILImage


def resize_post_image(source_path, dest_path, max_width=1024):
    """
    이미지를 리사이즈하고 PNG 형식으로 변환
    
    Args:
        source_path: 원본 이미지 파일 경로
        dest_path: 저장할 파일 경로
        max_width: 최대 이미지 너비 (기본값: 1024)
        
    Returns:
        성공 시 Path 객체, 실패 시 None
    """
    try:
        # 애니메이션 포맷 제외
        if source_path.suffix.lower() in ['.gif', '.webp']:
            return None
        
        with PILImage.open(source_path) as img:
            # 애니메이션 이미지 체크
            if hasattr(img, 'is_animated') and img.is_animated:
                return None
            
            # RGB 또는 RGBA로 변환
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA' if 'transparency' in img.info else 'RGB')
            
            # 너비가 max_width를 초과하면 리사이즈
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), PILImage.Resampling.LANCZOS)
            
            # PNG로 저장
            img.save(dest_path, 'PNG', optimize=True)
            return dest_path
            
    except Exception:
        return None


def resize_profile_image(source_path, dest_path, size=512):
    """
    프로필 이미지를 정사각형 PNG 형식으로 리사이즈 및 변환
    
    Args:
        source_path: 원본 이미지 파일 경로
        dest_path: 저장할 파일 경로
        size: 출력 정사각형 크기 (기본값: 512)
        
    Returns:
        성공 시 Path 객체, 실패 시 None
    """
    try:
        # 애니메이션 포맷 제외
        if source_path.suffix.lower() in ['.gif', '.webp']:
            return None
        
        with PILImage.open(source_path) as img:
            # 애니메이션 이미지 체크
            if hasattr(img, 'is_animated') and img.is_animated:
                return None
            
            # RGB로 변환
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
            
            # 목표 크기로 리사이즈
            img = img.resize((size, size), PILImage.Resampling.LANCZOS)
            
            # PNG로 저장
            img.save(dest_path, 'PNG', optimize=True)
            return dest_path
            
    except Exception:
        return None


def get_image_files(directory, recursive=True):
    """
    디렉토리에서 유효한 이미지 파일 목록 가져오기
    
    Args:
        directory: 디렉토리 경로
        recursive: True이면 하위 디렉토리 검색
        
    Returns:
        Path 객체 리스트
    """
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    directory = Path(directory)
    
    if not directory.exists():
        return []
    
    image_files = []
    
    if recursive:
        for ext in valid_extensions:
            image_files.extend(directory.rglob(f"*{ext}"))
            image_files.extend(directory.rglob(f"*{ext.upper()}"))
    else:
        for ext in valid_extensions:
            image_files.extend(directory.glob(f"*{ext}"))
            image_files.extend(directory.glob(f"*{ext.upper()}"))
    
    return image_files
