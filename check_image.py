from apps.app import create_app
from apps.post.models import Image
import os

app = create_app('development')

with app.app_context():
    uuid = 'b9df3a43-8271-4668-a193-a887c604f4c1'
    img = Image.query.filter_by(uuid=uuid).first()
    
    if img:
        print(f"✓ Image found in DB")
        print(f"  UUID: {img.uuid}")
        print(f"  Directory: {img.directory}")
        print(f"  Post ID: {img.post_id}")
        print(f"  User ID: {img.user_id}")
        
        # 파일 존재 확인
        file_path = img.directory
        if os.path.exists(file_path):
            print(f"✓ File exists: {file_path}")
        else:
            print(f"✗ File NOT found: {file_path}")
            
            # 경로 파싱 확인
            directory_parts = img.directory.split("/")
            directory = "/".join(directory_parts[:-1])
            filename = directory_parts[-1]
            print(f"  Parsed directory: {directory}")
            print(f"  Parsed filename: {filename}")
            
            full_path = os.path.join(directory, filename)
            print(f"  Full path: {full_path}")
            print(f"  Exists: {os.path.exists(full_path)}")
    else:
        print(f"✗ Image not found in DB with UUID: {uuid}")
        
        # 전체 이미지 수 확인
        total_images = Image.query.count()
        print(f"  Total images in DB: {total_images}")
        
        # 게시글 이미지 수
        post_images = Image.query.filter(Image.post_id != None).count()
        print(f"  Post images: {post_images}")
        
        # 샘플 UUID 표시
        sample = Image.query.first()
        if sample:
            print(f"  Sample UUID: {sample.uuid}")
