"""
인증 뷰 (라우트)
사용자 등록, 로그인, 로그아웃, 프로필 관리 처리
"""

from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, get_current_user
from email_validator import validate_email, EmailNotValidError
import os
import uuid
import requests
from datetime import datetime

from apps.config.server import db, BLACKLIST
from apps.auth.models import User, OauthType
from apps.post.models import Image
from apps.auth.utils import token_provider, is_valid_phone


bp = Blueprint("auth", __name__)

# OAuth 설정
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
NAVER_USER_INFO_URL = "https://openapi.naver.com/v1/nid/me"


# =====================================================
# 헬퍼 함수
# =====================================================


def save_profile_image(file, user_id=None):
    """
    프로필 이미지를 저장하고 Image 레코드 생성

    Args:
        file: 업로드된 파일 객체
        user_id: 사용자 ID (선택)

    Returns:
        str: 저장된 이미지의 UUID
    """
    print(
        f"[DEBUG] save_profile_image 시작 - user_id={user_id}, filename={file.filename}"
    )

    original_name = file.filename
    ext = file.filename.rsplit(".", 1)[1].lower()
    today = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(current_app.root_path, "static/profile_images", today)
    os.makedirs(folder_path, exist_ok=True)

    uuid_val = uuid.uuid4()
    filename = f"{uuid_val}.{ext}"
    file_path = os.path.join(folder_path, filename)

    print(f"[DEBUG] 파일 저장 중... path={file_path}")
    file.save(file_path)
    print(f"[DEBUG] 파일 저장 완료")

    relative_path = f"static/profile_images/{today}/{filename}"

    if user_id:
        print(f"[DEBUG] Image 레코드 생성 중... uuid={uuid_val}, user_id={user_id}")
        new_image = Image(
            uuid=str(uuid_val),
            user_id=user_id,
            directory=relative_path,
            original_image_name=original_name,
            updated_at=datetime.now(),
            post_id=None,
            ext=ext,
        )
        db.session.add(new_image)
        print(f"[DEBUG] Image 레코드 추가 완료 (db.session.add)")

    print(f"[DEBUG] save_profile_image 완료 - 반환 UUID={str(uuid_val)}")
    return str(uuid_val)


# =====================================================
# 회원가입
# =====================================================


