"""
프로필 이미지 UUID 조회 API 테스트 스크립트
"""
import requests
import time
import sys

base_url = "http://127.0.0.1:8002"

def test_server_connection():
    """서버 연결 확인"""
    print("🔍 서버 연결 확인 중...")
    for i in range(3):
        try:
            response = requests.get(f"{base_url}/auth/me", timeout=2)
            print(f"✅ 서버가 실행 중입니다!\n")
            return True
        except requests.exceptions.ConnectionError:
            print(f"⏳ 서버 대기 중... (시도 {i+1}/3)")
            time.sleep(1)
        except Exception as e:
            print(f"⚠️  서버 확인 중 오류: {e}")
            time.sleep(1)
    
    print("❌ 서버에 연결할 수 없습니다.")
    print("   다음 명령으로 서버를 실행해주세요:")
    print("   .\\venv\\Scripts\\Activate.ps1; python apps/app.py\n")
    return False


def test_uuid_endpoint(uuid_value, test_name, expected_status=200):
    """UUID 엔드포인트 테스트"""
    url = f"{base_url}/auth/image/uuid/{uuid_value}"
    print(f"[{test_name}]")
    print(f"GET {url}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"📊 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'unknown')
            content_length = len(response.content)
            print(f"📄 Content-Type: {content_type}")
            print(f"📦 Content-Length: {content_length:,} bytes")
            
            if 'image' in content_type.lower():
                print(f"✅ 성공: 이미지 파일이 정상적으로 반환되었습니다")
            else:
                print(f"⚠️  경고: 이미지 타입이 아닙니다 ({content_type})")
        elif response.status_code == 404:
            print(f"📄 응답: {response.text[:150]}")
            if expected_status == 404:
                print(f"✅ 정상: 404 에러가 예상대로 반환되었습니다")
            else:
                print(f"❌ 실패: 404 에러 발생")
        else:
            print(f"❌ 실패: 예상치 못한 상태 코드")
            print(f"📄 응답: {response.text[:150]}")
        
        return response.status_code == expected_status
    
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return False
    finally:
        print()


def test_user_endpoint(identifier, test_name):
    """User 엔드포인트 테스트"""
    url = f"{base_url}/auth/image/user/{identifier}"
    print(f"[{test_name}]")
    print(f"GET {url}")
    
    try:
        response = requests.get(url, timeout=5)
        print(f"📊 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'unknown')
            content_length = len(response.content)
            print(f"📄 Content-Type: {content_type}")
            print(f"📦 Content-Length: {content_length:,} bytes")
            print(f"✅ 성공: 프로필 이미지가 정상적으로 반환되었습니다")
        else:
            print(f"📄 응답: {response.text[:150]}")
            print(f"❌ 실패")
        
        return response.status_code == 200
    
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return False
    finally:
        print()


def main():
    print("=" * 60)
    print("프로필 이미지 UUID 조회 API 테스트")
    print("=" * 60)
    print()
    
    # 서버 연결 확인
    if not test_server_connection():
        sys.exit(1)
    
    results = []
    
    print("=" * 60)
    print("테스트 시작")
    print("=" * 60)
    print()
    
    # 테스트 1: 실제 UUID로 조회
    results.append(test_uuid_endpoint(
        "e4ea12c6-abff-4448-ad94-a83924c65e27",
        "테스트 1: 실제 UUID로 조회",
        expected_status=200
    ))
    
    # 테스트 2: default_profile 조회
    results.append(test_uuid_endpoint(
        "default_profile",
        "테스트 2: default_profile 조회",
        expected_status=200
    ))
    
    # 테스트 3: 존재하지 않는 UUID (404 예상)
    results.append(test_uuid_endpoint(
        "00000000-0000-0000-0000-000000000000",
        "테스트 3: 존재하지 않는 UUID (404 예상)",
        expected_status=404
    ))
    
    # 테스트 4: user_id로 조회
    results.append(test_user_endpoint(
        "1",
        "테스트 4: user_id로 프로필 이미지 조회"
    ))
    
    # 테스트 5: username으로 조회
    results.append(test_user_endpoint(
        "user1",
        "테스트 5: username으로 프로필 이미지 조회"
    ))
    
    # 결과 요약
    print("=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"✅ 통과: {passed}/{total}")
    print(f"❌ 실패: {total - passed}/{total}")
    print()
    
    if passed == total:
        print("🎉 모든 테스트를 통과했습니다!")
    else:
        print("⚠️  일부 테스트가 실패했습니다.")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
