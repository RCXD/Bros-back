"""
인증 뷰 (라우트)
사용자 등록, 로그인, 로그아웃, 프로필 관리 처리
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, get_current_user
from email_validator import validate_email, EmailNotValidError

from apps.config.server import db, BLACKLIST
from apps.auth.models import User
from apps.auth.utils import token_provider, is_valid_phone


bp = Blueprint("auth", __name__)


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
            return jsonify({"error": "username, password, email은 필수입니다"}), 400
        
        # 이메일 형식 검증
        try:
            validate_email(email)
        except EmailNotValidError:
            return jsonify({"error": "유효하지 않은 이메일 형식입니다"}), 400
        
        # 전화번호 검증 (제공된 경우)
        if phone and not is_valid_phone(phone):
            return jsonify({"error": "유효하지 않은 전화번호 형식입니다"}), 400
        
        # 기존 사용자명/이메일 확인
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "이미 존재하는 사용자명입니다"}), 409
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "이미 존재하는 이메일입니다"}), 409
        
        # 사용자 생성
        user = User(
            username=username,
            email=email,
            nickname=nickname,
            address=address,
            phone=phone,
            profile_img="apps/static/default_profile.jpg"
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # 프로필 이미지 업로드 처리 (제공된 경우)
        if "profile_img" in request.files:
            file = request.files["profile_img"]
            if file and file.filename:
                # TODO: 이미지 업로드 로직 구현
                pass
        
        return jsonify({
            "message": "회원가입이 완료되었습니다",
            "user": user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"회원가입 실패: {str(e)}"}), 400


# =====================================================
# 로그인
# =====================================================

@bp.post("/login")
def login():
    """
    사용자 로그인 엔드포인트
    
    JSON body:
        - username: 필수
        - password: 필수
    """
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"error": "username과 password는 필수입니다"}), 400
        
        # 사용자명으로 사용자 찾기
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "잘못된 인증 정보입니다"}), 401
        
        # 계정 정지 여부 확인
        if user.is_expired:
            return jsonify({"error": "정지된 계정입니다"}), 403
        
        # 비밀번호 확인
        if not user.check_password(password):
            return jsonify({"error": "잘못된 인증 정보입니다"}), 401
        
        # 마지막 로그인 시간 업데이트
        user.renew_login()
        db.session.commit()
        
        # 토큰 생성
        tokens = token_provider(user.user_id, access_require=True, refresh_require=True)
        
        # 토큰과 사용자 데이터 반환
        response_data = tokens.get_json()
        response_data["user"] = user.to_dict()
        
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({"error": f"로그인 실패: {str(e)}"}), 400


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
            return jsonify({"error": "사용자를 찾을 수 없습니다"}), 404
        
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
                return jsonify({"error": "유효하지 않은 이메일 형식입니다"}), 400
            
            # 다른 사용자가 해당 이메일을 사용하는지 확인
            existing = User.query.filter(User.email == email, User.user_id != current_user.user_id).first()
            if existing:
                return jsonify({"error": "이미 사용 중인 이메일입니다"}), 409
            
            current_user.email = email
        
        if password:
            current_user.set_password(password)
        
        if nickname:
            current_user.nickname = nickname
        
        if address:
            current_user.address = address
        
        if phone:
            if not is_valid_phone(phone):
                return jsonify({"error": "유효하지 않은 전화번호 형식입니다"}), 400
            current_user.phone = phone
        
        # 프로필 이미지 업로드 처리
        if "profile_img" in request.files:
            file = request.files["profile_img"]
            if file and file.filename:
                # TODO: 이미지 업로드 및 기존 이미지 삭제 구현
                pass
        
        db.session.commit()
        
        return jsonify({
            "message": "프로필이 성공적으로 업데이트되었습니다",
            "user": current_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"프로필 업데이트 실패: {str(e)}"}), 400

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
    사용자 계정 삭제
    """
    current_user = get_current_user()
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
        return jsonify({"error": "사용자를 찾을 수 없습니다"}), 404
    
    return jsonify(current_user.to_dict()), 200


# =====================================================
# OAuth 로그인 (Google, Kakao, Naver)
# =====================================================

@bp.post("/login/google")
def google_login():
    """Google OAuth 로그인"""
    # TODO: Google OAuth 구현
    return jsonify({"message": "Google OAuth - 구현 예정"}), 501


@bp.post("/login/kakao")
def kakao_login():
    """Kakao OAuth 로그인"""
    # TODO: Kakao OAuth 구현
    return jsonify({"message": "Kakao OAuth - 구현 예정"}), 501


@bp.post("/login/naver")
def naver_login():
    """Naver OAuth 로그인"""
    # TODO: Naver OAuth 구현
    return jsonify({"message": "Naver OAuth - 구현 예정"}), 501
