from flask import Blueprint, request, jsonify, send_from_directory, current_app
from ..extensions import db, BLACKLIST
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, get_current_user
from ..models import User, Image
from ..models.user import OauthType
from ..utils.image_utils import upload_profile, IMAGE_EXTENSIONS
from ..utils.user_utils import token_provider, is_valid_phone
from email_validator import validate_email, EmailNotValidError
import os
import uuid
from datetime import datetime
import requests

bp = Blueprint("auth", __name__)

# ----------------------- 유틸 함수 -----------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in IMAGE_EXTENSIONS


def save_profile_image(file, user_id=None):
    original_name = file.filename
    ext = file.filename.rsplit(".", 1)[1].lower()
    today = datetime.now().strftime("%Y-%m-%d")
    folder_path = os.path.join(current_app.root_path, "static/profile_images", today)
    os.makedirs(folder_path, exist_ok=True)
    uuid_val = uuid.uuid4()
    filename = f"{uuid_val}.{ext}"
    file_path = os.path.join(folder_path, filename)
    file.save(file_path)
    relative_path = f"static/profile_images/{today}/{filename}"

    if user_id:
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

    return relative_path


# ----------------------- 회원가입 -----------------------
@bp.route("/sign_up", methods=["POST"])
def sign_up():
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")
    nickname = request.form.get("nickname")
    address = request.form.get("address")
    phone = request.form.get("phone")

    if not username or not password or not email:
        return jsonify({"message": "필수 항목 누락되었습니다."}), 400

    try:
        validate_email(email)
    except EmailNotValidError:
        return jsonify({"message": "이메일 형식이 잘못되었습니다."}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "이미 존재하는 아이디입니다."}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "이미 사용중인 이메일입니다."}), 409
    if not nickname:
        nickname = username

    user = User(username=username, email=email, nickname=nickname, address=address, phone=phone, profile_img="")
    user.set_password(password)
    db.session.add(user)

    try:
        # ---------- 트랜잭션 시작 ----------
        db.session.commit()  # user_id 생성
        profile_img_path = "static/default_profile.jpg"
        if "profile_img" in request.files:
            files = request.files.getlist("profile_img")
            if files:
                if len(files) > 1:
                    raise ValueError("프로필 이미지는 1장만 업로드 가능합니다.")
                file = files[0]
                if file and allowed_file(file.filename):
                    profile_img_path = save_profile_image(file, user_id=user.user_id)
                else:
                    raise ValueError("지원하지 않는 이미지 형식입니다.")
        user.profile_img = profile_img_path
        db.session.commit()
        return jsonify({"message": "회원가입 완료", "user_id": user.user_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"회원가입 실패: {e}"}), 400


# ----------------------- 회원 정보 수정 -----------------------
@bp.route("/update", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "사용자를 찾을 수 없습니다."}), 404

    data = request.form.to_dict()
    email = data.get("email")
    password = data.get("password")
    nickname = data.get("nickname")
    address = data.get("address")
    phone = data.get("phone")
    file = request.files.get("profile_img")
    force_default = request.form.get("profile_img") in ["", None]
    default_img = "static/default_profile.jpg"
    current_img = user.profile_img

    try:
        # ---------- 이메일 / 중복 체크 ----------
        if email:
            validate_email(email)
            existing_email = User.query.filter(User.email == email, User.user_id != user.user_id).first()
            if existing_email:
                raise ValueError("이미 사용중인 이메일입니다.")
            user.email = email

        # ---------- 비밀번호, 닉네임, 주소, 전화번호 ----------
        if password:
            user.set_password(password)
        if nickname:
            user.nickname = nickname
        if address:
            user.address = address
        if phone:
            if not is_valid_phone(phone):
                raise ValueError("전화번호 형식이 잘못되었습니다.")
            user.phone = phone

        # ---------- 프로필 이미지 처리 ----------
        if file and file.filename:
            if current_img != default_img:
                old_image = Image.query.filter_by(directory=current_img).first()
                if old_image:
                    try:
                        os.remove(os.path.join(current_app.root_path, old_image.directory))
                    except:
                        pass
                    db.session.delete(old_image)
            user.profile_img = save_profile_image(file, user_id=user.user_id)
        elif force_default:
            if current_img != default_img:
                old_image = Image.query.filter_by(directory=current_img).first()
                if old_image:
                    try:
                        os.remove(os.path.join(current_app.root_path, old_image.directory))
                    except:
                        pass
                    db.session.delete(old_image)
            user.profile_img = default_img

        db.session.commit()
        return jsonify({"message": "회원 정보가 수정되었습니다."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"회원 정보 수정 실패: {e}"}), 400


