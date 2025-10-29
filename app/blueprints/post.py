from flask import Blueprint, request, jsonify
from ..models import Post, Image
from ..extensions import db
from flask_jwt_extended import get_current_user, jwt_required, get_jwt_identity

bp = Blueprint("post", __name__)

@bp.route("/write", methods=['POST'])
@jwt_required()
def write():
    data = request.get_json() or {}
    current_user_id = get_jwt_identity()

    post = Post(
        user_id=current_user_id,
        category_id=data.get("category_id"),
        content=data.get("content"),
        location=data.get("location"),
    )
    db.session.add(post)
    try:
        db.session.commit()
    except:
        db.session.rollback()
        return jsonify({"message": "글 저장 실패"}), 400

    return jsonify({"message": "글 생성 완료"}), 200

# @jwt.user_lookup_loader 등록 후 get_current_user() 사용 가능
@bp.route("/edit/<int:post_id>", methods=['PUT'])
@jwt_required()
def edit_post(post_id):
    post = Post.query.get(post_id) or {}
    current_user=get_current_user() or {}
    if post.get('user_id') == current_user.get('user_id'):
      return jsonify({'error' : '권한 없음'}), 400
    
    data = request.get_json() or {}

    post.content = data['content']
    post.images = []
    for img_data in data['images']:
        image = Image.query.filter_by(uuid=img_data['uuid']).first()
        if image:
            post.images.append(image)

    db.session.commit()
    return jsonify({'message' : '게시글 수정 완료'}), 200

# 조건부 게시글 조회(쿼리 없을 시 전체조회)
@bp.route('/posts', methods=['GET'])
def get_posts():
    filters = {}
    for key, value in request.args.items():  # 쿼리스트링 반복
        if value:
            filters[key] = value

    query = Post.query

    for key, value in filters.items():
        column = getattr(Post, key, None)  # Post 모델에 해당 컬럼이 있는지 확인
        if column is not None:
            query = query.filter(column.ilike(f"%{value}%"))  # 조건부 필터

    posts = query.all()

    result = []
    for p in posts:
        result.append({
            "post_id": p.post_id,
            "user_id": p.user_id,
            "category_id": p.category_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        })

    return jsonify(result), 200

# 게시글 id로 특정 게시글 조회
@bp.route("/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    return jsonify({
        "post_id": post.post_id,
        "user_id": post.user_id,
        "category_id": post.category_id,
        "content": post.content,
        "location": post.location,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat() if post.updated_at else None
    }), 200

# 유저 id로 특정 유저 게시글 조회
@bp.route("/posts/user/<int:user_id>", methods=["GET"])
def get_user_posts(user_id):
    posts = Post.query.filter_by(user_id=user_id).all()
    result = []
    for p in posts:
        result.append({
            "post_id": p.post_id,
            "category_id": p.category_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        })
    return jsonify(result), 200

# 카테고리 id로 특정 카테고리별 게시글 조회
@bp.route("/posts/categories/<int:category_id>", methods=["GET"])
def get_category_posts(category_id):
    posts = Post.query.filter_by(category_id=category_id).all()
    result = []
    for p in posts:
        result.append({
            "post_id": p.post_id,
            "user_id": p.user_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        })
    return jsonify(result), 200

# 내 게시글 조회
@bp.route("/posts/me", methods=["GET"])
@jwt_required()
def get_my_posts():
    current_user_id = get_jwt_identity()
    posts = Post.query.filter_by(user_id=current_user_id).all()
    result = []
    for p in posts:
        result.append({
            "post_id": p.post_id,
            "category_id": p.category_id,
            "content": p.content,
            "location": p.location,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        })
    return jsonify(result), 200

# get요청 - 추후에 필요할수도 있는 것
# 페이징/정렬, 통합 검색, 인기 게시글 / 최근 게시글 등