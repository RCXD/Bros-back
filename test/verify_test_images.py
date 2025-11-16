"""
테스트 환경 이미지 경로 검증 스크립트
--use-test-env 옵션으로 생성된 이미지가 올바른 경로로 저장되었는지 확인
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app
from app.extensions import db
from app.models.image import Image
from app.models.post import Post
import os


def verify_test_env_images():
    """테스트 환경에서 생성된 이미지 경로 검증"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*70)
        print("테스트 환경 이미지 검증")
        print("="*70)
        
        # 모든 이미지 조회
        all_images = Image.query.all()
        print(f"\n📊 총 이미지 수: {len(all_images)}개")
        
        if not all_images:
            print("⚠️  이미지가 없습니다. gen_profile_images.py와 gen_images.py를 먼저 실행하세요.")
            return
        
        # 프로필 이미지와 게시글 이미지 분리
        profile_images = [img for img in all_images if img.post_id is None]
        post_images = [img for img in all_images if img.post_id is not None]
        
        print(f"  - 프로필 이미지: {len(profile_images)}개")
        print(f"  - 게시글 이미지: {len(post_images)}개")
        
        # 프로필 이미지 검증
        print(f"\n🔍 프로필 이미지 검증...")
        profile_ok = 0
        profile_missing = 0
        profile_wrong_format = 0
        
        for img in profile_images[:5]:  # 샘플 5개만 출력
            print(f"\n  UUID: {img.uuid}")
            print(f"  Directory: {img.directory}")
            
            # 경로 형식 검증
            if not img.directory or img.directory == str(Path("test/uploads/profile_images")):
                print(f"    ❌ 잘못된 경로 형식 (디렉토리만 저장됨)")
                profile_wrong_format += 1
                continue
            
            # 파일 존재 확인
            if os.path.exists(img.directory):
                print(f"    ✅ 파일 존재")
                profile_ok += 1
            else:
                print(f"    ❌ 파일 없음: {img.directory}")
                profile_missing += 1
        
        # 게시글 이미지 검증
        print(f"\n🔍 게시글 이미지 검증...")
        post_ok = 0
        post_missing = 0
        post_wrong_format = 0
        
        for img in post_images[:5]:  # 샘플 5개만 출력
            print(f"\n  UUID: {img.uuid}")
            print(f"  Post ID: {img.post_id}")
            print(f"  Directory: {img.directory}")
            
            # 경로 형식 검증
            if not img.directory or img.directory == str(Path("test/uploads/post_images")):
                print(f"    ❌ 잘못된 경로 형식 (디렉토리만 저장됨)")
                post_wrong_format += 1
                continue
            
            # 파일 존재 확인
            if os.path.exists(img.directory):
                print(f"    ✅ 파일 존재")
                post_ok += 1
            else:
                print(f"    ❌ 파일 없음: {img.directory}")
                post_missing += 1
        
        # 전체 통계
        print(f"\n" + "="*70)
        print("검증 결과")
        print("="*70)
        
        print(f"\n프로필 이미지 ({len(profile_images)}개):")
        print(f"  ✅ 정상: {profile_ok}개")
        if profile_wrong_format > 0:
            print(f"  ❌ 잘못된 형식: {profile_wrong_format}개")
        if profile_missing > 0:
            print(f"  ❌ 파일 없음: {profile_missing}개")
        
        print(f"\n게시글 이미지 ({len(post_images)}개):")
        print(f"  ✅ 정상: {post_ok}개")
        if post_wrong_format > 0:
            print(f"  ❌ 잘못된 형식: {post_wrong_format}개")
        if post_missing > 0:
            print(f"  ❌ 파일 없음: {post_missing}개")
        
        # 권장사항
        if profile_wrong_format > 0 or post_wrong_format > 0:
            print(f"\n💡 권장사항:")
            print(f"  1. 데이터베이스 초기화: pytest test/database/clear_db.py -v -s --use-test-env")
            print(f"  2. 이미지 재생성: pytest test/database/gen_profile_images.py -v -s --use-test-env --keep-data")
            print(f"  3. 게시글 이미지 재생성: pytest test/database/gen_images.py -v -s --use-test-env --keep-data")
        
        print(f"\n" + "="*70 + "\n")


if __name__ == "__main__":
    verify_test_env_images()