@bp.post("/user")
def signup():
    """
    사용자 등록 엔드포인트

    Form data:
        - username: 필수
        - password: 필수
        - email: 필수
        - nickname: 선택
        - address: 선택
        - phone: 선택
        - profile_img: 선택 (multipart file)
    """
    try:
        # 폼 데이터 추출
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        nickname = request.form.get("nickname", username)
        address = request.form.get("address", "")
        phone = request.form.get("phone")

        # 필수 필드 검증
        if not username or not password or not email:
            return jsonify({"message": "username, password, email은 필수입니다"}), 400

        # 이메일 형식 검증
        try:
            validate_email(email)
        except EmailNotValidError:
            return jsonify({"message": "유효하지 않은 이메일 형식입니다"}), 400

        # 전화번호 검증 (제공된 경우)
        if phone and not is_valid_phone(phone):
            return jsonify({"message": "유효하지 않은 전화번호 형식입니다"}), 400

        # 기존 사용자명/이메일 확인
        if User.query.filter_by(username=username).first():
            return jsonify({"message": "이미 존재하는 사용자명입니다"}), 409
        if User.query.filter_by(email=email).first():
            return jsonify({"message": "이미 존재하는 이메일입니다"}), 409

        # 사용자 생성 (기본 프로필 이미지)
        user = User(
            username=username,
            email=email,
            nickname=nickname,
            address=address,
            phone=phone,
            profile_img="default_profile",
        )
        user.set_password(password)

        db.session.add(user)
        db.session.flush()  # user_id 확보

        # 프로필 이미지 업로드 처리 (제공된 경우)
        if "profile_img" in request.files:
            file = request.files["profile_img"]
            if file and file.filename:
                from apps.common.image_handlers import (
                    compress_image,
                    save_to_disk,
                    IMAGE_EXTENSIONS,
                )

                # 파일 확장자 검증
                ext = file.filename.rsplit(".", 1)[-1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    db.session.rollback()
                    return (
                        jsonify(
                            {"message": f"지원하지 않는 파일 형식: {file.filename}"}
                        ),
                        400,
                    )

                # 이미지 압축
                image_compressed, ext, filename = compress_image(
                    file, image_type="profile"
                )

                # Image 레코드 생성
                image = Image(
                    user_id=user.user_id,
                    post_id=None,
                    directory="",
                    original_image_name=file.filename,
                    ext=ext,
                )
                db.session.add(image)
                db.session.flush()  # UUID 생성

                # UUID로 파일명 생성하여 저장
                filename = f"{image.uuid}.{ext}"
                rel_path = save_to_disk(
                    image_compressed, ext, filename, category="profile"
                )
                image.directory = rel_path

                # user의 profile_img를 UUID로 설정
                user.profile_img = str(image.uuid)

        db.session.commit()

        return (
            jsonify(
                {
                    "message": "회원가입이 완료되었습니다",
                    "user": {"user_id": user.user_id},
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"회원가입 실패: {str(e)}"}), 400


# =====================================================
# 통합 로그인
# =====================================================


@bp.post("/login")
def login():
    """
    통합 로그인 엔드포인트 (일반 로그인 + OAuth)

    JSON body:
        일반 로그인:
            - username: 필수
            - password: 필수

        OAuth 로그인:
            - provider: 필수 ("google", "kakao", "naver")
            - token: 필수 (OAuth 토큰)
    """
    try:
        data = request.get_json()
        provider = data.get("provider")

        # OAuth 로그인
        if provider:
            token = data.get("token")
            if not token:
                return jsonify({"message": "토큰이 누락되었습니다"}), 400

            # OAuth 토큰 검증 및 사용자 정보 추출
            from apps.auth.utils import (
                verify_oauth_token,
                find_or_create_oauth_user,
                generate_login_response,
            )

            result = verify_oauth_token(provider.lower(), token)
            if result[0] is None:
                return jsonify({"message": result[1]}), 401

            oauth_type, username, email, nickname, profile_img_url = result

            # 사용자 찾기 또는 생성
            user = find_or_create_oauth_user(
                username=username,
                email=email,
                nickname=nickname,
                oauth_type=oauth_type,
                db_session=db.session,
                profile_img_url=profile_img_url,
            )

            # 로그인 응답 생성
            response_data, status_code = generate_login_response(user, db.session)
            return jsonify(response_data), status_code

        # 일반 로그인
        else:
            username = data.get("username")
            password = data.get("password")

            if not username or not password:
                return jsonify({"message": "username과 password는 필수입니다"}), 400

            # 사용자명으로 사용자 찾기
            user = User.query.filter_by(username=username).first()
            if not user:
                return jsonify({"message": "잘못된 인증 정보입니다"}), 401

            # 계정 정지 여부 확인
            if user.is_expired:
                return jsonify({"message": "정지된 계정입니다"}), 403

            # 비밀번호 확인
            if not user.check_password(password):
                return jsonify({"message": "잘못된 인증 정보입니다"}), 401

            # 로그인 응답 생성 (토큰 + 사용자 정보)
            from apps.auth.utils import generate_login_response

            response_data, status_code = generate_login_response(user, db.session)
            return jsonify(response_data), status_code

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"로그인 실패: {str(e)}"}), 400


# =====================================================
# OAuth 로그인 (Deprecated - 하위 호환성 유지)
# =====================================================
# 이 엔드포인트들은 /login 엔드포인트로 통합되었습니다.
# 기존 클라이언트 호환성을 위해 유지되며, /login 사용을 권장합니다.


@bp.post("/login/google")
def google_login():
    """
    Google OAuth 로그인 (Deprecated)

    대신 POST /login with {"provider": "google", "token": "..."} 사용
    """
    try:
        token = request.json.get("token")
        if not token:
            return jsonify({"message": "토큰이 누락되었습니다"}), 400

        # 통합 로그인 엔드포인트로 리다이렉트
        return login_with_provider("google", token)
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Google 로그인 실패: {str(e)}"}), 400