# ----------------------- 토큰 리프레시 -----------------------
@bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = token_provider(user_id=identity, refresh_require=False)
    return jsonify(access_token=access_token), 200


# ----------------------- 로그인 -----------------------
@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"message": "아이디와 비밀번호를 입력하세요"}), 400

    user = User.query.filter_by(username=username).first_or_404(description="아이디* 또는 비밀번호 오류입니다.")
    try:
        user.follower_count = User.calculate_follower(user)
        user.last_login = User.renew_login(user)
        db.session.commit()
    except:
        db.session.rollback()

    if not user.check_password(password):
        return jsonify({"message": "아이디 또는 비밀번호* 오류입니다."}), 401

    return token_provider(user.user_id, username=user.username, email=user.email, nickname=user.nickname)


# ----------------------- 소셜 로그인 -----------------------
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"

@bp.route("/login/google", methods=["POST"])
def google_login():
    google_token = request.json.get("token")
    if not google_token:
        return jsonify({"message": "토큰이 누락되었습니다."}), 400

    resp = requests.get(GOOGLE_TOKEN_INFO_URL, params={"id_token": google_token})
    if resp.status_code != 200:
        return jsonify({"message": "토큰 처리에 실패하였습니다."}), 401

    data = resp.json()
    email = data.get("email")
    social_id = data.get("sub")
    name = data.get("name", "GoogleUser")
    picture_url = data.get("picture")

    if not email or not social_id:
        return jsonify({"message": "수신된 정보에 오류가 있습니다."}), 401

    user = User.query.filter_by(username=social_id, oauth_type=OauthType.GOOGLE).first()
    if not user:
        user = User(username=social_id, email=email, nickname=name, oauth_type=OauthType.GOOGLE, address="", password_hash="")
        db.session.add(user)
        try:
            db.session.commit()
        except:
            db.session.rollback()
        upload_profile(user, url=picture_url)

    return token_provider(user.user_id, user.username, user.email, user.nickname)


@bp.route("/login/kakao", methods=["POST"])
def kakao_login():
    kakao_token = request.json.get("token")
    if not kakao_token:
        return jsonify({"message": "잘못된 요청입니다."}), 400

    kakao_user_info = requests.get("https://kapi.kakao.com/v2/user/me", headers={"Authorization": f"Bearer {kakao_token}"})
    if kakao_user_info.status_code != 200:
        return jsonify({"message": "잘못된 요청입니다."}), 401

    data = kakao_user_info.json()
    kakao_id = data.get("id")
    kakao_account = data.get("kakao_account", {})
    email = kakao_account.get("email", f"kakao_{kakao_id}@kakao.com")
    profile = kakao_account.get("profile", {})
    nickname = profile.get("nickname", "KakaoUser")
    image_url = profile.get("profile_image_url")

    user = User.query.filter_by(username=str(kakao_id), oauth_type=OauthType.KAKAO).first()
    if not user:
        user = User(username=str(kakao_id), email=email, nickname=nickname, oauth_type=OauthType.KAKAO, address="", password_hash="")
        db.session.add(user)
        db.session.commit()
        upload_profile(user, url=image_url)

    return token_provider(user.user_id, user.username, user.email, user.nickname)


@bp.route("/login/naver", methods=["POST"])
def naver_login():
    naver_token = request.json.get("token")
    if not naver_token:
        return jsonify({"message": "잘못된 요청입니다."}), 400

    naver_user_info = requests.get("https://openapi.naver.com/v1/nid/me", headers={"Authorization": f"Bearer {naver_token}"})
    if naver_user_info.status_code != 200:
        return jsonify({"message": "잘못된 요청입니다."}), 401

    data = naver_user_info.json().get("response", {})
    naver_id = data.get("id")
    email = data.get("email", f"naver_{naver_id}@naver.com")
    nickname = data.get("nickname", "NaverUser")
    image_url = data.get("profile_image")

    user = User.query.filter_by(username=str(naver_id), oauth_type=OauthType.NAVER).first()
    if not user:
        user = User(username=str(naver_id), email=email, nickname=nickname, oauth_type=OauthType.NAVER, address="", password_hash="")
        db.session.add(user)
        db.session.commit()
        upload_profile(user, url=image_url)

    return token_provider(user.user_id, user.username, user.email, user.nickname)


