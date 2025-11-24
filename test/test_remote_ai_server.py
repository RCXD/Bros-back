"""
리모트 AI 서버 검증 테스트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from PIL import Image
import io
import os

# 환경 변수 직접 설정
OBJECT_DETECTION_SERVER = 'http://192.168.1.79:8888'
ROAD_SEGMENTATION_SERVER = 'http://192.168.1.79:8889'

print("=" * 60)
print("리모트 AI 서버 검증 테스트")
print("=" * 60)


def create_test_image():
    """테스트용 이미지 생성"""
    img = Image.new('RGB', (640, 480), color='blue')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    return buffer.getvalue()


def test_server_health(server_url, server_name):
    """서버 상태 확인"""
    print(f"\n[{server_name}] 서버 상태 확인")
    print(f"URL: {server_url}")
    
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        if response.status_code == 200:
            print(f"✓ 상태: 정상 (200 OK)")
            return True
        else:
            print(f"✗ 상태: 비정상 ({response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ 연결 실패: 서버에 접속할 수 없습니다")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ 타임아웃: 서버 응답 없음")
        return False
    except Exception as e:
        print(f"✗ 오류: {str(e)}")
        return False


def test_attach_model(server_url, server_name):
    """모델 준비 테스트"""
    print(f"\n[{server_name}] 모델 준비 테스트")
    print(f"요청: GET {server_url}/attach-model")
    
    try:
        response = requests.get(f"{server_url}/attach-model", timeout=30)
        print(f"응답 코드: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"응답 데이터: {data}")
            except:
                print(f"응답 텍스트: {response.text}")
            print(f"✓ 모델 준비 성공")
            return True
        else:
            print(f"응답 내용: {response.text}")
            print(f"✗ 모델 준비 실패")
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ 타임아웃: 모델 로딩에 시간이 오래 걸립니다")
        return False
    except Exception as e:
        print(f"✗ 오류: {str(e)}")
        return False


def test_detect(server_url, server_name):
    """감지 테스트"""
    print(f"\n[{server_name}] 감지 테스트")
    print(f"요청: POST {server_url}/detect")
    
    try:
        # 테스트 이미지 생성
        image_data = create_test_image()
        print(f"이미지 크기: {len(image_data)} 바이트")
        
        # files 파라미터로 이미지 전송
        files = {'files': ('test.jpg', image_data, 'image/jpeg')}
        
        response = requests.post(
            f"{server_url}/detect",
            files=files,
            timeout=30
        )
        
        print(f"응답 코드: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"응답 데이터: {data}")
            except:
                print(f"응답 텍스트: {response.text}")
            print(f"✓ 감지 성공")
            return True
        else:
            print(f"응답 내용: {response.text}")
            print(f"✗ 감지 실패")
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ 타임아웃: 감지 처리에 시간이 오래 걸립니다")
        return False
    except Exception as e:
        print(f"✗ 오류: {str(e)}")
        return False


def test_detach_model(server_url, server_name):
    """모델 삭제 테스트"""
    print(f"\n[{server_name}] 모델 삭제 테스트")
    print(f"요청: DELETE {server_url}/detach-model")
    
    try:
        response = requests.delete(f"{server_url}/detach-model", timeout=10)
        print(f"응답 코드: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"응답 데이터: {data}")
            except:
                print(f"응답 텍스트: {response.text}")
            print(f"✓ 모델 삭제 성공")
            return True
        else:
            print(f"응답 내용: {response.text}")
            print(f"✗ 모델 삭제 실패")
            return False
            
    except Exception as e:
        print(f"✗ 오류: {str(e)}")
        return False


def main():
    """메인 테스트 실행"""
    results = {}
    
    # 8888 서버 테스트 (의미론적 객체 감지 - 필수)
    print("\n" + "=" * 60)
    print("8888 포트: 의미론적 객체 감지 서버 (필수)")
    print("=" * 60)
    
    results['8888_health'] = test_server_health(OBJECT_DETECTION_SERVER, "8888")
    
    if results['8888_health']:
        results['8888_attach'] = test_attach_model(OBJECT_DETECTION_SERVER, "8888")
        if results['8888_attach']:
            results['8888_detect'] = test_detect(OBJECT_DETECTION_SERVER, "8888")
            results['8888_detach'] = test_detach_model(OBJECT_DETECTION_SERVER, "8888")
    
    # 8889 서버 테스트 (도로 분할 - 선택사항)
    print("\n" + "=" * 60)
    print("8889 포트: 도로 분할 서버 (선택사항)")
    print("=" * 60)
    
    results['8889_health'] = test_server_health(ROAD_SEGMENTATION_SERVER, "8889")
    
    if results['8889_health']:
        results['8889_attach'] = test_attach_model(ROAD_SEGMENTATION_SERVER, "8889")
        if results['8889_attach']:
            results['8889_detect'] = test_detect(ROAD_SEGMENTATION_SERVER, "8889")
            results['8889_detach'] = test_detach_model(ROAD_SEGMENTATION_SERVER, "8889")
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    
    print("\n[8888 서버 - 의미론적 객체 감지] 필수")
    for key in ['8888_health', '8888_attach', '8888_detect', '8888_detach']:
        if key in results:
            status = "✓ 통과" if results[key] else "✗ 실패"
            print(f"  {key.replace('8888_', '')}: {status}")
    
    print("\n[8889 서버 - 도로 분할] 선택사항")
    for key in ['8889_health', '8889_attach', '8889_detect', '8889_detach']:
        if key in results:
            status = "✓ 통과" if results[key] else "✗ 실패"
            print(f"  {key.replace('8889_', '')}: {status}")
    
    # 전체 평가
    print("\n" + "=" * 60)
    print("전체 평가")
    print("=" * 60)
    
    server_8888_ok = results.get('8888_health', False) and results.get('8888_detect', False)
    server_8889_ok = results.get('8889_health', False)
    
    if server_8888_ok:
        print("✓ 8888 서버 (필수): 정상 작동")
    else:
        print("✗ 8888 서버 (필수): 문제 발생 - 서비스 불가능")
    
    if server_8889_ok:
        print("✓ 8889 서버 (선택): 정상 작동")
    else:
        print("⚠ 8889 서버 (선택): 사용 불가 - 기본 서비스는 가능")
    
    print("\n" + "=" * 60)
    
    if server_8888_ok:
        print("결론: AI 감지 서비스 사용 가능")
    else:
        print("결론: AI 감지 서비스 사용 불가 - 8888 서버 확인 필요")
    
    print("=" * 60)


if __name__ == '__main__':
    main()