@bp.post("/login/kakao")
def kakao_login():
    """
    Kakao OAuth 로그인 (Deprecated)

    대신 POST /login with {"provider": "kakao", "token": "..."} 사용
    """
    try:
        token = request.json.get("token")
        if not token:
            return jsonify({"message": "토큰이 누락되었습니다"}), 400

        # 통합 로그인 엔드포인트로 리다이렉트
        return login_with_provider("kakao", token)
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Kakao 로그인 실패: {str(e)}"}), 400


@bp.post("/login/naver")
def naver_login():
    """
    Naver OAuth 로그인 (Deprecated)

    대신 POST /login with {"provider": "naver", "token": "..."} 사용
    """
    try:
        token = request.json.get("token")
        if not token:
            return jsonify({"message": "토큰이 누락되었습니다"}), 400

        # 통합 로그인 엔드포인트로 리다이렉트
        return login_with_provider("naver", token)
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Naver 로그인 실패: {str(e)}"}), 400


def login_with_provider(provider, token):
    """내부 헬퍼: provider별 OAuth 로그인 처리"""
    from apps.auth.utils import (
        verify_oauth_token,
        find_or_create_oauth_user,
        generate_login_response,
    )

    result = verify_oauth_token(provider, token)
    if result[0] is None:
        return jsonify({"message": result[1]}), 401

    oauth_type, username, email, nickname, profile_img_url = result

    user = find_or_create_oauth_user(
        username=username,
        email=email,
        nickname=nickname,
        oauth_type=oauth_type,
        db_session=db.session,
        profile_img_url=profile_img_url,
    )

    response_data, status_code = generate_login_response(user, db.session)
    return jsonify(response_data), status_code


# =====================================================
# 프로필 수정
# =====================================================