# ----------------------- 로그아웃 -----------------------
@bp.route("/logout", methods=["DELETE"])
@jwt_required()
def logout_access():
    jti = get_jwt()["jti"]
    BLACKLIST.add(jti)
    return jsonify({"message": "로그아웃 되었습니다."}), 200


# ----------------------- 회원 조회 -----------------------
@bp.route("/users", methods=["GET"])
@jwt_required()
def get_users():
    filters = {k: v for k, v in request.args.items() if v}
    query = User.query
    for key, value in filters.items():
        column = getattr(User, key, None)
        if column:
            query = query.filter(column.ilike(f"%{value}%"))
    users = query.all()
    result = []
    for u in users:
        result.append({
            "user_id": u.user_id,
            "nickname": u.nickname,
            "email": u.email,
            "address": u.address,
            "profile_img": u.profile_img,
            "created_at": u.created_at.isoformat(),
            "follower_count": u.follower_count,
        })
    return jsonify(result), 200


@bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        "user_id": user.user_id,
        "username": user.username,
        "nickname": user.nickname,
        "email": user.email,
        "address": user.address,
        "profile_img": user.profile_img,
        "created_at": user.created_at.isoformat(),
        "follower_count": user.follower_count
    }), 200


# ----------------------- 내 정보 조회 -----------------------
@bp.route("/me", methods=["GET"])
@jwt_required()
def get_info():
    current_user = get_current_user()
    if not current_user:
        return jsonify({"message": "사용자를 찾을 수 없습니다."}), 404
    User.calculate_follower(current_user)
    db.session.add(current_user)
    db.session.commit()
    user_info = {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
        "nickname": current_user.nickname,
        "address": current_user.address,
        "profile_img": current_user.profile_img.split("/")[-1].split(".")[0],
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "follower_count": current_user.follower_count,
        "phone": current_user.phone
    }
    return jsonify(user_info), 200


# ----------------------- 회원 탈퇴 -----------------------
@bp.route("/", methods=["DELETE"])
@jwt_required()
def delete_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "사용자를 찾을 수 없습니다."}), 404
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "회원 탈퇴가 완료되었습니다."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "회원 탈퇴에 실패했습니다."}), 400


@bp.route("/<int:user_id>", methods=["DELETE"])
def delete_user_by_admin(user_id):
    target = User.query.get(user_id)
    if not target:
        return jsonify({"message": "대상 사용자를 찾을 수 없습니다."}), 404
    try:
        db.session.delete(target)
        db.session.commit()
        return jsonify({"message": "회원 삭제가 완료되었습니다."}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"message": "회원 삭제에 실패했습니다."}), 400


# ----------------------- uuid로 프로필 이미지 조회 -----------------------
@bp.route("/image/uuid/<string:uuid>", methods=["GET"])
def get_image_by_uuid(uuid):
    if uuid == "default_profile":
        path = "static/default_profile.jpg"
        return send_from_directory("/".join(path.split("/")[:-1]), path.split("/")[-1])
    else:
        image = Image.query.filter_by(uuid=uuid).first_or_404(description="이미지 없음")
        return send_from_directory("/".join(image.directory.split("/")[:-1]), image.directory.split("/")[-1])

@bp.route("/image/user/<int:user_id>", methods=["GET"])
def get_user_profile_image(user_id):
    image = Image.query.filter_by(user_id=user_id).first_or_404(description="이미지 없음")

    # DB: static/profile_images/2025-11-12/uuid.jpg
    relative_path = image.directory

    # 절대 경로 생성
    absolute_path = os.path.join(current_app.root_path, relative_path)

    folder = os.path.dirname(absolute_path)
    filename = os.path.basename(absolute_path)

    # 파일 존재 여부 체크
    if not os.path.exists(absolute_path):
        return {"message": f"파일 없음: {absolute_path}"}, 404

    return send_from_directory(folder, filename)