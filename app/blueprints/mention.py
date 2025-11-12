from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Mention, User, Post, Reply, Notification
from ..utils.mention_utils import serialize_mention

bp = Blueprint("mention", __name__)


# 1. 멘션 등록 + 알림 자동 생성
@bp.route("/", methods=["POST"])
@jwt_required()
def create_mention():
    data = request.get_json() or {}
    mentioner_id = int(get_jwt_identity())

    post_id = data.get("post_id")
    reply_id = data.get("reply_id")
    mentioned_user_id = data.get("mentioned_user_id")

    # 필수값 체크
    if not mentioned_user_id:
        return jsonify(success=False, message="mentioned_user_id는 필수입니다."), 400

    # 자기 자신 멘션 방지
    if mentioner_id == mentioned_user_id:
        return jsonify(success=False, message="자기 자신을 멘션할 수 없습니다."), 400

    # 멘션 대상 유저 존재 확인
    mentioned_user = User.query.get(mentioned_user_id)
    if not mentioned_user:
        return jsonify(success=False, message="해당 유저가 존재하지 않습니다."), 404

    # post_id / reply_id 동시 입력 방지
    filled_targets = [t for t in (post_id, reply_id) if t is not None]
    if len(filled_targets) != 1:
        return (
            jsonify(
                success=False, message="post_id, reply_id 중 하나만 전달해야 합니다."
            ),
            400,
        )

    # 대상 객체 확인
    target = Post.query.get(post_id) if post_id else Reply.query.get(reply_id)
    if not target:
        return jsonify(success=False, message="대상 객체를 찾을 수 없습니다."), 404

    # 중복 멘션 체크
    existing = Mention.query.filter_by(
        mentioner_id=mentioner_id,
        mentioned_user_id=mentioned_user_id,
        post_id=post_id,
        reply_id=reply_id,
    ).first()
    if existing:
        return jsonify(success=False, message="이미 등록된 멘션입니다."), 409

    # 멘션 생성
    mention = Mention(
        mentioner_id=mentioner_id,
        mentioned_user_id=mentioned_user_id,
        post_id=post_id,
        reply_id=reply_id,
    )
    db.session.add(mention)
    db.session.flush()  # mention_id 확보

    # 알림 생성
    notification = Notification(
        type="MENTION",
        from_user_id=mentioner_id,
        to_user_id=mentioned_user_id,
        post_id=post_id,
        reply_id=reply_id,
        mention_id=mention.mention_id,
    )
    db.session.add(notification)

    # DB 커밋
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return jsonify(success=False, message=f"중복 또는 DB 제약조건 오류: {e}"), 400
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=f"멘션 등록 실패: {e}"), 400

    # 1정상 등록 시
    return jsonify(success=True, data=serialize_mention(mention)), 201


# 2. 내가 받은 멘션 조회
@bp.route("/mine", methods=["GET"])
@jwt_required()
def get_mentions_for_user():
    current_user_id = int(get_jwt_identity())
    mentions = Mention.query.filter_by(mentioned_user_id=current_user_id).all()
    result = [serialize_mention(m) for m in mentions]
    return jsonify(success=True, data=result), 200


# 3. 내가 보낸 멘션 조회
@bp.route("/sent", methods=["GET"])
@jwt_required()
def get_mentions_sent_by_user():
    current_user_id = int(get_jwt_identity())
    mentions = Mention.query.filter_by(mentioner_id=current_user_id).all()
    result = [serialize_mention(m) for m in mentions]
    return jsonify(success=True, data=result), 200


# 4. 게시글 내 멘션 조회
@bp.route("/post/<int:post_id>", methods=["GET"])
def get_mentions_in_post(post_id):
    mentions = Mention.query.filter_by(post_id=post_id).all()
    result = [serialize_mention(m) for m in mentions]
    return jsonify(success=True, data=result), 200


# 5. 관리자용 전체 멘션 조회
@bp.route("/all", methods=["GET"])
@jwt_required()
def get_all_mentions():
    mentions = Mention.query.all()
    result = [serialize_mention(m) for m in mentions]
    return jsonify(success=True, data=result), 200


# 6. 멘션 타입별 조회 (POST / REPLY)
@bp.route("/type/<mention_type>", methods=["GET"])
def get_mentions_by_type(mention_type):
    mention_type = mention_type.upper()
    if mention_type == "POST":
        mentions = Mention.query.filter(Mention.post_id.isnot(None)).all()
    elif mention_type == "REPLY":
        mentions = Mention.query.filter(Mention.reply_id.isnot(None)).all()
    else:
        return jsonify(success=False, message="잘못된 멘션 타입"), 400

    result = [serialize_mention(m) for m in mentions]
    return jsonify(success=True, data=result), 200