@bp.put("/user")
@jwt_required()
def update_profile():
    """
    사용자 프로필 수정

    Form data (모두 선택):
        - email
        - password
        - nickname
        - address
        - phone
        - profile_img (multipart file)
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({"message": "사용자를 찾을 수 없습니다"}), 404

        # 제공된 필드 업데이트
        email = request.form.get("email")
        password = request.form.get("password")
        nickname = request.form.get("nickname")
        address = request.form.get("address")
        phone = request.form.get("phone")

        if email:
            # 이메일 형식 검증
            try:
                validate_email(email)
            except EmailNotValidError:
                return jsonify({"message": "유효하지 않은 이메일 형식입니다"}), 400

            # 다른 사용자가 해당 이메일을 사용하는지 확인
            existing = User.query.filter(
                User.email == email, User.user_id != current_user.user_id
            ).first()
            if existing:
                return jsonify({"message": "이미 사용 중인 이메일입니다"}), 409

            current_user.email = email

        if password:
            current_user.set_password(password)

        if nickname:
            current_user.nickname = nickname

        if address:
            current_user.address = address

        if phone:
            if not is_valid_phone(phone):
                return jsonify({"message": "유효하지 않은 전화번호 형식입니다"}), 400
            current_user.phone = phone

        # 프로필 이미지 업로드 처리
        default_img = "static/default_profile.jpg"
        current_img = current_user.profile_img

        print(f"[DEBUG] 프로필 이미지 처리 시작 - current_img={current_img}")
        print(f"[DEBUG] request.files: {list(request.files.keys())}")

        if "profile_img" in request.files:
            file = request.files["profile_img"]
            print(
                f"[DEBUG] profile_img 파일 발견 - filename={file.filename if file else 'None'}"
            )

            if file and file.filename:
                print(f"[DEBUG] 파일 업로드 처리 시작")

                # 기존 프로필 이미지 삭제 (기본 이미지가 아닌 경우)
                if current_img and current_img != default_img:
                    print(f"[DEBUG] 기존 이미지 삭제 시도 - current_img={current_img}")
                    old_image = Image.query.filter_by(
                        user_id=current_user.user_id, post_id=None
                    ).first()
                    if old_image:
                        try:
                            old_path = os.path.join(
                                current_app.root_path, old_image.directory
                            )
                            if os.path.exists(old_path):
                                os.remove(old_path)
                                print(f"[DEBUG] 기존 파일 삭제 완료 - {old_path}")
                        except Exception as e:
                            print(f"[DEBUG] 기존 파일 삭제 실패 - {e}")
                        db.session.delete(old_image)
                        print(f"[DEBUG] 기존 Image 레코드 삭제 완료")

                # 새 프로필 이미지 저장
                print(f"[DEBUG] 새 프로필 이미지 저장 호출")
                new_uuid = save_profile_image(file, user_id=current_user.user_id)
                print(f"[DEBUG] save_profile_image 반환값 - new_uuid={new_uuid}")

                current_user.profile_img = new_uuid
                print(f"[DEBUG] current_user.profile_img 업데이트 완료 - {new_uuid}")
        else:
            print(f"[DEBUG] profile_img 파일 없음")

        print(f"[DEBUG] db.session.commit() 호출 전")
        db.session.commit()
        print(f"[DEBUG] db.session.commit() 완료")

        # commit 후 DB에서 다시 조회
        db.session.refresh(current_user)
        print(
            f"[DEBUG] refresh 후 current_user.profile_img = {current_user.profile_img}"
        )

        # Image 레코드 확인
        image_check = Image.query.filter_by(
            user_id=current_user.user_id, post_id=None
        ).first()
        print(f"[DEBUG] Image 레코드 확인: {image_check}")
        if image_check:
            print(f"[DEBUG]   - UUID: {image_check.uuid}")
            print(f"[DEBUG]   - Directory: {image_check.directory}")

        return (
            jsonify(
                {
                    "message": "프로필이 성공적으로 업데이트되었습니다",
                    "user": current_user.to_dict(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"프로필 업데이트 실패: {str(e)}"}), 400


# =====================================================
# 로그아웃
# =====================================================


@bp.delete("/logout")
@jwt_required()
def logout():
    """
    사용자 로그아웃 엔드포인트
    현재 토큰을 블랙리스트에 추가
    """
    jti = get_jwt()["jti"]
    BLACKLIST.add(jti)
    return jsonify({"message": "로그아웃 성공"}), 200


# =====================================================
# 계정 삭제
# =====================================================


@bp.delete("/user")
@jwt_required()
def remove_account():
    """
    사용자 계정 삭제 (연관된 모든 데이터 삭제)
    """
    current_user = get_current_user()

    # 연관된 알림 삭제 (발신/수신 모두)
    from apps.notification.models import Notification

    Notification.query.filter(
        (Notification.from_user_id == current_user.user_id)
        | (Notification.to_user_id == current_user.user_id)
    ).delete(synchronize_session=False)

    db.session.delete(current_user)
    db.session.commit()
    return jsonify({"message": "계정이 삭제되었습니다"}), 200


# =====================================================
# 토큰 갱신
# =====================================================


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    """
    리프레시 토큰을 사용하여 액세스 토큰 갱신
    """
    user_id = get_jwt_identity()
    return token_provider(user_id, access_require=True, refresh_require=False)


# =====================================================
# 현재 사용자 정보 조회
# =====================================================


@bp.get("/me")
@jwt_required()
def get_me():
    """
    현재 인증된 사용자 정보 조회
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify({"message": "사용자를 찾을 수 없습니다"}), 404

    return jsonify(current_user.to_dict()), 200


# =====================================================
# 프로필 이미지 조회
# =====================================================


@bp.get("/image/<string:uuid>")
def get_image_by_uuid(uuid):
    """
    UUID로 이미지 조회

    Args:
        uuid: 이미지 UUID 또는 'default_profile'
    """
    if uuid == "default_profile":
        path = "static/default_profile.jpg"
        folder = os.path.join(current_app.root_path, "static")
        return send_from_directory(folder, "default_profile.jpg")
    else:
        image = Image.query.filter_by(uuid=uuid).first_or_404(description="이미지 없음")

        # DB: static/profile_images/2025-11-12/uuid.jpg
        relative_path = image.directory

        # 절대 경로 생성
        absolute_path = os.path.join(current_app.root_path, relative_path)

        folder = os.path.dirname(absolute_path)
        filename = os.path.basename(absolute_path)

        # 파일 존재 여부 체크
        if not os.path.exists(absolute_path):
            return jsonify({"message": f"파일 없음: {absolute_path}"}), 404

        return send_from_directory(folder, filename)
